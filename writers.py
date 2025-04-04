"""
Exporter functions.
"""

import csv
import json
from collections import OrderedDict
from pathlib import Path
from unicodedata import normalize

from jinja2 import Environment, PackageLoader, select_autoescape
from pyexcel_ods3 import save_data
from xhtml2pdf import pisa

from app_config import get_config
from utilities import format_timestamp

env = Environment(loader=PackageLoader("writers"), autoescape=select_autoescape())

config = get_config()

USE_SPEAKER_DIARIZATION = config["whisper"].get("use_speaker_diarization", False)


def write_vtt(path_without_ext: Path, segments: list):
    """Write the processed segments to a VTT subtitle file."""
    full_path = path_without_ext.with_suffix(".vtt")
    with open(full_path, "w", encoding="utf-8") as file:
        file.write("WEBVTT\n\n")
        for i, seg in enumerate(segments):
            _, start_time = format_timestamp(seg["start"])
            _, end_time = format_timestamp(seg["end"])
            file.write(f"{i + 1}\n")
            file.write(f"{start_time} --> {end_time}\n")
            file.write(f"{seg['text']}\n\n")


def write_word_segments_vtt(path_without_ext: Path, word_segments: list):
    """Convert processed word segments to VTT format."""
    full_path = path_without_ext.with_suffix(".vtt")
    with open(full_path, "w", encoding="utf-8") as vtt_file:
        vtt_file.write("WEBVTT\n\n")
        for i, word_seg in enumerate(word_segments):
            _, timecode_start = format_timestamp(word_seg["start"])
            _, timecode_end = format_timestamp(word_seg["end"])
            word = word_seg["word"]
            vtt_file.write(f"{i + 1}\n")
            vtt_file.write(f"{timecode_start} --> {timecode_end}\n")
            vtt_file.write(f"{word}\n\n")


def write_srt(path_without_ext: Path, segments: list):
    """Write the processed segments to an SRT subtitle file."""
    full_path = path_without_ext.with_suffix(".srt")
    with open(full_path, "w", encoding="utf-8") as file:
        for i, seg in enumerate(segments):
            _, start_time = format_timestamp(seg["start"], milli_separator=",")
            _, end_time = format_timestamp(seg["end"], milli_separator=",")
            file.write(f"{i + 1}\n")
            file.write(f"{start_time} --> {end_time}\n")
            file.write(f"{seg['text']}\n\n")


def write_text(path_without_ext: Path, segments: list):
    """
    Write the processed segments to a text file.
    This file will contain only the transcribed text of each segment.
    """
    full_path = path_without_ext.with_suffix(".txt")
    with open(full_path, "w", encoding="utf-8") as txt_file:
        for seg in segments:
            if "text" in seg:
                txt_file.write(f"{seg['text']}\n")


def write_csv(
    path_without_ext: Path,
    segments: list,
    delimiter="\t",
    speaker_column=False,
    write_header=False,
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

    full_path = path_without_ext.with_suffix(".csv")
    with open(full_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=delimiter)

        if write_header:
            writer.writeheader()

        for seg in segments:
            _, timecode = format_timestamp(seg["start"])
            text = seg["text"]

            if speaker_column:
                row = {
                    "IN": timecode,
                    "SPEAKER": seg.get("speaker", ""),
                    "TRANSCRIPT": text,
                }
            else:
                row = {"IN": timecode, "TRANSCRIPT": text}

            writer.writerow(row)


def write_word_segments_csv(
    path_without_ext: Path, word_segments: list, delimiter="\t"
):
    """Write the processed word segments to a CSV file."""
    fieldnames = ["WORD", "START", "END", "SCORE"]
    full_path = path_without_ext.with_suffix(".csv")
    with open(full_path, "w", newline="", encoding="utf-8") as csvfile:
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


def write_json(path_without_ext: Path, segments: list):
    """Write a dictionary as a JSON file."""
    full_path = path_without_ext.with_suffix(".json")
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=4, ensure_ascii=False)


def write_pdf(path_without_ext: Path, segments: list):
    """Write a PDF file with the transcript text."""
    template = env.get_template("pdf_template.html")
    normalized_filename = normalize("NFC", path_without_ext.stem)
    segments_for_template = prepare_segments_for_template(segments)

    html_content = template.render(
        lang="en", filename=normalized_filename, segments=segments_for_template
    )

    full_path = path_without_ext.with_suffix(".pdf")
    with open(full_path, "wb") as file:
        pisa.CreatePDF(html_content, dest=file)


def prepare_segments_for_template(segments: list) -> list:
    """
    Transform the segment data for the template that is used for
    creating the PDF file.
    """
    segments_for_template = []
    last_speaker = ""
    for segment in segments:
        new_segment = {"text": segment["text"]}
        speaker = segment.get("speaker", "")
        if speaker != last_speaker:
            new_segment["speaker"] = speaker
            last_speaker = speaker
        segments_for_template.append(new_segment)

    return segments_for_template


def write_ods(path_without_ext: Path, segments: list):
    """
    Write the processed segments to an ODS file.
    """
    fieldnames = ["IN", "SPEAKER", "TRANSCRIPT"]

    rows = []
    rows.append(fieldnames)

    for segment in segments:
        _, timecode = format_timestamp(segment["start"])
        row = [timecode, segment.get("speaker", ""), segment["text"]]
        rows.append(row)

    data = OrderedDict()
    data.update({"Sheet 1": rows})

    full_path = path_without_ext.with_suffix(".ods")
    save_data(str(full_path), data)


def write_output_files(base_path: Path, all: list, segments: list, word_segments: list):
    """Write all types of output files."""
    write_vtt(base_path, segments)
    write_word_segments_vtt(
        base_path.with_stem(base_path.stem + "_word_segments"), word_segments
    )
    write_srt(base_path, segments)
    write_text(base_path, segments)
    write_csv(
        base_path,
        segments,
        delimiter="\t",
        speaker_column=False,
        write_header=False,
    )
    write_csv(
        base_path.with_stem(base_path.stem + "_speaker"),
        segments,
        delimiter="\t",
        speaker_column=True,
        write_header=True,
    )
    write_word_segments_csv(
        base_path.with_stem(base_path.stem + "_word_segments"),
        word_segments,
        delimiter="\t",
    )
    write_json(base_path, segments)
    write_json(base_path.with_stem(base_path.stem + "_unprocessed"), all)
    write_pdf(base_path, segments)
    write_ods(base_path, segments)
