"""
Simple whisper-only ASR for testing.
"""
import whisperx
from datetime import datetime, timedelta
import os
import torch

from app_config import get_config
from utilities import ignore_file, audio_duration
from whisper_tools import get_transcription_model, get_alignment_model

config = get_config()

# Set the number of threads used by PyTorch
number_threads = config['whisper']['thread_count']

# Define parameters for WhisperX model
device = config['whisper']['device']
batch_size = config['whisper']['batch_size']
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

model = get_transcription_model()

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

        torch.set_num_threads(number_threads)

        audioduration_in_seconds = audio_duration(audio_file)
        print('--> Audio Duration in seconds:', audioduration_in_seconds)

        # Convert the duration from seconds to hh:mm:ss format and print it:
        audioduration = str(timedelta(seconds=audioduration_in_seconds))
        audioduration_list.append(str(audioduration))

        # Load audio file and transcribe it
        audio = whisperx.load_audio(audio_file)
        transcription_result = model.transcribe(audio, batch_size=batch_size)

        # Align transcribed segments to original audio and get time stamps
        # for start and end of each segment.
        model_a, metadata = get_alignment_model(transcription_result["language"])
        alignment_result = whisperx.align(transcription_result["segments"],
                                          model_a,
                                          metadata,
                                          audio,
                                          device,
                                          return_char_alignments=False)

        print(transcription_result)
