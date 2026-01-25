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
from config.app_config import get_config
from asr_workflow import (
    run_llm_if_enabled,
    build_output_layout,
    write_primary_outputs,
)
from utils.language_utils import (
    build_language_meta,
    derive_model_name,
)
from utils.utilities import (
    copy_documentation_files,
    duplicate_speaker_csvs_to_ohd_import,
    build_bag_info,
    finalize_and_zip_bag,
)


config = get_config()


def print_llm_output(llm_output: dict) -> None:
    """Print all LLM results automatically (summaries, toc, etc.)."""
    print("\n" + "=" * 50)

    for key, value in llm_output.items():
        if key.startswith("_"):  # Skip meta keys like _meta
            continue

        if isinstance(value, dict) and value:
            print(f"\n{key.upper()}:")
            for lang, content in value.items():
                preview = content[:500] + "..." if len(content) > 500 else content
                print(f"\n[{lang.upper()}]\n{preview}")

    # Show metadata
    meta = llm_output.get("_meta", {})
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

    language_meta = build_language_meta(data)
    model_name = derive_model_name(data)
    # Audio length not available in debug mode (no audio file)
    audio_length = 0.0

    # LLM subprocess
    llm_output = run_llm_if_enabled(segments)

    # Output layout + docs + writing
    layout = build_output_layout(
        output_directory=output_dir,
        filename=debug_file.name,
        model_name=model_name,
        language_meta=language_meta,
    )

    copy_documentation_files(layout.dir_path)

    write_primary_outputs(
        layout=layout,
        result=data,
        processed=data,
        llm_output=llm_output,
    )

    duplicate_speaker_csvs_to_ohd_import(layout)

    # Bag metadata + finalize
    bag_info = build_bag_info(
        filename=debug_file.name,
        model_name=model_name,
        language_meta=language_meta,
        audio_length=audio_length,
        translation_enabled=False,
    )
    finalize_and_zip_bag(layout.dir_path, layout.data_dir, bag_info)


if __name__ == "__main__":
    exit(main())
