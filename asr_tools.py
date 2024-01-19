"""
Utilities and helper functions for automatic speech recognition.
"""
import io
import csv
from datetime import datetime

class Tee(io.StringIO):
    "What does this class do?"
    def __init__(self, terminal):
        self.terminal = terminal
        super().__init__()

    def write(self, message):
        self.terminal.write(message)
        super().write(message)


def ignore_file(file):
    "Checks whether the file should be ignored. File has which type?"
    if file.endswith(".DS_Store"):
        return True
    elif file.endswith("backup"):
        return True
    elif file.endswith("_test_"):
        return True
    elif file.startswith("_"):
        return True
    elif file.startswith("_test"):
        return True
    elif file.startswith("."):
        return True
    else:
        return False


def write_vtt_file(output_file, custom_segs):
    """
    Write the processed segments to a VTT file.
    This file will contain the start and end times of each segment along with
    the transcribed text.
    """
    with open(output_file + '.vtt', "w", encoding='utf-8') as vtt_file:
        vtt_file.write("WEBVTT\n\n")
        for i, seg in enumerate(custom_segs):
            start_time = datetime.utcfromtimestamp(seg["start"]).strftime('%H:%M:%S.%f')[:-3]
            end_time = datetime.utcfromtimestamp(seg["end"]).strftime('%H:%M:%S.%f')[:-3]
            vtt_file.write(f"{i + 1}\n")
            vtt_file.write(f"{start_time} --> {end_time}\n")
            vtt_file.write(f"{seg['sentence']}\n\n")


def write_text_file(output_file, custom_segs):
    """
    Write the processed segments to a text file.
    This file will contain only the transcribed text of each segment.
    """
    with open(output_file + '.txt', "w", encoding='utf-8') as txt_file:
        for seg in custom_segs:
            if "sentence" in seg:
                txt_file.write(f"{seg['sentence']}\n")


def write_csv_file(output_file, custom_segs, write_header=False):
    """
    Write the processed segments to a CSV file.
    This file will contain the start timestamps of each segment in the first
    column and the transcribed text of each segment in the second column.
    """
    with open(output_file + '.csv', 'w', newline='') as csvfile:
        fieldnames = ['start', 'sentence']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if write_header: writer.writeheader()

        for seg in custom_segs:
            start_content = "{:02}:{:02}:{:06.3f}".format(int(seg['start'] // 3600),
                                                          int((seg['start'] % 3600) // 60),
                                                          seg['start'] % 60)
            sentence_content = seg['sentence']
            writer.writerow({'start': start_content, 'sentence': sentence_content})
