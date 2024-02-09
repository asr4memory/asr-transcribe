"""
ASR workflow script.
This is the main script that runs the ASR and alignment processes and sends
emails.
"""
from datetime import datetime
import os
import sys
import re

from email_notifications import (send_success_email, send_failure_email,
                                 send_warning_email)
from app_config import get_config, print_config
from utilities import (ignore_file, Tee, write_text_file, write_csv_file,
                       write_vtt_file)
from whisper_tools import get_audio, transcribe, align, get_audio_length
from post_processing import process_whisperx_segments

# The following lines are to capture the stdout/terminal output
# Save a reference to the original stdout and stderr
original_stdout = sys.stdout
original_stderr = sys.stderr

# Redirect stdout and stderr to the buffer
stdout_buffer = Tee(original_stdout)
stderr_buffer = Tee(original_stderr)
sys.stdout = stdout_buffer
sys.stderr = stderr_buffer

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

input_file_list = []
workflowduration_list = []
workflowduration_in_seconds_list = []
audioduration_list = []
real_time_factor_list = []

warning_count = 0
warning_audio_inputs = []
warning_word = "failed"

print_config()

try:
    # This loop iterates over all the files in the input directory and
    # transcribes them using the specified model.
    for root, directories, files in os.walk(input_path):
        for audio_input in files:
            if ignore_file(audio_input): continue

            input_file_list.append(audio_input)
            audio_file = os.path.join(input_path, audio_input)
            output_file = os.path.join(output_directory,
                                       audio_input.split(".")[0] + filename_suffix)

            workflowstarttime = datetime.now()
            print(f'--> Whisper workflow for {audio_input} started: {workflowstarttime}')

            # Main part: Loading, transcription and alignment.
            audio = get_audio(path=audio_file)

            duration, formatted_duration = get_audio_length(audio)
            audioduration_list.append(formatted_duration)
            print('--> Audio duration: %s (%.1fs)' % (formatted_duration, duration))

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

            # These lines prints the time of the workflow end:
            workflowendtime = datetime.now()
            print(f'--> Whisper workflow completed for {audio_input}: {workflowendtime}')

            # Calculate the duration of the workflow:
            workflowduration = workflowendtime - workflowstarttime
            print(f'==> Whisper workflow duration for transcribing the file {audio_input}: {workflowduration}')
            workflowduration_list.append(str(workflowduration))

            # Assume workflowduration is a datetime.timedelta object and print
            # the duration in seconds:
            workflowduration_in_seconds = workflowduration.total_seconds()
            print(f"==> Whisper workflow duration for transcribing the file {audio_input}:", workflowduration_in_seconds)
            workflowduration_in_seconds_list.append(str(workflowduration_in_seconds))

            # Calculate the real time factor for processing an audio file,
            # i.e. the ratio of workflowduration_in_seconds to audioduration_in_seconds:
            real_time_factor = workflowduration_in_seconds / duration
            print("==> Whisper real time factor - the ratio of workflow duration compared to audio duration:", real_time_factor)
            real_time_factor_list.append(str(real_time_factor))

            # The following lines send email warnings of the output of the
            # stdout/terminal output:
            # Get the output from the buffer
            output = stdout_buffer.getvalue()

            # Restore the original stdout and stderr
            sys.stdout = original_stdout
            sys.stderr = original_stderr

            # Check the output for the specific message
            # Goal is to find the message "failed to align segment" in the
            # stdout/terminal output to identify AI hallucinations.
            for match in re.finditer(rf"({warning_word})", output.lower()):
                line_start = output.rfind('\n', 0, match.start()) + 1
                line_end = output.find('\n', match.end())
                line = output[line_start:line_end]
                print(f"==> The following warning message was captured in the stdout/terminal output: {line}")
                warning_count += 1
                warning_audio_inputs.append(audio_input)

                send_warning_email(audio_input=audio_input,
                                   warning_word=warning_word, line=line)


    send_success_email(input_file_list=input_file_list,
                       audioduration_list=audioduration_list,
                       workflowduration_list=workflowduration_list,
                       real_time_factor_list=real_time_factor_list,
                       warning_count=warning_count,
                       warning_word=warning_word,
                       warning_audio_inputs=warning_audio_inputs)


except Exception as e:
    print('==> The following error occured: ', e)

    send_failure_email(input_file_list=input_file_list, audio_input=audio_input,
                       warning_count=warning_count, warning_word=warning_word,
                       warning_audio_inputs=warning_audio_inputs, exception=e)


# Final message.
print('====> Overall workflow is finished. <====')
