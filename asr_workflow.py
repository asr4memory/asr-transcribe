"""
ASR workflow script.
This is the main script that runs the ASR and alignment processes and sends
emails.
"""
from datetime import datetime
import os
import sys
import io

from email_notifications import (send_success_email, send_failure_email,
                                 send_warning_email)
from app_config import get_config, print_config
from utilities import (ignore_file, format_duration,
                       check_for_hallucination_warnings)
from writers import (write_text_file, write_csv_file, write_vtt_file,
                     write_json_file)
from stats import ProcessInfo
from whisper_tools import get_audio, transcribe, align, get_audio_length
from post_processing import process_whisperx_segments


# The following lines are to capture the stdout/terminal output
class Tee(io.StringIO):
    "Writes to two streams simultanously."
    def __init__(self, terminal):
        self.terminal = terminal
        super().__init__()

    def write(self, message):
        self.terminal.write(message)
        super().write(message)


# Save a reference to the original stdout
original_stdout = sys.stdout
# Redirect stdout to the buffer
stdout_buffer = Tee(original_stdout)
sys.stdout = stdout_buffer

#####

config = get_config()

# Define parameters for WhisperX model
language_audio = config['whisper']['language']

# Define input und output folders
input_path = config['system']['input_path']
output_path = config['system']['output_path']
input_directory = os.listdir(path=input_path)
output_directory = os.path.dirname(output_path)
# Filename suffix corresponds to the variable "language_audio" above.
filename_suffix = "_" + language_audio

stats = []

warning_count = 0
warning_audio_inputs = []

print_config()

try:
    # This loop iterates over all the files in the input directory and
    # transcribes them using the specified model.
    for root, directories, files in os.walk(input_path):
        files.sort()
        for audio_input in files:
            if ignore_file(audio_input): continue

            audio_file = os.path.join(input_path, audio_input)
            output_file = os.path.join(output_directory,
                                       audio_input.split(".")[0] + filename_suffix)

            process_info = ProcessInfo(audio_input)
            process_info.start = datetime.now()

            # Main part: Loading, transcription and alignment.
            audio = get_audio(path=audio_file)
            audio_length = get_audio_length(audio)
            process_info.audio_length = audio_length
            formatted_audio_length = format_duration(audio_length)

            start_message = "\033[94m{0}\033[0m Transcribing {1}, {2}...".format(
                process_info.start.isoformat(sep=" ", timespec="seconds"),
                process_info.filename,
                process_info.formatted_audio_length()
            )
            print(start_message)

            transcription_result = transcribe(audio)
            result = align(audio=audio,
                           segments=transcription_result['segments'],
                           language=transcription_result['language'])

            custom_segs = process_whisperx_segments(result['segments'])

            write_vtt_file(output_file, custom_segs)
            write_text_file(output_file, custom_segs)
            write_csv_file(output_file, custom_segs)
            write_csv_file(output_file, custom_segs, delimiter="\t",
                           speaker_column=True, write_header=True)
            write_json_file(output_file, custom_segs)

            process_info.end = datetime.now()
            stats.append(process_info);
            end_message = "\033[94m{0}\033[0m Completed {1} after {2} \033[92m(rtf {3:.2f})\033[0m".format(
                process_info.end.isoformat(sep=" ", timespec="seconds"),
                process_info.filename,
                process_info.formatted_process_duration(),
                process_info.realtime_factor()
            )
            print(end_message)


            output = stdout_buffer.getvalue()
            warnings = check_for_hallucination_warnings(output)

            if warnings:
                warnings_str = ", ".join(warnings)
                print(f"==> Possible hallucation(s) detected: {warnings_str}")
                warning_count += len(warnings)
                warning_audio_inputs.append(audio_input)
                send_warning_email(audio_input=audio_input, warnings=warnings)

            # Clear buffer after checking for warnings.
            stdout_buffer.truncate(0)
            stdout_buffer.seek(0)


    send_success_email(stats=stats,
                       warning_count=warning_count,
                       warning_audio_inputs=warning_audio_inputs)


except Exception as e:
    print('==> The following error occured: ', e)
    sys.stdout = original_stdout

    send_failure_email(stats=stats,
                       audio_input=audio_input,
                       warning_count=warning_count,
                       warning_audio_inputs=warning_audio_inputs,
                       exception=e)


# Final message.
print('====> Overall workflow is finished. <====')
sys.stdout = original_stdout
