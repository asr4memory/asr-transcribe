"""Tests for deterministic batching helpers: chunking, TOC validation, boundary fixing."""


# ---------------------------------------------------------------------------
# Helpers — build fake segments
# ---------------------------------------------------------------------------


def _seg(start, end, text="hello world"):
    return {"start": start, "end": end, "text": text}


def _segs_minutes(minutes, seg_duration=10.0):
    """Generate segments spanning `minutes` of audio, each `seg_duration` seconds."""
    segs = []
    t = 0.0
    total = minutes * 60
    while t < total:
        end = min(t + seg_duration, total)
        segs.append(_seg(t, end, f"segment at {t:.1f}"))
        t = end
    return segs


# ---------------------------------------------------------------------------
# Chunking tests
# ---------------------------------------------------------------------------


class TestChunkSegments:
    def test_empty_segments(self):
        from llm_workflows.chunking import chunk_segments

        assert chunk_segments([]) == []

    def test_single_segment(self):
        from llm_workflows.chunking import chunk_segments

        segs = [_seg(0.0, 5.0, "short")]
        chunks = chunk_segments(segs, target_minutes=12, max_chars=10000)
        assert len(chunks) == 1
        assert chunks[0]["chunk_id"] == 0
        assert chunks[0]["start"] == 0.0
        assert chunks[0]["end"] == 5.0
        assert chunks[0]["segments"] == segs

    def test_respects_time_limit(self):
        from llm_workflows.chunking import chunk_segments

        # 30 minutes of segments, 12-min target → should get ~3 chunks
        segs = _segs_minutes(30, seg_duration=30.0)
        chunks = chunk_segments(segs, target_minutes=12, max_chars=999999)
        assert len(chunks) >= 2
        # All segments accounted for
        all_segs = [s for c in chunks for s in c["segments"]]
        assert len(all_segs) == len(segs)

    def test_respects_char_limit(self):
        from llm_workflows.chunking import chunk_segments

        # Each segment ~20 chars, max_chars=100 → ~5 per chunk
        segs = [_seg(i * 10.0, (i + 1) * 10.0, "x" * 20) for i in range(20)]
        chunks = chunk_segments(segs, target_minutes=999, max_chars=100)
        assert len(chunks) >= 3
        for chunk in chunks:
            total_chars = sum(len(s["text"]) for s in chunk["segments"])
            # First segment might push over, but should be close
            assert total_chars <= 120  # 100 + one segment overshoot

    def test_never_splits_segment(self):
        from llm_workflows.chunking import chunk_segments

        segs = [_seg(0.0, 100.0, "a" * 50000)]  # One huge segment
        chunks = chunk_segments(segs, target_minutes=1, max_chars=100)
        assert len(chunks) == 1
        assert chunks[0]["segments"] == segs

    def test_chunk_ids_sequential(self):
        from llm_workflows.chunking import chunk_segments

        segs = _segs_minutes(60, seg_duration=30.0)
        chunks = chunk_segments(segs, target_minutes=12, max_chars=999999)
        for i, chunk in enumerate(chunks):
            assert chunk["chunk_id"] == i

    def test_preserves_segment_order(self):
        from llm_workflows.chunking import chunk_segments

        segs = _segs_minutes(30, seg_duration=15.0)
        chunks = chunk_segments(segs, target_minutes=12, max_chars=999999)
        all_starts = [s["start"] for c in chunks for s in c["segments"]]
        assert all_starts == sorted(all_starts)

    def test_no_segment_lost_or_duplicated(self):
        from llm_workflows.chunking import chunk_segments

        segs = _segs_minutes(45, seg_duration=20.0)
        chunks = chunk_segments(segs, target_minutes=10, max_chars=5000)
        all_segs = [s for c in chunks for s in c["segments"]]
        assert len(all_segs) == len(segs)
        # Check identity — same objects
        for orig, chunked in zip(segs, all_segs):
            assert orig is chunked


# ---------------------------------------------------------------------------
# should_use_batching tests
# ---------------------------------------------------------------------------


class TestShouldUseBatching:
    def test_short_transcript_single_pass(self):
        from llm_workflows.chunking import should_use_batching

        segs = [_seg(0, 60, "x" * 100)]
        assert should_use_batching(segs, threshold=25000) is False

    def test_long_transcript_batched(self):
        from llm_workflows.chunking import should_use_batching

        segs = [_seg(0, 60, "x" * 30000)]
        assert should_use_batching(segs, threshold=25000) is True

    def test_exact_threshold_not_batched(self):
        from llm_workflows.chunking import should_use_batching

        segs = [_seg(0, 60, "x" * 25000)]
        assert should_use_batching(segs, threshold=25000) is False


# ---------------------------------------------------------------------------
# TOC validation tests
# ---------------------------------------------------------------------------


def _toc_entry(level, title, start, end):
    return {"level": level, "title": title, "start": start, "end": end}


class TestValidateToc:
    def test_valid_toc(self):
        from llm_workflows.shared_synopsis import validate_toc

        entries = [
            _toc_entry("H1", "Intro", 0.0, 100.0),
            _toc_entry("H2", "Detail", 100.0, 200.0),
            _toc_entry("H1", "Conclusion", 200.0, 300.0),
        ]
        assert validate_toc(entries, 0.0, 300.0) is None

    def test_empty_toc(self):
        from llm_workflows.shared_synopsis import validate_toc

        assert validate_toc([], 0.0, 300.0) == "TOC is empty"

    def test_wrong_first_start(self):
        from llm_workflows.shared_synopsis import validate_toc

        entries = [_toc_entry("H1", "Late start", 10.0, 300.0)]
        error = validate_toc(entries, 0.0, 300.0)
        assert error is not None
        assert "first entry start" in error

    def test_wrong_last_end(self):
        from llm_workflows.shared_synopsis import validate_toc

        entries = [_toc_entry("H1", "Short", 0.0, 200.0)]
        error = validate_toc(entries, 0.0, 300.0)
        assert error is not None
        assert "last entry end" in error

    def test_gap_between_entries(self):
        from llm_workflows.shared_synopsis import validate_toc

        entries = [
            _toc_entry("H1", "A", 0.0, 100.0),
            _toc_entry("H1", "B", 150.0, 300.0),  # gap
        ]
        error = validate_toc(entries, 0.0, 300.0)
        assert error is not None
        assert "start" in error

    def test_invalid_level(self):
        from llm_workflows.shared_synopsis import validate_toc

        entries = [_toc_entry("H4", "Bad", 0.0, 300.0)]
        error = validate_toc(entries, 0.0, 300.0)
        assert error is not None
        assert "invalid level" in error

    def test_title_too_long(self):
        from llm_workflows.shared_synopsis import validate_toc

        entries = [_toc_entry("H1", "x" * 81, 0.0, 300.0)]
        error = validate_toc(entries, 0.0, 300.0)
        assert error is not None
        assert "80 characters" in error

    def test_start_not_less_than_end(self):
        from llm_workflows.shared_synopsis import validate_toc

        entries = [_toc_entry("H1", "Zero", 100.0, 100.0)]
        error = validate_toc(entries, 100.0, 100.0)
        assert error is not None

    def test_missing_field(self):
        from llm_workflows.shared_synopsis import validate_toc

        entries = [{"level": "H1", "start": 0.0, "end": 300.0}]  # no title
        error = validate_toc(entries, 0.0, 300.0)
        assert error is not None
        assert "missing field" in error


# ---------------------------------------------------------------------------
# TOC boundary fixing tests
# ---------------------------------------------------------------------------


class TestFixTocBoundaries:
    def test_fixes_first_and_last(self):
        from llm_workflows.shared_synopsis import fix_toc_boundaries

        entries = [
            _toc_entry("H1", "A", 5.0, 100.0),
            _toc_entry("H1", "B", 100.0, 295.0),
        ]
        fixed = fix_toc_boundaries(entries, 0.0, 300.0)
        assert fixed[0]["start"] == 0.0
        assert fixed[-1]["end"] == 300.0

    def test_closes_gaps(self):
        from llm_workflows.shared_synopsis import fix_toc_boundaries

        entries = [
            _toc_entry("H1", "A", 0.0, 100.0),
            _toc_entry("H1", "B", 150.0, 300.0),  # gap at 100-150
        ]
        fixed = fix_toc_boundaries(entries, 0.0, 300.0)
        assert fixed[1]["start"] == fixed[0]["end"]

    def test_removes_degenerate_entries(self):
        from llm_workflows.shared_synopsis import fix_toc_boundaries

        entries = [
            _toc_entry("H1", "A", 0.0, 100.0),
            _toc_entry("H1", "Tiny", 100.0, 100.0),  # degenerate
            _toc_entry("H1", "B", 100.0, 300.0),
        ]
        fixed = fix_toc_boundaries(entries, 0.0, 300.0)
        # Degenerate entry should be removed
        assert all(e["start"] < e["end"] for e in fixed)

    def test_empty_entries(self):
        from llm_workflows.shared_synopsis import fix_toc_boundaries

        assert fix_toc_boundaries([], 0.0, 300.0) == []

    def test_result_passes_validation(self):
        from llm_workflows.shared_synopsis import fix_toc_boundaries, validate_toc

        entries = [
            _toc_entry("H1", "A", 10.0, 90.0),
            _toc_entry("H1", "B", 120.0, 250.0),
            _toc_entry("H1", "C", 260.0, 280.0),
        ]
        fixed = fix_toc_boundaries(entries, 0.0, 300.0)
        assert validate_toc(fixed, 0.0, 300.0) is None


# ---------------------------------------------------------------------------
# TOC candidate merging tests
# ---------------------------------------------------------------------------


class TestCollectTocCandidates:
    def test_sorts_and_aligns(self):
        from llm_workflows.shared_synopsis import collect_toc_candidates

        synopses = [
            {
                "chunk_id": 0,
                "toc_entries": [
                    _toc_entry("H1", "A", 0.0, 100.0),
                ],
            },
            {
                "chunk_id": 1,
                "toc_entries": [
                    _toc_entry("H1", "B", 105.0, 200.0),  # small gap
                ],
            },
        ]
        candidates = collect_toc_candidates(synopses)
        assert len(candidates) == 2
        # Gap should be closed
        assert candidates[1]["start"] == candidates[0]["end"]

    def test_skips_error_synopses(self):
        from llm_workflows.shared_synopsis import collect_toc_candidates

        synopses = [
            {"_error": "parse failed"},
            {
                "chunk_id": 1,
                "toc_entries": [_toc_entry("H1", "A", 0.0, 100.0)],
            },
        ]
        candidates = collect_toc_candidates(synopses)
        assert len(candidates) == 1


# ---------------------------------------------------------------------------
# Synopsis aggregation helper tests
# ---------------------------------------------------------------------------


class TestCollectSummaryPoints:
    def test_collects_in_order(self):
        from llm_workflows.shared_synopsis import collect_summary_points

        synopses = [
            {"summary_points": ["point A", "point B"]},
            {"summary_points": ["point C"]},
        ]
        assert collect_summary_points(synopses) == ["point A", "point B", "point C"]

    def test_skips_errors(self):
        from llm_workflows.shared_synopsis import collect_summary_points

        synopses = [
            {"_error": "bad"},
            {"summary_points": ["ok"]},
        ]
        assert collect_summary_points(synopses) == ["ok"]


class TestCollectKeyEntities:
    def test_deduplicates_case_insensitive(self):
        from llm_workflows.shared_synopsis import collect_key_entities

        synopses = [
            {"key_entities": ["Berlin", "berlin", "BERLIN"]},
        ]
        assert collect_key_entities(synopses) == ["Berlin"]

    def test_preserves_first_seen_order(self):
        from llm_workflows.shared_synopsis import collect_key_entities

        synopses = [
            {"key_entities": ["Alice", "Bob"]},
            {"key_entities": ["Charlie", "alice"]},
        ]
        assert collect_key_entities(synopses) == ["Alice", "Bob", "Charlie"]
