"""LLM workflow operations — summaries and table of contents."""

import json
from pathlib import Path

from cli_anything.asr_transcribe.utils.asr_backend import ensure_project_importable


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
