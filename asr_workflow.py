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
import shutil
from email_notifications import (
    send_success_email,
    send_failure_email,
    send_warning_email,
)
from app_config import get_config, log_config
from utilities import (
    should_be_processed,
    check_for_hallucination_warnings,
    create_output_files_directory_path,
    prepare_bag_directory,
    finalize_bag,
    zip_bag_directory,
)
from subprocess_handler import (
    run_whisper_subprocess,
    run_llm_subprocess,
)
from writers import write_output_files
from stats import ProcessInfo
from whisper_subprocess import get_audio, get_audio_length
from post_processing import process_whisperx_segments

from logger import logger, memoryHandler

from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple, List


config = get_config()
stats = []
warning_count = 0
warning_audio_inputs = []
use_llms = config["llm"]["use_llms"]

@dataclass(frozen=True)
class LanguageMeta:
    source_language: str
    output_language: str
    descriptor: str
    target_language: str


@dataclass(frozen=True)
class OutputLayout:
    dir_path: Path
    transcripts_dir: Path
    data_dir: Path
    translations_dir: Path
    output_base_path: Path
    transcript_filename: str
    translation_filename: str


def get_llm_languages():
    languages = config["llm"].get("llm_languages", ["de", "en"])
    if isinstance(languages, str):
        languages = [languages]
    cleaned = []
    for lang in languages:
        if isinstance(lang, str) and lang.strip():
            cleaned.append(lang.strip().lower())
    return cleaned


LLM_LANGUAGES = get_llm_languages()


def _normalize_language(value, default="auto"):
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def get_language_descriptor(result: dict):
    """
    Build language metadata for filenames/bag info.
    Returns (source_language, output_language, descriptor_string, target_language).
    """
    configured_language = config["whisper"].get("language")
    translation_enabled = result.get("translation_enabled", False)
    source_language = result.get("source_language") or configured_language
    output_language = result.get("output_language") or source_language
    target_language = (
        result.get("translation_target_language")
        or result.get("translation_output_language")
        or output_language
    )

    normalized_source = _normalize_language(source_language)
    normalized_output = _normalize_language(output_language, default=normalized_source)
    normalized_target = _normalize_language(target_language, default=normalized_output)

    descriptor = normalized_output
    if translation_enabled:
        descriptor = f"{normalized_source}_to_{normalized_target}"

    return normalized_source, normalized_output, descriptor, normalized_target


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


def postprocess_pipeline(result: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    logger.info("Starting segment post-processing of WhisperX output...")
    processed = process_whisperx_segments(result["segments"])

    translation_processed = None
    translation_payload = result.get("translation_result")
    if translation_payload:
        translation_processed = process_whisperx_segments(translation_payload["segments"])
    
    logger.info("Segment post-processing completed.")

    return processed, translation_processed


def build_language_meta(result: Dict[str, Any]) -> LanguageMeta:
    src, out, desc, tgt = get_language_descriptor(result)
    return LanguageMeta(source_language=src, output_language=out, descriptor=desc, target_language=tgt)


def derive_model_name(result: Dict[str, Any]) -> str:
    model_used = result.get("model_name") or config["whisper"]["model"]
    return Path(str(model_used)).name if model_used else "unknown-model"


def run_llm_if_enabled(segments: List[Dict[str, Any]]) -> Dict[str, str]:
    # Always return a dict for all configured languages, default empty strings
    summaries = {lang: "" for lang in LLM_LANGUAGES}

    if not use_llms:
        return summaries
    if not LLM_LANGUAGES:
        logger.info("Summarization enabled but no languages configured; skipping.")
        return summaries

    llm_result = run_llm_subprocess(segments)

    if llm_result and llm_result.get("summaries"):
        summaries.update(llm_result["summaries"])
    else:
        logger.warning("LLM processing skipped (subprocess failed or no summaries).")

    return summaries


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

    dir_path = create_output_files_directory_path(output_directory, translation_filename)
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


def copy_documentation_files(dir_path: Path) -> None:
    documentation_dir = dir_path / "documentation"
    documentation_dir.mkdir(parents=True, exist_ok=True)

    doc_files = ["asr_export_formats.rtf", "citation.txt", "ohd_upload.txt"]
    doc_files_dir = Path(__file__).parent / "doc_files"
    current_year = datetime.now().year

    for doc_filename in doc_files:
        doc_file = doc_files_dir / doc_filename
        if not doc_file.exists():
            continue

        dest_file = documentation_dir / doc_file.name

        if doc_filename == "citation.txt":
            content = doc_file.read_text(encoding="utf-8")
            content = content.replace("<{year}>", str(current_year))
            dest_file.write_text(content, encoding="utf-8")
        else:
            shutil.copy2(doc_file, dest_file)


def write_primary_outputs(
    *,
    layout: OutputLayout,
    result: Dict[str, Any],
    processed: Dict[str, Any],
    summaries: Dict[str, str],
) -> None:
    write_output_files(
        base_path=layout.output_base_path,
        unprocessed_whisperx_output=result,
        processed_whisperx_output=processed,
        summaries=summaries,
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
        translation_unprocessed["word_segments"] = translation_processed["word_segments"]

    write_output_files(
        base_path=translation_base_path,
        unprocessed_whisperx_output=translation_unprocessed,
        processed_whisperx_output=translation_processed,
        summaries=None,
    )


def duplicate_speaker_csvs_to_ohd_import(layout: OutputLayout) -> None:
    ohd_import_dir = layout.data_dir / "ohd_import"

    speaker_csv = layout.output_base_path.with_stem(
        layout.output_base_path.stem + "_speaker"
    ).with_suffix(".csv")
    if speaker_csv.exists():
        shutil.copy2(speaker_csv, ohd_import_dir / speaker_csv.name)

    speaker_nopause_csv = layout.output_base_path.with_stem(
        layout.output_base_path.stem + "_speaker_nopause"
    ).with_suffix(".csv")
    if speaker_nopause_csv.exists():
        shutil.copy2(speaker_nopause_csv, ohd_import_dir / speaker_nopause_csv.name)


def build_bag_info(
    *,
    filename: str,
    model_name: str,
    language_meta: LanguageMeta,
    audio_length: float,
    translation_enabled: bool,
) -> Dict[str, str]:
    bag_info = {
        "Source-Filename": filename,
        "Model": model_name,
        "Language": language_meta.descriptor,
        "Audio-Length-Seconds": f"{audio_length:.2f}",
    }

    if translation_enabled:
        bag_info["Source-Language"] = language_meta.source_language
        bag_info["Target-Language"] = language_meta.target_language

    bag_config = config.get("bag", {}) or {}

    group_identifier = bag_config.get("group_identifier")
    if group_identifier:
        bag_info["Bag-Group-Identifier"] = group_identifier

    bag_count = bag_config.get("bag_count")
    if bag_count:
        bag_info["Bag-Count"] = bag_count

    sender_identifier = bag_config.get("internal_sender_identifier")
    if sender_identifier:
        bag_info["Internal-Sender-Identifier"] = sender_identifier

    sender_description = bag_config.get("internal_sender_description")
    if sender_description:
        bag_info["Internal-Sender-Description"] = sender_description

    return bag_info


def finalize_and_zip_bag(dir_path: Path, data_dir: Path, bag_info: Dict[str, str]) -> None:
    payload_files = [p for p in data_dir.rglob("*") if p.is_file()]
    finalize_bag(dir_path, payload_files, bag_info)

    if config["system"].get("zip_bags", True):
        try:
            zip_bag_directory(dir_path)
        except Exception as zip_error:
            logger.warning("Failed to create ZIP archive for %s: %s", dir_path, zip_error)


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

        processed_whisperx_output, translation_processed_output = postprocess_pipeline(result)

        language_meta = build_language_meta(result)
        model_name = derive_model_name(result)

        # LLM summaries (subprocess)
        summaries = run_llm_if_enabled(processed_whisperx_output["segments"])
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
            summaries=summaries,
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
