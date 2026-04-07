"""
Chunking utility for splitting transcript segments into manageable windows.

Splits on segment boundaries — never inside a segment.
Respects both time-based and character-based limits.
"""

from config.app_config import get_config

config = get_config()


def chunk_segments(
    segments: list[dict],
    target_minutes: float | None = None,
    max_chars: int | None = None,
) -> list[dict]:
    """Split segments into chunks respecting segment boundaries.

    Each chunk is a dict with:
        chunk_id: int
        start: float (seconds)
        end: float (seconds)
        segments: list[dict]

    Args:
        segments: List of segment dicts with 'start', 'end', 'text' keys.
        target_minutes: Target chunk duration in minutes. Uses config default if None.
        max_chars: Soft cap on total text characters per chunk. Uses config default if None.

    Returns:
        List of chunk dicts.
    """
    if target_minutes is None:
        target_minutes = config["llm_meta"].get("chunk_target_minutes", 12)
    if max_chars is None:
        max_chars = config["llm_meta"].get("chunk_max_chars", 10000)

    target_seconds = target_minutes * 60

    if not segments:
        return []

    chunks = []
    current_segments = []
    current_chars = 0
    chunk_start = segments[0].get("start", 0.0)

    for seg in segments:
        seg_chars = len(seg.get("text", ""))
        seg_end = seg.get("end", seg.get("start", 0.0))
        elapsed = seg_end - chunk_start

        # Start new chunk if adding this segment would exceed limits,
        # but only if we already have at least one segment in current chunk
        if current_segments and (
            elapsed >= target_seconds or current_chars + seg_chars > max_chars
        ):
            chunks.append(
                {
                    "chunk_id": len(chunks),
                    "start": chunk_start,
                    "end": current_segments[-1].get(
                        "end", current_segments[-1].get("start", 0.0)
                    ),
                    "segments": current_segments,
                }
            )
            current_segments = []
            current_chars = 0
            chunk_start = seg.get("start", 0.0)

        current_segments.append(seg)
        current_chars += seg_chars

    # Final chunk
    if current_segments:
        chunks.append(
            {
                "chunk_id": len(chunks),
                "start": chunk_start,
                "end": current_segments[-1].get(
                    "end", current_segments[-1].get("start", 0.0)
                ),
                "segments": current_segments,
            }
        )

    return chunks


def total_text_chars(segments: list[dict]) -> int:
    """Total character count of all segment texts."""
    return sum(len(seg.get("text", "")) for seg in segments)


def should_use_batching(segments: list[dict], threshold: int | None = None) -> bool:
    """Check if transcript exceeds batching threshold.

    Args:
        segments: Transcript segments.
        threshold: Character threshold. Uses config default if None.
    """
    if threshold is None:
        threshold = config["llm_meta"].get("batching_threshold_chars", 25000)
    return total_text_chars(segments) > threshold
