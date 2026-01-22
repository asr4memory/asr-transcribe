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

config = get_config()
stats = []
warning_count = 0
warning_audio_inputs = []
use_llms = config["llm"]["use_llms"]


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


def process_file(filepath: Path, output_directory: Path):
    global warning_count, warning_audio_inputs, stats
    filename = filepath.name

    try:
        process_info = ProcessInfo(filename)
        process_info.start = datetime.now()

        # Get audio length for statistics (lightweight operation)
        audio = get_audio(path=filepath)
        audio_length = get_audio_length(audio)
        process_info.audio_length = audio_length

        start_message = "Starting transcription of {0}, {1}...".format(
            process_info.filename, process_info.formatted_audio_length()
        )
        logger.info(start_message)

        # Run complete Whisper pipeline in subprocess
        # Includes: transcription + alignment + (optional) diarization
        # Memory is guaranteed freed when subprocess exits
        result = run_whisper_subprocess(filepath)
        translation_payload = result.get("translation_result")

        intermediate_message_3 = (
            "Whisper pipeline completed for {0}, starting post-processing...".format(
                process_info.filename
            )
        )
        logger.info(intermediate_message_3)

        # Post-processing (runs in main process, lightweight)
        processed_whisperx_output = process_whisperx_segments(result["segments"])
        translation_processed_output = None
        if translation_payload:
            translation_processed_output = process_whisperx_segments(
                translation_payload["segments"]
            )

        (
            source_language,
            output_language,
            language_descriptor,
            target_language,
        ) = get_language_descriptor(result)

        model_used = result.get("model_name") or config["whisper"]["model"]
        model_name = Path(str(model_used)).name if model_used else "unknown-model"

        summaries = {lang: "" for lang in LLM_LANGUAGES}
        if use_llms and LLM_LANGUAGES:
            logger.info(
                f"Post-processing completed for {process_info.filename}, starting LLM processes..."
            )

            # Run LLM tasks in subprocess (returns unified result dict)
            # Memory is guaranteed freed when subprocess exits
            llm_result = run_llm_subprocess(processed_whisperx_output["segments"])

            if llm_result is not None:
                # Process summaries
                if llm_result.get("summaries"):
                    summaries.update(llm_result["summaries"])
                    logger.info(f"Summarization completed for {process_info.filename}.")

                # Future: Process table of contents
                # if llm_result.get("toc"):
                #     toc.update(llm_result["toc"])
                #     logger.info(f"Table of contents completed for {process_info.filename}.")
            else:
                logger.warning(
                    f"LLM processing skipped for {process_info.filename} (subprocess failed)"
                )
        elif use_llms and not LLM_LANGUAGES:
            logger.info("Summarization enabled but no languages configured; skipping.")
            intermediate_message_5 = "Post-processing completed for {0}.".format(
                process_info.filename
            )
            logger.info(intermediate_message_5)
        else:
            intermediate_message_5 = "Post-processing completed for {0}.".format(
                process_info.filename
            )
            logger.info(intermediate_message_5)

        file_stem = filename.split(".")[0]
        transcript_filename = f"{file_stem}_{model_name}_{output_language}"
        translation_filename = f"{file_stem}_{model_name}_{language_descriptor}"

        dir_path = create_output_files_directory_path(
            output_directory, translation_filename
        )
        transcripts_dir = prepare_bag_directory(dir_path)

        # Copy documentation files to documentation/ directory
        documentation_dir = dir_path / "documentation"
        documentation_dir.mkdir(parents=True, exist_ok=True)
        doc_files = ["asr_export_formats.rtf", "citation.txt", "ohd_upload.txt"]
        doc_files_dir = Path(__file__).parent / "doc_files"
        current_year = datetime.now().year
        for doc_filename in doc_files:
            doc_file = doc_files_dir / doc_filename
            if doc_file.exists():
                dest_file = documentation_dir / doc_file.name
                # Special handling for citation.txt: replace <{year}> with current year
                if doc_filename == "citation.txt":
                    content = doc_file.read_text(encoding="utf-8")
                    content = content.replace("<{year}>", str(current_year))
                    dest_file.write_text(content, encoding="utf-8")
                else:
                    shutil.copy2(doc_file, dest_file)

        output_base_path = transcripts_dir / transcript_filename
        data_dir = dir_path / "data"
        translations_dir = data_dir / "translations"

        write_output_files(
            base_path=output_base_path,
            unprocessed_whisperx_output=result,
            processed_whisperx_output=processed_whisperx_output,
            summaries=summaries,
        )

        if translation_payload:
            translations_dir.mkdir(parents=True, exist_ok=True)
            translation_base_path = translations_dir / translation_filename
            translation_unprocessed = translation_payload
            if (
                translation_processed_output
                and "word_segments" not in translation_unprocessed
            ):
                translation_unprocessed = dict(translation_payload)
                translation_unprocessed["word_segments"] = translation_processed_output[
                    "word_segments"
                ]
            write_output_files(
                base_path=translation_base_path,
                unprocessed_whisperx_output=translation_unprocessed,
                processed_whisperx_output=translation_processed_output,
                summaries=None,
            )

        # Duplicate the speaker CSV into the ohd_import directory for downstream ingestion.
        ohd_import_dir = data_dir / "ohd_import"
        speaker_csv = output_base_path.with_stem(
            output_base_path.stem + "_speaker"
        ).with_suffix(".csv")
        if speaker_csv.exists():
            shutil.copy2(speaker_csv, ohd_import_dir / speaker_csv.name)
        speaker_nopause_csv = output_base_path.with_stem(
            output_base_path.stem + "_speaker_nopause"
        ).with_suffix(".csv")
        if speaker_nopause_csv.exists():
            shutil.copy2(speaker_nopause_csv, ohd_import_dir / speaker_nopause_csv.name)

        payload_files = [p for p in data_dir.rglob("*") if p.is_file()]
        bag_info = {
            "Source-Filename": filename,
            "Model": model_name,
            "Language": language_descriptor,
            "Audio-Length-Seconds": f"{audio_length:.2f}",
        }
        if result.get("translation_enabled"):
            bag_info["Source-Language"] = source_language
            bag_info["Target-Language"] = target_language
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

        finalize_bag(dir_path, payload_files, bag_info)

        if config["system"].get("zip_bags", True):
            try:
                zip_bag_directory(dir_path)
            except Exception as zip_error:
                logger.warning(
                    "Failed to create ZIP archive for %s: %s", dir_path, zip_error
                )

        process_info.end = datetime.now()
        stats.append(process_info)

        end_message = (
            "Completed transcription process of {0} after {1} (rtf {2:.2f})".format(
                process_info.filename,
                process_info.formatted_process_duration(),
                process_info.realtime_factor(),
            )
        )
        logger.info(end_message)

        output = memoryHandler.stream.getvalue()
        warnings = check_for_hallucination_warnings(output)

        if warnings:
            warnings_str = ", ".join(warnings)
            logger.warn(f"Possible hallucation(s) detected: {warnings_str}")
            warning_count += len(warnings)
            warning_audio_inputs.append(filename)
            send_warning_email(audio_input=filename, warnings=warnings)

        # Clear buffer after checking for warnings.
        memoryHandler.stream.truncate(0)
        memoryHandler.stream.seek(0)

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
