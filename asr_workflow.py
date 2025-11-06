"""
ASR workflow script.
This is the main script that runs the ASR and alignment processes and sends
emails.
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
)
from writers import write_output_files
from stats import ProcessInfo
from whisper_tools import get_audio, transcribe, align, get_audio_length, diarize
#from post_processing import process_whisperx_segments, process_whisperx_word_segments
from post_processing import process_whisperx_segments

from logger import logger, memoryHandler

config = get_config()
stats = []
warning_count = 0
warning_audio_inputs = []
use_speaker_diarization = config["whisper"]["use_speaker_diarization"]


def process_file(filepath: Path, output_directory: Path):
    global warning_count, warning_audio_inputs, stats
    language_audio = config["whisper"]["language"]
    model_name = Path(config["whisper"]["model"]).name
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
        transcripts_dir = prepare_bag_directory(dir_path)
        
        # Copy documentation files to documentation/ directory
        documentation_dir = dir_path / "documentation"
        documentation_dir.mkdir(parents=True, exist_ok=True)
        doc_files = [
            "asr_export_formats.rtf",
            "citation.txt",
            "ohd_upload.txt"
        ]
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
        
        output_base_path = transcripts_dir / new_filename

        write_output_files(
            base_path=output_base_path,
            all=result,
            segments=custom_segs,
            word_segments=word_segments_filled,
        )

        data_dir = dir_path / "data"
        payload_files = [p for p in data_dir.rglob("*") if p.is_file()]
        bag_info = {
            "Source-Filename": filename,
            "Model": model_name,
            "Language": language_audio,
            "Audio-Length-Seconds": f"{audio_length:.2f}",
        }
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
