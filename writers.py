"""
Exporter functions.
"""
import csv
import json
from datetime import datetime
from pathlib import Path
from app_config import get_config

config = get_config()

USE_SPEAKER_DIARIZATION = config['whisper'].get('use_speaker_diarization', False)

def write_vtt_file(filepath: Path, custom_segs):
    """
    Write the processed segments to a VTT file.
    This file will contain the start and end times of each segment along with
    the transcribed text.
    """
    with open(filepath, "w", encoding="utf-8") as vtt_file:
        vtt_file.write("WEBVTT\n\n")
        for i, seg in enumerate(custom_segs):
            start_time = datetime.utcfromtimestamp(seg["start"]).strftime('%H:%M:%S.%f')[:-3]
            end_time = datetime.utcfromtimestamp(seg["end"]).strftime('%H:%M:%S.%f')[:-3]
            vtt_file.write(f"{i + 1}\n")
            vtt_file.write(f"{start_time} --> {end_time}\n")
            vtt_file.write(f"{seg['text']}\n\n")


def write_text_file(filepath: Path, custom_segs):
    """
    Write the processed segments to a text file.
    This file will contain only the transcribed text of each segment.
    """
    with open(filepath, "w", encoding='utf-8') as txt_file:
        for seg in custom_segs:
            if "text" in seg:
                txt_file.write(f"{seg['text']}\n")


def write_csv_file(filepath, custom_segs, delimiter="\t",
                   speaker_column=False, write_header=False, USE_SPEAKER_DIARIZATION=False):
    """
    Write the processed segments to a CSV file.
    This file will contain the start timestamps of each segment in the
    first column, optionally a "SPEAKER" column, and the
    transcribed text of each segment in the last column.
    """
    fieldnames = (['IN', 'SPEAKER', 'TRANSCRIPT'] if speaker_column
                  else ['IN', 'TRANSCRIPT'])

    with open(filepath, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                delimiter=delimiter)

        if write_header: writer.writeheader()

        for seg in custom_segs:
            timecode = "{:02}:{:02}:{:06.3f}".format(int(seg['start'] // 3600),
                                                    int((seg['start'] % 3600) // 60),
                                                    seg['start'] % 60)
            text = seg['text']
            if USE_SPEAKER_DIARIZATION == True and speaker_column == True:
                speaker = seg['speaker']
                row = {'IN': timecode, 'SPEAKER': speaker, 'TRANSCRIPT': text}
            elif USE_SPEAKER_DIARIZATION == False and speaker_column == False:
                row = {'IN': timecode, 'TRANSCRIPT': text}                
            # Leave the "SPEAKER" column empty if USE_SPEAKER_DIARIZATION option is false
            elif USE_SPEAKER_DIARIZATION == False and speaker_column == True: 
                row = {'IN': timecode, 'SPEAKER': '', 'TRANSCRIPT': text}
            writer.writerow(row)


def write_json_file(filepath: Path, data):
    """Write a dictionary as a JSON file."""
    with open(filepath, "w") as f:
        json.dump(data, f, indent=4)

def write_csv_word_segments_file(filepath, word_segments, delimiter="\t"):
    """
    Write the processed word segments to a CSV file.
    """
    fieldnames = (['WORD', 'START', 'END', 'SCORE'])
    with open(filepath, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                delimiter=delimiter)
        writer.writeheader()

        for word_seg in word_segments:
            timecode_start = "{:02}:{:02}:{:06.3f}".format(int(word_seg['start'] // 3600),
                                                    int((word_seg['start'] % 3600) // 60),
                                                    word_seg['start'] % 60)
            timecode_end = "{:02}:{:02}:{:06.3f}".format(int(word_seg['end'] // 3600),
                                                    int((word_seg['end'] % 3600) // 60),
                                                    word_seg['end'] % 60)
            word = word_seg['word']
            score = word_seg.get('score', 'NaN')  
            row = {'WORD': word, 'START': timecode_start, 'END': timecode_end, 'SCORE': score} 
            writer.writerow(row)

def write_output_files(base_path: Path, segments: list, word_segments: list):
    write_vtt_file(base_path.with_suffix('.vtt'), segments)
    write_text_file(base_path.with_suffix('.txt'), segments)
    write_csv_file(base_path.with_suffix('.csv'), 
                    segments,
                    delimiter="\t",  # Use tab as delimiter
                    speaker_column=False,
                    write_header=False,
                    USE_SPEAKER_DIARIZATION=False)
    write_csv_file(base_path.with_name(base_path.name + "_speaker.csv"),
                    segments,
                    delimiter="\t", # Use tab as delimiter
                    speaker_column=True,
                    write_header=True,
                    USE_SPEAKER_DIARIZATION=USE_SPEAKER_DIARIZATION)
    write_json_file(base_path.with_suffix('.json'), segments)
    write_csv_word_segments_file(base_path.with_name(base_path.name + "_word_segments.csv"),         
                    word_segments,
                    delimiter="\t")