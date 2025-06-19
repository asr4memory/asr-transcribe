"""
ASR workflow script.
This is the main script that runs the ASR and alignment processes and sends
emails.
"""

from datetime import datetime
from pathlib import Path
from os import mkdir
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
)
from writers import write_output_files
from stats import ProcessInfo
from whisper_tools import get_audio, transcribe, align, get_audio_length, diarize
#from post_processing import process_whisperx_segments, process_whisperx_word_segments
from post_processing import process_whisperx_segments

from app_config import get_config
from logger import logger, memoryHandler

config = get_config()
stats = []
warning_count = 0
warning_audio_inputs = []
use_speaker_diarization = config["whisper"]["use_speaker_diarization"]


def process_file(filepath: Path, output_directory: Path):
    global warning_count, warning_audio_inputs, stats
    language_audio = config["whisper"]["language"]
    custom_model = config["whisper"].get("custom_model", False)
    if custom_model == False:
        model_name = config["whisper"]["model"]
    else:
        model_name = "custom"
    filename = filepath.name

    try:
        process_info = ProcessInfo(filename)
        process_info.start = datetime.now()

        # Main part: Loading, transcription and alignment.
        audio = get_audio(path=filepath)
        audio_length = get_audio_length(audio)
        process_info.audio_length = audio_length

        start_message = "Starting transcription of {0}, {1}...".format(
            process_info.filename, process_info.formatted_audio_length()
        )
        logger.info(start_message)

        transcription_result = transcribe(audio)
        result = align(
            audio=audio,
            segments=transcription_result["segments"],
            language=transcription_result["language"],
        )
        if use_speaker_diarization:
            result = diarize(audio=audio, result=result)

        custom_segs = process_whisperx_segments(result["segments"])
        # word_segments_filled = process_whisperx_word_segments(result["word_segments"])
        word_segments_filled = result["word_segments"]

        new_filename = f"{filename.split('.')[0]}_{model_name}_{language_audio}"

        dir_path = create_output_files_directory_path(output_directory, new_filename)
        mkdir(dir_path)
        output_base_path = dir_path / new_filename

        write_output_files(
            base_path=output_base_path,
            all=result,
            segments=custom_segs,
            word_segments=word_segments_filled,
        )

        process_info.end = datetime.now()
        stats.append(process_info)

        end_message = "Completed transcription of {0} after {1} (rtf {2:.2f})".format(
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
