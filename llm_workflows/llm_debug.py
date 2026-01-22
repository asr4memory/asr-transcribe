"""
Debug script for testing LLM workflows independently.

Usage:
    python -m llm_workflows.llm_debug
"""

import json
from pathlib import Path
from app_config import get_config
from subprocess_handler import run_llm_subprocess
from writers import write_summary

config = get_config()


def main():
    debug_file = Path(config["llm"]["debug_file"])
    output_dir = Path(config["llm"]["output_debug"])
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running LLM on {debug_file}...")

    with open(debug_file, encoding="utf-8") as f:
        data = json.load(f)
    segments = data.get("segments", data)

    result = run_llm_subprocess(segments)

    if result is None:
        print("LLM subprocess failed.")
        return 1

    # Use base_path for write_summary (it creates abstracts/ subdirectory)
    base_path = output_dir / debug_file.stem

    print("\n" + "=" * 50)
    for lang, summary in result.items():
        print(f"\n[{lang.upper()}]\n{summary}")
        write_summary(base_path, summary, language_code=lang)
        print(f"Saved via write_summary")

    return 0


if __name__ == "__main__":
    exit(main())
