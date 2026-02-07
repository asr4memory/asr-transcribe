"""
Subprocess wrapper for LLM tasks.
Runs LLM model in isolated subprocess to ensure memory is freed after processing.
This allows large models (20GB+) to be loaded and fully cleaned up between files.

Returns a unified result dict:
{
    "summaries": {"de": "...", "en": "..."},
    "toc": {"de": "...", "en": "..."},  # future
    ...
    "_meta": {"trial": 1}
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
from llm_workflows import system_prompt_summaries, system_prompt_toc

config = get_config()
n_gpu_layers = config["llm"]["n_gpu_layers"]
model_path = config["llm"]["model_path"]
verbose = config["llm"].get("verbose", False)
use_summarization = config["llm"].get("use_summarization", False)
use_toc = config["llm"].get("use_toc", False)
reasoning_log_path = config["llm"].get("reasoning_log", "")
reasoning_log_max_chars = int(config["llm"].get("reasoning_log_max_chars", 0) or 0)
run_id = f"{datetime.utcnow().isoformat(timespec='seconds')}Z_{os.getpid()}"


def _resolve_reasoning_log_path() -> str:
    if not reasoning_log_path:
        return ""
    if "{run_id}" in reasoning_log_path:
        return reasoning_log_path.format(run_id=run_id)
    path = Path(reasoning_log_path).expanduser()
    if str(reasoning_log_path).endswith(os.sep) or path.is_dir():
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


def _log_removed_reasoning(
    removed: str, kind: str, meta: dict | None = None
) -> None:
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


def get_languages() -> list[str]:
    languages = config["llm"].get("summary_languages", ["de", "en"])
    if isinstance(languages, str):
        languages = [languages]
    cleaned = []
    for lang in languages:
        if isinstance(lang, str) and lang.strip():
            cleaned.append(lang.strip().lower())
    return cleaned


def load_model(trial: int) -> Llama:
    """Initialise the Llama model with trial-specific context settings."""
    if trial == 1:
        return Llama(
            model_path=model_path,
            n_gpu_layers=n_gpu_layers,
            n_ctx=32768,
            n_batch=1024,
            verbose=verbose,
        )
    return Llama(
        model_path=model_path,
        n_gpu_layers=n_gpu_layers,
        n_ctx=65536,
        n_batch=256,
        verbose=verbose,
    )


def user_prompt(segments) -> str:
    """Concatenate all segment texts for the user prompt."""
    return "\n".join(segment["text"] for segment in segments)


def user_prompt_with_timestamps(segments) -> str:
    """Return segments as JSON with start/end timestamps for TOC generation."""
    import json

    data = [
        {
            "start": seg.get("start", 0),
            "end": seg.get("end", 0),
            "text": seg.get("text", ""),
        }
        for seg in segments
    ]
    return json.dumps(data, ensure_ascii=False)


def strip_reasoning(text: str, meta: dict | None = None) -> str:
    """Removes model reasoning/analysis from output, keeping only final response."""
    if not text:
        return ""

    # Pattern 1: <|channel|>final<|message|> marks the final output
    if "<|channel|>final<|message|>" in text:
        before, after = text.split("<|channel|>final<|message|>", 1)
        _log_removed_reasoning(
            removed=before,
            kind="final_marker",
            meta=meta,
        )
        text = after
        # Also remove any trailing channel markers
        if "<|" in text:
            text = text.split("<|")[0]
        return text.strip()

    # Pattern 2: Old delimiter format
    old_delimiter = "|end|><|start|>assistant<|channel|>final<|message|>"
    if old_delimiter in text:
        before, after = text.split(old_delimiter, 1)
        _log_removed_reasoning(
            removed=before,
            kind="old_delimiter",
            meta=meta,
        )
        return after.strip()

    # Pattern 3: Remove anything starting with <|channel|>analysis
    if "<|channel|>analysis" in text:
        # Take everything before the analysis starts
        before, after = text.split("<|channel|>analysis", 1)
        _log_removed_reasoning(
            removed="<|channel|>analysis" + after,
            kind="analysis_block",
            meta=meta,
        )
        return before.strip()

    return text


def generate(
    llm: Llama,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    top_p: float = 0.9,
    repeat_penalty: float = 1.2,
    meta: dict | None = None,
) -> str:
    """Generate a summary using llama_cpp for a given prompt."""
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

    return strip_reasoning(result, meta=meta)


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


def generate_task(
    llm: Llama,
    task_name: str,
    languages: list[str],
    prompt_fn,
    user_prompt_text: str,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    top_p: float = 0.9,
    repeat_penalty: float = 1.2,
    parse_json: bool = False,
    trial: int = 0,
) -> dict:
    """
    Generate LLM output for a task across all languages.
    Returns dict with language codes as keys.
    """
    results = {}
    for language in languages:
        meta = {
            "task": task_name,
            "lang": language,
            "trial": trial,
        }
        system_prompt = prompt_fn(language)
        output = generate(
            llm,
            system_prompt,
            user_prompt_text,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            repeat_penalty=repeat_penalty,
            meta=meta,
        )
        if parse_json:
            results[language] = parse_json_output(output)
        else:
            results[language] = output
        print(f"{task_name} ({language}): done", file=sys.stderr)
    return results


def main():
    """Main subprocess entry point."""
    max_trials = 2
    languages = get_languages()

    # Return empty result if no languages configured
    if not languages:
        result = {"summaries": {}, "toc": {}}
        sys.stdout.buffer.write(pickle.dumps(result))
        sys.exit(0)

    # Read segments from stdin
    input_data = sys.stdin.buffer.read()
    segments = pickle.loads(input_data)

    user_prompt_text = user_prompt(segments)
    user_prompt_toc_text = user_prompt_with_timestamps(segments)

    result = {}
    llm = None

    # 1. Generate Summaries (with retries)
    if use_summarization:
        for trial in range(1, max_trials + 1):
            try:
                if llm is None:
                    llm = load_model(trial)
                result["summaries"] = generate_task(
                    llm,
                    "Summary",
                    languages,
                    system_prompt_summaries,
                    user_prompt_text,
                    max_tokens=12288, #originally 4096
                    temperature=0.0, #originally 0.3
                    top_p=1.0, #originally 0.9
                    repeat_penalty=1.0, #originally 1.2
                    trial=trial,
                )
                break
            except Exception as e:
                if llm is not None:
                    del llm
                    llm = None
                cleanup_cuda_memory()
                if trial < max_trials:
                    print(
                        f"Summary error on trial {trial}, retrying...", file=sys.stderr
                    )
                else:
                    print(f"Summary failed: {e}", file=sys.stderr)
                    result["summaries"] = {lang: "" for lang in languages}

    # 2. Generate TOC (with retries)
    if use_toc:
        for trial in range(1, max_trials + 1):
            try:
                if llm is None:
                    llm = load_model(trial)
                result["toc"] = generate_task(
                    llm,
                    "TOC",
                    languages,
                    system_prompt_toc,
                    user_prompt_toc_text,
                    max_tokens=8192,
                    temperature=0.3,
                    top_p=0.9,
                    repeat_penalty=1.1,
                    parse_json=True,
                    trial=trial,
                )
                break
            except Exception as e:
                if llm is not None:
                    del llm
                llm = None
                cleanup_cuda_memory()
                if trial < max_trials:
                    print(f"TOC error on trial {trial}, retrying...", file=sys.stderr)
                else:
                    print(f"TOC failed: {e}", file=sys.stderr)
                    result["toc"] = {lang: {"_error": str(e)} for lang in languages}

    # Cleanup
    if llm is not None:
        del llm
    cleanup_cuda_memory()

    sys.stdout.buffer.write(pickle.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
