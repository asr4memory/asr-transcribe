"""
Exporter functions.
"""

from collections import OrderedDict
from decimal import Decimal, ROUND_HALF_UP
import csv
import json
from pathlib import Path
from unicodedata import normalize

from jinja2 import Environment, PackageLoader, select_autoescape
from pyexcel_ods3 import save_data
from xhtml2pdf import pisa
from tei_builder.converter import WhisperToTEIConverter

from app_config import get_config
from utilities import format_timestamp

env = Environment(loader=PackageLoader("writers"), autoescape=select_autoescape())

config = get_config()

USE_SPEAKER_DIARIZATION = config["whisper"].get("use_speaker_diarization", False)
def _resolve_pause_threshold() -> float:
    value = config["whisper"].get("pause_marker_threshold", 2.0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 2.0


PAUSE_MARKER_THRESHOLD = _resolve_pause_threshold()


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
    full_path = path_without_ext.with_stem(
        path_without_ext.stem + "_speaker"
    ).with_suffix(".txt")
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
    full_path = path_without_ext.with_stem(path_without_ext.stem + "_tab").with_suffix(
        ".txt"
    )
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


def _format_maxqda_timestamp(seconds: float) -> str:
    """Format timestamps as h:mm:ss.x for MAXQDA exports."""
    formatted_time, formatted_time_ms = format_timestamp(seconds, milli_separator=".")
    hours_str, minutes, seconds_str = formatted_time.split(":")
    fractional = formatted_time_ms.split(".")[1] if "." in formatted_time_ms else ""
    tenths = fractional[0] if fractional else "0"
    hours = str(int(hours_str))
    return f"{hours}:{minutes}:{seconds_str}.{tenths}"


def _format_pause_marker(seconds: float) -> str:
    """Format pause duration with decimal comma, rounded to 1 decimal place."""
    if seconds is None:
        return "[Pause ? s]"
    quantized = Decimal(str(seconds)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    seconds_str = format(quantized, "f").replace(".", ",")
    return f"[Pause {seconds_str} s]"


def _format_pause_marker_tag_floor(seconds: float) -> str:
    """Format pause duration as <pN> using floor to whole seconds."""
    if seconds is None:
        return "<p?>"
    whole = int(float(seconds))
    if whole < 0:
        whole = 0
    return f"<p{whole}>"


def _collect_pause_markers_per_segment(
    segments: list,
    word_segments: list | None,
    gap_threshold: float = PAUSE_MARKER_THRESHOLD,
    marker_formatter=_format_pause_marker,
) -> list[list[str]]:
    """
    Collect pause markers per segment based on word-level gaps without rebuilding text.
    Pauses (>= gap_threshold) are attached to the segment that precedes the gap.
    """
    if not word_segments:
        return [[] for _ in segments]

    markers_per_segment: list[list[str]] = [[] for _ in segments]
    seg_idx = 0
    last_word_end = None
    last_seg_idx = None

    for word_seg in word_segments:
        w_start = word_seg.get("start")
        w_end = word_seg.get("end")
        if w_start is None:
            continue

        # Advance segment pointer until current word fits into segment window.
        while seg_idx < len(segments):
            seg = segments[seg_idx]
            seg_start = seg.get("start")
            seg_end = seg.get("end")
            if seg_start is None or seg_end is None:
                seg_idx += 1
                continue
            if w_start < seg_end:
                break
            seg_idx += 1

        if seg_idx >= len(segments):
            break

        gap = None
        if last_word_end is not None:
            gap = w_start - last_word_end
        if gap is not None and gap >= gap_threshold and last_seg_idx is not None:
            markers_per_segment[last_seg_idx].append(marker_formatter(gap))

        last_word_end = w_end if w_end is not None else last_word_end
        last_seg_idx = seg_idx

    return markers_per_segment


def write_text_speaker_maxqda(
    path_without_ext: Path, segments: list, word_segments: list | None = None
):
    """
    Write the processed segments to a tab-delimited text file for MAXQDA imports.
    Uses truncated timestamps (h:mm:ss.x), omits headers, and appends a colon to speaker labels.
    """
    full_path = path_without_ext.with_stem(
        path_without_ext.stem + "_speaker_maxqda"
    ).with_suffix(".txt")
    pause_markers = _collect_pause_markers_per_segment(segments, word_segments)
    with open(full_path, "w", encoding="utf-8") as txt_file:
        for idx, seg in enumerate(segments):
            timestamp = _format_maxqda_timestamp(seg["start"])
            speaker = seg.get("speaker", "")
            speaker_label = f"{speaker}:" if speaker else ""
            text = seg["text"]
            if pause_markers[idx]:
                text = f"{text} {' '.join(pause_markers[idx])}".strip()
            txt_file.write(f"{timestamp}\t{speaker_label}\t{text}\n")


def write_text_speaker_segment_maxqda(
    path_without_ext: Path, segments: list, word_segments: list | None = None
):
    """
    Write MAXQDA-ready text with timestamps only when the speaker changes.
    Consecutive segments from the same speaker are merged into one line.
    Inserts pause markers (>=2s) based on word-level timing, attached to the
    preceding segment text.
    """
    full_path = path_without_ext.with_stem(
        path_without_ext.stem + "_speaker_segment_maxqda"
    ).with_suffix(".txt")
    pause_markers = _collect_pause_markers_per_segment(segments, word_segments)
    with open(full_path, "w", encoding="utf-8") as txt_file:
        last_speaker = ""
        block_start = None
        block_text_parts: list[str] = []

        def flush_block():
            if block_start is None or not block_text_parts:
                return
            timestamp = _format_maxqda_timestamp(block_start)
            speaker_label = f"{last_speaker}:" if last_speaker else ""
            combined_text = " ".join(block_text_parts).strip()
            txt_file.write(f"{timestamp}\t{speaker_label}\t{combined_text}\n")

        # Merge by segment speaker (no word-level speaker switching).
        for idx, seg in enumerate(segments):
            raw_speaker = seg.get("speaker", "")
            speaker = raw_speaker if raw_speaker else last_speaker
            text = seg["text"]
            if pause_markers[idx]:
                text = f"{text} {' '.join(pause_markers[idx])}".strip()

            if block_start is None:
                block_start = seg["start"]
                last_speaker = speaker
                block_text_parts = [text]
                continue

            if speaker == last_speaker:
                block_text_parts.append(text)
            else:
                flush_block()
                block_start = seg["start"]
                last_speaker = speaker
                block_text_parts = [text]

        flush_block()


def write_text_maxqda(
    path_without_ext: Path, segments: list, word_segments: list | None = None
):
    """
    Write the processed segments to a tab-delimited text file for MAXQDA without speaker labels.
    Each line contains the truncated timestamp and transcript text.
    """
    full_path = path_without_ext.with_stem(
        path_without_ext.stem + "_maxqda"
    ).with_suffix(".txt")
    pause_markers = _collect_pause_markers_per_segment(segments, word_segments)
    with open(full_path, "w", encoding="utf-8") as txt_file:
        for idx, seg in enumerate(segments):
            timestamp = _format_maxqda_timestamp(seg["start"])
            text = seg["text"]
            if pause_markers[idx]:
                text = f"{text} {' '.join(pause_markers[idx])}".strip()
            txt_file.write(f"{timestamp}\t{text}\n")


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
        rtf_file.write(
            "\\pard\\tx720\\tx1440\\tx2160\\tx2880\\tx3600\\tx4320\\tx5040\\tx5760\\tx6480\\tx7200\\tx7920\\tx8640\\pardirnatural\\partightenfactor0\n\n"
        )
        rtf_file.write("\\f0\\fs24 \\cf0 ")

        # Write text content
        for seg in segments:
            if "text" in seg:
                # Properly encode special characters including umlauts
                text = encode_rtf_text(seg["text"])
                rtf_file.write(f"{text}\\par\n")

        # RTF footer
        rtf_file.write("}")


def write_rtf_speaker(path_without_ext: Path, segments: list):
    """
    Write the processed segments to an RTF file with speaker markings and timestamps.
    This file will contain the transcribed text of each segment with speaker information
    and start/end timestamps for each segment.
    """
    full_path = path_without_ext.with_stem(
        path_without_ext.stem + "_speaker"
    ).with_suffix(".rtf")
    with open(full_path, "w", encoding="utf-8") as rtf_file:
        # RTF header
        rtf_file.write("{\\rtf1\\ansi\\ansicpg1252\\cocoartf2580\\cocoasubrtf220\n")
        rtf_file.write(
            "{\\fonttbl\\f0\\fswiss\\fcharset0 Helvetica;\\f1\\fswiss\\fcharset0 Helvetica-Bold;}\n"
        )
        rtf_file.write(
            "{\\colortbl;\\red255\\green255\\blue255;\\red0\\green0\\blue0;}\n"
        )
        rtf_file.write("\\margl1440\\margr1440\\vieww11520\\viewh8400\\viewkind0\n")
        rtf_file.write(
            "\\pard\\tx720\\tx1440\\tx2160\\tx2880\\tx3600\\tx4320\\tx5040\\tx5760\\tx6480\\tx7200\\tx7920\\tx8640\\pardirnatural\\partightenfactor0\n\n"
        )

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
        if char in "\\{}":
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
    word_segments: list | None = None,
    pause_formatter=_format_pause_marker_tag_floor,
    include_pause_markers: bool = True,
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

    pause_markers = None
    if include_pause_markers and speaker_column and word_segments:
        pause_markers = _collect_pause_markers_per_segment(
            segments,
            word_segments,
            marker_formatter=pause_formatter,
        )

    with open(full_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=delimiter)

        if write_header:
            writer.writeheader()

        for idx, seg in enumerate(segments):
            _, timecode = format_timestamp(seg["start"])
            text = seg["text"]
            if include_pause_markers and pause_markers and pause_markers[idx]:
                text = f"{text} {' '.join(pause_markers[idx])}".strip()

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

    full_path = path_without_ext.with_stem(
        path_without_ext.stem + "_timestamps"
    ).with_suffix(".pdf")
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
    with zipfile.ZipFile(full_path, "w") as odt_zip:
        # Add mimetype file (must be first and uncompressed)
        odt_zip.writestr(
            "mimetype",
            "application/vnd.oasis.opendocument.text",
            compress_type=zipfile.ZIP_STORED,
        )

        # Add META-INF/manifest.xml
        manifest_xml = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">
 <manifest:file-entry manifest:media-type="application/vnd.oasis.opendocument.text" manifest:full-path="/"/>
 <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="content.xml"/>
 <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="styles.xml"/>
 <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="meta.xml"/>
</manifest:manifest>"""
        odt_zip.writestr("META-INF/manifest.xml", manifest_xml)

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
        odt_zip.writestr("meta.xml", meta_xml)

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
        odt_zip.writestr("styles.xml", styles_xml)

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
            text = (
                seg["text"]
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;")
            )
            timestamp = f"[{start_time} --> {end_time}]"

            # Only write the speaker when it changes
            if speaker != last_speaker:
                escaped_speaker = (
                    speaker.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;")
                    .replace("'", "&apos;")
                )
                content_buffer.write(
                    f'  <text:p><text:span text:style-name="Bold">{escaped_speaker}:</text:span></text:p>\n'
                )
                last_speaker = speaker

            # Write timestamp and text
            content_buffer.write(
                f'  <text:p><text:span text:style-name="Italic">{timestamp}</text:span></text:p>\n'
            )
            content_buffer.write(f"  <text:p>{text}</text:p>\n")
            content_buffer.write("  <text:p></text:p>\n")  # Empty paragraph for spacing

        content_buffer.write("""  </office:text>
 </office:body>
</office:document-content>""")

        # Add content.xml to the zip file
        odt_zip.writestr("content.xml", content_buffer.getvalue())


def write_tei_xml(path_without_ext: Path, segments: list):
    """
    Write TEI XML file
    """
    full_path = path_without_ext.with_suffix(".tei.xml")
    converter = WhisperToTEIConverter()
    tei_xml_content = converter.convert(segments, full_path.name)
    with open(full_path, "w", encoding="utf-8") as xml_file:
        xml_file.write(tei_xml_content)


def write_summary(path_without_ext: Path, summary: str, language_code: str = "de"):
    """
    Write the summary to a localized text file in the llm_output directory.
    """
    bag_data_dir = path_without_ext.parent.parent
    llm_output_dir = bag_data_dir / "llm_output"
    llm_output_dir.mkdir(parents=True, exist_ok=True)
    summary_filename = f"{path_without_ext.stem}_summary_{language_code}.txt"
    full_path = llm_output_dir / summary_filename
    with open(full_path, "w", encoding="utf-8") as txt_file:
        txt_file.write(summary)

def write_toc(path_without_ext: Path, toc: str, language_code: str = "de"):
    """
    Write the table of contents to a localized text file in the llm_output directory.
    """
    bag_data_dir = path_without_ext.parent.parent
    llm_output_dir = bag_data_dir / "llm_output"
    llm_output_dir.mkdir(parents=True, exist_ok=True)
    toc_filename = f"{path_without_ext.stem}_toc_{language_code}.vtt"
    full_path = llm_output_dir / toc_filename
    with open(full_path, "w", encoding="utf-8") as vtt_file:
        vtt_file.write(toc)


def write_output_files(
    base_path: Path,
    unprocessed_whisperx_output: list,
    processed_whisperx_output: list,
    llm_output: dict,
):
    segments = processed_whisperx_output["segments"]
    word_segments = unprocessed_whisperx_output["word_segments"]

    """Write all types of output files."""

    # 1. WhisperX output files
    write_vtt(base_path, segments)
    write_word_segments_vtt(
        base_path.with_stem(base_path.stem + "_word_segments"), word_segments
    )
    write_srt(base_path, segments)
    write_text(base_path, segments)
    write_text_speaker(base_path, segments)
    write_text_speaker_tab(base_path, segments)
    write_text_speaker_maxqda(base_path, segments, word_segments)
    write_text_speaker_segment_maxqda(base_path, segments, word_segments)
    write_text_maxqda(base_path, segments, word_segments)
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
        word_segments=word_segments,
        pause_formatter=_format_pause_marker_tag_floor,
    )
    write_csv(
        base_path.with_stem(base_path.stem + "_speaker_nopause"),
        segments,
        delimiter="\t",
        speaker_column=True,
        write_header=True,
        word_segments=word_segments,
        include_pause_markers=False,
    )
    write_word_segments_csv(
        base_path.with_stem(base_path.stem + "_word_segments"),
        word_segments,
        delimiter="\t",
    )
    write_json(base_path, processed_whisperx_output)
    write_json(
        base_path.with_stem(base_path.stem + "_unprocessed"),
        unprocessed_whisperx_output,
    )
    write_ods(base_path, segments)
    write_tei_xml(base_path, segments)

    # 2. Write llm_output JSON to llm_output directory
    llm_output_dir = base_path.parent.parent / "llm_output"
    llm_output_dir.mkdir(parents=True, exist_ok=True)
    write_json(llm_output_dir / f"{base_path.stem}_llm_output", llm_output)
    summaries = llm_output.get("summaries", {})
    if summaries:
        for language_code, text in summaries.items():
            if text:
                write_summary(base_path, text, language_code=language_code)
    toc = llm_output.get("toc", {})
    if toc:
        for language_code, toc_text in toc.items():
            if toc_text:
                write_toc(base_path, toc_text, language_code=language_code)
