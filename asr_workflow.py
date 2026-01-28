"""
ASR workflow script.
This is the main script that runs the ASR and alignment processes and sends
emails.

Uses subprocess architecture for memory isolation:
- Whisper pipeline runs in subprocess (guaranteed memory cleanup)
- LLM summarization runs in subprocess (guaranteed memory cleanup)
- Main process coordinates workflow and writes files
"""

from datetime import datetime
from pathlib import Path
from utils.email_notifications import (
    send_success_email,
    send_failure_email,
    send_warning_email,
)
from config.app_config import get_config, log_config
from utils.utilities import (
    should_be_processed,
    check_for_hallucination_warnings,
    create_output_files_directory_path,
    prepare_bag_directory,
    copy_documentation_files,
    duplicate_speaker_csvs_to_ohd_import,
    build_bag_info,
    finalize_and_zip_bag,
)
from subprocesses.subprocess_handler import (
    run_whisper_subprocess,
    run_llm_subprocess,
)
from output.writers import write_output_files
from utils.stats import ProcessInfo
from subprocesses.whisper_subprocess import get_audio, get_audio_length
from output.post_processing import process_whisperx_segments

from config.logger import logger, memoryHandler
from utils.language_utils import (
    LanguageMeta,
    LLM_LANGUAGES,
    build_language_meta,
    derive_model_name,
)

from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple, List


config = get_config()
stats = []
warning_count = 0
warning_audio_inputs = []
use_summarization = config["llm"].get("use_summarization", False)
use_toc = config["llm"].get("use_toc", False)


@dataclass(frozen=True)
class OutputLayout:
    dir_path: Path
    transcripts_dir: Path
    data_dir: Path
    translations_dir: Path
    output_base_path: Path
    transcript_filename: str
    translation_filename: str


def init_process_info(filepath: Path) -> ProcessInfo:
    pi = ProcessInfo(filepath.name)
    pi.start = datetime.now()
    return pi


def compute_audio_length_seconds(filepath: Path) -> float:
    # Lightweight operation (your existing helpers)
    audio = get_audio(path=filepath)
    return float(get_audio_length(audio))


def run_whisper_pipeline(filepath: Path) -> Dict[str, Any]:
    # Subprocess boundary (memory isolation)
    return run_whisper_subprocess(filepath)


def postprocess_pipeline(
    result: Dict[str, Any],
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    logger.info("Starting segment post-processing of WhisperX output...")
    processed = process_whisperx_segments(result["segments"])

    translation_processed = None
    translation_payload = result.get("translation_result")
    if translation_payload:
        translation_processed = process_whisperx_segments(
            translation_payload["segments"]
        )

    logger.info("Segment post-processing completed.")

    return processed, translation_processed


def run_llm_if_enabled(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run LLM subprocess if enabled, return unified llm_output dict."""
    empty_result = {}
    if use_summarization:
        empty_result["summaries"] = {lang: "" for lang in LLM_LANGUAGES}
    if use_toc:
        empty_result["toc"] = {lang: "" for lang in LLM_LANGUAGES}

    if not use_summarization and not use_toc:
        return empty_result
    if not LLM_LANGUAGES:
        logger.info("LLM usage enabled but no languages configured; skipping.")
        return empty_result

    llm_output = run_llm_subprocess(segments)

    if not llm_output:
        logger.error("LLM subprocess failed completely or returned no result.")
        return empty_result

    if not llm_output.get("summaries") and use_summarization:
        logger.warning("No summaries found in LLM subprocess result.")
    if not llm_output.get("toc") and use_toc:
        logger.warning("No table of contents found in LLM subprocess result.")

    return llm_output


def build_output_layout(
    *,
    output_directory: Path,
    filename: str,
    model_name: str,
    language_meta: LanguageMeta,
) -> OutputLayout:
    file_stem = filename.split(".")[0]
    transcript_filename = f"{file_stem}_{model_name}_{language_meta.output_language}"
    translation_filename = f"{file_stem}_{model_name}_{language_meta.descriptor}"

    dir_path = create_output_files_directory_path(
        output_directory, translation_filename
    )
    transcripts_dir = prepare_bag_directory(dir_path)

    data_dir = dir_path / "data"
    translations_dir = data_dir / "translations"
    output_base_path = transcripts_dir / transcript_filename

    return OutputLayout(
        dir_path=dir_path,
        transcripts_dir=transcripts_dir,
        data_dir=data_dir,
        translations_dir=translations_dir,
        output_base_path=output_base_path,
        transcript_filename=transcript_filename,
        translation_filename=translation_filename,
    )


def write_primary_outputs(
    *,
    layout: OutputLayout,
    result: Dict[str, Any],
    processed: Dict[str, Any],
    llm_output: Dict[str, Any],
) -> None:
    write_output_files(
        base_path=layout.output_base_path,
        unprocessed_whisperx_output=result,
        processed_whisperx_output=processed,
        llm_output=llm_output,
    )


def write_translation_outputs_if_any(
    *,
    layout: OutputLayout,
    translation_payload: Optional[Dict[str, Any]],
    translation_processed: Optional[Dict[str, Any]],
) -> None:
    if not translation_payload:
        return

    layout.translations_dir.mkdir(parents=True, exist_ok=True)

    translation_base_path = layout.translations_dir / layout.translation_filename

    translation_unprocessed = translation_payload
    if translation_processed and "word_segments" not in translation_unprocessed:
        translation_unprocessed = dict(translation_payload)
        translation_unprocessed["word_segments"] = translation_processed[
            "word_segments"
        ]

    write_output_files(
        base_path=translation_base_path,
        unprocessed_whisperx_output=translation_unprocessed,
        processed_whisperx_output=translation_processed,
    )


def handle_hallucination_warnings_for_file(filename: str) -> None:
    global warning_count, warning_audio_inputs

    output = memoryHandler.stream.getvalue()
    warnings = check_for_hallucination_warnings(output)

    if warnings:
        warnings_str = ", ".join(warnings)
        logger.warning(f"Possible hallucation(s) detected: {warnings_str}")
        warning_count += len(warnings)
        warning_audio_inputs.append(filename)
        send_warning_email(audio_input=filename, warnings=warnings)

    # Clear buffer after checking for warnings.
    memoryHandler.stream.truncate(0)
    memoryHandler.stream.seek(0)


def process_file(filepath: Path, output_directory: Path):
    global stats
    filename = filepath.name

    try:
        process_info = init_process_info(filepath)

        audio_length = compute_audio_length_seconds(filepath)
        process_info.audio_length = audio_length

        logger.info(
            "Starting transcription of %s, %s...",
            process_info.filename,
            process_info.formatted_audio_length(),
        )

        result = run_whisper_pipeline(filepath)
        translation_payload = result.get("translation_result")

        logger.info(
            "Whisper pipeline completed for %s, starting post-processing...",
            process_info.filename,
        )

        processed_whisperx_output, translation_processed_output = postprocess_pipeline(
            result
        )

        language_meta = build_language_meta(result)
        model_name = derive_model_name(result)

        # LLM subprocess
        llm_output = run_llm_if_enabled(processed_whisperx_output["segments"])
        logger.info("Post-processing completed for %s.", process_info.filename)

        # Output layout + docs + writing
        layout = build_output_layout(
            output_directory=output_directory,
            filename=filename,
            model_name=model_name,
            language_meta=language_meta,
        )

        copy_documentation_files(layout.dir_path)

        write_primary_outputs(
            layout=layout,
            result=result,
            processed=processed_whisperx_output,
            llm_output=llm_output,
        )

        write_translation_outputs_if_any(
            layout=layout,
            translation_payload=translation_payload,
            translation_processed=translation_processed_output,
        )

        duplicate_speaker_csvs_to_ohd_import(layout)

        # Bag metadata + finalize
        bag_info = build_bag_info(
            filename=filename,
            model_name=model_name,
            language_meta=language_meta,
            audio_length=audio_length,
            translation_enabled=bool(result.get("translation_enabled")),
        )
        finalize_and_zip_bag(layout.dir_path, layout.data_dir, bag_info)

        # Stats + logging
        process_info.end = datetime.now()
        stats.append(process_info)

        logger.info(
            "Completed transcription process of %s after %s (rtf %.2f)",
            process_info.filename,
            process_info.formatted_process_duration(),
            process_info.realtime_factor(),
        )

        # Warning scan (log buffer)
        handle_hallucination_warnings_for_file(filename)

    except Exception as e:
        logger.error(e, exc_info=True)
        send_failure_email(stats=stats, audio_input=filename, exception=e)


def process_directory(input_directory: Path, output_directory: Path):
    """
    This loop iterates over all files in the input directory and
    transcribes them using the specified model.
    """
    all_filepaths = input_directory.glob("*")
    filtered_paths = [p for p in all_filepaths if should_be_processed(p)]
    filtered_paths.sort()

    if len(filtered_paths) == 0:
        logger.info("No files found.")
    elif len(filtered_paths) == 1:
        logger.info("Processing 1 file...")
    else:
        logger.info(f"Processing {len(filtered_paths)} files...")

    for filepath in filtered_paths:
        process_file(filepath, output_directory)

    send_success_email(
        stats=stats,
        warning_count=warning_count,
        warning_audio_inputs=warning_audio_inputs,
    )


if __name__ == "__main__":
    input_directory = Path(config["system"]["input_path"])
    output_directory = Path(config["system"]["output_path"])

    if not input_directory.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_directory}")

    if not output_directory.exists():
        raise FileNotFoundError(f"Output directory does not exist: {output_directory}")

    log_config()
    process_directory(input_directory, output_directory)
