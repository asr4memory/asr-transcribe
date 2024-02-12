# Module functions for (1) normalizing, (2) filtering, (3) denoising and (4) converting to WAV

import subprocess
from subprocess import check_output, CalledProcessError, STDOUT
import json

# This function uses the FFmpeg filter "loudnorm" to measure the loudness of an input file, to normalize it and then to convert it to WAV:
def normalize_extract_audio(audio_input, audio_output):
    # Step 1: Extracting the measured values from the first run:
    measure_cmds = [
        "/applications/ffmpeg",
        "-i",
        audio_input,
        "-filter_complex",
        "loudnorm=print_format=json",
        "-f",
        "null",
        "-"]
    try:
        output = check_output(measure_cmds, stderr=STDOUT).decode('utf8', 'ignore')
        # Searching for the start and end of the JSON part of the output:
        json_str_start = output.find('{')
        json_str_end = output.rfind('}')
        if json_str_start == -1 or json_str_end == -1:
            print("No JSON output in FFmpeg response.")
            return
    
        # Extracting the JSON string: 
        json_str = output[json_str_start:json_str_end+1]
        loudness_values = json.loads(json_str)
        print(loudness_values)
    except CalledProcessError as e:
        print("Error during loudness measurement.")
        print(e.output.decode(encoding="utf-8").strip())
        return
    except json.JSONDecodeError as e:
        print("Failed to parse JSON output from loudness measurement.")
        print("JSON Decode Error:", e)
        return

    # Step 2: Using the values in a second run with linear normalization enabled; also using filtering and denoising for audio optimizing:
    extract_cmds = [
        "/applications/ffmpeg",
        "-i",
        audio_input,
        "-filter_complex",
        f"loudnorm=measured_I={loudness_values['input_i']}:measured_TP={loudness_values['input_tp']}:measured_LRA={loudness_values['input_lra']}:measured_thresh={loudness_values['input_thresh']},highpass=f=70,lowpass=f=10000,arnndn=m=rnnoise-models-master/conjoined-burgers-2018-08-28/cb.rnnn",
        "-c:a", 
        "pcm_s24le",
        "-ar", 
        "48000",
        "-ac",
        "2",
        "-y",
        audio_output
    ]

    try:
        # Start the process with subprocess.Popen and wait until it is finished: 
        subprocess.run(extract_cmds, check=True, stderr=subprocess.PIPE)
        # After successfull normalization we do not need the normal output. 
        final_output = "Loudness normalization and conversion to WAV completed."
    except CalledProcessError as e:
        error_message = e.stderr.decode(encoding="utf-8").strip() if e.stderr else "Unknown error"
        print("Error during loudness normalization:", error_message)
        return None, None

    return final_output, loudness_values
