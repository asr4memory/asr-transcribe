"""Unit tests for cli-anything-asr-transcribe core modules.

All tests use synthetic data and do not require WhisperX, CUDA, or external models.
"""

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────

SAMPLE_SEGMENTS = [
    {
        "start": 0.0,
        "end": 3.5,
        "text": "Hello, this is a test transcription.",
        "speaker": "SPEAKER_00",
        "words": [
            {"word": "Hello,", "start": 0.0, "end": 0.5, "score": 0.95},
            {"word": "this", "start": 0.6, "end": 0.8, "score": 0.92},
            {"word": "is", "start": 0.9, "end": 1.0, "score": 0.90},
            {"word": "a", "start": 1.1, "end": 1.2, "score": 0.88},
            {"word": "test", "start": 1.3, "end": 1.6, "score": 0.94},
            {"word": "transcription.", "start": 1.7, "end": 3.5, "score": 0.91},
        ],
    },
    {
        "start": 4.0,
        "end": 8.2,
        "text": "We are testing the export pipeline.",
        "speaker": "SPEAKER_01",
        "words": [
            {"word": "We", "start": 4.0, "end": 4.2, "score": 0.93},
            {"word": "are", "start": 4.3, "end": 4.5, "score": 0.91},
            {"word": "testing", "start": 4.6, "end": 5.0, "score": 0.89},
            {"word": "the", "start": 5.1, "end": 5.2, "score": 0.90},
            {"word": "export", "start": 5.3, "end": 5.7, "score": 0.92},
            {"word": "pipeline.", "start": 5.8, "end": 8.2, "score": 0.88},
        ],
    },
    {
        "start": 9.0,
        "end": 13.5,
        "text": "This is the third segment with more content.",
        "speaker": "SPEAKER_00",
        "words": [
            {"word": "This", "start": 9.0, "end": 9.2, "score": 0.95},
            {"word": "is", "start": 9.3, "end": 9.4, "score": 0.94},
            {"word": "the", "start": 9.5, "end": 9.6, "score": 0.92},
            {"word": "third", "start": 9.7, "end": 10.0, "score": 0.90},
            {"word": "segment", "start": 10.1, "end": 10.5, "score": 0.93},
            {"word": "with", "start": 10.6, "end": 10.8, "score": 0.91},
            {"word": "more", "start": 10.9, "end": 11.2, "score": 0.89},
            {"word": "content.", "start": 11.3, "end": 13.5, "score": 0.87},
        ],
    },
]

SAMPLE_WHISPERX_OUTPUT = {
    "segments": SAMPLE_SEGMENTS,
    "word_segments": [w for seg in SAMPLE_SEGMENTS for w in seg["words"]],
    "language": "en",
}


@pytest.fixture
def tmp_dir():
    """Create a temporary directory that is cleaned up after the test."""
    d = tempfile.mkdtemp(prefix="cli_asr_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_json(tmp_dir):
    """Write sample WhisperX output to a JSON file and return the path."""
    path = os.path.join(tmp_dir, "test_segments.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_WHISPERX_OUTPUT, f, indent=2)
    return path


@pytest.fixture
def sample_bag(tmp_dir):
    """Create a minimal valid BagIt directory and return its path."""
    bag_dir = os.path.join(tmp_dir, "test_bag")
    os.makedirs(bag_dir)

    # bagit.txt
    bagit_path = os.path.join(bag_dir, "bagit.txt")
    with open(bagit_path, "w", encoding="utf-8") as f:
        f.write("BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n")

    # data directory with a sample file
    data_dir = os.path.join(bag_dir, "data")
    transcripts_dir = os.path.join(data_dir, "transcripts")
    os.makedirs(transcripts_dir)

    payload_file = os.path.join(transcripts_dir, "test.txt")
    with open(payload_file, "w", encoding="utf-8") as f:
        f.write("Test transcript content.\n")

    # bag-info.txt
    bag_info_path = os.path.join(bag_dir, "bag-info.txt")
    with open(bag_info_path, "w", encoding="utf-8") as f:
        f.write("Source-Filename: test.wav\n")
        f.write("Model: large-v3\n")
        f.write("Language: en\n")

    # manifest-sha512.txt
    digest = hashlib.sha512()
    with open(payload_file, "rb") as f:
        digest.update(f.read())
    checksum = digest.hexdigest()

    manifest_path = os.path.join(bag_dir, "manifest-sha512.txt")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(f"{checksum}  data/transcripts/test.txt\n")

    return bag_dir


# ── audio_info tests ──────────────────────────────────────────────────


class TestAudioInfo:
    def test_get_segments_info_missing_file(self):
        from cli_anything.asr_transcribe.core.audio_info import get_segments_info

        with pytest.raises(FileNotFoundError):
            get_segments_info("/nonexistent/file.json")

    def test_get_segments_info_basic(self, sample_json):
        from cli_anything.asr_transcribe.core.audio_info import get_segments_info

        result = get_segments_info(sample_json)
        assert result["segment_count"] == 3
        assert result["total_words"] > 0
        assert result["language"] == "en"
        assert result["speaker_count"] == 2

    def test_get_segments_info_with_speakers(self, sample_json):
        from cli_anything.asr_transcribe.core.audio_info import get_segments_info

        result = get_segments_info(sample_json)
        assert "SPEAKER_00" in result["speakers"]
        assert "SPEAKER_01" in result["speakers"]
        assert result["speaker_count"] == 2

    def test_get_segments_info_list_format(self, tmp_dir):
        from cli_anything.asr_transcribe.core.audio_info import get_segments_info

        path = os.path.join(tmp_dir, "list.json")
        with open(path, "w") as f:
            json.dump(SAMPLE_SEGMENTS, f)

        result = get_segments_info(path)
        assert result["segment_count"] == 3
        assert result["language"] is None

    def test_get_segments_info_empty(self, tmp_dir):
        from cli_anything.asr_transcribe.core.audio_info import get_segments_info

        path = os.path.join(tmp_dir, "empty.json")
        with open(path, "w") as f:
            json.dump({"segments": [], "word_segments": []}, f)

        result = get_segments_info(path)
        assert result["segment_count"] == 0

    def test_format_duration(self):
        from cli_anything.asr_transcribe.core.audio_info import _format_duration

        assert _format_duration(0) == "00:00:00"
        assert _format_duration(65) == "00:01:05"
        assert _format_duration(3661) == "01:01:01"

    def test_format_size(self):
        from cli_anything.asr_transcribe.core.audio_info import _format_size

        assert _format_size(500) == "500 B"
        assert "KB" in _format_size(2048)
        assert "MB" in _format_size(2 * 1024 * 1024)

    def test_get_audio_info_missing_file(self):
        from cli_anything.asr_transcribe.core.audio_info import get_audio_info

        with pytest.raises(FileNotFoundError):
            get_audio_info("/nonexistent/audio.wav")

    def test_get_segments_info_duration(self, sample_json):
        from cli_anything.asr_transcribe.core.audio_info import get_segments_info

        result = get_segments_info(sample_json)
        assert result["total_duration_seconds"] == 13.5
        assert result["avg_segment_duration"] > 0


# ── export tests ──────────────────────────────────────────────────────


class TestExport:
    def test_list_formats_returns_all(self):
        from cli_anything.asr_transcribe.core.export import list_formats

        formats = list_formats()
        assert len(formats) >= 20
        assert "vtt" in formats
        assert "srt" in formats
        assert "tei_xml" in formats

    def test_list_formats_has_descriptions(self):
        from cli_anything.asr_transcribe.core.export import list_formats

        for name, desc in list_formats().items():
            assert isinstance(desc, str) and len(desc) > 0, f"Empty description for {name}"

    def test_export_convert_missing_file(self):
        from cli_anything.asr_transcribe.core.export import export_convert

        with pytest.raises(FileNotFoundError):
            export_convert("/nonexistent/file.json")

    def test_export_convert_unknown_format(self, sample_json):
        from cli_anything.asr_transcribe.core.export import export_convert

        result = export_convert(sample_json, formats=["nonexistent_format"])
        assert "error" in result

    def test_export_convert_vtt(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.export import export_convert

        result = export_convert(sample_json, formats=["vtt"], output_dir=tmp_dir)
        assert "vtt" in result["exported"]
        vtt_path = os.path.join(tmp_dir, "test_segments.vtt")
        assert os.path.exists(vtt_path)
        content = open(vtt_path, encoding="utf-8").read()
        assert "WEBVTT" in content

    def test_export_convert_srt(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.export import export_convert

        result = export_convert(sample_json, formats=["srt"], output_dir=tmp_dir)
        assert "srt" in result["exported"]
        srt_path = os.path.join(tmp_dir, "test_segments.srt")
        assert os.path.exists(srt_path)
        content = open(srt_path, encoding="utf-8").read()
        assert "-->" in content

    def test_export_convert_txt(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.export import export_convert

        result = export_convert(sample_json, formats=["txt"], output_dir=tmp_dir)
        assert "txt" in result["exported"]
        txt_path = os.path.join(tmp_dir, "test_segments.txt")
        assert os.path.exists(txt_path)
        content = open(txt_path, encoding="utf-8").read()
        assert "Hello" in content

    def test_export_convert_json(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.export import export_convert

        result = export_convert(sample_json, formats=["json"], output_dir=tmp_dir)
        assert "json" in result["exported"]

    def test_export_convert_csv(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.export import export_convert

        result = export_convert(sample_json, formats=["csv"], output_dir=tmp_dir)
        assert "csv" in result["exported"]

    def test_export_convert_multiple(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.export import export_convert

        result = export_convert(
            sample_json, formats=["vtt", "srt", "txt", "json"], output_dir=tmp_dir
        )
        assert len(result["exported"]) == 4
        assert len(result["errors"]) == 0


# ── bag_manager tests ─────────────────────────────────────────────────


class TestBagManager:
    def test_validate_bag_missing_path(self):
        from cli_anything.asr_transcribe.core.bag_manager import validate_bag

        result = validate_bag("/nonexistent/bag")
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_validate_bag_valid(self, sample_bag):
        from cli_anything.asr_transcribe.core.bag_manager import validate_bag

        result = validate_bag(sample_bag)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_bag_missing_manifest(self, sample_bag):
        from cli_anything.asr_transcribe.core.bag_manager import validate_bag

        os.remove(os.path.join(sample_bag, "manifest-sha512.txt"))
        result = validate_bag(sample_bag)
        assert result["valid"] is False
        assert any("manifest" in e.lower() for e in result["errors"])

    def test_validate_bag_checksum_mismatch(self, sample_bag):
        from cli_anything.asr_transcribe.core.bag_manager import validate_bag

        # Corrupt the payload file
        payload = os.path.join(sample_bag, "data", "transcripts", "test.txt")
        with open(payload, "w") as f:
            f.write("CORRUPTED CONTENT")

        result = validate_bag(sample_bag)
        assert result["valid"] is False
        assert any("checksum" in e.lower() for e in result["errors"])

    def test_get_bag_info(self, sample_bag):
        from cli_anything.asr_transcribe.core.bag_manager import get_bag_info

        result = get_bag_info(sample_bag)
        assert result["Source-Filename"] == "test.wav"
        assert result["Model"] == "large-v3"
        assert result["Language"] == "en"

    def test_get_bag_info_missing(self, tmp_dir):
        from cli_anything.asr_transcribe.core.bag_manager import get_bag_info

        with pytest.raises(FileNotFoundError):
            get_bag_info(tmp_dir)

    def test_sha512_computation(self, tmp_dir):
        from cli_anything.asr_transcribe.core.bag_manager import _sha512

        test_file = Path(tmp_dir) / "test.txt"
        test_file.write_text("hello world\n", encoding="utf-8")

        result = _sha512(test_file)
        expected = hashlib.sha512(b"hello world\n").hexdigest()
        assert result == expected


# ── session tests ─────────────────────────────────────────────────────


class TestSession:
    def test_session_record(self):
        from cli_anything.asr_transcribe.core.session import Session

        session = Session()
        session.record("config show", {"status": "ok"})
        session.record("export formats")

        assert len(session.history) == 2
        assert session.history[0]["command"] == "config show"

    def test_session_to_dict(self):
        from cli_anything.asr_transcribe.core.session import Session

        session = Session()
        session.last_json_path = "/tmp/test.json"
        result = session.to_dict()

        assert result["last_json_path"] == "/tmp/test.json"
        assert result["history_count"] == 0


# ── config_manager tests (without modifying real config) ──────────────


class TestConfigManager:
    def test_mask_sensitive_hides_tokens(self):
        from cli_anything.asr_transcribe.core.config_manager import _mask_sensitive

        config = {
            "whisper": {"model": "large-v3", "hf_token": "secret123"},
            "email": {"password": "pass", "from": "a@b.com"},
        }
        masked = _mask_sensitive(config)
        assert masked["whisper"]["hf_token"] == "***"
        assert masked["email"]["password"] == "***"
        assert masked["whisper"]["model"] == "large-v3"
        assert masked["email"]["from"] == "a@b.com"

    def test_mask_sensitive_empty_values(self):
        from cli_anything.asr_transcribe.core.config_manager import _mask_sensitive

        config = {"whisper": {"hf_token": None, "api_key": ""}}
        masked = _mask_sensitive(config)
        assert masked["whisper"]["hf_token"] is None
        assert masked["whisper"]["api_key"] == ""


# ── process tests (using project's post_processing) ───────────────────


class TestProcess:
    def test_process_segments_missing_file(self):
        from cli_anything.asr_transcribe.core.process import process_segments

        with pytest.raises(FileNotFoundError):
            process_segments("/nonexistent/file.json")

    def test_process_segments_basic(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.process import process_segments

        output_path = os.path.join(tmp_dir, "processed.json")
        result = process_segments(sample_json, output_path)

        assert result["segments_before"] == 3
        assert result["segments_after"] > 0
        assert os.path.exists(output_path)

        with open(output_path) as f:
            data = json.load(f)
        assert "segments" in data
        assert "word_segments" in data

    def test_buffer_step(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.process import buffer_step

        output_path = os.path.join(tmp_dir, "buffered.json")
        result = buffer_step(sample_json, output_path)

        assert result["segments_before"] == 3
        assert result["segment_count"] > 0
        assert os.path.exists(output_path)

    def test_uppercase_step(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.process import uppercase_step

        output_path = os.path.join(tmp_dir, "uppercased.json")
        result = uppercase_step(sample_json, output_path)

        assert result["segment_count"] > 0
        assert os.path.exists(output_path)

    def test_split_step(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.process import split_step

        output_path = os.path.join(tmp_dir, "split.json")
        result = split_step(sample_json, output_path)

        assert result["segments_before"] == 3
        assert result["segment_count"] > 0
        assert os.path.exists(output_path)

    def test_buffer_step_missing_file(self):
        from cli_anything.asr_transcribe.core.process import buffer_step

        with pytest.raises(FileNotFoundError):
            buffer_step("/nonexistent/file.json")


# ── audio_info deep inspection tests ─────────────────────────────────


class TestAudioInfoDeep:
    def test_get_words_info_basic(self, sample_json):
        from cli_anything.asr_transcribe.core.audio_info import get_words_info

        result = get_words_info(sample_json)
        assert result["word_count"] == 20
        assert result["avg_confidence"] is not None
        assert result["avg_confidence"] > 0.8
        assert result["low_confidence_count"] == 0

    def test_get_words_info_missing_file(self):
        from cli_anything.asr_transcribe.core.audio_info import get_words_info

        with pytest.raises(FileNotFoundError):
            get_words_info("/nonexistent/file.json")

    def test_get_words_info_low_confidence(self, tmp_dir):
        from cli_anything.asr_transcribe.core.audio_info import get_words_info

        data = {
            "segments": [{
                "start": 0.0, "end": 2.0, "text": "test low",
                "words": [
                    {"word": "test", "start": 0.0, "end": 1.0, "score": 0.2},
                    {"word": "low", "start": 1.0, "end": 2.0, "score": 0.3},
                ],
            }],
        }
        path = os.path.join(tmp_dir, "low_conf.json")
        with open(path, "w") as f:
            json.dump(data, f)

        result = get_words_info(path)
        assert result["low_confidence_count"] == 2
        assert result["min_confidence"] <= 0.3

    def test_get_speakers_info_basic(self, sample_json):
        from cli_anything.asr_transcribe.core.audio_info import get_speakers_info

        result = get_speakers_info(sample_json)
        assert result["speaker_count"] == 2
        assert "SPEAKER_00" in result["speakers"]
        assert "SPEAKER_01" in result["speakers"]
        assert result["speakers"]["SPEAKER_00"]["segment_count"] == 2
        assert result["speakers"]["SPEAKER_01"]["segment_count"] == 1

    def test_get_speakers_info_empty(self, tmp_dir):
        from cli_anything.asr_transcribe.core.audio_info import get_speakers_info

        path = os.path.join(tmp_dir, "empty.json")
        with open(path, "w") as f:
            json.dump({"segments": []}, f)

        result = get_speakers_info(path)
        assert result["speaker_count"] == 0

    def test_get_language_info(self, tmp_dir):
        from cli_anything.asr_transcribe.core.audio_info import get_language_info

        data = {
            "language": "de",
            "source_language": "de",
            "model_name": "large-v3",
            "translation_enabled": True,
            "translation_target_language": "en",
        }
        path = os.path.join(tmp_dir, "lang.json")
        with open(path, "w") as f:
            json.dump(data, f)

        result = get_language_info(path)
        assert result["language"] == "de"
        assert result["model_name"] == "large-v3"
        assert result["translation_enabled"] is True
        assert result["translation_target_language"] == "en"

    def test_get_language_info_minimal(self, sample_json):
        from cli_anything.asr_transcribe.core.audio_info import get_language_info

        result = get_language_info(sample_json)
        assert result["language"] == "en"

    def test_check_hallucinations_clean(self, sample_json):
        from cli_anything.asr_transcribe.core.audio_info import check_hallucinations

        result = check_hallucinations(sample_json)
        assert result["warning_count"] == 0
        assert result["segment_count"] == 3
        assert result["word_count"] == 20

    def test_check_hallucinations_repeated_text(self, tmp_dir):
        from cli_anything.asr_transcribe.core.audio_info import check_hallucinations

        segments = [
            {"start": 0.0, "end": 2.0, "text": "This is a repeated segment text.", "words": []},
            {"start": 2.0, "end": 4.0, "text": "This is a repeated segment text.", "words": []},
            {"start": 4.0, "end": 6.0, "text": "Something unique here.", "words": []},
        ]
        path = os.path.join(tmp_dir, "halluc.json")
        with open(path, "w") as f:
            json.dump({"segments": segments}, f)

        result = check_hallucinations(path)
        assert result["warning_count"] > 0
        types = [w["type"] for w in result["warnings"]]
        assert "repeated_text" in types

    def test_check_hallucinations_no_alignment(self, tmp_dir):
        from cli_anything.asr_transcribe.core.audio_info import check_hallucinations

        segments = [
            {"start": 0.0, "end": 2.0, "text": "Text with no word alignment"},
        ]
        path = os.path.join(tmp_dir, "no_align.json")
        with open(path, "w") as f:
            json.dump({"segments": segments}, f)

        result = check_hallucinations(path)
        types = [w["type"] for w in result["warnings"]]
        assert "no_alignment" in types


# ── config_manager extended tests ────────────────────────────────────


class TestConfigManagerExtended:
    def test_coerce_value_bool(self):
        from cli_anything.asr_transcribe.core.config_manager import _coerce_value

        assert _coerce_value("true") is True
        assert _coerce_value("True") is True
        assert _coerce_value("false") is False
        assert _coerce_value("False") is False

    def test_coerce_value_none(self):
        from cli_anything.asr_transcribe.core.config_manager import _coerce_value

        assert _coerce_value("none") is None
        assert _coerce_value("null") is None

    def test_coerce_value_numbers(self):
        from cli_anything.asr_transcribe.core.config_manager import _coerce_value

        assert _coerce_value("42") == 42
        assert _coerce_value("3.14") == 3.14
        assert _coerce_value("hello") == "hello"

    def test_coerce_value_list(self):
        from cli_anything.asr_transcribe.core.config_manager import _coerce_value

        assert _coerce_value('["a", "b"]') == ["a", "b"]


# ── bag_manager extended tests ───────────────────────────────────────


class TestBagManagerExtended:
    def test_create_bag_empty(self, tmp_dir):
        from cli_anything.asr_transcribe.core.bag_manager import create_bag

        bag_path = os.path.join(tmp_dir, "new_bag")
        result = create_bag(bag_path)

        assert result["created"] is True
        assert result["file_count"] == 0
        assert os.path.exists(os.path.join(bag_path, "bagit.txt"))
        assert os.path.exists(os.path.join(bag_path, "data", "transcripts"))

    def test_create_bag_with_files(self, tmp_dir):
        from cli_anything.asr_transcribe.core.bag_manager import create_bag

        # Create a source file
        src_file = os.path.join(tmp_dir, "source.txt")
        with open(src_file, "w") as f:
            f.write("Source content\n")

        bag_path = os.path.join(tmp_dir, "bag_with_files")
        result = create_bag(bag_path, files=[src_file], metadata={"Model": "large-v3"})

        assert result["created"] is True
        assert result["file_count"] == 1
        assert os.path.exists(os.path.join(bag_path, "data", "transcripts", "source.txt"))
        assert os.path.exists(os.path.join(bag_path, "manifest-sha512.txt"))

    def test_create_bag_already_exists(self, tmp_dir):
        from cli_anything.asr_transcribe.core.bag_manager import create_bag

        bag_path = os.path.join(tmp_dir, "existing_bag")
        os.makedirs(bag_path)

        result = create_bag(bag_path)
        assert result["created"] is False

    def test_create_and_validate(self, tmp_dir):
        from cli_anything.asr_transcribe.core.bag_manager import create_bag, validate_bag

        src_file = os.path.join(tmp_dir, "test.txt")
        with open(src_file, "w") as f:
            f.write("Test content\n")

        bag_path = os.path.join(tmp_dir, "valid_bag")
        create_bag(bag_path, files=[src_file])

        result = validate_bag(bag_path)
        assert result["valid"] is True


# ── llm_tasks: chunk preview tests ──────────────────────────────────


class TestChunkPreview:
    def test_chunk_preview_basic(self, sample_json):
        from cli_anything.asr_transcribe.core.llm_tasks import run_chunk_preview

        result = run_chunk_preview(sample_json)
        assert result["status"] == "success"
        assert result["total_segments"] == 3
        assert result["total_chars"] > 0
        assert isinstance(result["would_use_batching"], bool)
        assert result["chunk_count"] >= 1
        assert len(result["chunks"]) == result["chunk_count"]

    def test_chunk_preview_short_transcript_no_batching(self, sample_json):
        from cli_anything.asr_transcribe.core.llm_tasks import run_chunk_preview

        result = run_chunk_preview(sample_json)
        # Our sample data is tiny — well below 25000 chars
        assert result["would_use_batching"] is False

    def test_chunk_preview_custom_params(self, sample_json):
        from cli_anything.asr_transcribe.core.llm_tasks import run_chunk_preview

        # Very small limits to force multiple chunks
        result = run_chunk_preview(sample_json, target_minutes=0.01, max_chars=20)
        assert result["status"] == "success"
        assert result["chunk_count"] >= 2
        assert result["target_minutes"] == 0.01
        assert result["max_chars_per_chunk"] == 20

    def test_chunk_preview_chunk_details(self, sample_json):
        from cli_anything.asr_transcribe.core.llm_tasks import run_chunk_preview

        result = run_chunk_preview(sample_json, target_minutes=0.01, max_chars=20)
        for chunk in result["chunks"]:
            assert "chunk_id" in chunk
            assert "start" in chunk
            assert "end" in chunk
            assert "duration_sec" in chunk
            assert "segment_count" in chunk
            assert "char_count" in chunk
            assert chunk["segment_count"] >= 1
            assert chunk["char_count"] > 0

    def test_chunk_preview_missing_file(self):
        from cli_anything.asr_transcribe.core.llm_tasks import run_chunk_preview

        with pytest.raises(FileNotFoundError):
            run_chunk_preview("/nonexistent/file.json")

    def test_chunk_preview_empty_segments(self, tmp_dir):
        from cli_anything.asr_transcribe.core.llm_tasks import run_chunk_preview

        path = os.path.join(tmp_dir, "empty.json")
        with open(path, "w") as f:
            json.dump({"segments": []}, f)

        result = run_chunk_preview(path)
        assert result["status"] == "error"

    def test_chunk_preview_no_segments_lost(self, sample_json):
        from cli_anything.asr_transcribe.core.llm_tasks import run_chunk_preview

        result = run_chunk_preview(sample_json, target_minutes=0.01, max_chars=20)
        total_segments_in_chunks = sum(c["segment_count"] for c in result["chunks"])
        assert total_segments_in_chunks == result["total_segments"]

    def test_chunk_preview_list_format(self, tmp_dir):
        from cli_anything.asr_transcribe.core.llm_tasks import run_chunk_preview

        path = os.path.join(tmp_dir, "list.json")
        with open(path, "w") as f:
            json.dump(SAMPLE_SEGMENTS, f)

        result = run_chunk_preview(path)
        assert result["status"] == "success"
        assert result["total_segments"] == 3


# ── llm_tasks: models info tests ────────────────────────────────────


class TestModelsInfo:
    def test_models_info_returns_structure(self):
        from cli_anything.asr_transcribe.core.llm_tasks import run_models_info

        result = run_models_info()
        assert result["status"] == "success"
        assert "models" in result
        assert "summarization" in result["models"]
        assert "toc" in result["models"]
        assert "llm_meta" in result

    def test_models_info_model_fields(self):
        from cli_anything.asr_transcribe.core.llm_tasks import run_models_info

        result = run_models_info()
        for name in ("summarization", "toc"):
            model = result["models"][name]
            assert "model_path" in model
            assert "model_exists" in model
            assert "config_path" in model
            assert "config_loaded" in model
            assert "profile_count" in model
            assert "profiles" in model
            assert isinstance(model["profiles"], list)

    def test_models_info_llm_meta_fields(self):
        from cli_anything.asr_transcribe.core.llm_tasks import run_models_info

        result = run_models_info()
        meta = result["llm_meta"]
        assert "use_summarization" in meta
        assert "use_toc" in meta
        assert "llm_languages" in meta
        assert "batching_threshold_chars" in meta
        assert "chunk_target_minutes" in meta
        assert "chunk_max_chars" in meta
        assert "emit_debug_artifacts" in meta


# ── llm_tasks: validate-toc tests ───────────────────────────────────


VALID_TOC = [
    {"level": "H1", "title": "Introduction", "start": 0.0, "end": 5.0},
    {"level": "H2", "title": "Details", "start": 5.0, "end": 10.0},
    {"level": "H1", "title": "Conclusion", "start": 10.0, "end": 15.0},
]


class TestValidateToc:
    def test_validate_toc_valid(self, tmp_dir):
        from cli_anything.asr_transcribe.core.llm_tasks import run_validate_toc

        toc_path = os.path.join(tmp_dir, "toc.json")
        with open(toc_path, "w") as f:
            json.dump(VALID_TOC, f)

        result = run_validate_toc(toc_path)
        assert result["status"] == "success"
        assert result["valid"] is True
        assert result["entry_count"] == 3
        assert result["boundary_source"] == "toc_self"

    def test_validate_toc_with_transcript(self, tmp_dir, sample_json):
        from cli_anything.asr_transcribe.core.llm_tasks import run_validate_toc

        # Align TOC to sample transcript boundaries (0.0 - 13.5)
        toc = [
            {"level": "H1", "title": "Part One", "start": 0.0, "end": 8.2},
            {"level": "H1", "title": "Part Two", "start": 8.2, "end": 13.5},
        ]
        toc_path = os.path.join(tmp_dir, "toc.json")
        with open(toc_path, "w") as f:
            json.dump(toc, f)

        result = run_validate_toc(toc_path, transcript_json=sample_json)
        assert result["valid"] is True
        assert result["boundary_source"] == "transcript"
        assert result["transcript_start"] == 0.0
        assert result["transcript_end"] == 13.5

    def test_validate_toc_boundary_mismatch(self, tmp_dir, sample_json):
        from cli_anything.asr_transcribe.core.llm_tasks import run_validate_toc

        # TOC ends at 10.0 but transcript ends at 13.5
        toc = [
            {"level": "H1", "title": "Part One", "start": 0.0, "end": 10.0},
        ]
        toc_path = os.path.join(tmp_dir, "toc.json")
        with open(toc_path, "w") as f:
            json.dump(toc, f)

        result = run_validate_toc(toc_path, transcript_json=sample_json)
        assert result["valid"] is False
        assert "transcript end" in result["error"]

    def test_validate_toc_empty(self, tmp_dir):
        from cli_anything.asr_transcribe.core.llm_tasks import run_validate_toc

        toc_path = os.path.join(tmp_dir, "empty.json")
        with open(toc_path, "w") as f:
            json.dump([], f)

        result = run_validate_toc(toc_path)
        assert result["valid"] is False

    def test_validate_toc_not_list(self, tmp_dir):
        from cli_anything.asr_transcribe.core.llm_tasks import run_validate_toc

        toc_path = os.path.join(tmp_dir, "bad.json")
        with open(toc_path, "w") as f:
            json.dump({"title": "not a list"}, f)

        result = run_validate_toc(toc_path)
        assert result["status"] == "error"
        assert result["valid"] is False

    def test_validate_toc_gap_between_entries(self, tmp_dir):
        from cli_anything.asr_transcribe.core.llm_tasks import run_validate_toc

        toc = [
            {"level": "H1", "title": "A", "start": 0.0, "end": 5.0},
            {"level": "H1", "title": "B", "start": 6.0, "end": 10.0},
        ]
        toc_path = os.path.join(tmp_dir, "gap.json")
        with open(toc_path, "w") as f:
            json.dump(toc, f)

        result = run_validate_toc(toc_path)
        assert result["valid"] is False
        assert "previous end" in result["error"]

    def test_validate_toc_invalid_level(self, tmp_dir):
        from cli_anything.asr_transcribe.core.llm_tasks import run_validate_toc

        toc = [
            {"level": "H4", "title": "Bad level", "start": 0.0, "end": 5.0},
        ]
        toc_path = os.path.join(tmp_dir, "level.json")
        with open(toc_path, "w") as f:
            json.dump(toc, f)

        result = run_validate_toc(toc_path)
        assert result["valid"] is False
        assert "level" in result["error"]

    def test_validate_toc_missing_file(self):
        from cli_anything.asr_transcribe.core.llm_tasks import run_validate_toc

        with pytest.raises(FileNotFoundError):
            run_validate_toc("/nonexistent/toc.json")

    def test_validate_toc_missing_transcript_json(self, tmp_dir):
        from cli_anything.asr_transcribe.core.llm_tasks import run_validate_toc

        toc_path = os.path.join(tmp_dir, "toc.json")
        with open(toc_path, "w") as f:
            json.dump(VALID_TOC, f)

        with pytest.raises(FileNotFoundError):
            run_validate_toc(toc_path, transcript_json="/nonexistent/segments.json")
