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
from os import mkdir
import subprocess
import sys
import pickle
from email_notifications import (
    send_success_email,
    send_failure_email,
    send_warning_email,
)
from app_config import get_config, log_config
from utilities import (
    should_be_processed,
    check_for_hallucination_warnings,
    create_output_files_directory_path
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
use_speaker_diarization = config["whisper"]["use_speaker_diarization"]
use_summarization = config["llm"]["use_summarization"]


def run_whisper_subprocess(audio_path: str):
    """
    Run complete Whisper pipeline in isolated subprocess.
    Returns: dict with 'segments', 'word_segments', and 'language' keys

    Memory is guaranteed to be freed when subprocess exits.
    """
    logger.info("Starting Whisper subprocess...")

    result = subprocess.run(
        [sys.executable, "whisper_subprocess.py", str(audio_path)],
        capture_output=True,
        check=False  # Don't raise exception, we'll handle errors manually
    )

    if result.returncode != 0:
        error_msg = result.stderr.decode('utf-8') if result.stderr else "Unknown error"
        logger.error(f"Whisper subprocess failed: {error_msg}")
        raise RuntimeError(f"Whisper subprocess failed: {error_msg}")

    # Deserialize result
    whisper_result = pickle.loads(result.stdout)
    logger.info("Whisper subprocess completed successfully")

    return whisper_result


def run_llm_subprocess(segments):
    """
    Run LLM summarization in isolated subprocess.
    Returns: str (summary text)

    Memory is guaranteed to be freed when subprocess exits.
    """
    logger.info("Starting LLM subprocess...")

    # Serialize segments and pass via stdin
    input_data = pickle.dumps(segments)

    result = subprocess.run(
        [sys.executable, "llm_subprocess.py"],
        input=input_data,
        capture_output=True,
        check=False  # Don't raise exception, we'll handle errors manually
    )

    if result.returncode != 0:
        error_msg = result.stderr.decode('utf-8') if result.stderr else "Unknown error"
        logger.warning(f"LLM subprocess failed: {error_msg}")
        # LLM is optional, so we return None instead of raising
        return None

    # Deserialize result - subprocess returns a tuple (summary, trials)
    summary, trials = pickle.loads(result.stdout)

    if trials == 1:
        logger.info("LLM subprocess succeeded on first trial with 32k context window with faster processing")
    elif trials == 2:
        logger.info("LLM subprocess succeeded on second trial with 64k context window with slower processing")

    logger.info("LLM subprocess completed successfully")

    return summary


def process_file(filepath: Path, output_directory: Path):
    global warning_count, warning_audio_inputs, stats
    language_audio = config["whisper"]["language"]
    model_name = Path(config["whisper"]["model"]).name
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

        intermediate_message_3 = "Whisper pipeline completed for {0}, starting post-processing...".format(
            process_info.filename
        )
        logger.info(intermediate_message_3)

        # Post-processing (runs in main process, lightweight)
        custom_segs = process_whisperx_segments(result["segments"])
        word_segments_filled = result["word_segments"]

        if use_summarization:
            intermediate_message_4 = "Post-processing completed for {0}, starting summarization...".format(
                process_info.filename
            )
            logger.info(intermediate_message_4)

            # Run LLM summarization in subprocess
            # Memory is guaranteed freed when subprocess exits
            summary = run_llm_subprocess(result["segments"])

            if summary is not None:
                intermediate_message_5 = "Summarization completed for {0}.".format(
                    process_info.filename
                )
                logger.info(intermediate_message_5)
            else:
                logger.warning(f"Summarization skipped for {process_info.filename} (subprocess failed)")
                summary = ""  # Use empty string as fallback
        else:
            intermediate_message_5 = "Post-processing completed for {0}.".format(
                process_info.filename
            )
            logger.info(intermediate_message_5)
            summary = ""  # No summarization requested

        new_filename = f"{filename.split('.')[0]}_{model_name}_{language_audio}"

        dir_path = create_output_files_directory_path(output_directory, new_filename)
        mkdir(dir_path)
        output_base_path = dir_path / new_filename

        write_output_files(
            base_path=output_base_path,
            all=result,
            segments=custom_segs,
            word_segments=word_segments_filled,
            summary=summary,
        )

        process_info.end = datetime.now()
        stats.append(process_info)

        end_message = "Completed transcription process of {0} after {1} (rtf {2:.2f})".format(
            process_info.filename,
            process_info.formatted_process_duration(),
            process_info.realtime_factor(),
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
