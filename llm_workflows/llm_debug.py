"""
Debug script for testing LLM workflows independently.

Usage:
    python -m llm_workflows.llm_debug
"""

import json
from pathlib import Path
from unittest import result
from app_config import get_config
from subprocess_handler import run_llm_subprocess
from writers import write_output_files

config = get_config()


def main():
    debug_file = Path(config["llm"]["debug_file"])
    output_dir = Path(config["llm"]["output_debug"])
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running LLM on {debug_file}...")

    with open(debug_file, encoding="utf-8") as f:
        data = json.load(f)
    segments = data.get("segments", data)

    # Run LLM subprocess (returns unified result dict)
    llm_result = run_llm_subprocess(segments)

    if llm_result is None:
        print("LLM subprocess failed.")
        return 1

    # Base path for write_summary
    base_path = output_dir / debug_file.stem

    print("\n" + "=" * 50)

    # Process summaries
    summaries = llm_result.get("summaries", {})
    # toc = llm_result.get("toc", {})
    
    write_output_files(
        base_path=base_path,
        unprocessed_whisperx_output=segments,
        processed_whisperx_output=segments,
        summaries=summaries,
    )
    # Show metadata
    meta = llm_result.get("_meta", {})
    if meta.get("trial"):
        print(f"\n(Completed on trial {meta['trial']})")

    return 0


if __name__ == "__main__":
    exit(main())
