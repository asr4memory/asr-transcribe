"""
ASR workflow script.
This is the main script that runs the ASR and alignment processes and sends
emails.
"""
from datetime import datetime
from pathlib import Path
import sys
import io

from email_notifications import (send_success_email, send_failure_email,
                                 send_warning_email)
from app_config import get_config, print_config
from utilities import (should_be_processed, check_for_hallucination_warnings,
                       log_to_console)
from writers import write_output_files
from stats import ProcessInfo
from whisper_tools import get_audio, transcribe, align, get_audio_length, diarize
from post_processing import process_whisperx_segments

from app_config import get_config

config = get_config()
use_speaker_diarization = config['whisper'].get('use_speaker_diarization', False)

# The following lines are to capture the stdout/terminal output
class Tee(io.StringIO):
    "Writes to two streams simultanously."
    def __init__(self, terminal):
        self.terminal = terminal
        super().__init__()

    def write(self, message):
        self.terminal.write(message)
        super().write(message)

original_stdout = sys.stdout
stdout_buffer = Tee(original_stdout)
sys.stdout = stdout_buffer

config = get_config()
stats = []
warning_count = 0
warning_audio_inputs = []


def process_file(filepath: Path, output_directory: Path):
    global warning_count, warning_audio_inputs, stats
    language_audio = config['whisper']['language']
    filename = filepath.name

    try:
        process_info = ProcessInfo(filename)
        process_info.start = datetime.now()

        # Main part: Loading, transcription and alignment.
        audio = get_audio(path=filepath)
        audio_length = get_audio_length(audio)
        process_info.audio_length = audio_length

        start_message = "Starting transcription of {0}, {1}...".format(
            process_info.filename,
            process_info.formatted_audio_length()
        )
        log_to_console(start_message)

        transcription_result = transcribe(audio)
        result = align(audio=audio,
                        segments=transcription_result['segments'],
                        language=transcription_result['language'])
        if use_speaker_diarization: result = diarize(audio=audio, result=result)

        custom_segs = process_whisperx_segments(result['segments'])


        new_filename = f"{filename.split('.')[0]}_{language_audio}"
        output_base_path = output_directory / new_filename

        write_output_files(base_path=output_base_path,
                           segments=custom_segs)

        process_info.end = datetime.now()
        stats.append(process_info);

        end_message = "Completed transcription of {0} after {1} \033[92m(rtf {2:.2f})\033[0m".format(
            process_info.filename,
            process_info.formatted_process_duration(),
            process_info.realtime_factor()
        )
        log_to_console(end_message)

        output = stdout_buffer.getvalue()
        warnings = check_for_hallucination_warnings(output)

        if warnings:
            warnings_str = ", ".join(warnings)
            log_to_console(f"Possible hallucation(s) detected: {warnings_str}")
            warning_count += len(warnings)
            warning_audio_inputs.append(filename)
            send_warning_email(audio_input=filename, warnings=warnings)

        # Clear buffer after checking for warnings.
        stdout_buffer.truncate(0)
        stdout_buffer.seek(0)


    except Exception as e:
        log_to_console(f"The following error occured: {e}")
        send_failure_email(stats=stats, audio_input=filename, exception=e)


def process_directory(input_directory: Path, output_directory: Path):
    """
    This loop iterates over all files in the input directory and
    transcribes them using the specified model.
    """
    all_filepaths = input_directory.glob('*')
    filtered_paths = [p for p in all_filepaths if should_be_processed(p)]
    filtered_paths.sort()

    if len(filtered_paths) == 0:
        log_to_console("No files found.")
    elif len(filtered_paths) == 1:
        log_to_console("Processing 1 file...")
    else:
        log_to_console(f"Processing {len(filtered_paths)} files...")

    for filepath in filtered_paths:
        process_file(filepath, output_directory)

    send_success_email(stats=stats,
                       warning_count=warning_count,
                       warning_audio_inputs=warning_audio_inputs)

    log_to_console("Workflow finished.")
    sys.stdout = original_stdout


if __name__ == "__main__":
    input_directory = Path(config['system']['input_path'])
    output_directory = Path(config['system']['output_path'])

    if not input_directory.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_directory}")

    if not output_directory.exists():
        raise FileNotFoundError(f"Output directory does not exist: {output_directory}")

    print_config()
    process_directory(input_directory, output_directory)
