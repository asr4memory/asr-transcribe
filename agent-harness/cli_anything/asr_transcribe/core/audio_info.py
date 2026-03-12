"""Audio file inspection."""

import json
import os
from pathlib import Path


def get_audio_info(audio_path: str) -> dict:
    """Get metadata about an audio file.

    Returns dict with filename, size, duration, etc.
    """
    path = Path(audio_path)

    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    info = {
        "filename": path.name,
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "size_human": _format_size(path.stat().st_size),
        "extension": path.suffix.lower(),
    }

    # Try to get audio duration using whisperx
    try:
        from cli_anything.asr_transcribe.utils.asr_backend import ensure_project_importable
        ensure_project_importable()
        from subprocesses.whisper_subprocess import get_audio, get_audio_length

        audio = get_audio(path=path)
        duration = float(get_audio_length(audio))
        info["duration_seconds"] = round(duration, 2)
        info["duration_human"] = _format_duration(duration)
    except Exception:
        info["duration_seconds"] = None
        info["duration_human"] = "unavailable (whisperx not loaded)"

    return info


def get_segments_info(json_path: str) -> dict:
    """Get statistics about WhisperX segments from a JSON file.

    Args:
        json_path: Path to a WhisperX JSON output file.

    Returns:
        Dict with segment count, total duration, speakers, word count, etc.
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle both raw WhisperX output and processed output
    if isinstance(data, dict):
        segments = data.get("segments", [])
        word_segments = data.get("word_segments", [])
        language = data.get("language")
    elif isinstance(data, list):
        segments = data
        word_segments = []
        language = None
    else:
        return {"error": "Unexpected JSON structure"}

    if not segments:
        return {
            "segment_count": 0,
            "total_duration": 0,
            "language": language,
        }

    # Compute stats
    speakers = set()
    total_words = 0
    total_chars = 0

    for seg in segments:
        text = seg.get("text", "")
        total_words += len(text.split())
        total_chars += len(text)
        speaker = seg.get("speaker")
        if speaker:
            speakers.add(speaker)

    first_start = segments[0].get("start", 0)
    last_end = segments[-1].get("end", 0)
    total_duration = last_end - first_start

    return {
        "filename": path.name,
        "segment_count": len(segments),
        "word_segment_count": len(word_segments),
        "total_words": total_words,
        "total_characters": total_chars,
        "total_duration_seconds": round(total_duration, 2),
        "total_duration_human": _format_duration(total_duration),
        "speakers": sorted(speakers) if speakers else [],
        "speaker_count": len(speakers),
        "language": language,
        "avg_segment_duration": round(total_duration / len(segments), 2) if segments else 0,
        "avg_words_per_segment": round(total_words / len(segments), 1) if segments else 0,
    }


def list_eligible_files(directory: str) -> dict:
    """List files in a directory that would be processed by transcribe batch.

    Uses the same should_be_processed() filter as the main pipeline.

    Returns:
        Dict with eligible files, skipped files, and counts.
    """
    from cli_anything.asr_transcribe.utils.asr_backend import ensure_project_importable
    ensure_project_importable()
    from utils.utilities import should_be_processed

    path = Path(directory)
    if not path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    all_files = sorted(path.glob("*"))
    eligible = []
    skipped = []

    for f in all_files:
        if not f.is_file():
            continue
        if should_be_processed(f):
            eligible.append({
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "size_human": _format_size(f.stat().st_size),
                "extension": f.suffix.lower(),
            })
        else:
            skipped.append(f.name)

    return {
        "directory": str(path.resolve()),
        "eligible_count": len(eligible),
        "skipped_count": len(skipped),
        "eligible": eligible,
        "skipped": skipped,
    }


def get_words_info(json_path: str) -> dict:
    """Get word-level detail from a WhisperX JSON file.

    Returns per-word timing, confidence scores, and aggregate stats.
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Extract word segments
    if isinstance(data, dict):
        word_segments = data.get("word_segments", [])
        # Fallback: collect from segment.words
        if not word_segments:
            for seg in data.get("segments", []):
                word_segments.extend(seg.get("words", []))
    elif isinstance(data, list):
        word_segments = []
        for seg in data:
            word_segments.extend(seg.get("words", []))
    else:
        return {"error": "Unexpected JSON structure"}

    if not word_segments:
        return {"word_count": 0, "message": "No word-level data found."}

    scores = [w.get("score", 0) for w in word_segments if w.get("score") is not None]
    durations = []
    for w in word_segments:
        s, e = w.get("start"), w.get("end")
        if s is not None and e is not None:
            durations.append(e - s)

    # Low-confidence words (score < 0.5)
    low_confidence = [
        {"word": w.get("word", ""), "score": round(w.get("score", 0), 3),
         "start": w.get("start"), "end": w.get("end")}
        for w in word_segments
        if w.get("score") is not None and w.get("score") < 0.5
    ]

    return {
        "word_count": len(word_segments),
        "avg_confidence": round(sum(scores) / len(scores), 3) if scores else None,
        "min_confidence": round(min(scores), 3) if scores else None,
        "max_confidence": round(max(scores), 3) if scores else None,
        "avg_word_duration": round(sum(durations) / len(durations), 3) if durations else None,
        "low_confidence_count": len(low_confidence),
        "low_confidence_words": low_confidence[:20],  # Cap at 20 for readability
    }


def get_speakers_info(json_path: str) -> dict:
    """Get speaker timing breakdown from a WhisperX JSON file.

    Returns per-speaker statistics: segment count, word count, total duration.
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", []) if isinstance(data, dict) else data

    if not segments:
        return {"speaker_count": 0, "speakers": {}}

    speaker_stats = {}
    for seg in segments:
        speaker = seg.get("speaker", "UNKNOWN")
        text = seg.get("text", "")
        duration = (seg.get("end", 0) - seg.get("start", 0))

        if speaker not in speaker_stats:
            speaker_stats[speaker] = {
                "segment_count": 0,
                "word_count": 0,
                "total_duration_seconds": 0.0,
                "character_count": 0,
            }

        speaker_stats[speaker]["segment_count"] += 1
        speaker_stats[speaker]["word_count"] += len(text.split())
        speaker_stats[speaker]["total_duration_seconds"] += duration
        speaker_stats[speaker]["character_count"] += len(text)

    # Round durations and add human-readable
    for speaker, stats in speaker_stats.items():
        stats["total_duration_seconds"] = round(stats["total_duration_seconds"], 2)
        stats["total_duration_human"] = _format_duration(stats["total_duration_seconds"])

    return {
        "speaker_count": len(speaker_stats),
        "speakers": speaker_stats,
    }


def get_language_info(json_path: str) -> dict:
    """Extract language metadata from a WhisperX JSON result.

    Returns detected language, translation status, model info.
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        return {"error": "Expected dict-format WhisperX output with metadata fields."}

    return {
        "language": data.get("language"),
        "source_language": data.get("source_language"),
        "output_language": data.get("output_language"),
        "requested_language": data.get("requested_language"),
        "translation_enabled": data.get("translation_enabled", False),
        "translation_target_language": data.get("translation_target_language"),
        "translation_output_language": data.get("translation_output_language"),
        "model_name": data.get("model_name"),
        "requested_model_name": data.get("requested_model_name"),
    }


def check_hallucinations(json_path: str) -> dict:
    """Check for potential hallucination indicators in WhisperX output.

    Looks for: very short segments with text, low-confidence words,
    repeated text patterns, and segments with no word-level alignment.

    Returns dict with warning count and details.
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", []) if isinstance(data, dict) else data

    warnings = []

    # Check 1: Segments with no words (alignment may have failed)
    for i, seg in enumerate(segments):
        words = seg.get("words", [])
        text = seg.get("text", "").strip()
        if text and not words:
            warnings.append({
                "type": "no_alignment",
                "segment_index": i,
                "text": text[:80],
                "detail": "Segment has text but no word-level alignment",
            })

    # Check 2: Very low average confidence words
    all_words = []
    for seg in segments:
        all_words.extend(seg.get("words", []))

    low_conf_words = [w for w in all_words if w.get("score") is not None and w.get("score") < 0.3]
    if low_conf_words:
        warnings.append({
            "type": "low_confidence",
            "count": len(low_conf_words),
            "examples": [{"word": w.get("word", ""), "score": round(w.get("score", 0), 3)}
                         for w in low_conf_words[:5]],
            "detail": f"{len(low_conf_words)} words with confidence < 0.3",
        })

    # Check 3: Repeated text (hallucination pattern)
    texts = [seg.get("text", "").strip() for seg in segments]
    seen = {}
    for text in texts:
        if len(text) > 10:  # Ignore very short segments
            seen[text] = seen.get(text, 0) + 1
    repeated = {t: c for t, c in seen.items() if c > 1}
    if repeated:
        warnings.append({
            "type": "repeated_text",
            "count": len(repeated),
            "examples": [{"text": t[:80], "occurrences": c} for t, c in list(repeated.items())[:5]],
            "detail": f"{len(repeated)} repeated text segments detected",
        })

    return {
        "warning_count": len(warnings),
        "warnings": warnings,
        "segment_count": len(segments),
        "word_count": len(all_words),
    }


def _format_size(num_bytes: int) -> str:
    """Human-readable file size."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    size = float(num_bytes)
    for unit in ["KB", "MB", "GB"]:
        size /= 1024.0
        if size < 1024.0:
            return f"{size:.1f} {unit}"
    return f"{size:.1f} TB"


def _format_duration(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
