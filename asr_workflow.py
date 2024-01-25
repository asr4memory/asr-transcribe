"""
ASR workflow script.
This is the main script that runs the ASR and alignment processes and sends
emails.
"""
import whisperx
from datetime import datetime, timedelta
import re
import os
import torch

from email_notifications import send_success_email, send_failure_email, send_warning_email
from app_config import get_config
from utilities import ignore_file, Tee, write_text_file, write_csv_file, write_csv_speaker_file, write_vtt_file, audio_duration
from alignment import align_segments

# The following lines are to capture the stdout/terminal output
import sys

# Save a reference to the original stdout and stderr
original_stdout = sys.stdout
original_stderr = sys.stderr

# Redirect stdout and stderr to the buffer
stdout_buffer = Tee(original_stdout)
stderr_buffer = Tee(original_stderr)
sys.stdout = stdout_buffer
sys.stderr = stderr_buffer

config = get_config()

# Set the number of threads used by PyTorch
number_threads = config['whisper']['thread_count']

# Define parameters for WhisperX model
model_name = config['whisper']['model']
device = config['whisper']['device']
batch_size = config['whisper']['batch_size']
beam_size = config['whisper']['beam_size']
compute_type = config['whisper']['compute_type']
language_audio = config['whisper']['language']
initial_prompt = config['whisper']['initial_prompt']

# Define input und output folders
input_path = config['system']['input_path']
output_path = config['system']['output_path']
input_directory = os.listdir(path=input_path)
output_directory = os.path.dirname(output_path)
filename_suffix = "_" + language_audio # Filename suffix corresponds to the variable "language_audio" above.

input_file_list = []
workflowduration_list = []
workflowduration_in_seconds_list = []
audioduration_list = []
real_time_factor_list = []

warning_count = 0
warning_audio_inputs = []

torch.set_num_threads(number_threads)
print(f'--> Number of threads: {number_threads}')

try:
    # Load WhisperX model
    model = whisperx.load_model(model_name, device, language=language_audio, compute_type=compute_type, asr_options={"beam_size": beam_size}) # WITHOUT  "initial_prompt": initial_prompt
    #model = whisperx.load_model(model_name, device, language=language_audio, compute_type=compute_type, asr_options={"beam_size": beam_size, "initial_prompt": initial_prompt}) # WITH  "initial_prompt": initial_prompt

    # This loop iterates over all the files in the input directory and
    # transcribes them using the specified model.
    for root, directories, files in os.walk(input_path):
        for audio_input in files:
            if ignore_file(audio_input): continue

            input_file_list.append(audio_input)
            audio_file = os.path.join(input_path, audio_input)
            output_file = os.path.join(output_directory, audio_input.split(".")[0] + filename_suffix)
            workflowstarttime = datetime.now()
            print(f'--> Whisper workflow for {audio_input} started: {workflowstarttime}')

            print(f'--> Value of beam size: {beam_size}')

            audioduration_in_seconds = audio_duration(audio_file)
            print('--> Audio Duration in seconds:', audioduration_in_seconds)

            # Convert the duration from seconds to hh:mm:ss format and print it:
            audioduration = str(timedelta(seconds=audioduration_in_seconds))
            print("--> Audio Duration in hours:minutes:seconds :", audioduration)
            audioduration_list.append(str(audioduration))

            # Load audio file and transcribe it
            audio = whisperx.load_audio(audio_file)
            result = model.transcribe(audio, batch_size=batch_size)

            # Align transcribed segments to original audio and get time stamps
            # for start and end of each segment.
            model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device) # With default align model
            #model_a, metadata = whisperx.load_align_model(model_name="WAV2VEC2_ASR_LARGE_LV60K_960H",language_code=result["language"], device=device) # WITH greater align model which uses more computing ressources.
            result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)

            custom_segs = align_segments(result['segments'])

            write_vtt_file(output_file=output_file, custom_segs=custom_segs)
            write_text_file(output_file=output_file, custom_segs=custom_segs)
            write_csv_file(output_file=output_file, custom_segs=custom_segs)
            write_csv_speaker_file(output_file=output_file, custom_segs=custom_segs)

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
            real_time_factor = workflowduration_in_seconds / audioduration_in_seconds
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
            warning_word = "failed" # Goal is to find the message "failed to align segment" in the stdout/terminal output to identify AI hallucinations.
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
                       warning_audio_inputs=warning_audio_inputs)


# Final message.
print('====> Overall workflow is finished. <====')
