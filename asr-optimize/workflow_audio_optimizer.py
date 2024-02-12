# One workflow script for checking and optimizing audio tracks in video files using FFmpeg and FFprobe.
# Separate workflow modules for: checking/verifing, WAV-conversion & -normalizing & filtering, (enhancing,) emailing

import os
import re
from typing import List, Tuple, Any

from module_input_verifying import check_audiotrack, verifyInputFile, probeInputFile, getProbeScore
from module_wav_conversion_normalizing import normalize_extract_audio

# Audio Check Workflow:
input_path = '/Users/ahenderson/Documents/Whisper_Test_Files/_input/'
exclusions = (".DS_Store", "backup", "_test_", "_", "_test", ".")

# Pre-compile regular expressions
probe_score_regex = re.compile(r"probe_score=([^\n]+)")

# Initialization of the lists at the beginning of the script:
loudnorm_list: List[Tuple[str, Any]] = []
failed_files_list = []

for root, directories, files in os.walk(input_path):
    for audio_input in files:
        if any(audio_input.endswith(ext) or audio_input.startswith(ext) for ext in exclusions):
            continue

        full_path = os.path.join(root, audio_input)
        
        if check_audiotrack(full_path):
            print(f"======> The input file contains an audio track: {audio_input}")
            video_verifier = verifyInputFile(full_path)
            if "Conversion failed" in video_verifier or "Packet corrupt" in video_verifier:
                failed_files_list.append((full_path, "Conversion failed or packet corrupt"))
                continue

            video_prober = probeInputFile(full_path)
            if "Invalid" in video_prober:
                failed_files_list.append((full_path, "Contains INVALID AV DATA according to FFprobe"))
                continue

            video_probescore = getProbeScore(full_path)
            match = probe_score_regex.search(video_probescore)
            if match:
                video_probescore_final = re.sub(r"[^a-zA-Z0-9]", "", match.group(1))
                if int(video_probescore_final) < 25:
                    failed_files_list.append((full_path, "Low FFprobe score"))
                    continue

                print(f"======> This input file is valid and will be converted by FFmpeg: {full_path}, Probe-Score: {video_probescore_final}")
                audio_output = full_path.rsplit('.', 1)[0] + "_audio-optimized.wav"
                wav_converter, loudness_values = normalize_extract_audio(full_path, audio_output)
                if loudness_values:
                    loudnorm_list.append((full_path, loudness_values))
                
                    # After the WAV file has been normalized and extracted, the module_xxx function is called with the path of the WAV file:
                    #module_xxx(audio_input, audio_output) # This is an optinaml module to be use for speech enhancing in future.

            else:
                failed_files_list.append((full_path, "Unable to determine the FFprobe score"))
        else:
            failed_files_list.append((full_path, "No audio track"))

# After all files have been processed, display the collected loudness values:
print("\n======> Summary of loudness values for converted files:")
for file_path, loudness_values in loudnorm_list:
    print(f"Input File: {file_path}")
    print("Loudness Values:")
    for key, value in loudness_values.items():
        print(f"  {key}: {value}")
    print() # Empty line for readability

# Summary of files that have not been converted:
print("\n======> List of files that have not met the conditions:")
for file_path, reason in failed_files_list:
    print(f"Input File: {file_path} - Reason: {reason}")

