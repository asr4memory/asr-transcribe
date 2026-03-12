"""Export operations — re-export transcripts from WhisperX JSON to various formats."""

import json
from pathlib import Path

from cli_anything.asr_transcribe.utils.asr_backend import ensure_project_importable

# All supported export formats with descriptions
EXPORT_FORMATS = {
    "vtt": "WebVTT subtitles",
    "srt": "SubRip subtitles",
    "txt": "Plain text transcript",
    "txt_speaker": "Text with speaker labels and timestamps",
    "txt_tab": "Tab-delimited: IN, SPEAKER, TRANSCRIPT",
    "txt_maxqda": "MAXQDA format (timestamp + text)",
    "txt_speaker_maxqda": "MAXQDA with speaker labels",
    "txt_speaker_segment_maxqda": "MAXQDA merged by speaker",
    "rtf": "Rich Text Format",
    "rtf_speaker": "RTF with speaker labels and timestamps",
    "csv": "Tab-delimited CSV (IN, TRANSCRIPT)",
    "csv_speaker": "Tab-delimited CSV with speaker + pause markers",
    "csv_speaker_nopause": "Tab-delimited CSV with speaker, no pause markers",
    "word_vtt": "Word-level VTT (one word per cue)",
    "word_csv": "Word-level CSV (WORD, START, END, SCORE)",
    "json": "Processed segments JSON",
    "pdf": "PDF document",
    "pdf_timestamps": "PDF with timestamps",
    "odt": "OpenDocument Text",
    "ods": "OpenDocument Spreadsheet",
    "tei_xml": "TEI-XML with timeline and speakers",
}


def list_formats() -> dict:
    """Return all available export formats.

    Returns:
        Dict mapping format name to description.
    """
    return EXPORT_FORMATS.copy()


def export_convert(
    json_path: str,
    formats: list[str] | None = None,
    output_dir: str | None = None,
) -> dict:
    """Export WhisperX JSON to one or more output formats.

    Args:
        json_path: Path to a WhisperX JSON file (processed or unprocessed).
        formats: List of format names to export. None = all formats.
        output_dir: Output directory. Defaults to same directory as input.

    Returns:
        Dict with exported files and any errors.
    """
    root = ensure_project_importable()

    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Parse segments
    if isinstance(data, dict):
        segments = data.get("segments", [])
        word_segments = data.get("word_segments", [])
    elif isinstance(data, list):
        segments = data
        word_segments = []
    else:
        raise ValueError("Unexpected JSON structure")

    if not segments:
        return {"error": "No segments found in JSON file", "exported": []}

    # Determine output base path
    if output_dir:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = path.parent

    base_name = path.stem
    if base_name.endswith("_processed"):
        base_name = base_name[:-10]
    if base_name.endswith("_unprocessed"):
        base_name = base_name[:-12]

    base_path = out_dir / base_name

    # Determine which formats to export
    if formats is None:
        formats = list(EXPORT_FORMATS.keys())
    else:
        unknown = [f for f in formats if f not in EXPORT_FORMATS]
        if unknown:
            return {"error": f"Unknown format(s): {', '.join(unknown)}", "exported": []}

    # Import writers
    from output.writers import (
        write_vtt, write_srt, write_text, write_text_speaker,
        write_text_speaker_tab, write_text_maxqda,
        write_text_speaker_maxqda, write_text_speaker_segment_maxqda,
        write_rtf, write_rtf_speaker, write_csv, write_word_segments_csv,
        write_word_segments_vtt, write_json, write_pdf, write_pdf_timestamps,
        write_odt, write_ods, write_tei_xml,
        _format_pause_marker_tag_floor,
    )
    from utils.utilities import append_affix

    exported = []
    errors = []

    format_handlers = {
        "vtt": lambda: write_vtt(base_path, segments),
        "srt": lambda: write_srt(base_path, segments),
        "txt": lambda: write_text(base_path, segments),
        "txt_speaker": lambda: write_text_speaker(base_path, segments),
        "txt_tab": lambda: write_text_speaker_tab(base_path, segments),
        "txt_maxqda": lambda: write_text_maxqda(base_path, segments, word_segments),
        "txt_speaker_maxqda": lambda: write_text_speaker_maxqda(base_path, segments, word_segments),
        "txt_speaker_segment_maxqda": lambda: write_text_speaker_segment_maxqda(base_path, segments, word_segments),
        "rtf": lambda: write_rtf(base_path, segments),
        "rtf_speaker": lambda: write_rtf_speaker(base_path, segments),
        "csv": lambda: write_csv(base_path, segments, delimiter="\t", speaker_column=False, write_header=False),
        "csv_speaker": lambda: write_csv(
            append_affix(base_path, "_speaker"), segments, delimiter="\t",
            speaker_column=True, write_header=True, word_segments=word_segments,
            pause_formatter=_format_pause_marker_tag_floor,
        ),
        "csv_speaker_nopause": lambda: write_csv(
            append_affix(base_path, "_speaker_nopause"), segments, delimiter="\t",
            speaker_column=True, write_header=True, word_segments=word_segments,
            include_pause_markers=False,
        ),
        "word_vtt": lambda: write_word_segments_vtt(append_affix(base_path, "_word_segments"), word_segments) if word_segments else None,
        "word_csv": lambda: write_word_segments_csv(append_affix(base_path, "_word_segments"), word_segments, delimiter="\t") if word_segments else None,
        "json": lambda: write_json(base_path, data if isinstance(data, dict) else segments),
        "pdf": lambda: write_pdf(base_path, segments),
        "pdf_timestamps": lambda: write_pdf_timestamps(base_path, segments),
        "odt": lambda: write_odt(base_path, segments),
        "ods": lambda: write_ods(base_path, segments),
        "tei_xml": lambda: write_tei_xml(base_path, segments),
    }

    for fmt in formats:
        handler = format_handlers.get(fmt)
        if handler is None:
            errors.append({"format": fmt, "error": "No handler available"})
            continue
        try:
            handler()
            exported.append(fmt)
        except Exception as e:
            errors.append({"format": fmt, "error": str(e)})

    return {
        "input_file": str(path),
        "output_directory": str(out_dir),
        "base_name": base_name,
        "exported": exported,
        "errors": errors,
        "message": f"Exported {len(exported)} format(s) to {out_dir}",
    }
