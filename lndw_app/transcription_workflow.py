import subprocess
import torch
import whisperx
import re
from datetime import datetime, timedelta

def transcribe_audio(input_file, output_directory, timestamp):

    # Define parameters for WhisperX model
    model_name = "large-v3"
    device = "cpu"
    batch_size = 28
    beam_size = 4
    compute_type = "float32"
    language_audio = "de"

    # Set the number of threads used by PyTorch
    number_threads = 5

    titles = {"Dr", "Prof", "Mr", "Mrs", "Ms", "Hr", "Fr", "usw", "bzw", "resp", "i.e", "e.g", "ca", "M. A", "M. Sc", "M. Eng", "B. A", "B. Sc"}

    # Compile patterns to identify titles, dates and segments without sentence-ending punctuation in transcribed text
    title_pattern = re.compile(r'\b(' + '|'.join(titles) + r')[\.,:;!\?]*$', re.IGNORECASE)
    num_pattern = re.compile(r'\b([1-9]|[12]\d|3[01])([.])$')
    non_punct_pattern = re.compile(r'[^\.\?!]$')

    torch.set_num_threads(number_threads)

    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                             input_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    audioduration_in_seconds = float(result.stdout)

    workflowduration_list = []
    workflowduration_in_seconds_list = []
    audioduration_list = []
    real_time_factor_list = []

    workflowstarttime = datetime.now()
    print(f'--> Whisper workflow for {input_file} started: {workflowstarttime}')

    torch.set_num_threads(number_threads)
    print(f'--> Number of threads: {number_threads}')

    print(f'--> Value of beam size: {beam_size}')

    # Run ffprobe command to extract duration information:
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                            input_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Get the duration of the audio file in seconds:
    audioduration_in_seconds = float(result.stdout)
    print('--> Audio Duration in seconds:', audioduration_in_seconds)

    # Convert the duration from seconds to hh:mm:ss format and print it:
    audioduration = str(timedelta(seconds=audioduration_in_seconds))
    print("--> Audio Duration in hours:minutes:seconds :", audioduration)
    audioduration_list.append(str(audioduration))

    model = whisperx.load_model(model_name, device, language=language_audio, compute_type=compute_type, asr_options={"beam_size": beam_size})
    audio = whisperx.load_audio(input_file)
    result = model.transcribe(audio, batch_size=batch_size)
    del model

    model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
    del model_a

    custom_segs = []
    sentence_buffer = ""
    start_time = None
    end_time = None

    for i, segment in enumerate(result["segments"]):
        segment_start_time = segment["start"]
        segment_end_time = segment["end"]
        sentence = segment["text"].strip()
        if title_pattern.search(sentence) or num_pattern.search(sentence) or non_punct_pattern.search(sentence):
            sentence_buffer += sentence + " "
            if start_time is None:
                start_time = segment_start_time
            end_time = segment_end_time
        else:
            if sentence_buffer:
                sentence_buffer += sentence
                end_time = segment_end_time
                custom_segs.append({"start": start_time, "end": end_time, "sentence": sentence_buffer.strip()})
                sentence_buffer = ""
                start_time = None
                end_time = None
            else:
                custom_segs.append({"start": segment_start_time, "end": segment_end_time, "sentence": sentence})
    if sentence_buffer:
        custom_segs.append({"start": start_time, "end": end_time, "sentence": sentence_buffer.strip()})

    for i in range(1, len(custom_segs)):
        if (custom_segs[i-1]["sentence"][-1] != ',') and (custom_segs[i]["sentence"][0].islower()):
            custom_segs[i]["sentence"] = custom_segs[i]["sentence"][0].upper() + custom_segs[i]["sentence"][1:]

    i = 0
    while i < len(custom_segs):
        seg = custom_segs[i]
        sentence = seg["sentence"]
        if len(sentence) > 120:
            split_point = sentence.find(',', 120)
            if split_point != -1:
                first_sentence = sentence[:split_point + 1].strip()
                second_sentence = sentence[split_point + 1:].strip()
                duration = seg["end"] - seg["start"]
                split_time = seg["start"] + duration * (len(first_sentence) / len(sentence))
                custom_segs[i] = {"start": seg["start"], "end": split_time, "sentence": first_sentence}
                custom_segs.insert(i + 1, {"start": split_time, "end": seg["end"], "sentence": second_sentence})
        i += 1

    output_file = output_directory + "/" + timestamp + "_de"
    with open(output_file + '.vtt', "w", encoding='utf-8') as vtt_file:
        vtt_file.write("WEBVTT\n\n")
        for i, seg in enumerate(custom_segs):
            start_time = datetime.utcfromtimestamp(seg["start"]).strftime('%H:%M:%S.%f')[:-3]
            end_time = datetime.utcfromtimestamp(seg["end"]).strftime('%H:%M:%S.%f')[:-3]
            vtt_file.write(f"{i+1}\n")
            vtt_file.write(f"{start_time} --> {end_time}\n")
            vtt_file.write(f"{seg['sentence']}\n\n")

    with open(output_file + '.txt', "w", encoding='utf-8') as txt_file:
        for seg in custom_segs:
            if "sentence" in seg:
                txt_file.write(f"{seg['sentence']}\n")

    # These lines print the time of the workflow end:
    workflowendtime = datetime.now()
    print(f'--> Whisper workflow completed for {input_file}: {workflowendtime}')

    # Calculate the duration of the workflow:
    workflowduration = workflowendtime - workflowstarttime
    print(f'==> Whisper workflow duration for transcribing the file {input_file}: {workflowduration}')
    workflowduration_list.append(str(workflowduration))

    # Assume workflowduration is a datetime.timedelta object and print the duration in seconds:
    workflowduration_in_seconds = workflowduration.total_seconds()
    print(f"==> Whisper workflow duration for transcribing the file {input_file}:", workflowduration_in_seconds)
    workflowduration_in_seconds_list.append(str(workflowduration_in_seconds))

    # Calculate the real time factor for processing an audio file, i.e. the ratio of workflowduration_in_seconds to audioduration_in_seconds:
    real_time_factor = workflowduration_in_seconds / audioduration_in_seconds
    print("==> Whisper real time factor - the ratio of workflow duration compared to audio duration:", real_time_factor)
    real_time_factor_list.append(str(real_time_factor))

    print('==> The Whisper workflow is completed. <==')