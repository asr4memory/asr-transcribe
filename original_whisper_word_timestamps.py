# Import essential libraries
import whisper
from whisper.utils import get_writer
from datetime import datetime, timedelta
import re
import os
import subprocess
import json
import pandas as pd

# Define parameters for WhisperX model
model_name = "large-v3"
device = "cpu"
language = "de"
# initial_prompt = "Oral History Interview Freie Universität Berlin Cord Pagenstecher Almut Leh" # Add filler words: "äh ähm ah oh aja aha ja" ATTENTION: This ASR option may lead to omissions in the transcript.
word_timestamps = True

# Define input und output folders
input_path = 'data/input/'
input_directory = os.listdir(path=input_path)
output_directory = os.path.dirname('data/output/')
filename_suffix = "" # Optional: Add a filename suffix to the output files, e.g. "_beam5_threads5_batch28_noinitialprompt" 

# This loop iterates over all the files in the input directory and transcribes them using the specified model:
for root, directories, files in os.walk(input_path): 
    for audio_input in files:
        if audio_input.endswith(".DS_Store"):
            continue
        if audio_input.endswith("backup"):
            continue
        if audio_input.endswith("_test_"):
            continue
        if audio_input.startswith("_"):
            continue
        if audio_input.startswith("_test"):
            continue
        # This line uses regular expression matching to check if the file name starts with a period followed by an underscore. If it does, the loop skips that file and moves on to the next one:
        m = re.match(r"._", audio_input)
        if m != None:
            continue
        audio_file = input_path + audio_input
        output_file = output_directory + "/" + audio_input.split(".")[0] + filename_suffix
        workflowstarttime = datetime.now()
        print(f'--> Whisper workflow for {audio_input} started: {workflowstarttime}')

        #torch.set_num_threads(number_threads)
        #print(f'--> Number of threads: {number_threads}')

        # print(f'--> Value of beam size: {beam_size}')

        # Run ffprobe command to extract duration information:
        result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                                audio_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Get the duration of the audio file in seconds:
        audioduration_in_seconds = float(result.stdout)
        print('--> Audio Duration in seconds:', audioduration_in_seconds)

        # Convert the duration from seconds to hh:mm:ss format and print it:
        audioduration = str(timedelta(seconds=audioduration_in_seconds))
        print("--> Audio Duration in hours:minutes:seconds :", audioduration)

        # Load Whisper model, audio file and transcribe it
        model = whisper.load_model(model_name, device, language)
        audio = whisper.load_audio(audio_file)
        result = model.transcribe(audio, word_timestamps=word_timestamps)

        # print(result)
        # print(result["text"])

        # Write all output formats
        word_options = {
        "highlight_words": True,
        #"max_line_count": 50,
        #"max_line_width": 3
        }
        all_writer = get_writer("all", output_directory)
        all_writer(result, audio_file, word_options)

        # Extract word segments
        words_info = []
        for segment in result['segments']:
            for word in segment['words']:
                word_data = {
                    "word": word.get("word"),
                    "start": word.get("start"),
                    "end": word.get("end"),
                "probability": word.get("probability")
                }
                words_info.append(word_data)
        
        print(words_info)

        # Save extracted word segments in a JSON and CSV file
        with open(output_file + '_word_timestamps.json', 'w', encoding='utf-8') as json_file:
            json.dump(words_info, json_file, ensure_ascii=False, indent=4)

        # Remove puctuation
        df = pd.DataFrame(words_info)
        df["word"] = df["word"].str.strip().str.replace(r'[^\w\s]', '', regex=True)

        # Convert start and end time codes to hh:mm:ss:ms format
        def convert_to_hh_mm_ss_ms(time_in_seconds):
            hours, remainder = divmod(time_in_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            milliseconds = int((seconds - int(seconds)) * 1000)
            return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}:{milliseconds:03}"
        
        df['start'] = df['start'].apply(convert_to_hh_mm_ss_ms)
        df['end'] = df['end'].apply(convert_to_hh_mm_ss_ms)

        # Save converted word segements in tab separated CSV file
        df.to_csv(output_file + '_word_timestamps_ms.csv', index=False, encoding="utf-8", sep='\t')

        # These lines prints the time of the workflow end:
        workflowendtime = datetime.now()
        print(f'--> Whisper workflow completed for {audio_input}: {workflowendtime}')

        # Calculate the duration of the workflow:
        workflowduration = workflowendtime - workflowstarttime
        print(f'==> Whisper workflow duration for transcribing the file {audio_input}: {workflowduration}')

        # Assume workflowduration is a datetime.timedelta object and print the duration in seconds:
        workflowduration_in_seconds = workflowduration.total_seconds()
        print(f"==> Whisper workflow duration for transcribing the file {audio_input}:", workflowduration_in_seconds)

        # Calculate the real time factor for processing an audio file, i.e. the ratio of workflowduration_in_seconds to audioduration_in_seconds:
        real_time_factor = workflowduration_in_seconds / audioduration_in_seconds
        print("==> Whisper real time factor - the ratio of workflow duration compared to audio duration:", real_time_factor)

        # Print the final message that workflow is finished:
        print('====> Overall workflow is finished. <====' )