"""Post-processing of WhisperX segments."""

import json
from pathlib import Path

from cli_anything.asr_transcribe.utils.asr_backend import ensure_project_importable


def process_segments(json_path: str, output_path: str = None) -> dict:
    """Run post-processing on WhisperX JSON output.

    Applies: sentence buffering, uppercasing, long sentence splitting.

    Args:
        json_path: Path to WhisperX JSON file (raw or processed).
        output_path: Optional output path for the processed JSON. Defaults to <input>_processed.json.

    Returns:
        Dict with segment count before/after, output path.
    """
    root = ensure_project_importable()

    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Extract segments from various formats
    if isinstance(data, dict):
        segments = data.get("segments", [])
    elif isinstance(data, list):
        segments = data
    else:
        raise ValueError("Unexpected JSON structure — expected dict with 'segments' key or a list.")

    original_count = len(segments)

    from output.post_processing import process_whisperx_segments

    result = process_whisperx_segments(segments)

    processed_count = len(result["segments"])

    # Write output
    if output_path is None:
        output_path = str(path.with_name(path.stem + "_processed.json"))

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)

    return {
        "input_file": str(path),
        "output_file": output_path,
        "segments_before": original_count,
        "segments_after": processed_count,
        "word_segments": len(result.get("word_segments", [])),
        "message": f"Post-processing complete: {original_count} -> {processed_count} segments.",
    }


def _load_segments(json_path: str) -> tuple[list, Path]:
    """Load segments from a JSON file. Returns (segments, path)."""
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        segments = data.get("segments", [])
    elif isinstance(data, list):
        segments = data
    else:
        raise ValueError("Unexpected JSON structure.")

    return segments, path


def _write_result(segments: list, output_path: str, label: str) -> dict:
    """Write processed segments and return a result dict."""
    word_segments = []
    for seg in segments:
        word_segments.extend(seg.get("words", []))

    result = {"segments": segments, "word_segments": word_segments}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)

    return {
        "output_file": output_path,
        "segment_count": len(segments),
        "word_count": len(word_segments),
        "message": f"{label} complete: {len(segments)} segments.",
    }


def buffer_step(json_path: str, output_path: str = None) -> dict:
    """Run only the sentence-buffering step on segments.

    Joins sentences falsely split after titles, abbreviations, or numbers.
    """
    ensure_project_importable()
    from output.post_processing import buffer_sentences

    segments, path = _load_segments(json_path)
    original_count = len(segments)

    buffered = buffer_sentences(segments)

    if output_path is None:
        output_path = str(path.with_name(path.stem + "_buffered.json"))

    result = _write_result(buffered, output_path, "Buffer step")
    result["segments_before"] = original_count
    return result


def uppercase_step(json_path: str, output_path: str = None) -> dict:
    """Run only the uppercase-first-letter step on segments."""
    ensure_project_importable()
    from output.post_processing import uppercase_sentences

    segments, path = _load_segments(json_path)

    uppercase_sentences(segments)  # modifies in place

    if output_path is None:
        output_path = str(path.with_name(path.stem + "_uppercased.json"))

    return _write_result(segments, output_path, "Uppercase step")


def split_step(json_path: str, output_path: str = None, max_length: int = 120) -> dict:
    """Run only the long-sentence-splitting step on segments."""
    ensure_project_importable()
    from output.post_processing import split_long_sentences

    segments, path = _load_segments(json_path)
    original_count = len(segments)

    split_result = list(split_long_sentences(segments, max_sentence_length=max_length))

    if output_path is None:
        output_path = str(path.with_name(path.stem + "_split.json"))

    result = _write_result(split_result, output_path, "Split step")
    result["segments_before"] = original_count
    return result
