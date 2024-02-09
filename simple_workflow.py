"""
Simple whisper-only ASR for testing.
"""
from datetime import datetime
import os
from app_config import get_config
from utilities import ignore_file
from whisper_tools import get_audio, transcribe, align, get_audio_length

config = get_config()

language_audio = config['whisper']['language']

# Define input und output folders
input_path = config['system']['input_path']
output_path = config['system']['output_path']
input_directory = os.listdir(path=input_path)
output_directory = os.path.dirname(output_path)
 # Filename suffix corresponds to the variable "language_audio" above.
filename_suffix = "_" + language_audio

warning_count = 0
warning_audio_inputs = []

# This loop iterates over all the files in the input directory and
# transcribes them using the specified model.
for root, directories, files in os.walk(input_path):
    for audio_input in files:
        if ignore_file(audio_input): continue

        input_file_list.append(audio_input)
        audio_file = input_path + audio_input
        output_file = output_directory + "/" + audio_input.split(".")[0] + filename_suffix
        workflowstarttime = datetime.now()
        print(f'--> Whisper workflow for {audio_input} started: {workflowstarttime}')

        # Main part: Loading, transcription and alignment.
        audio = get_audio(path=audio_file)

        duration, formatted_duration = get_audio_length(audio)
        audioduration_list.append(formatted_duration)
        print('--> Audio duration: %s (%.1fs)' % (formatted_duration, duration))

        transcription_result = transcribe(audio)
        alignment_result = align(audio=audio,
                                 segments=transcription_result['segments'],
                                 language=transcription_result['language'])

        print(transcription_result)
