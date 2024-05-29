# Notice: Works only from WhisperX vs. 3.1.1 (https://github.com/m-bain/whisperX)
# Done/Fixed: 
    # Avoids misinterpreting titles and dates as sentence endings.
    # Merges segments that do not have punctuation with the following segments.
    # Splits segments longer than 120 characters at the next comma.
    # Changes the lowercase letter of the first word of the segment to an uppercase letter (only in cases where the previous segment ends without a comma).
    # Enables word lists for names, special terms or filler words.
    # Embeds the code into an automated input/output folder workflow.
    # Calculates audio duration, workflow duration and real time factor for transcribing an audio file.
    # To speed up processing, it is possible to change the calculation type to "int8" and the beam size to 4 or less (default = 5), but there is a risk of quality loss. 
    # Sends an success or failed email if the workflow is (not) completed successfully. 
    # Captures the stdout/terminal output and sends an email if the word "failed" is found in the output.


# Import essential libraries
import whisperx
from datetime import datetime, timedelta
import re
import os
import subprocess
import torch

# Import translation libraries
import os
import glob
import wave
from transformers import MarianMTModel, MarianTokenizer

# Import llm library
from mlx_lm import load, generate

# Import text-to-speech library
from TTS.api import TTS

# # Import Suno.ai bark libraries

# from bark import SAMPLE_RATE, generate_audio, preload_models
# from scipy.io.wavfile import write as write_wav
# from IPython.display import Audio

# The following lines are to capture the stdout/terminal output
import sys
import io

class Tee(io.StringIO):
    def __init__(self, terminal):
        self.terminal = terminal
        super().__init__()

    def write(self, message):
        self.terminal.write(message)
        super().write(message)

# Save a reference to the original stdout and stderr
original_stdout = sys.stdout
original_stderr = sys.stderr

# Redirect stdout and stderr to the buffer
stdout_buffer = Tee(original_stdout)
stderr_buffer = Tee(original_stderr)
sys.stdout = stdout_buffer
sys.stderr = stdout_buffer


# Set the number of threads used by PyTorch
number_threads = 5 # the value 5 is default and recommended concerning the accuracy of the model. 

# Define parameters for WhisperX model
model_name = "large-v3"
device = "cpu"
#print("Using device:", device)
batch_size = 28 # The value 28 is the optimal batch size for CPU on Mac Studio 2022 Apple M1 Max 10 CPU 64 GB RAM
beam_size = 4 # The value 5 is default and recommended concerning the accuracy of the model. 
compute_type = "float32"
language_audio = "de" # Set this option to None (without quotation marks) if automatic language detection should be enabled.

initial_prompt = "example prompt" # Add filler words: "äh ähm ah oh aja aha ja" ATTENTION: This ASR option may lead to omissions in the transcript.

# Define set of titles and abbreviations that should not be treated as sentence endings
titles = {"Dr", "Prof", "Mr", "Mrs", "Ms", "Hr", "Fr", "usw", "bzw", "resp", "i.e", "e.g", "ca", "M. A", "M. Sc", "M. Eng", "B. A", "B. Sc"}

# Compile patterns to identify titles, dates and segments without sentence-ending punctuation in transcribed text
title_pattern = re.compile(r'\b(' + '|'.join(titles) + r')[\.,:;!\?]*$', re.IGNORECASE)
num_pattern = re.compile(r'\b([1-9]|[12]\d|3[01])([.])$')
non_punct_pattern = re.compile(r'[^\.\?!]$')

# Define input und output folders
input_path = '/Users/peterkompiel/python_scripts/asr4memory/processing_files/lndw-pipeline/_input/'
input_directory = os.listdir(path=input_path)
output_directory = os.path.dirname('/Users/peterkompiel/python_scripts/asr4memory/processing_files/lndw-pipeline/_output/')
filename_suffix = "_" + language_audio # Filename suffix corresponds to the variable "language_audio" above.
#filename_suffix = "_de" # Optional: Add a filename suffix to the output files, e.g. "_beam5_threads5_batch28_noinitialprompt" 

input_file_list = []
workflowduration_list = []
workflowduration_in_seconds_list = []
audioduration_list = []
real_time_factor_list = []

warning_count = 0
warning_audio_inputs = []

try:
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
            if audio_input.startswith("."):
                continue
            
            full_audio_path = os.path.join(root, audio_input)
            #print(full_audio_path)

            # Check if the file contains an audio track:
            #if check_audiotrack(full_audio_path):
            #    print("The file contains an audio track.")
            #else:
            #    print("The file does not contain an audio track.")
            #    sys.exit('==> The script is aborted because the input file does not contain an audio track: ' + str(audio_input)) # If a video does not contain an audio track, the script is aborted.

            # Create the extended audio file by concatenating the input file four times
            extended_audio_file = os.path.join(output_directory, f"extended_{audio_input}")
            subprocess.run([
                "ffmpeg", "-y", "-i", full_audio_path,
                "-filter_complex", "[0:a][0:a][0:a][0:a]concat=n=4:v=0:a=1[out]",
                "-map", "[out]", extended_audio_file
            ])

            # Get the input file path for further processing
            audio_file = full_audio_path

            # This line uses regular expression matching to check if the file name starts with a period followed by an underscore. If it does, the loop skips that file and moves on to the next one:
            #m = re.match(r"._", audio_input)
            #äif m != None:
            #    continue
            input_file_list.append(audio_input)
            output_file = output_directory + "/" + audio_input.split(".")[0] + filename_suffix
            workflowstarttime = datetime.now()
            print(f'--> Whisper workflow for {audio_input} started: {workflowstarttime}')

            torch.set_num_threads(number_threads)
            print(f'--> Number of threads: {number_threads}')

            print(f'--> Value of beam size: {beam_size}')

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
            audioduration_list.append(str(audioduration))

            # Load WhisperX model, audio file and transcribe it in German
            model = whisperx.load_model(model_name, device, language=language_audio, compute_type=compute_type, asr_options={"beam_size": beam_size}) # WITHOUT  "initial_prompt": initial_prompt
            #model = whisperx.load_model(model_name, device, language=language_audio, compute_type=compute_type, asr_options={"beam_size": beam_size, "initial_prompt": initial_prompt}) # WITH  "initial_prompt": initial_prompt
            audio = whisperx.load_audio(audio_file)
            result = model.transcribe(audio, batch_size=batch_size)

            # Align transcribed segments to original audio and get time stamps for start and end of each segment
            model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device) # With default align model
            #model_a, metadata = whisperx.load_align_model(model_name="WAV2VEC2_ASR_LARGE_LV60K_960H",language_code=result["language"], device=device) # WITH greater align model which uses more computing ressources.
            result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)

            # Initialize processing variables
            custom_segs = []
            sentence_buffer = ""
            start_time = None
            end_time = None

            # Iterate through each transcribed segment
            for i, segment in enumerate(result["segments"]):
                segment_start_time = segment["start"]
                segment_end_time = segment["end"]
                sentence = segment["text"].strip()
                # Check if sentence needs to be buffered (ends with title, number, or without punctuation)
                if title_pattern.search(sentence) or num_pattern.search(sentence) or non_punct_pattern.search(sentence):
                    sentence_buffer += sentence + " "
                    if start_time is None:
                        start_time = segment_start_time
                    end_time = segment_end_time
                else:
                    # Handle sentence completion or standalone sentences
                    if sentence_buffer:
                        sentence_buffer += sentence
                        end_time = segment_end_time
                        custom_segs.append({"start": start_time, "end": end_time, "sentence": sentence_buffer.strip()})
                        sentence_buffer = ""
                        start_time = None
                        end_time = None
                    else:
                        custom_segs.append({"start": segment_start_time, "end": segment_end_time, "sentence": sentence})
            # Add any remaining buffered sentence to the segments list
            if sentence_buffer:
                custom_segs.append({"start": start_time, "end": end_time, "sentence": sentence_buffer.strip()})

            # Check if first letter of segment's sentence needs to be changed to uppercase
            for i in range(1, len(custom_segs)):
                if (custom_segs[i-1]["sentence"][-1] != ',') and (custom_segs[i]["sentence"][0].islower()):
                    custom_segs[i]["sentence"] = custom_segs[i]["sentence"][0].upper() + custom_segs[i]["sentence"][1:]

            # Start of loop to check for sentences that are longer than 120 characters
            i = 0
            while i < len(custom_segs):
                seg = custom_segs[i]
                sentence = seg["sentence"]
                # If sentence is longer than 120 characters, find the position of the next comma after the 120th character
                if len(sentence) > 120:
                    split_point = sentence.find(',', 120)
                    # If a comma is found, split the sentence at this point and trim any leading/trailing whitespace
                    if split_point != -1:
                        first_sentence = sentence[:split_point + 1].strip()
                        second_sentence = sentence[split_point + 1:].strip()
                        # Calculate duration of the segment and find the time point to split the segment
                        duration = seg["end"] - seg["start"]
                        split_time = seg["start"] + duration * (len(first_sentence) / len(sentence))
                        # Replace the original segment with the first part and insert the second part after it
                        custom_segs[i] = {"start": seg["start"], "end": split_time, "sentence": first_sentence}
                        custom_segs.insert(i + 1, {"start": split_time, "end": seg["end"], "sentence": second_sentence})
                i += 1

            # Write the processed segments to a .vtt file
            # This file will contain the start and end times of each segment along with the transcribed text
            with open(output_file + '.vtt', "w", encoding='utf-8') as vtt_file:
                vtt_file.write("WEBVTT\n\n")
                for i, seg in enumerate(custom_segs):
                    start_time = datetime.utcfromtimestamp(seg["start"]).strftime('%H:%M:%S.%f')[:-3]
                    end_time = datetime.utcfromtimestamp(seg["end"]).strftime('%H:%M:%S.%f')[:-3]
                    vtt_file.write(f"{i+1}\n")
                    vtt_file.write(f"{start_time} --> {end_time}\n")
                    vtt_file.write(f"{seg['sentence']}\n\n")

            # Write the processed segments to a .txt file
            # This file will contain only the transcribed text of each segment
            with open(output_file + '.txt', "w", encoding='utf-8') as txt_file:
                for seg in custom_segs:
                    if "sentence" in seg:
                        txt_file.write(f"{seg['sentence']}\n")

            # These lines print the time of the workflow end:
            workflowendtime = datetime.now()
            print(f'--> Whisper workflow completed for {audio_input}: {workflowendtime}')

            # Calculate the duration of the workflow:
            workflowduration = workflowendtime - workflowstarttime
            print(f'==> Whisper workflow duration for transcribing the file {audio_input}: {workflowduration}')
            workflowduration_list.append(str(workflowduration))

            # Assume workflowduration is a datetime.timedelta object and print the duration in seconds:
            workflowduration_in_seconds = workflowduration.total_seconds()
            print(f"==> Whisper workflow duration for transcribing the file {audio_input}:", workflowduration_in_seconds)
            workflowduration_in_seconds_list.append(str(workflowduration_in_seconds))

            # Calculate the real time factor for processing an audio file, i.e. the ratio of workflowduration_in_seconds to audioduration_in_seconds:
            real_time_factor = workflowduration_in_seconds / audioduration_in_seconds
            print("==> Whisper real time factor - the ratio of workflow duration compared to audio duration:", real_time_factor)
            real_time_factor_list.append(str(real_time_factor))

finally: 
    print('==> The Whisper workflow is completed. <==')


############################################################################################################
# Start of the translation part

# Funktion zur Übersetzung eines Textes ins Englische
def translate_to_en(text, num_beams):
    return translate_text(text, "Helsinki-NLP/opus-mt-de-en", num_beams)

# Funktion zur Übersetzung eines Textes ins Spanische
def translate_to_es(text, num_beams):
    return translate_text(text, "Helsinki-NLP/opus-mt-en-es", num_beams)

# Funktion zur Übersetzung eines Textes ins Deutsche
def translate_to_de(text, num_beams):
    return translate_text(text, "Helsinki-NLP/opus-mt-es-de", num_beams)

# Allgemeine Funktion zur Übersetzung eines Textes
def translate_text(text, model_name, num_beams):
    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)
    encoded_text = tokenizer(text, return_tensors="pt", padding=True)
    translated_tokens = model.generate(**encoded_text, num_beams=num_beams)
    translated_text = tokenizer.decode(translated_tokens[0], skip_special_tokens=True)
    return translated_text

# Funktion zum Verarbeiten der VTT-Dateien in einem Verzeichnis
def process_vtt_file(input_dir, output_dir, translate_funcs, lang_codes, num_beams):
    os.makedirs(output_dir, exist_ok=True)
    processed_files = {}

    for vtt_file_path in glob.glob(os.path.join(input_dir, '*_de.vtt')):
        print(f"Verarbeite VTT-Datei: {vtt_file_path}")

        with open(vtt_file_path, 'r', encoding='utf-8') as vtt_file:
            vtt_lines = vtt_file.readlines()

        # Entferne die erste "WEBVTT" Zeile und die erste Leerzeile
        if vtt_lines[0].strip() == "WEBVTT":
            vtt_lines = vtt_lines[1:]
        if vtt_lines[0].strip() == "":
            vtt_lines = vtt_lines[1:]

        segments = []
        current_segment = []

        for line in vtt_lines:
            if line.strip() == "" and current_segment:
                segments.append(current_segment)
                current_segment = []
            else:
                current_segment.append(line)
        if current_segment:
            segments.append(current_segment)

        intermediate_translations = [segment[2].strip() for segment in segments if len(segment) > 2]

        # Speichere die Originaldatei
        original_file_path = os.path.join(output_dir, os.path.basename(vtt_file_path))
        with open(original_file_path, 'w', encoding='utf-8') as output_file:
            output_file.writelines(["WEBVTT\n\n"] + vtt_lines)
        processed_files['de'] = original_file_path

        for translate_func, lang_code in zip(translate_funcs, lang_codes):
            output_translations = []
            translated_lines = ["WEBVTT\n\n"]  # Initialize only once per output file
            for segment, translation in zip(segments, intermediate_translations):
                translated_lines.extend(segment[:2])
                translated_text = translate_func(translation, num_beams)
                output_translations.append(translated_text)
                translated_lines.append(translated_text + '\n\n')

            output_file_path = os.path.join(output_dir, os.path.basename(vtt_file_path).replace('_de.vtt', f'_{lang_code}.vtt'))
            with open(output_file_path, 'w', encoding='utf-8') as output_file:
                output_file.writelines(translated_lines)

            print(f"Die bearbeitete Datei wurde gespeichert unter: {output_file_path}")
            intermediate_translations = output_translations
            processed_files[lang_code] = output_file_path

    return processed_files

# Funktion zur Anpassung der Timecodes
def adjust_timecodes(vtt_lines, start_offset):
    adjusted_lines = []
    for line in vtt_lines:
        if '-->' in line:
            start_time, end_time = line.split(' --> ')
            new_start_time = adjust_time(start_time.strip(), start_offset)
            new_end_time = adjust_time(end_time.strip(), start_offset)
            adjusted_lines.append(f"{new_start_time} --> {new_end_time}\n")
        else:
            adjusted_lines.append(line)
    return adjusted_lines

def adjust_time(time_str, offset):
    h, m, s = map(float, time_str.split(':'))
    total_seconds = h * 3600 + m * 60 + s + offset
    new_h = int(total_seconds // 3600)
    new_m = int((total_seconds % 3600) // 60)
    new_s = total_seconds % 60
    return f"{new_h:02}:{new_m:02}:{new_s:06.3f}"

# Funktion zur Erstellung der kombinierten VTT-Datei mit fortlaufenden Segmentnummern
def create_combined_vtt(input_dir, output_dir, processed_files):
    # Suchen der WAV-Datei
    wav_files = glob.glob(os.path.join(input_dir, '*.wav'))
    if not wav_files:
        raise FileNotFoundError("Keine WAV-Datei im Eingabeverzeichnis gefunden.")
    audio_file = wav_files[0]
    audio_base_name = os.path.splitext(os.path.basename(audio_file))[0]
    
    # Berechne die Dauer der Audiodatei
    with wave.open(audio_file, 'r') as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        duration = frames / float(rate)
    segment_duration = duration / 4

    combined_lines = ["WEBVTT\n\n"]
    file_order = ['de', 'en', 'es', 'de_final']
    segment_counter = 1
    
    for i, lang_code in enumerate(file_order):
        file_path = processed_files.get(lang_code)
        if not file_path:
            raise FileNotFoundError(f"Die Datei für {lang_code} wurde nicht gefunden.")
        with open(file_path, 'r', encoding='utf-8') as vtt_file:
            vtt_lines = vtt_file.readlines()[1:]  # Entferne "WEBVTT"
            if i > 0:
                start_offset = segment_duration * i
                vtt_lines = adjust_timecodes(vtt_lines, start_offset)
            
            for line in vtt_lines:
                if line.strip().isdigit():
                    combined_lines.append(f"{segment_counter}\n")
                    segment_counter += 1
                else:
                    combined_lines.append(line)
            combined_lines.append('\n')

    combined_output_file = os.path.join(output_dir, f'{audio_base_name}.vtt')
    with open(combined_output_file, 'w', encoding='utf-8') as output_file:
        output_file.writelines(combined_lines)
    
    print(f"Die kombinierte Datei wurde gespeichert unter: {combined_output_file}")

# Pfade zum Eingabe- und Ausgabeverzeichnis
output_dir = '/Users/peterkompiel/python_scripts/asr4memory/processing_files/lndw-pipeline/_output/'
input_dir = output_dir
num_beams = 2

# Liste der Übersetzungsfunktionen und der entsprechenden Sprachcodes
translate_funcs = [translate_to_en, translate_to_es, translate_to_de]
lang_codes = ["en", "es", "de_final"]

# Verarbeite die VTT-Dateien für die mehrfache Übersetzung und erhalte die Liste der erstellten Dateien
processed_files = process_vtt_file(input_dir, output_dir, translate_funcs, lang_codes, num_beams)

# Erstelle die kombinierte VTT-Datei mit fortlaufenden Segmentnummern
create_combined_vtt(input_dir, output_dir, processed_files)

print('====> Translation workflow is finished. <====')

############################################################################################################
# Start of the LLM part

for txt_file_path in glob.glob(os.path.join(input_dir, '*.txt')):
    print(f"Verarbeite TXT-Datei: {txt_file_path}")

    with open(txt_file_path, 'r', encoding='utf-8') as txt_file:
        transcript = txt_file.read()

    transcript = transcript.strip()

    prompt = f"Erstelle auf Basis des folgenden Texts nach dem Doppelpunkt einen Rapsong, der sich an 13-jährige in Berlin richtet:\n'{transcript}'"

    llm_model, llm_tokenizer = load("mlx-community/Mixtral-8x7B-Instruct-v0.1-4bit")
    response = generate(llm_model, llm_tokenizer, prompt=prompt, verbose=True, max_tokens=1000, temp=1)  

    response = response.strip()
   
    # llm_model, llm_tokenizer = load("mlx-community/Mixtral-8x22B-Instruct-v0.1-4bit")
    # response = generate(llm_model, llm_tokenizer, prompt=prompt, verbose=True, max_tokens=1000)

    transcribed_txt_file_path = txt_file_path.replace('.txt', '_llm.txt')
    with open(transcribed_txt_file_path, 'w', encoding='utf-8') as transcribed_txt_file:
        transcribed_txt_file.write(response)  

    print(f"Die bearbeitete Datei wurde gespeichert unter: {transcribed_txt_file_path}") 

    print('====> LLM workflow is finished. <====')

############################################################################################################
# Start text-to-speech part

# Init TTS with the target model name
tts = TTS(model_name="tts_models/de/thorsten/tacotron2-DDC", progress_bar=False).to(device)

for llm_txt_file_path in glob.glob(os.path.join(input_dir, '*_llm.txt')):
    print(f"Verarbeite TXT-Datei: {txt_file_path}")

    with open(llm_txt_file_path, 'r', encoding='utf-8') as llm_txt_file:
        llm_transcript = llm_txt_file.read()
    
    text_to_speech_file_path = llm_txt_file_path.replace('.txt', '.wav')

    # Run TTS
    tts.tts_to_file(text=llm_transcript, file_path=text_to_speech_file_path)

    print(f"Die bearbeitete Datei wurde gespeichert unter: {text_to_speech_file_path}") 

    print('====> Text-to-Speech workflow is finished. <====')

############################################################################################################
# # Alternative text-to-speech part using Suno.ai bark

# # download and load all models
# preload_models()

# for llm_txt_file_path in glob.glob(os.path.join(input_dir, '*_llm.txt')):
#     print(f"Verarbeite TXT-Datei: {llm_txt_file_path}")

#     with open(llm_txt_file_path, 'r', encoding='utf-8') as llm_txt_file:
#        llm_transcript = llm_txt_file.read()
    
#     llm_transcript_music = f"♪{llm_transcript}♪"

#     print(llm_transcript_music)

#     text_to_speech_file_path = llm_txt_file_path.replace('.txt', '.wav')

#     audio_array = generate_audio(llm_transcript_music)

#     # save audio to disk
#     write_wav(text_to_speech_file_path, SAMPLE_RATE, audio_array)

# Print the final message that workflow is finished:
print('====> Overall workflow is finished. <====')