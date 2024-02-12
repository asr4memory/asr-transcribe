# Module functions for verifying input file: (1) check audio track, (2) verify input file, (3) check loglevel, (4) check probe score

import subprocess
from subprocess import check_output, CalledProcessError, STDOUT

# Check if the input file contains an audio track:
def check_audiotrack(audio_input):
    command = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=codec_name",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_input
    ]
    # Execute the command and record the output:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # Check whether the output is empty:
    return len(result.stdout) > 0 # True if there's an output, indicating an audio track; False if there's no output, indicating no audio track.    

# Check if the input file can be converted by FFmpeg:
def verifyInputFile(audio_input):
    cmds = [
        "/applications/ffmpeg",
        "-i",
        audio_input,
        "-f",
        "null",
        "-" 
    ]
    subprocess.Popen(cmds).wait()
    try:
        # Using check_output for capturing output; it raises CalledProcessError if the command exits with a non-zero status
        output = check_output(cmds, stderr=STDOUT).decode('utf-8', 'ignore')
    except CalledProcessError as e:
        output = e.output.decode('utf-8', 'ignore')
    return output.strip()

# Check if the message "error" appeared in the input file's FFmpeg loglevel:
def probeInputFile(audio_input):
    cmds = [
        "/applications/ffprobe",
        "-loglevel",
        "error", # loglevel = ‘quiet, -8’, ‘panic, 0’, ‘fatal, 8’, ‘error, 16’, ‘warning, 24’, ‘info, 32’, ‘verbose, 40’, ‘debug, 48’, ‘trace, 56’
        audio_input
    ]
    subprocess.Popen(cmds).wait()
    try:
        # Using check_output for capturing output; it raises CalledProcessError if the command exits with a non-zero status
        output = check_output(cmds, stderr=STDOUT).decode('utf-8', 'ignore')
    except CalledProcessError as e:
        output = e.output.decode('utf-8', 'ignore')
    return output.strip()

# Check the FFmpeg probe score of the input file:
def getProbeScore(audio_input):
    command = [
        '/applications/ffprobe',
        '-v',
        'error',
        '-show_entries',
        'format=probe_score',
        #'-of',
        #'default=noprint_wrappers=1:nokey=1',
        audio_input
    ]
    try:
        output = check_output(command, stderr=STDOUT).decode()
    except CalledProcessError as e:
        output = e.output.decode()
    return (output).strip()

# Function for testing the workflow:
def convert_audio(full_path, audio_output):
    cmds = [
        "/applications/ffmpeg",
        "-i",
        full_path,
        #"-vcodec", 
        #"libx264",
        #"-r",
        #"25", 
        "-c",
        "copy",
        "-map",
        "0",
        "-y",
        audio_output]
    subprocess.Popen(cmds).wait()
    try:
        output = check_output(cmds, stderr=STDOUT).decode(encoding="utf-8")
    except CalledProcessError as e:
        output = e.output.decode(encoding="utf-8")
    return (output).strip() 
