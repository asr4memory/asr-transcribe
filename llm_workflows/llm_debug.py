"""
Debug script for testing LLM workflows independently.

Automatically outputs all LLM results (summaries, toc, etc.)
without needing changes when new LLM tasks are added.

Usage:
    python -m llm_workflows.llm_debug
"""

import json
from datetime import datetime
from pathlib import Path
from app_config import get_config
from subprocess_handler import run_llm_subprocess
from writers import write_output_files

config = get_config()


def print_llm_results(llm_result: dict) -> None:
    """Print all LLM results automatically (summaries, toc, etc.)."""
    print("\n" + "=" * 50)

    for key, value in llm_result.items():
        if key.startswith("_"):  # Skip meta keys like _meta
            continue

        if isinstance(value, dict) and value:
            print(f"\n{key.upper()}:")
            for lang, content in value.items():
                preview = content[:500] + "..." if len(content) > 500 else content
                print(f"\n[{lang.upper()}]\n{preview}")

    # Show metadata
    meta = llm_result.get("_meta", {})
    if meta.get("trial"):
        print(f"\n(LLM completed on trial {meta['trial']})")


def main():
    debug_file = Path(config["llm"]["debug_file"])
    output_dir = Path(config["llm"]["output_debug"])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"{debug_file.stem}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading {debug_file}...")

    with open(debug_file, encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", [])
    if not segments:
        print("No segments found in input file.")
        return 1

    print(f"Running LLM on {len(segments)} segments...")

    # Run LLM subprocess (returns unified result dict)
    llm_result = run_llm_subprocess(segments)

    if llm_result is None:
        print("LLM subprocess failed.")
        return 1

    # Write all output files (like the full workflow, without BagIt)
    # NOTE: Extend parameters here when adding new LLM tasks to write_output_files
    base_path = run_dir / debug_file.stem
    write_output_files(
        base_path=base_path,
        unprocessed_whisperx_output=data,
        processed_whisperx_output=data,
        summaries=llm_result.get("summaries"),
    )

    print(f"\nOutput written to {run_dir}/")
    return 0


if __name__ == "__main__":
    exit(main())
