"""
Exporter functions.
"""

from collections import OrderedDict
import csv
import json
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


def write_text_speaker(path_without_ext: Path, segments: list):
    """
    Write the processed segments to a text file with speaker markings and timestamps.
    This file will contain the transcribed text of each segment with speaker information
    and start/end timestamps for each segment.
    """
    full_path = path_without_ext.with_stem(path_without_ext.stem + "_speaker").with_suffix(".txt")
    with open(full_path, "w", encoding="utf-8") as txt_file:
        last_speaker = ""
        for seg in segments:
            # Get formatted timestamps
            _, start_time = format_timestamp(seg["start"])
            _, end_time = format_timestamp(seg["end"])
            
            speaker = seg.get("speaker", "")
            text = seg["text"]
            
            # Only write the speaker when it changes
            if speaker != last_speaker:
                txt_file.write(f"{speaker}:\n")
                last_speaker = speaker
            
            # Write timestamps and text
            txt_file.write(f"[{start_time} --> {end_time}]\n")
            txt_file.write(f"{text}\n\n")


def write_text_speaker_tab(path_without_ext: Path, segments: list):
    """
    Write the processed segments to a tab-delimited text file.
    This file will contain IN timestamp, SPEAKER, and TRANSCRIPT columns.
    """
    full_path = path_without_ext.with_stem(path_without_ext.stem + "_tab").with_suffix(".txt")
    with open(full_path, "w", encoding="utf-8") as txt_file:
        # Write header without OUT column
        txt_file.write("IN\tSPEAKER\tTRANSCRIPT\n")
        
        for seg in segments:
            # Get formatted timestamps, only using start time
            _, start_time = format_timestamp(seg["start"])
            
            speaker = seg.get("speaker", "")
            text = seg["text"]
            
            # Write tab-delimited line without OUT column
            txt_file.write(f"{start_time}\t{speaker}\t{text}\n")


def write_rtf(path_without_ext: Path, segments: list):
    """
    Write the processed segments to an RTF file.
    This file will contain only the transcribed text of each segment.
    """
    full_path = path_without_ext.with_suffix(".rtf")
    with open(full_path, "w", encoding="utf-8") as rtf_file:
        # RTF header
        rtf_file.write("{\\rtf1\\ansi\\ansicpg1252\\cocoartf2580\\cocoasubrtf220\n")
        rtf_file.write("{\\fonttbl\\f0\\fswiss\\fcharset0 Helvetica;}\n")
        rtf_file.write("{\\colortbl;\\red255\\green255\\blue255;}\n")
        rtf_file.write("\\margl1440\\margr1440\\vieww11520\\viewh8400\\viewkind0\n")
        rtf_file.write("\\pard\\tx720\\tx1440\\tx2160\\tx2880\\tx3600\\tx4320\\tx5040\\tx5760\\tx6480\\tx7200\\tx7920\\tx8640\\pardirnatural\\partightenfactor0\n\n")
        rtf_file.write("\\f0\\fs24 \\cf0 ")
        
        # Write text content
        for seg in segments:
            if "text" in seg:
                # Properly encode special characters including umlauts
                text = encode_rtf_text(seg['text'])
                rtf_file.write(f"{text}\\par\n")
        
        # RTF footer
        rtf_file.write("}")


def write_rtf_speaker(path_without_ext: Path, segments: list):
    """
    Write the processed segments to an RTF file with speaker markings and timestamps.
    This file will contain the transcribed text of each segment with speaker information
    and start/end timestamps for each segment.
    """
    full_path = path_without_ext.with_stem(path_without_ext.stem + "_speaker").with_suffix(".rtf")
    with open(full_path, "w", encoding="utf-8") as rtf_file:
        # RTF header
        rtf_file.write("{\\rtf1\\ansi\\ansicpg1252\\cocoartf2580\\cocoasubrtf220\n")
        rtf_file.write("{\\fonttbl\\f0\\fswiss\\fcharset0 Helvetica;\\f1\\fswiss\\fcharset0 Helvetica-Bold;}\n")
        rtf_file.write("{\\colortbl;\\red255\\green255\\blue255;\\red0\\green0\\blue0;}\n")
        rtf_file.write("\\margl1440\\margr1440\\vieww11520\\viewh8400\\viewkind0\n")
        rtf_file.write("\\pard\\tx720\\tx1440\\tx2160\\tx2880\\tx3600\\tx4320\\tx5040\\tx5760\\tx6480\\tx7200\\tx7920\\tx8640\\pardirnatural\\partightenfactor0\n\n")
        
        last_speaker = ""
        for seg in segments:
            # Get formatted timestamps
            _, start_time = format_timestamp(seg["start"])
            _, end_time = format_timestamp(seg["end"])
            
            speaker = seg.get("speaker", "")
            text = encode_rtf_text(seg["text"])
            
            # Only write the speaker when it changes
            if speaker != last_speaker:
                speaker_encoded = encode_rtf_text(speaker)
                rtf_file.write(f"\\f1\\b \\cf0 {speaker_encoded}:\\f0\\b0\\par\n")
                last_speaker = speaker
            
            # Write timestamps and text
            timestamp = f"[{start_time} --> {end_time}]"
            timestamp_encoded = encode_rtf_text(timestamp)
            rtf_file.write(f"\\f1\\i {timestamp_encoded}\\f0\\i0\\par\n")
            rtf_file.write(f"{text}\\par\n\\par\n")
        
        # RTF footer
        rtf_file.write("}")


def encode_rtf_text(text):
    """
    Encode text for proper RTF representation, including umlauts and special characters.
    """
    result = ""
    for char in text:
        # Handle RTF control characters
        if char in '\\{}':
            result += f"\\{char}"
        # Handle umlauts and special characters by using their unicode representation
        elif ord(char) > 127:
            result += f"\\u{ord(char)}?"  # The '?' is a replacement char for non-Unicode readers
        else:
            result += char
    return result


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


def write_pdf_timestamps(path_without_ext: Path, segments: list):
    """Write a PDF file with the transcript text and timestamps."""
    template = env.get_template("pdf_template.html")
    normalized_filename = normalize("NFC", path_without_ext.stem)
    
    # Modify segments to include timestamps in text
    modified_segments = []
    for segment in segments:
        # Get formatted timestamps
        _, start_time = format_timestamp(segment["start"])
        _, end_time = format_timestamp(segment["end"])
        
        # Create a copy of the segment with modified text
        modified_segment = segment.copy()
        modified_segment["text"] = f"[{start_time} --> {end_time}]\n{segment['text']}"
        modified_segments.append(modified_segment)
    
    # Use the same preparation function as write_pdf
    segments_for_template = prepare_segments_for_template(modified_segments)

    html_content = template.render(
        lang="en", filename=normalized_filename, segments=segments_for_template
    )

    full_path = path_without_ext.with_stem(path_without_ext.stem + "_timestamps").with_suffix(".pdf")
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


def write_odt(path_without_ext: Path, segments: list):
    """
    Write the processed segments to an ODT (OpenDocument Text) file with speaker markings and timestamps.
    This file will contain the transcribed text of each segment with speaker information
    and start/end timestamps for each segment.
    Uses standard libraries to create the ODT file structure.
    """
    import zipfile
    import io
    
    full_path = path_without_ext.with_suffix(".odt")
    
    # Create a new zip file (ODT is a zip file with XML content)
    with zipfile.ZipFile(full_path, 'w') as odt_zip:
        
        # Add mimetype file (must be first and uncompressed)
        odt_zip.writestr('mimetype', 'application/vnd.oasis.opendocument.text', compress_type=zipfile.ZIP_STORED)
        
        # Add META-INF/manifest.xml
        manifest_xml = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">
 <manifest:file-entry manifest:media-type="application/vnd.oasis.opendocument.text" manifest:full-path="/"/>
 <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="content.xml"/>
 <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="styles.xml"/>
 <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="meta.xml"/>
</manifest:manifest>"""
        odt_zip.writestr('META-INF/manifest.xml', manifest_xml)
        
        # Add meta.xml
        meta_xml = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" 
                     xmlns:dc="http://purl.org/dc/elements/1.1/">
 <office:meta>
  <dc:title>Transcript</dc:title>
  <dc:description>Transcription with speaker markings and timestamps</dc:description>
  <dc:creator>Automatic Speech Recognition</dc:creator>
 </office:meta>
</office:document-meta>"""
        odt_zip.writestr('meta.xml', meta_xml)
        
        # Add styles.xml
        styles_xml = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
                       xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
                       xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
                       xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0">
 <office:styles>
  <style:style style:name="Bold" style:family="text">
   <style:text-properties fo:font-weight="bold"/>
  </style:style>
  <style:style style:name="Italic" style:family="text">
   <style:text-properties fo:font-style="italic"/>
  </style:style>
 </office:styles>
</office:document-styles>"""
        odt_zip.writestr('styles.xml', styles_xml)
        
        # Create content.xml with the actual content
        content_buffer = io.StringIO()
        content_buffer.write("""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
                       xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
                       xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0">
 <office:body>
  <office:text>
""")
        
        # Add the transcript content
        last_speaker = ""
        for seg in segments:
            # Get formatted timestamps
            _, start_time = format_timestamp(seg["start"])
            _, end_time = format_timestamp(seg["end"])
            
            speaker = seg.get("speaker", "")
            # Escape XML special characters
            text = seg["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
            timestamp = f"[{start_time} --> {end_time}]"
            
            # Only write the speaker when it changes
            if speaker != last_speaker:
                escaped_speaker = speaker.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
                content_buffer.write(f'  <text:p><text:span text:style-name="Bold">{escaped_speaker}:</text:span></text:p>\n')
                last_speaker = speaker
            
            # Write timestamp and text
            content_buffer.write(f'  <text:p><text:span text:style-name="Italic">{timestamp}</text:span></text:p>\n')
            content_buffer.write(f'  <text:p>{text}</text:p>\n')
            content_buffer.write(f'  <text:p></text:p>\n')  # Empty paragraph for spacing
        
        content_buffer.write("""  </office:text>
 </office:body>
</office:document-content>""")
        
        # Add content.xml to the zip file
        odt_zip.writestr('content.xml', content_buffer.getvalue())


def write_output_files(base_path: Path, all: list, segments: list, word_segments: list):
    """Write all types of output files."""
    write_vtt(base_path, segments)
    write_word_segments_vtt(
        base_path.with_stem(base_path.stem + "_word_segments"), word_segments
    )
    write_srt(base_path, segments)
    write_text(base_path, segments)
    write_text_speaker(base_path, segments)
    write_text_speaker_tab(base_path, segments)
    write_rtf(base_path, segments)
    write_rtf_speaker(base_path, segments)
    write_odt(base_path, segments)  # Added new ODT function
    write_pdf(base_path, segments)
    write_pdf_timestamps(base_path, segments)
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
    write_ods(base_path, segments)
