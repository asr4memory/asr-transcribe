import subprocess

def create_extended_output_file(output_directory, input_file, timestamp):
    # Create the extended audio file by concatenating the input file four times
    extended_audio_file = output_directory + "/" + timestamp + "_extended_audio_file.wav"
    subprocess.run([
        "ffmpeg", "-y", "-i", input_file,
        "-filter_complex", "[0:a][0:a][0:a][0:a]concat=n=4:v=0:a=1[out]",
        "-map", "[out]", extended_audio_file
         ])
    return extended_audio_file