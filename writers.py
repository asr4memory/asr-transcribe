"""
Exporter functions.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, PackageLoader, select_autoescape
from xhtml2pdf import pisa
from app_config import get_config
from utilities import format_timestamp

env = Environment(loader=PackageLoader("writers"), autoescape=select_autoescape())

config = get_config()

USE_SPEAKER_DIARIZATION = config["whisper"].get("use_speaker_diarization", False)


def write_vtt_file(filepath: Path, custom_segs):
    """Write the processed segments to a VTT subtitle file."""
    with open(filepath, "w", encoding="utf-8") as file:
        file.write("WEBVTT\n\n")
        for i, seg in enumerate(custom_segs):
            _, start_time = format_timestamp(seg["start"])
            _, end_time = format_timestamp(seg["end"])
            file.write(f"{i + 1}\n")
            file.write(f"{start_time} --> {end_time}\n")
            file.write(f"{seg['text']}\n\n")


def write_srt_file(filepath: Path, custom_segs):
    """Write the processed segments to an SRT subtitle file."""
    with open(filepath, "w", encoding="utf-8") as file:
        for i, seg in enumerate(custom_segs):
            _, start_time = format_timestamp(seg["start"], milli_separator=",")
            _, end_time = format_timestamp(seg["end"], milli_separator=",")
            file.write(f"{i + 1}\n")
            file.write(f"{start_time} --> {end_time}\n")
            file.write(f"{seg['text']}\n\n")


def write_text_file(filepath: Path, custom_segs):
    """
    Write the processed segments to a text file.
    This file will contain only the transcribed text of each segment.
    """
    with open(filepath, "w", encoding="utf-8") as txt_file:
        for seg in custom_segs:
            if "text" in seg:
                txt_file.write(f"{seg['text']}\n")


def write_csv_file(
    filepath,
    custom_segs,
    delimiter="\t",
    speaker_column=False,
    write_header=False,
    USE_SPEAKER_DIARIZATION=False,
):
    """
    Write the processed segments to a CSV file.
    This file will contain the start timestamps of each segment in the
    first column, optionally a "SPEAKER" column, and the
    transcribed text of each segment in the last column.
    """
    fieldnames = (
        ["IN", "SPEAKER", "TRANSCRIPT"] if speaker_column else ["IN", "TRANSCRIPT"]
    )

    with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=delimiter)

        if write_header:
            writer.writeheader()

        for seg in custom_segs:
            _, timecode = format_timestamp(seg["start"])
            text = seg["text"]
            if USE_SPEAKER_DIARIZATION == True and speaker_column == True:
                speaker = seg["speaker"]
                row = {"IN": timecode, "SPEAKER": speaker, "TRANSCRIPT": text}
            elif USE_SPEAKER_DIARIZATION == False and speaker_column == False:
                row = {"IN": timecode, "TRANSCRIPT": text}
            # Leave the "SPEAKER" column empty if USE_SPEAKER_DIARIZATION option is false
            elif USE_SPEAKER_DIARIZATION == False and speaker_column == True:
                row = {"IN": timecode, "SPEAKER": "", "TRANSCRIPT": text}
            writer.writerow(row)


def write_json_file(filepath: Path, data):
    """Write a dictionary as a JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def write_csv_word_segments_file(filepath: Path, word_segments, delimiter="\t"):
    """
    Write the processed word segments to a CSV file.
    """
    fieldnames = ["WORD", "START", "END", "SCORE"]
    with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=delimiter)
        writer.writeheader()

        for word_seg in word_segments:
            _, timecode_start = format_timestamp(word_seg["start"])
            _, timecode_end = format_timestamp(word_seg["end"])
            word = word_seg["word"]
            score = word_seg.get("score", "values approximately calculated")
            row = {
                "WORD": word,
                "START": timecode_start,
                "END": timecode_end,
                "SCORE": score,
            }
            writer.writerow(row)


def write_vtt_word_segments_file(filepath: Path, word_segments):
    """
    Convert processed word segments to VTT format
    """
    with open(filepath, "w", encoding="utf-8") as vtt_file:
        vtt_file.write("WEBVTT\n\n")
        for i, word_seg in enumerate(word_segments):
            _, timecode_start = format_timestamp(word_seg["start"])
            _, timecode_end = format_timestamp(word_seg["end"])
            word = word_seg["word"]
            vtt_file.write(f"{i + 1}\n")
            vtt_file.write(f"{timecode_start} --> {timecode_end}\n")
            vtt_file.write(f"{word}\n\n")


def write_pdf_file(filepath: Path, segments: list):
    """Write a PDF file with the transcript text."""
    paragraphs = [segment["text"] for segment in segments]

    template = env.get_template("pdf_template.html")
    html_content = template.render(
        lang="en", filename=filepath.stem, paragraphs=paragraphs
    )

    with open(filepath, "wb") as file:
        pisa.CreatePDF(html_content, dest=file)


def write_output_files(base_path: Path, all: list, segments: list, word_segments: list):
    "Write all types of output files."
    write_vtt_file(base_path.with_suffix(".vtt"), segments)
    write_srt_file(base_path.with_suffix(".srt"), segments)
    write_text_file(base_path.with_suffix(".txt"), segments)
    write_csv_file(
        base_path.with_suffix(".csv"),
        segments,
        delimiter="\t",  # Use tab as delimiter
        speaker_column=False,
        write_header=False,
        USE_SPEAKER_DIARIZATION=False,
    )
    write_csv_file(
        base_path.with_name(base_path.name + "_speaker.csv"),
        segments,
        delimiter="\t",  # Use tab as delimiter
        speaker_column=True,
        write_header=True,
        USE_SPEAKER_DIARIZATION=USE_SPEAKER_DIARIZATION,
    )
    write_json_file(base_path.with_suffix(".json"), segments)
    write_json_file(base_path.with_name(base_path.name + "_unprocessed.json"), all)
    write_csv_word_segments_file(
        base_path.with_name(base_path.name + "_word_segments.csv"),
        word_segments,
        delimiter="\t",
    )
    write_vtt_word_segments_file(
        base_path.with_name(base_path.name + "_word_segments.vtt"), word_segments
    )
    write_pdf_file(base_path.with_suffix(".pdf"), segments)
