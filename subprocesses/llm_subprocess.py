"""
Subprocess wrapper for LLM tasks.
Runs LLM model in isolated subprocess to ensure memory is freed after processing.
This allows large models (20GB+) to be loaded and fully cleaned up between files.

Returns a unified result dict:
{
    "summaries": {"de": "...", "en": "..."},
    "toc": {"de": "...", "en": "..."},
    ...
    "_meta": {"profile": 1}
}
"""

import sys
import pickle
import json
import os
from datetime import datetime
from pathlib import Path
from llama_cpp import Llama
from config.app_config import get_config
from utils.utilities import cleanup_cuda_memory

config = get_config()
verbose = config["llm_meta"].get("verbose", False)
reasoning_log_path = config["llm_meta"].get("reasoning_log", "")
reasoning_log_max_chars = int(config["llm_meta"].get("reasoning_log_max_chars", 0) or 0)
run_id = f"{datetime.utcnow().isoformat(timespec='seconds')}Z_{os.getpid()}"


class JSONParsingError(Exception):
    """Raised when LLM output cannot be parsed as valid JSON."""

    def __init__(self, error_msg: str, raw_output: str, truncated: bool = False):
        self.error_msg = error_msg
        self.raw_output = raw_output
        self.truncated = truncated
        super().__init__(
            f"JSON parsing failed{' (truncated)' if truncated else ''}: {error_msg}"
        )


def _resolve_reasoning_log_path() -> str:
    if not reasoning_log_path:
        return ""
    if "{run_id}" in reasoning_log_path:
        return reasoning_log_path.format(run_id=run_id)
    path = Path(reasoning_log_path).expanduser()
    if str(reasoning_log_path).endswith(os.sep) or path.is_dir() or not path.suffix:
        filename = f"llm_reasoning_{run_id}.jsonl"
        return str(path / filename)
    return str(path)


reasoning_log_file = _resolve_reasoning_log_path()


def log_reasoning(entry: dict) -> None:
    """Best-effort JSONL logging of removed reasoning blocks."""
    if not reasoning_log_file:
        return
    try:
        log_path = Path(reasoning_log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Never break LLM flow due to logging issues.
        pass


def _truncate_reasoning(text: str) -> str:
    if not text:
        return ""
    if reasoning_log_max_chars > 0 and len(text) > reasoning_log_max_chars:
        return text[:reasoning_log_max_chars] + "…"
    return text


def _log_removed_reasoning(removed: str, kind: str, meta: dict | None = None) -> None:
    if not reasoning_log_file or removed is None:
        return
    entry = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "run_id": run_id,
        "kind": kind,
        "removed_len": len(removed),
        "removed": _truncate_reasoning(removed),
    }
    if meta:
        entry.update(meta)
    log_reasoning(entry)


def load_model_config(config_path: str) -> dict:
    """Load per-model TOML config. Returns empty dict if path is unset or missing."""
    if not config_path:
        return {}
    import tomllib

    path = Path(config_path).expanduser()
    if not path.is_absolute():
        path = Path(__file__).parent.parent / path
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def get_languages() -> list[str]:
    languages = config["llm_meta"].get("llm_languages", ["de", "en"])
    if isinstance(languages, str):
        languages = [languages]
    cleaned = []
    for lang in languages:
        if isinstance(lang, str) and lang.strip():
            cleaned.append(lang.strip().lower())
    return cleaned


def select_profile(model_cfg: dict, input_chars: int, max_tokens: int) -> int:
    """Select the first profile whose n_ctx fits estimated input + output tokens.
    Falls back to the last (largest) profile if none fits.
    Uses 2.5 chars/token as a conservative estimate for German/English mixed text.
    """
    CHARS_PER_TOKEN = 2.5
    estimated_input_tokens = int(input_chars / CHARS_PER_TOKEN)
    required_ctx = estimated_input_tokens + max_tokens
    profiles = model_cfg.get("profiles", [])
    for i, p in enumerate(profiles, start=1):
        if p.get("n_ctx", 0) >= required_ctx:
            return i
    return len(profiles) or 1


def load_model_from_config(model_path: str, profile: int, model_cfg: dict) -> Llama:
    """Initialise the Llama model with profile-specific context settings."""
    profiles = model_cfg.get("profiles", [])
    if profile > len(profiles):
        raise ValueError(
            f"Profile {profile} requested but model config only defines {len(profiles)} profile(s)."
        )
    profile_cfg = profiles[profile - 1]
    model_section = model_cfg.get("model", {})

    return Llama(
        model_path=model_path,
        n_gpu_layers=profile_cfg["n_gpu_layers"],
        n_ctx=profile_cfg["n_ctx"],
        n_batch=profile_cfg["n_batch"],
        n_ubatch=profile_cfg["n_ubatch"],
        n_threads=model_section.get("n_threads", 8),
        n_threads_batch=model_section.get("n_threads_batch", 16),
        flash_attn=model_section.get("flash_attn", True),
        verbose=verbose,
    )


def strip_reasoning(text: str, meta: dict | None = None) -> str:
    """Removes model reasoning/analysis from output, keeping only final response."""
    if not text:
        return ""

    # Pattern 1: Multi-step reasoning — analysis block followed by final output
    if "<|channel|>final<|message|>" in text:
        before, after = text.split("<|channel|>final<|message|>", 1)
        _log_removed_reasoning(
            removed=before,
            kind="multi_step",
            meta=meta,
        )
        text = after
        # Also remove any trailing channel markers
        if "<|" in text:
            text = text.split("<|")[0]
        return text.strip()

    # Pattern 2: Single-step reasoning — direct final output without separate analysis block
    single_step_delimiter = "|end|><|start|>assistant<|channel|>final<|message|>"
    if single_step_delimiter in text:
        before, after = text.split(single_step_delimiter, 1)
        _log_removed_reasoning(
            removed=before,
            kind="single_step",
            meta=meta,
        )
        return after.strip()

    # Pattern 3: Incomplete reasoning — model stuck in analysis, no final output produced
    if "<|channel|>analysis" in text:
        before, after = text.split("<|channel|>analysis", 1)
        _log_removed_reasoning(
            removed="<|channel|>analysis" + after,
            kind="incomplete_reasoning",
            meta=meta,
        )
        return before.strip()

    return text


def parse_json_output(text: str) -> dict | list:
    """
    Parse LLM output as JSON.
    Returns parsed JSON (list or dict) if valid, otherwise returns dict with _error key.
    """
    import json
    import re

    # Strip markdown code blocks if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        return {"_error": str(e), "_raw": text}


def generate(
    llm: Llama,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    top_p: float = 0.9,
    repeat_penalty: float = 1.2,
    meta: dict | None = None,
) -> tuple[str, str]:
    """Generate using llama_cpp. Returns (content, finish_reason)."""
    output = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        repeat_penalty=repeat_penalty,
    )
    result = output["choices"][0]["message"]["content"]
    finish_reason = output["choices"][0].get("finish_reason", "stop")

    return strip_reasoning(result, meta=meta), finish_reason


def main():
    """Main subprocess entry point."""
    languages = get_languages()
    use_summarization = config["llm_meta"].get("use_summarization", False)
    use_toc = config["llm_meta"].get("use_toc", False)

    if not languages:
        sys.stdout.buffer.write(pickle.dumps({"summaries": {}, "toc": {}}))
        sys.exit(0)

    segments = pickle.loads(sys.stdin.buffer.read())
    result = {}

    if use_summarization:
        from llm_workflows.llm_task_summary import run as run_summary

        result["summaries"] = run_summary(segments, languages)

    cleanup_cuda_memory()

    if use_toc:
        from llm_workflows.llm_task_toc import run as run_toc

        result["toc"] = run_toc(segments, languages)

    cleanup_cuda_memory()
    sys.stdout.buffer.write(pickle.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
