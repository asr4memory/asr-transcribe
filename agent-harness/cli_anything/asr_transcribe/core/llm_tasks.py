"""LLM workflow operations — summaries, table of contents, and inspection."""

import json
from pathlib import Path

from cli_anything.asr_transcribe.utils.asr_backend import ensure_project_importable


# ── Inspection commands (no GPU required) ────────────────────────────


def run_chunk_preview(
    json_path: str,
    target_minutes: float = None,
    max_chars: int = None,
) -> dict:
    """Preview how a transcript would be chunked for batched LLM processing.

    Args:
        json_path: Path to WhisperX JSON with segments.
        target_minutes: Override chunk_target_minutes config.
        max_chars: Override chunk_max_chars config.

    Returns:
        Dict with batching detection, total chars, and per-chunk details.
    """
    ensure_project_importable()

    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", []) if isinstance(data, dict) else data

    if not segments:
        return {"status": "error", "message": "No segments found in JSON file."}

    from llm_workflows.chunking import chunk_segments, should_use_batching, total_text_chars
    from config.app_config import get_config

    config = get_config()
    total_chars = total_text_chars(segments)
    threshold = config["llm_meta"].get("batching_threshold_chars", 25000)
    would_batch = should_use_batching(segments)

    kwargs = {}
    if target_minutes is not None:
        kwargs["target_minutes"] = target_minutes
    if max_chars is not None:
        kwargs["max_chars"] = max_chars

    chunks = chunk_segments(segments, **kwargs)

    chunk_details = []
    for c in chunks:
        seg_chars = sum(len(s.get("text", "")) for s in c["segments"])
        duration = c["end"] - c["start"]
        chunk_details.append({
            "chunk_id": c["chunk_id"],
            "start": round(c["start"], 2),
            "end": round(c["end"], 2),
            "duration_sec": round(duration, 1),
            "segment_count": len(c["segments"]),
            "char_count": seg_chars,
        })

    return {
        "status": "success",
        "total_segments": len(segments),
        "total_chars": total_chars,
        "batching_threshold": threshold,
        "would_use_batching": would_batch,
        "chunk_count": len(chunks),
        "target_minutes": target_minutes or config["llm_meta"].get("chunk_target_minutes", 12),
        "max_chars_per_chunk": max_chars or config["llm_meta"].get("chunk_max_chars", 10000),
        "chunks": chunk_details,
    }


def run_models_info() -> dict:
    """Inspect loaded model configurations for summary and TOC models.

    Returns:
        Dict with model paths, config paths, and profile details.
    """
    ensure_project_importable()

    from config.app_config import get_config
    from subprocesses.llm_subprocess import load_model_config

    config = get_config()
    result = {"status": "success", "models": {}}

    for name, section, path_key, config_key in [
        ("summarization", "summarization", "sum_model_path", "sum_model_config"),
        ("toc", "toc", "toc_model_path", "toc_model_config"),
    ]:
        model_path = config[section].get(path_key, "")
        config_path = config[section].get(config_key, "")
        model_cfg = load_model_config(config_path)

        profiles = model_cfg.get("profiles", [])
        model_section = model_cfg.get("model", {})

        profile_details = []
        for i, p in enumerate(profiles, start=1):
            profile_details.append({
                "profile": i,
                "n_ctx": p.get("n_ctx"),
                "n_gpu_layers": p.get("n_gpu_layers"),
                "n_batch": p.get("n_batch"),
                "n_ubatch": p.get("n_ubatch"),
            })

        model_exists = bool(model_path) and Path(model_path).expanduser().exists()

        result["models"][name] = {
            "model_path": model_path or "(not configured)",
            "model_exists": model_exists,
            "config_path": config_path or "(not configured)",
            "config_loaded": bool(model_cfg),
            "n_threads": model_section.get("n_threads"),
            "n_threads_batch": model_section.get("n_threads_batch"),
            "flash_attn": model_section.get("flash_attn"),
            "profile_count": len(profiles),
            "profiles": profile_details,
        }

    # Include relevant llm_meta settings
    result["llm_meta"] = {
        "use_summarization": config["llm_meta"].get("use_summarization", False),
        "use_toc": config["llm_meta"].get("use_toc", False),
        "llm_languages": config["llm_meta"].get("llm_languages", []),
        "batching_threshold_chars": config["llm_meta"].get("batching_threshold_chars", 25000),
        "chunk_target_minutes": config["llm_meta"].get("chunk_target_minutes", 12),
        "chunk_max_chars": config["llm_meta"].get("chunk_max_chars", 10000),
        "emit_debug_artifacts": config["llm_meta"].get("emit_debug_artifacts", False),
        "verbose": config["llm_meta"].get("verbose", False),
    }

    return result


def run_validate_toc(
    toc_path: str,
    transcript_json: str = None,
) -> dict:
    """Validate a TOC JSON file.

    Args:
        toc_path: Path to TOC JSON file (list of entries).
        transcript_json: Optional path to source WhisperX JSON for boundary validation.

    Returns:
        Dict with validation result and details.
    """
    ensure_project_importable()

    path = Path(toc_path)
    if not path.exists():
        raise FileNotFoundError(f"TOC file not found: {toc_path}")

    with open(path, "r", encoding="utf-8") as f:
        toc_data = json.load(f)

    if not isinstance(toc_data, list):
        return {
            "status": "error",
            "valid": False,
            "message": "TOC file must contain a JSON array of entries.",
        }

    # Determine transcript boundaries
    if transcript_json:
        tj_path = Path(transcript_json)
        if not tj_path.exists():
            raise FileNotFoundError(f"Transcript JSON not found: {transcript_json}")
        with open(tj_path, "r", encoding="utf-8") as f:
            tj_data = json.load(f)
        segments = tj_data.get("segments", []) if isinstance(tj_data, dict) else tj_data
        if segments:
            transcript_start = segments[0].get("start", 0.0)
            transcript_end = segments[-1].get("end", 0.0)
        else:
            transcript_start = 0.0
            transcript_end = 0.0
    else:
        # Use TOC's own boundaries when no transcript provided
        if toc_data:
            transcript_start = toc_data[0].get("start", 0.0)
            transcript_end = toc_data[-1].get("end", 0.0)
        else:
            transcript_start = 0.0
            transcript_end = 0.0

    from llm_workflows.shared_synopsis import validate_toc

    error = validate_toc(toc_data, transcript_start, transcript_end)

    return {
        "status": "success" if error is None else "error",
        "valid": error is None,
        "error": error,
        "entry_count": len(toc_data),
        "transcript_start": transcript_start,
        "transcript_end": transcript_end,
        "boundary_source": "transcript" if transcript_json else "toc_self",
        "message": "TOC is valid." if error is None else f"Validation failed: {error}",
    }


# ── LLM execution commands ──────────────────────────────────────────


def run_summarize(json_path: str, output_dir: str = None) -> dict:
    """Generate summaries from a transcript JSON file.

    Args:
        json_path: Path to processed WhisperX JSON with segments.
        output_dir: Output directory. Defaults to same directory as input.

    Returns:
        Dict with summaries per language and output paths.
    """
    root = ensure_project_importable()

    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", []) if isinstance(data, dict) else data

    if not segments:
        return {"status": "error", "message": "No segments found in JSON file."}

    from subprocesses.subprocess_handler import run_llm_subprocess

    llm_output = run_llm_subprocess(segments)

    if not llm_output or not llm_output.get("summaries"):
        return {"status": "error", "message": "LLM subprocess returned no summaries."}

    # Write output files
    out_dir = Path(output_dir) if output_dir else path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    summaries = llm_output.get("summaries", {})
    output_files = {}

    for lang, text in summaries.items():
        if text:
            out_file = out_dir / f"{path.stem}_summary_{lang}.txt"
            out_file.write_text(text, encoding="utf-8")
            output_files[lang] = str(out_file)

    return {
        "status": "success",
        "summaries": summaries,
        "output_files": output_files,
        "message": f"Generated summaries for {len(output_files)} language(s).",
    }


def run_toc(json_path: str, output_dir: str = None) -> dict:
    """Generate table of contents from a transcript JSON file.

    Args:
        json_path: Path to processed WhisperX JSON with segments.
        output_dir: Output directory. Defaults to same directory as input.

    Returns:
        Dict with TOC per language and output paths.
    """
    root = ensure_project_importable()

    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", []) if isinstance(data, dict) else data

    if not segments:
        return {"status": "error", "message": "No segments found in JSON file."}

    from subprocesses.subprocess_handler import run_llm_subprocess

    llm_output = run_llm_subprocess(segments)

    if not llm_output or not llm_output.get("toc"):
        return {"status": "error", "message": "LLM subprocess returned no table of contents."}

    out_dir = Path(output_dir) if output_dir else path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    toc = llm_output.get("toc", {})
    output_files = {}

    for lang, entries in toc.items():
        if entries:
            out_file = out_dir / f"{path.stem}_toc_{lang}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
            output_files[lang] = str(out_file)

    return {
        "status": "success",
        "toc": toc,
        "output_files": output_files,
        "message": f"Generated TOC for {len(output_files)} language(s).",
    }


def run_debug() -> dict:
    """Run LLM debug mode using the configured debug_file.

    Returns:
        Dict with status and output paths.
    """
    root = ensure_project_importable()

    from config.app_config import get_config

    config = get_config()
    debug_file = config["llm_meta"].get("debug_file", "")
    output_debug = config["llm_meta"].get("output_debug", "")

    if not debug_file or not Path(debug_file).exists():
        return {
            "status": "error",
            "message": f"Debug file not found or not configured: {debug_file}",
        }

    # Import and run the debug workflow
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "llm_workflows.llm_debug"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )

    return {
        "status": "success" if result.returncode == 0 else "error",
        "debug_file": debug_file,
        "output_debug": output_debug,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "message": "LLM debug completed." if result.returncode == 0 else f"LLM debug failed (exit code {result.returncode}).",
    }
