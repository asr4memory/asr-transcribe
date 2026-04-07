"""
Shared synopsis utilities for the batched long-transcript pipeline.

- Synopsis generation (map step): one structured JSON per chunk
- TOC candidate merging and boundary alignment
- TOC validation (deterministic)
"""

import sys
from pathlib import Path

from subprocesses.llm_subprocess import generate, parse_json_output


# ---------------------------------------------------------------------------
# Synopsis prompt loading
# ---------------------------------------------------------------------------


def get_synopsis_prompt(language: str) -> str:
    base = Path(__file__).parent / "prompts" / "shared"
    filename = "chunk_synopsis_en.md" if language == "en" else "chunk_synopsis_de.md"
    return (base / filename).read_text()


# ---------------------------------------------------------------------------
# Synopsis generation (map step)
# ---------------------------------------------------------------------------


def build_chunk_user_prompt(chunk: dict) -> str:
    """Build tab-separated user prompt from a chunk's segments."""
    lines = ["start\tend\ttranscript"]
    for seg in chunk["segments"]:
        start = seg.get("start", 0)
        end = seg.get("end", start)
        text = seg.get("text", "")
        lines.append(f"{start}\t{end}\t{text}")
    return "\n".join(lines)


def generate_synopsis(
    llm,
    chunk: dict,
    language: str,
    model_cfg: dict,
    max_json_retries: int = 3,
) -> dict:
    """Generate a synopsis for a single chunk. Returns parsed JSON dict.

    On JSON parse failure after all retries, returns dict with _error key.
    """
    system_prompt = get_synopsis_prompt(language)
    user_prompt = build_chunk_user_prompt(chunk)

    max_tokens = 4096
    temperature = 0.3
    top_p = 0.9
    repeat_penalty = 1.1

    chunk_id = chunk["chunk_id"]

    for attempt in range(1, max_json_retries + 1):
        meta = {
            "task": "Chunk Synopsis",
            "lang": language,
            "chunk_id": chunk_id,
            "json_attempt": attempt,
        }
        output, finish_reason = generate(
            llm,
            system_prompt,
            user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            repeat_penalty=repeat_penalty,
            meta=meta,
        )
        parsed = parse_json_output(output)

        if isinstance(parsed, dict) and "_error" in parsed:
            if finish_reason == "length":
                parsed["_truncated"] = True
                print(
                    f"Synopsis chunk {chunk_id}: truncated, stopping",
                    file=sys.stderr,
                )
                return parsed
            if attempt < max_json_retries:
                print(
                    f"Synopsis chunk {chunk_id}: invalid JSON attempt {attempt}, retrying...",
                    file=sys.stderr,
                )
                continue
            print(
                f"Synopsis chunk {chunk_id}: invalid JSON after {max_json_retries} attempts",
                file=sys.stderr,
            )
            return parsed

        # Attach chunk metadata
        parsed["chunk_id"] = chunk_id
        parsed["start"] = chunk["start"]
        parsed["end"] = chunk["end"]
        print(
            f"Synopsis chunk {chunk_id}: done (attempt {attempt})",
            file=sys.stderr,
        )
        return parsed

    return {"_error": "unreachable"}


def generate_all_synopses(
    llm,
    chunks: list[dict],
    language: str,
    model_cfg: dict,
) -> list[dict]:
    """Generate synopses for all chunks sequentially. Returns list of synopsis dicts."""
    synopses = []
    for chunk in chunks:
        synopsis = generate_synopsis(llm, chunk, language, model_cfg)
        synopses.append(synopsis)
    return synopses


# ---------------------------------------------------------------------------
# TOC candidate merging and boundary alignment
# ---------------------------------------------------------------------------


def collect_toc_candidates(synopses: list[dict]) -> list[dict]:
    """Collect all toc_entries from synopses, sorted by start time.

    Also performs boundary alignment: sets each entry's start equal to
    the previous entry's end (no gaps, no overlaps).
    """
    candidates = []
    for synopsis in synopses:
        if isinstance(synopsis, dict) and "_error" not in synopsis:
            for entry in synopsis.get("toc_entries", []):
                candidates.append(entry)

    # Sort by start time
    candidates.sort(key=lambda e: e.get("start", 0))

    # Boundary alignment: close gaps
    for i in range(1, len(candidates)):
        candidates[i]["start"] = candidates[i - 1]["end"]

    return candidates


def fix_toc_boundaries(
    entries: list[dict],
    transcript_start: float,
    transcript_end: float,
) -> list[dict]:
    """Programmatic boundary fixes for a TOC entry list.

    Ensures:
    - First entry starts at transcript_start
    - Last entry ends at transcript_end
    - No gaps between consecutive entries
    - start < end for every entry
    """
    if not entries:
        return entries

    # Sort by start
    entries.sort(key=lambda e: e.get("start", 0))

    # Fix first/last boundaries
    entries[0]["start"] = transcript_start
    entries[-1]["end"] = transcript_end

    # Close gaps
    for i in range(1, len(entries)):
        entries[i]["start"] = entries[i - 1]["end"]

    # Ensure start < end (remove degenerate entries)
    entries = [e for e in entries if e["start"] < e["end"]]

    # Re-fix last boundary after potential removal
    if entries:
        entries[-1]["end"] = transcript_end

    return entries


# ---------------------------------------------------------------------------
# TOC validation (deterministic)
# ---------------------------------------------------------------------------

VALID_LEVELS = {"H1", "H2", "H3"}


def validate_toc(
    entries: list[dict],
    transcript_start: float,
    transcript_end: float,
) -> str | None:
    """Validate a final TOC entry list.

    Returns None if valid, or an error message string if invalid.
    """
    if not entries:
        return "TOC is empty"

    if not isinstance(entries, list):
        return "TOC is not a list"

    # Check first/last boundaries
    if abs(entries[0]["start"] - transcript_start) > 0.01:
        return f"first entry start {entries[0]['start']} != transcript start {transcript_start}"

    if abs(entries[-1]["end"] - transcript_end) > 0.01:
        return f"last entry end {entries[-1]['end']} != transcript end {transcript_end}"

    for i, entry in enumerate(entries):
        # Required fields
        for field in ("level", "title", "start", "end"):
            if field not in entry:
                return f"entry {i}: missing field '{field}'"

        # Level check
        if entry["level"] not in VALID_LEVELS:
            return f"entry {i}: invalid level '{entry['level']}'"

        # Title length
        if len(entry.get("title", "")) > 80:
            return f"entry {i}: title exceeds 80 characters"

        # start < end
        if entry["start"] >= entry["end"]:
            return f"entry {i}: start ({entry['start']}) >= end ({entry['end']})"

        # Chronological order / no gaps
        if i > 0:
            prev_end = entries[i - 1]["end"]
            if abs(entry["start"] - prev_end) > 0.01:
                return (
                    f"entry {i}: start ({entry['start']}) != previous end ({prev_end})"
                )

    return None


# ---------------------------------------------------------------------------
# Synopsis aggregation helpers
# ---------------------------------------------------------------------------


def collect_summary_points(synopses: list[dict]) -> list[str]:
    """Collect all summary_points from synopses in order."""
    points = []
    for synopsis in synopses:
        if isinstance(synopsis, dict) and "_error" not in synopsis:
            points.extend(synopsis.get("summary_points", []))
    return points


def collect_key_entities(synopses: list[dict]) -> list[str]:
    """Collect deduplicated key_entities from all synopses, preserving first-seen order."""
    seen = set()
    entities = []
    for synopsis in synopses:
        if isinstance(synopsis, dict) and "_error" not in synopsis:
            for entity in synopsis.get("key_entities", []):
                lower = entity.lower()
                if lower not in seen:
                    seen.add(lower)
                    entities.append(entity)
    return entities
