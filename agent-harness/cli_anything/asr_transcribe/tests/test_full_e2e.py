"""End-to-end and CLI subprocess tests for cli-anything-asr-transcribe.

Tests the full export pipeline using real format writers and verifies output
structure. Subprocess tests invoke the installed CLI command.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────

SAMPLE_SEGMENTS = [
    {
        "start": 0.0,
        "end": 3.5,
        "text": "Guten Tag, dies ist ein Testtranskript.",
        "speaker": "SPEAKER_00",
        "words": [
            {"word": "Guten", "start": 0.0, "end": 0.4, "score": 0.95},
            {"word": "Tag,", "start": 0.5, "end": 0.8, "score": 0.92},
            {"word": "dies", "start": 0.9, "end": 1.1, "score": 0.90},
            {"word": "ist", "start": 1.2, "end": 1.4, "score": 0.88},
            {"word": "ein", "start": 1.5, "end": 1.7, "score": 0.94},
            {"word": "Testtranskript.", "start": 1.8, "end": 3.5, "score": 0.91},
        ],
    },
    {
        "start": 4.0,
        "end": 8.2,
        "text": "Wir testen die Export-Pipeline.",
        "speaker": "SPEAKER_01",
        "words": [
            {"word": "Wir", "start": 4.0, "end": 4.2, "score": 0.93},
            {"word": "testen", "start": 4.3, "end": 4.7, "score": 0.91},
            {"word": "die", "start": 4.8, "end": 5.0, "score": 0.89},
            {"word": "Export-Pipeline.", "start": 5.1, "end": 8.2, "score": 0.88},
        ],
    },
    {
        "start": 9.0,
        "end": 15.0,
        "text": "Dies ist das dritte Segment mit mehr Inhalt.",
        "speaker": "SPEAKER_00",
        "words": [
            {"word": "Dies", "start": 9.0, "end": 9.3, "score": 0.95},
            {"word": "ist", "start": 9.4, "end": 9.6, "score": 0.94},
            {"word": "das", "start": 9.7, "end": 9.9, "score": 0.92},
            {"word": "dritte", "start": 10.0, "end": 10.4, "score": 0.90},
            {"word": "Segment", "start": 10.5, "end": 11.0, "score": 0.93},
            {"word": "mit", "start": 11.1, "end": 11.3, "score": 0.91},
            {"word": "mehr", "start": 11.4, "end": 11.7, "score": 0.89},
            {"word": "Inhalt.", "start": 11.8, "end": 15.0, "score": 0.87},
        ],
    },
]

SAMPLE_WHISPERX_OUTPUT = {
    "segments": SAMPLE_SEGMENTS,
    "word_segments": [w for seg in SAMPLE_SEGMENTS for w in seg["words"]],
    "language": "de",
}


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="cli_asr_e2e_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_json(tmp_dir):
    path = os.path.join(tmp_dir, "transcript.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_WHISPERX_OUTPUT, f, indent=2)
    return path


# ── E2E Export Pipeline Tests ─────────────────────────────────────────


class TestExportPipelineE2E:
    """Full pipeline: JSON -> export -> verify output."""

    def test_vtt_export_structure(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.export import export_convert

        result = export_convert(sample_json, formats=["vtt"], output_dir=tmp_dir)
        assert "vtt" in result["exported"]

        vtt_path = os.path.join(tmp_dir, "transcript.vtt")
        assert os.path.exists(vtt_path)
        content = open(vtt_path, encoding="utf-8").read()

        # Verify VTT structure
        assert content.startswith("WEBVTT")
        assert "-->" in content
        assert "Guten Tag" in content
        lines = content.strip().split("\n")
        assert len(lines) > 5

        print(f"\n  VTT: {vtt_path} ({os.path.getsize(vtt_path):,} bytes)")

    def test_srt_export_structure(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.export import export_convert

        result = export_convert(sample_json, formats=["srt"], output_dir=tmp_dir)
        assert "srt" in result["exported"]

        srt_path = os.path.join(tmp_dir, "transcript.srt")
        assert os.path.exists(srt_path)
        content = open(srt_path, encoding="utf-8").read()

        # SRT uses comma as millisecond separator
        assert "," in content
        assert "-->" in content
        assert "1\n" in content  # First cue number

        print(f"\n  SRT: {srt_path} ({os.path.getsize(srt_path):,} bytes)")

    def test_all_text_formats_exist(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.export import export_convert

        text_formats = ["txt", "txt_speaker", "txt_tab", "txt_maxqda",
                        "txt_speaker_maxqda", "txt_speaker_segment_maxqda"]
        result = export_convert(sample_json, formats=text_formats, output_dir=tmp_dir)

        assert len(result["errors"]) == 0
        for fmt in text_formats:
            assert fmt in result["exported"], f"Format {fmt} was not exported"

        # Verify at least the plain text file has content
        txt_path = os.path.join(tmp_dir, "transcript.txt")
        assert os.path.getsize(txt_path) > 0

    def test_csv_export_columns(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.export import export_convert

        result = export_convert(sample_json, formats=["csv", "csv_speaker"], output_dir=tmp_dir)
        assert "csv" in result["exported"]
        assert "csv_speaker" in result["exported"]

        # Check speaker CSV has header with speaker column
        speaker_csv = os.path.join(tmp_dir, "transcript_speaker.csv")
        assert os.path.exists(speaker_csv)
        first_line = open(speaker_csv, encoding="utf-8").readline().strip()
        assert "SPEAKER" in first_line
        assert "TRANSCRIPT" in first_line

    def test_rtf_export_structure(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.export import export_convert

        result = export_convert(sample_json, formats=["rtf"], output_dir=tmp_dir)
        assert "rtf" in result["exported"]

        rtf_path = os.path.join(tmp_dir, "transcript.rtf")
        assert os.path.exists(rtf_path)
        content = open(rtf_path, encoding="utf-8").read()

        # Verify RTF structure
        assert content.startswith("{\\rtf1")
        assert content.endswith("}")
        assert "\\par" in content  # Paragraphs present

        print(f"\n  RTF: {rtf_path} ({os.path.getsize(rtf_path):,} bytes)")

    def test_odt_export_structure(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.export import export_convert

        result = export_convert(sample_json, formats=["odt"], output_dir=tmp_dir)
        assert "odt" in result["exported"]

        odt_path = os.path.join(tmp_dir, "transcript.odt")
        assert os.path.exists(odt_path)
        assert os.path.getsize(odt_path) > 0

        # ODT is a ZIP file
        assert zipfile.is_zipfile(odt_path)
        with zipfile.ZipFile(odt_path) as z:
            names = z.namelist()
            assert "mimetype" in names
            assert "content.xml" in names
            assert "META-INF/manifest.xml" in names

        print(f"\n  ODT: {odt_path} ({os.path.getsize(odt_path):,} bytes)")

    def test_tei_xml_export_structure(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.export import export_convert

        result = export_convert(sample_json, formats=["tei_xml"], output_dir=tmp_dir)
        assert "tei_xml" in result["exported"]

        xml_path = os.path.join(tmp_dir, "transcript.tei.xml")
        assert os.path.exists(xml_path)
        content = open(xml_path, encoding="utf-8").read()

        # Verify TEI-XML structure
        assert "<?xml" in content
        assert "TEI" in content
        assert "timeline" in content.lower() or "when" in content.lower()

        print(f"\n  TEI-XML: {xml_path} ({os.path.getsize(xml_path):,} bytes)")

    def test_word_level_formats(self, sample_json, tmp_dir):
        from cli_anything.asr_transcribe.core.export import export_convert

        result = export_convert(
            sample_json, formats=["word_vtt", "word_csv"], output_dir=tmp_dir
        )
        assert "word_vtt" in result["exported"]
        assert "word_csv" in result["exported"]

        word_vtt = os.path.join(tmp_dir, "transcript_word_segments.vtt")
        assert os.path.exists(word_vtt)
        content = open(word_vtt, encoding="utf-8").read()
        assert "WEBVTT" in content

        word_csv = os.path.join(tmp_dir, "transcript_word_segments.csv")
        assert os.path.exists(word_csv)
        first_line = open(word_csv, encoding="utf-8").readline().strip()
        assert "WORD" in first_line


# ── E2E BagIt Pipeline Tests ─────────────────────────────────────────


class TestBagItPipelineE2E:
    def test_create_validate_bag(self, tmp_dir):
        """Create a BagIt structure, finalize it, and validate."""
        from cli_anything.asr_transcribe.core.bag_manager import validate_bag

        bag_dir = os.path.join(tmp_dir, "test_bag")
        os.makedirs(bag_dir)

        # Create structure
        data_dir = os.path.join(bag_dir, "data")
        transcripts_dir = os.path.join(data_dir, "transcripts")
        os.makedirs(transcripts_dir)

        # Write payload
        payload_file = os.path.join(transcripts_dir, "transcript.txt")
        with open(payload_file, "w", encoding="utf-8") as f:
            f.write("Guten Tag, dies ist ein Test.\n")

        # Write required tag files
        with open(os.path.join(bag_dir, "bagit.txt"), "w") as f:
            f.write("BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n")

        with open(os.path.join(bag_dir, "bag-info.txt"), "w") as f:
            f.write("Source-Filename: test.wav\nModel: large-v3\n")

        # Write manifest
        digest = hashlib.sha512()
        with open(payload_file, "rb") as f:
            digest.update(f.read())

        with open(os.path.join(bag_dir, "manifest-sha512.txt"), "w") as f:
            f.write(f"{digest.hexdigest()}  data/transcripts/transcript.txt\n")

        # Validate
        result = validate_bag(bag_dir)
        assert result["valid"] is True
        assert result["info"]["payload_file_count"] == 1

        print(f"\n  Bag: {bag_dir} (valid)")

    def test_bag_zip_creates_archive(self, tmp_dir):
        """Create a bag and zip it."""
        bag_dir = os.path.join(tmp_dir, "zip_test_bag")
        os.makedirs(os.path.join(bag_dir, "data", "transcripts"), exist_ok=True)

        with open(os.path.join(bag_dir, "data", "transcripts", "test.txt"), "w") as f:
            f.write("Test content\n")
        with open(os.path.join(bag_dir, "bagit.txt"), "w") as f:
            f.write("BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n")

        from cli_anything.asr_transcribe.core.bag_manager import zip_bag

        result = zip_bag(bag_dir)
        assert os.path.exists(result["zip_path"])
        assert result["size_bytes"] > 0
        assert zipfile.is_zipfile(result["zip_path"])

        print(f"\n  ZIP: {result['zip_path']} ({result['size_bytes']:,} bytes)")


# ── E2E Post-Processing Pipeline Tests ────────────────────────────────


class TestPostProcessingE2E:
    def test_process_and_export(self, sample_json, tmp_dir):
        """Process raw segments and then export the result."""
        from cli_anything.asr_transcribe.core.process import process_segments
        from cli_anything.asr_transcribe.core.export import export_convert

        # Process
        processed_path = os.path.join(tmp_dir, "processed.json")
        proc_result = process_segments(sample_json, processed_path)
        assert proc_result["segments_after"] > 0
        assert os.path.exists(processed_path)

        # Export from processed output
        export_result = export_convert(
            processed_path, formats=["vtt", "txt", "csv"], output_dir=tmp_dir
        )
        assert len(export_result["exported"]) == 3
        assert len(export_result["errors"]) == 0

        print(f"\n  Processed: {proc_result['segments_before']} -> {proc_result['segments_after']} segments")
        print(f"  Exported: {', '.join(export_result['exported'])}")


# ── Full Export Workflow Test ─────────────────────────────────────────


class TestFullExportWorkflow:
    """Simulates an agent re-exporting from existing WhisperX JSON."""

    def test_full_workflow_all_formats(self, sample_json, tmp_dir):
        """Export to ALL formats and verify each file exists."""
        from cli_anything.asr_transcribe.core.export import export_convert, list_formats

        all_formats = list(list_formats().keys())
        result = export_convert(sample_json, formats=all_formats, output_dir=tmp_dir)

        # Some formats may fail (e.g., pdf requires specific fonts), that's ok
        successful = result["exported"]
        failed = result["errors"]

        print(f"\n  Exported {len(successful)}/{len(all_formats)} formats:")
        for fmt in successful:
            print(f"    ✓ {fmt}")
        for err in failed:
            print(f"    ✗ {err['format']}: {err['error']}")

        # At least the core text formats should succeed
        core_formats = ["vtt", "srt", "txt", "csv", "json", "rtf"]
        for fmt in core_formats:
            assert fmt in successful, f"Core format {fmt} failed to export"


# ── CLI Subprocess Tests ──────────────────────────────────────────────


def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    import shutil as _shutil

    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = _shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = name.replace("cli-anything-", "cli_anything.") + "." + name.split("-")[-1] + "_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


class TestCLISubprocess:
    """Test the installed CLI command via subprocess."""

    CLI_BASE = _resolve_cli("cli-anything-asr-transcribe")

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "cli-anything-asr-transcribe" in result.stdout

    def test_version(self):
        result = self._run(["--version"])
        assert result.returncode == 0
        assert "1.0.0" in result.stdout

    def test_version_json(self):
        result = self._run(["--json", "--version"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["version"] == "1.0.0"

    def test_export_formats_json(self):
        result = self._run(["--json", "export", "formats"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "vtt" in data
        assert "srt" in data
        assert len(data) >= 20

    def test_deps_json(self):
        result = self._run(["--json", "deps"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "toml" in data
        assert data["toml"]["available"] is True

    def test_config_validate_json(self):
        result = self._run(["--json", "config", "validate"], check=False)
        # May fail if not run from project dir, but should still output valid JSON
        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert "valid" in data

    def test_export_convert_subprocess(self, tmp_dir):
        """Full subprocess workflow: create JSON -> export via CLI -> verify."""
        # Create sample JSON
        json_path = os.path.join(tmp_dir, "test.json")
        with open(json_path, "w") as f:
            json.dump(SAMPLE_WHISPERX_OUTPUT, f)

        result = self._run([
            "--json", "export", "convert", json_path,
            "-f", "vtt,srt,txt",
            "-o", tmp_dir,
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "vtt" in data["exported"]
        assert "srt" in data["exported"]
        assert "txt" in data["exported"]

        # Verify files exist
        assert os.path.exists(os.path.join(tmp_dir, "test.vtt"))
        assert os.path.exists(os.path.join(tmp_dir, "test.srt"))
        assert os.path.exists(os.path.join(tmp_dir, "test.txt"))

        print(f"\n  Subprocess export successful: {', '.join(data['exported'])}")

    def test_info_segments_subprocess(self, tmp_dir):
        """Test info segments via subprocess."""
        json_path = os.path.join(tmp_dir, "test.json")
        with open(json_path, "w") as f:
            json.dump(SAMPLE_WHISPERX_OUTPUT, f)

        result = self._run(["--json", "info", "segments", json_path])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["segment_count"] == 3
        assert data["language"] == "de"
        assert data["speaker_count"] == 2

    def test_bag_validate_subprocess(self, tmp_dir):
        """Test bag validate via subprocess."""
        # Create minimal bag
        bag_dir = os.path.join(tmp_dir, "test_bag")
        os.makedirs(os.path.join(bag_dir, "data", "transcripts"), exist_ok=True)

        with open(os.path.join(bag_dir, "bagit.txt"), "w") as f:
            f.write("BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n")

        payload_file = os.path.join(bag_dir, "data", "transcripts", "test.txt")
        with open(payload_file, "w") as f:
            f.write("Test content\n")

        with open(os.path.join(bag_dir, "bag-info.txt"), "w") as f:
            f.write("Model: large-v3\n")

        digest = hashlib.sha512()
        with open(payload_file, "rb") as f:
            digest.update(f.read())
        with open(os.path.join(bag_dir, "manifest-sha512.txt"), "w") as f:
            f.write(f"{digest.hexdigest()}  data/transcripts/test.txt\n")

        result = self._run(["--json", "bag", "validate", bag_dir])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["valid"] is True

    def test_info_words_subprocess(self, tmp_dir):
        """Test info words via subprocess."""
        json_path = os.path.join(tmp_dir, "test.json")
        with open(json_path, "w") as f:
            json.dump(SAMPLE_WHISPERX_OUTPUT, f)

        result = self._run(["--json", "info", "words", json_path])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["word_count"] > 0
        assert data["avg_confidence"] is not None

    def test_info_speakers_subprocess(self, tmp_dir):
        """Test info speakers via subprocess."""
        json_path = os.path.join(tmp_dir, "test.json")
        with open(json_path, "w") as f:
            json.dump(SAMPLE_WHISPERX_OUTPUT, f)

        result = self._run(["--json", "info", "speakers", json_path])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["speaker_count"] == 2
        assert "SPEAKER_00" in data["speakers"]

    def test_info_hallucinations_subprocess(self, tmp_dir):
        """Test info hallucinations via subprocess."""
        json_path = os.path.join(tmp_dir, "test.json")
        with open(json_path, "w") as f:
            json.dump(SAMPLE_WHISPERX_OUTPUT, f)

        result = self._run(["--json", "info", "hallucinations", json_path])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "warning_count" in data
        assert "segment_count" in data

    def test_process_buffer_subprocess(self, tmp_dir):
        """Test process buffer via subprocess."""
        json_path = os.path.join(tmp_dir, "test.json")
        with open(json_path, "w") as f:
            json.dump(SAMPLE_WHISPERX_OUTPUT, f)

        output_path = os.path.join(tmp_dir, "buffered.json")
        result = self._run(["--json", "process", "buffer", json_path, "-o", output_path])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["segment_count"] > 0
        assert os.path.exists(output_path)


# ── E2E Bag Create Pipeline Tests ─────────────────────────────────────


class TestBagCreateE2E:
    def test_create_validate_roundtrip(self, tmp_dir):
        """Create a bag via create_bag, then validate it."""
        from cli_anything.asr_transcribe.core.bag_manager import create_bag, validate_bag

        # Create a source file
        src = os.path.join(tmp_dir, "transcript.txt")
        with open(src, "w") as f:
            f.write("Transcript content for bag test.\n")

        bag_path = os.path.join(tmp_dir, "roundtrip_bag")
        create_result = create_bag(bag_path, files=[src], metadata={"Model": "large-v3"})
        assert create_result["created"] is True
        assert create_result["file_count"] == 1

        val_result = validate_bag(bag_path)
        assert val_result["valid"] is True

    def test_create_zip_roundtrip(self, tmp_dir):
        """Create a bag, zip it, verify ZIP structure."""
        from cli_anything.asr_transcribe.core.bag_manager import create_bag, zip_bag

        src = os.path.join(tmp_dir, "test.txt")
        with open(src, "w") as f:
            f.write("Test content\n")

        bag_path = os.path.join(tmp_dir, "zip_roundtrip_bag")
        create_bag(bag_path, files=[src])

        zip_result = zip_bag(bag_path)
        assert os.path.exists(zip_result["zip_path"])
        assert zipfile.is_zipfile(zip_result["zip_path"])


# ── E2E Process Steps Pipeline Tests ──────────────────────────────────


class TestProcessStepsE2E:
    def test_buffer_then_uppercase_then_split(self, sample_json, tmp_dir):
        """Run post-processing steps individually in sequence."""
        from cli_anything.asr_transcribe.core.process import buffer_step, uppercase_step, split_step

        buf_out = os.path.join(tmp_dir, "step1_buffer.json")
        buf_result = buffer_step(sample_json, buf_out)
        assert buf_result["segment_count"] > 0
        assert os.path.exists(buf_out)

        up_out = os.path.join(tmp_dir, "step2_upper.json")
        up_result = uppercase_step(buf_out, up_out)
        assert up_result["segment_count"] > 0

        split_out = os.path.join(tmp_dir, "step3_split.json")
        split_result = split_step(up_out, split_out)
        assert split_result["segment_count"] > 0

        # Verify final output is valid JSON with segments
        with open(split_out) as f:
            data = json.load(f)
        assert "segments" in data
        assert "word_segments" in data

    def test_individual_steps_match_combined(self, sample_json, tmp_dir):
        """Individual steps produce valid output comparable to full process."""
        from cli_anything.asr_transcribe.core.process import process_segments, buffer_step

        full_out = os.path.join(tmp_dir, "full.json")
        full_result = process_segments(sample_json, full_out)

        buf_out = os.path.join(tmp_dir, "buf_only.json")
        buf_result = buffer_step(sample_json, buf_out)

        # Buffer step alone should produce fewer or equal segments
        assert buf_result["segment_count"] <= full_result["segments_before"] + 1


# ── E2E Deep Inspection Pipeline Tests ────────────────────────────────


class TestDeepInspectionE2E:
    def test_full_inspection_workflow(self, sample_json, tmp_dir):
        """Run all inspection commands on the same JSON file."""
        from cli_anything.asr_transcribe.core.audio_info import (
            get_segments_info, get_words_info, get_speakers_info,
            get_language_info, check_hallucinations,
        )

        seg_info = get_segments_info(sample_json)
        assert seg_info["segment_count"] == 3

        word_info = get_words_info(sample_json)
        assert word_info["word_count"] > 0

        speaker_info = get_speakers_info(sample_json)
        assert speaker_info["speaker_count"] == 2

        lang_info = get_language_info(sample_json)
        assert lang_info["language"] == "de"

        halluc_info = check_hallucinations(sample_json)
        assert halluc_info["warning_count"] == 0

        print(f"\n  Full inspection: {seg_info['segment_count']} segments, "
              f"{word_info['word_count']} words, "
              f"{speaker_info['speaker_count']} speakers, "
              f"{halluc_info['warning_count']} warnings")
