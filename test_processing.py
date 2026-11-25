import copy
import json
import pytest
import zipfile
from datetime import datetime
from types import SimpleNamespace
from output.post_processing import (
    sentence_is_incomplete,
    uppercase_sentences,
    split_long_sentences,
)
from utils.utilities import (
    prepare_bag_directory,
    finalize_bag,
    sha512,
    zip_bag_directory,
    copy_documentation_files,
    create_output_files_directory_path,
    append_affix,
    duplicate_speaker_csvs_to_ohd_import,
)
from output.writers import write_summary, write_text, write_text_speaker
from output import writers as writers_module
from output import disclosure
from config.default_config import CONST_DEFAULT_CONFIG


class TestSentenceIsIncomplete:
    def test_no_punctuation(self):
        assert sentence_is_incomplete("This sentence has no punctuation")

    def test_number(self):
        """
        Do we actually need the number check?
        What does it even do?
        """
        assert sentence_is_incomplete("This sentence ends with 821")

    def test_academic_title(self):
        assert sentence_is_incomplete("This sentence ends with a Dr.")

    def test_normal_sentence(self):
        assert not sentence_is_incomplete("This is a normal sentence with punctuation.")


def test_uppercase_sentences():
    segment1 = {"text": "The first sentence is not affected.", "start": 0.0, "end": 0.0}
    segment2 = {
        "text": "the sentences after that are affected,",
        "start": 0.0,
        "end": 0.0,
    }
    segment3 = {
        "text": "unless there is a comma before them.",
        "start": 0.0,
        "end": 0.0,
    }
    segments = [segment1, segment2, segment3]

    expected = [
        copy.deepcopy(segment1),
        {"text": "The sentences after that are affected,", "start": 0.0, "end": 0.0},
        copy.deepcopy(segment3),
    ]

    uppercase_sentences(segments)
    assert expected == segments


def test_split_sentences():
    segment1 = {
        "text": "This sentence is way shorter than 120 characters.",
        "start": 0.0,
        "end": 10.0,
    }
    segment2 = {
        "text": (
            "This sentence is longer than 120 characters "
            "and it should be broken up into two sentences "
            "after the comma appearing shortly after 120, "
            "and so in the end we have two sentences instead "
            "of one."
        ),
        "start": 10.0,
        "end": 40.0,
    }
    segment3 = {
        "text": "The last sentence is also below 120 characters.",
        "start": 40.0,
        "end": 50.0,
    }
    original_segments = [segment1, segment2, segment3]

    segment2a = {
        "start": 10.0,
        "end": 31.157894736842106,
        "text": (
            "This sentence is longer than 120 characters "
            "and it should be broken up into two sentences "
            "after the comma appearing shortly after 120,"
        ),
        "words": [],
    }
    segment2b = {
        "start": 31.157894736842106,
        "end": 40.0,
        "text": ("and so in the end we have two sentences instead of one."),
        "words": [],
    }

    expected_segments = [segment1, segment2a, segment2b, segment3]
    actual_segments = list(split_long_sentences(original_segments))

    assert expected_segments == actual_segments


def test_split_long_sentences_repeated_splits_keep_time_continuity():
    segment = {
        "text": ("A" * 60 + ", " + "B" * 60 + ", " + "C" * 60 + ", " + "D" * 60),
        "start": 0.0,
        "end": 40.0,
        "words": [],
    }
    result = list(
        split_long_sentences(
            [segment], use_speaker_diarization=False, max_sentence_length=50
        )
    )

    assert len(result) > 2
    assert result[0]["start"] == pytest.approx(0.0)
    assert result[-1]["end"] == pytest.approx(40.0)

    for idx in range(len(result) - 1):
        assert result[idx]["end"] == pytest.approx(result[idx + 1]["start"])
        assert result[idx]["start"] < result[idx]["end"]

    total_duration = result[-1]["end"] - result[0]["start"]
    assert total_duration == pytest.approx(40.0)


def test_split_long_sentences_stops_when_no_comma_after_threshold():
    segment = {
        "text": "A" * 60 + ", " + "B" * 200,
        "start": 5.0,
        "end": 25.0,
        "words": [],
    }
    result = list(
        split_long_sentences(
            [segment], use_speaker_diarization=False, max_sentence_length=50
        )
    )

    assert len(result) == 2
    assert result[0]["end"] == pytest.approx(result[1]["start"])
    assert result[-1]["end"] == pytest.approx(25.0)


def test_split_long_sentences_no_comma_no_split():
    segment = {"text": "A" * 200, "start": 0.0, "end": 10.0, "words": []}
    result = list(
        split_long_sentences(
            [segment], use_speaker_diarization=False, max_sentence_length=50
        )
    )

    assert result == [segment]


def test_prepare_segments_for_template_without_timestamps():
    segments = [
        {"text": "Hallo", "speaker": "SPEAKER_01", "start": 0.0, "end": 1.0},
        {"text": "Welt", "speaker": "SPEAKER_01", "start": 1.0, "end": 2.0},
        {"text": "Test", "speaker": "SPEAKER_02", "start": 2.0, "end": 3.0},
        {"text": "Leer", "speaker": "", "start": 3.0, "end": 4.0},
    ]

    prepared = writers_module.prepare_segments_for_template(
        segments, include_timestamps=False
    )

    assert prepared[0] == {"text": "Hallo", "speaker": "SPEAKER_01"}
    assert prepared[1] == {"text": "Welt"}
    assert prepared[2] == {"text": "Test", "speaker": "SPEAKER_02"}
    assert prepared[3] == {"text": "Leer"}
    assert all("timestamp" not in item for item in prepared)


def test_prepare_segments_for_template_with_timestamps_and_missing_bounds():
    segments = [
        {"text": "Alpha", "speaker": "SPEAKER_01", "start": 0.0, "end": 1.0},
        {"text": "Beta", "speaker": "SPEAKER_01", "start": 1.0},  # missing end
        {"text": "Gamma", "speaker": "SPEAKER_02", "start": 2.0, "end": 3.0},
    ]

    prepared = writers_module.prepare_segments_for_template(
        segments, include_timestamps=True
    )

    assert prepared[0]["text"] == "Alpha"
    assert prepared[0]["speaker"] == "SPEAKER_01"
    assert "timestamp" in prepared[0]
    assert "-->" in prepared[0]["timestamp"]

    assert prepared[1]["text"] == "Beta"
    assert "timestamp" not in prepared[1]
    assert "speaker" not in prepared[1]

    assert prepared[2]["text"] == "Gamma"
    assert prepared[2]["speaker"] == "SPEAKER_02"
    assert "timestamp" in prepared[2]


def test_prepare_segments_for_template_resets_after_empty_speaker():
    segments = [
        {"text": "Alpha", "speaker": "SPEAKER_01", "start": 0.0, "end": 1.0},
        {"text": "Pause", "speaker": "", "start": 1.0, "end": 2.0},
        {"text": "Back", "speaker": "SPEAKER_01", "start": 2.0, "end": 3.0},
    ]

    prepared = writers_module.prepare_segments_for_template(
        segments, include_timestamps=False
    )

    assert prepared[0]["speaker"] == "SPEAKER_01"
    assert "speaker" not in prepared[1]
    assert prepared[2]["speaker"] == "SPEAKER_01"


def test_write_pdf_calls_central_helper(monkeypatch, tmp_path):
    captured = {}

    class DummyTemplate:
        def render(self, **kwargs):
            captured["render_kwargs"] = kwargs
            return "<html><body>ok</body></html>"

    def fake_get_template(_name):
        return DummyTemplate()

    def fake_pdf_helper(html_content, full_path, *, base_url):
        captured["html_content"] = html_content
        captured["full_path"] = full_path
        captured["base_url"] = base_url

    monkeypatch.setattr(writers_module.env, "get_template", fake_get_template)
    monkeypatch.setattr(writers_module, "_write_pdfa_2a_from_html", fake_pdf_helper)

    base_path = tmp_path / "beispiel"
    segments = [{"text": "Hallo Welt", "speaker": "SPEAKER_01", "start": 0.0, "end": 1.0}]
    writers_module.write_pdf(base_path, segments)

    assert captured["full_path"] == tmp_path / "beispiel.pdf"
    assert captured["html_content"].startswith("<html>")
    assert captured["base_url"] == str(
        writers_module.Path(writers_module.__file__).resolve().parent.parent
    )
    assert all(
        "timestamp" not in segment
        for segment in captured["render_kwargs"]["segments"]
    )


def test_write_pdf_timestamps_calls_central_helper(monkeypatch, tmp_path):
    captured = {}

    class DummyTemplate:
        def render(self, **kwargs):
            captured["render_kwargs"] = kwargs
            return "<html><body>ok</body></html>"

    def fake_get_template(_name):
        return DummyTemplate()

    def fake_pdf_helper(html_content, full_path, *, base_url):
        captured["html_content"] = html_content
        captured["full_path"] = full_path
        captured["base_url"] = base_url

    monkeypatch.setattr(writers_module.env, "get_template", fake_get_template)
    monkeypatch.setattr(writers_module, "_write_pdfa_2a_from_html", fake_pdf_helper)

    base_path = tmp_path / "beispiel"
    segments = [
        {"text": "Hallo Welt", "speaker": "SPEAKER_01", "start": 0.0, "end": 1.0},
        {"text": "Noch ein Satz", "speaker": "SPEAKER_01", "start": 1.0, "end": 2.0},
    ]
    writers_module.write_pdf_timestamps(base_path, segments)

    assert captured["full_path"] == tmp_path / "beispiel_timestamps.pdf"
    rendered_segments = captured["render_kwargs"]["segments"]
    assert all("timestamp" in segment for segment in rendered_segments)
    assert rendered_segments[0]["text"] == "Hallo Welt"
    assert rendered_segments[1]["text"] == "Noch ein Satz"


def test_write_pdf_smoke_if_weasyprint_available(tmp_path):
    pytest.importorskip("weasyprint")

    base_path = tmp_path / "smoke_pdf"
    segments = [{"text": "Kurzer Test", "speaker": "SPEAKER_01", "start": 0.0, "end": 1.0}]

    try:
        writers_module.write_pdf(base_path, segments)
    except RuntimeError as exc:
        pytest.skip(f"WeasyPrint runtime not available in test environment: {exc}")

    pdf_path = tmp_path / "smoke_pdf.pdf"
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0
    assert pdf_path.read_bytes().startswith(b"%PDF-")


def test_write_pdf_timestamps_smoke_if_weasyprint_available(tmp_path):
    pytest.importorskip("weasyprint")

    base_path = tmp_path / "smoke_pdf_ts"
    segments = [{"text": "Kurzer Test", "speaker": "SPEAKER_01", "start": 0.0, "end": 1.0}]

    try:
        writers_module.write_pdf_timestamps(base_path, segments)
    except RuntimeError as exc:
        pytest.skip(f"WeasyPrint runtime not available in test environment: {exc}")

    pdf_path = tmp_path / "smoke_pdf_ts_timestamps.pdf"
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0
    assert pdf_path.read_bytes().startswith(b"%PDF-")


# --- BagIt Tests ---


@pytest.fixture
def bagit_test_structure(tmp_path):
    """Creates a temporary directory for BagIt tests."""
    bag_root = tmp_path / "test_bag"
    return bag_root


def test_prepare_bag_directory(bagit_test_structure):
    """Tests the creation of the BagIt directory structure."""
    bag_root = bagit_test_structure
    transcripts_dir = prepare_bag_directory(bag_root)

    assert bag_root.exists() and bag_root.is_dir()
    data_dir = bag_root / "data"
    assert data_dir.exists() and data_dir.is_dir()
    transcripts_dir = bag_root / "data" / "transcripts"
    assert transcripts_dir.exists() and transcripts_dir.is_dir()
    assert transcripts_dir.name == "transcripts"
    assert transcripts_dir.parent == data_dir
    ohd_import_dir = bag_root / "data" / "ohd_import"
    assert ohd_import_dir.exists() and ohd_import_dir.is_dir()
    assert ohd_import_dir.parent == data_dir

    # Test documentation directory
    documentation_dir = bag_root / "documentation"
    assert documentation_dir.exists() and documentation_dir.is_dir()
    assert documentation_dir.name == "documentation"
    assert documentation_dir.parent == bag_root


def test_finalize_bag_manifests_and_info(bagit_test_structure):
    """
    Tests the creation of bagit.txt, manifest-sha512.txt, and bag-info.txt.
    """
    bag_root = bagit_test_structure
    transcripts_dir = prepare_bag_directory(bag_root)

    # Create dummy payload files
    file1_content = "This is file one."
    file2_content = "This is file two, which is different."
    file1 = transcripts_dir / "file1.txt"
    file2 = transcripts_dir / "file2.txt"
    file1.write_text(file1_content, encoding="utf-8")
    file2.write_text(file2_content, encoding="utf-8")
    payload_files = [file1, file2]

    # Calculate expected checksums
    sha512_file1 = sha512(file1)
    sha512_file2 = sha512(file2)

    # Define extra info for bag-info.txt
    extra_info = {
        "Source-Filename": "test.wav",
        "Internal-Sender-Identifier": "test-sender",
    }

    finalize_bag(bag_root, payload_files, extra_info)

    # 1. Test manifest-sha512.txt
    manifest_path = bag_root / "manifest-sha512.txt"
    assert manifest_path.exists()
    manifest_content = manifest_path.read_text(encoding="utf-8")
    assert f"{sha512_file1}  data/transcripts/file1.txt" in manifest_content
    assert f"{sha512_file2}  data/transcripts/file2.txt" in manifest_content

    # 2. Test bag-info.txt
    bag_info_path = bag_root / "bag-info.txt"
    assert bag_info_path.exists()
    bag_info_content = bag_info_path.read_text(encoding="utf-8")
    assert "Source-Filename: test.wav" in bag_info_content
    assert "Internal-Sender-Identifier: test-sender" in bag_info_content
    assert "Payload-Oxum:" in bag_info_content
    assert "Bagging-Date:" in bag_info_content

    # 3. Test bagit.txt
    bagit_txt_path = bag_root / "bagit.txt"
    assert bagit_txt_path.exists()
    bagit_txt_content = bagit_txt_path.read_text(encoding="utf-8")
    assert "BagIt-Version: 1.0" in bagit_txt_content
    assert "Tag-File-Character-Encoding: UTF-8" in bagit_txt_content


def test_docu_directory_in_tag_manifest(bagit_test_structure):
    """
    Tests that files in documentation/ directory are included in tagmanifest-sha512.txt.
    """
    bag_root = bagit_test_structure
    transcripts_dir = prepare_bag_directory(bag_root)

    # Create payload files
    file1 = transcripts_dir / "payload.txt"
    file1.write_text("Payload content", encoding="utf-8")
    payload_files = [file1]

    # Create documentation files in documentation/
    documentation_dir = bag_root / "documentation"
    readme = documentation_dir / "README.md"
    readme.write_text("# Documentation\nThis is a test bag.", encoding="utf-8")

    license_file = documentation_dir / "LICENSE.txt"
    license_file.write_text("MIT License", encoding="utf-8")

    # Calculate checksums
    sha512_readme = sha512(readme)
    sha512_license = sha512(license_file)

    finalize_bag(bag_root, payload_files, {})

    # Test that documentation files are NOT in payload manifest
    manifest_path = bag_root / "manifest-sha512.txt"
    manifest_content = manifest_path.read_text(encoding="utf-8")
    assert "documentation/" not in manifest_content

    # Test that documentation files ARE in tag manifest
    tag_manifest_path = bag_root / "tagmanifest-sha512.txt"
    assert tag_manifest_path.exists()
    tag_manifest_content = tag_manifest_path.read_text(encoding="utf-8")
    assert f"{sha512_readme}  documentation/README.md" in tag_manifest_content
    assert f"{sha512_license}  documentation/LICENSE.txt" in tag_manifest_content


def test_zip_bag_directory_creates_archive(bagit_test_structure):
    """Ensures that a ZIP archive of the bag directory is created."""
    bag_root = bagit_test_structure
    transcripts_dir = prepare_bag_directory(bag_root)

    payload_file = transcripts_dir / "payload.txt"
    payload_file.write_text("Payload content", encoding="utf-8")
    finalize_bag(bag_root, [payload_file], {})

    archive_path = zip_bag_directory(bag_root)
    assert archive_path.exists()
    assert archive_path.suffix == ".zip"

    with zipfile.ZipFile(archive_path) as zip_file:
        names = zip_file.namelist()
        assert any(name.startswith(f"{bag_root.name}/") for name in names)


def test_write_summary_multiple_languages(tmp_path):
    """Ensure summary files for DE and EN are written into content_extraction."""
    bag_root = tmp_path / "bag"
    data_transcripts = bag_root / "data" / "transcripts"
    data_transcripts.mkdir(parents=True)
    base_path = data_transcripts / "sample.v1.final"

    write_summary(base_path, "Zusammenfassung DE")
    write_summary(base_path, "Summary EN", language_code="en")

    content_extraction_dir = bag_root / "data" / "content_extraction"
    de_file = content_extraction_dir / "sample.v1.final_summary_de.txt"
    en_file = content_extraction_dir / "sample.v1.final_summary_en.txt"

    assert de_file.exists()
    assert en_file.exists()
    assert "Zusammenfassung" in de_file.read_text(encoding="utf-8")
    assert "Summary EN" in en_file.read_text(encoding="utf-8")


def test_write_text_preserves_multiple_dots(tmp_path):
    base_path = tmp_path / "PART2.Pagenstecher.vorstellung_de"
    segments = [{"text": "Hallo", "start": 0.0, "end": 1.0}]

    write_text(base_path, segments)

    assert (tmp_path / "PART2.Pagenstecher.vorstellung_de.txt").exists()


def test_write_text_speaker_preserves_multiple_dots(tmp_path):
    base_path = tmp_path / "PART2.Pagenstecher.vorstellung_de"
    segments = [{"text": "Hallo", "start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]

    write_text_speaker(base_path, segments)

    assert (tmp_path / "PART2.Pagenstecher.vorstellung_de_speaker.txt").exists()


def test_write_rtf_contains_only_transcript_text(tmp_path):
    base_path = tmp_path / "sample.v1.final"
    segments = [{"text": "Hallo {Welt} ä", "start": 0.0, "end": 1.0, "speaker": "SPK_A"}]

    writers_module.write_rtf(base_path, segments)

    content = (tmp_path / "sample.v1.final.rtf").read_text(encoding="utf-8")
    assert "SPK_A:" not in content
    assert "-->" not in content
    assert "\\{Welt\\}" in content
    assert "\\u228?" in content


def test_write_rtf_speaker_contains_speakers_without_timestamps(tmp_path):
    base_path = tmp_path / "sample.v1.final"
    segments = [
        {"text": "Hallo", "start": 0.0, "end": 1.0, "speaker": "SPK_A"},
        {"text": "Weiter", "start": 1.0, "end": 2.0, "speaker": "SPK_A"},
        {"text": "Grüße", "start": 2.0, "end": 3.0, "speaker": "SPK_B"},
    ]

    writers_module.write_rtf_speaker(base_path, segments)

    content = (tmp_path / "sample.v1.final_speaker.rtf").read_text(encoding="utf-8")
    assert content.count("SPK_A:") == 1
    assert content.count("SPK_B:") == 1
    assert "-->" not in content
    assert "Hallo Weiter\\par\n" in content
    assert "Hallo\\par" not in content
    assert "\\u252?" in content


def test_write_rtf_timestamps_contains_speakers_and_timestamps(tmp_path):
    base_path = tmp_path / "sample.v1.final"
    segments = [
        {"text": "Hallo", "start": 0.0, "end": 1.0, "speaker": "SPK_A"},
        {"text": "Weiter", "start": 1.0, "end": 2.0, "speaker": "SPK_A"},
        {"text": "Grüße", "start": 2.0, "end": 3.0, "speaker": "SPK_B"},
    ]

    writers_module.write_rtf_timestamps(base_path, segments)

    content = (tmp_path / "sample.v1.final_timestamps.rtf").read_text(encoding="utf-8")
    assert content.count("SPK_A:") == 1
    assert content.count("SPK_B:") == 1
    assert "[00:00:00.000 --> 00:00:01.000]" in content
    assert "\\u252?" in content


def test_duplicate_speaker_csvs_preserves_multiple_dots(tmp_path):
    data_dir = tmp_path / "bag" / "data"
    transcripts_dir = data_dir / "transcripts"
    ohd_import_dir = data_dir / "ohd_import"
    transcripts_dir.mkdir(parents=True)
    ohd_import_dir.mkdir(parents=True)

    base_path = transcripts_dir / "PART2.Pagenstecher.vorstellung_de"
    speaker_csv = append_affix(base_path, "_speaker", ".csv")
    speaker_nopause_csv = append_affix(base_path, "_speaker_nopause", ".csv")
    speaker_csv.write_text("speaker", encoding="utf-8")
    speaker_nopause_csv.write_text("speaker", encoding="utf-8")

    layout = SimpleNamespace(data_dir=data_dir, output_base_path=base_path)
    duplicate_speaker_csvs_to_ohd_import(layout)

    assert (ohd_import_dir / speaker_csv.name).exists()
    assert (ohd_import_dir / speaker_nopause_csv.name).exists()


def test_copy_documentation_files_copies_required_docs_and_updates_citation(tmp_path):
    """Ensure all documentation files are copied and citation year is rendered."""
    bag_root = tmp_path / "bag"

    copy_documentation_files(bag_root)

    documentation_dir = bag_root / "documentation"
    assert documentation_dir.exists()

    required_docs = ["asr_export_formats.rtf", "citation.txt", "ohd_upload.txt"]
    for filename in required_docs:
        assert (documentation_dir / filename).exists()

    citation_text = (documentation_dir / "citation.txt").read_text(encoding="utf-8")
    assert "<{year}>" not in citation_text
    assert str(datetime.now().year) in citation_text


def test_build_output_layout_preserves_multiple_dots_in_filename(tmp_path, monkeypatch):
    """Ensure only the last dot is treated as extension separator."""
    import socket

    monkeypatch.setattr(socket, "gethostbyname", lambda _name: "127.0.0.1")
    from asr_workflow import build_output_layout
    from utils.language_utils import LanguageMeta

    language_meta = LanguageMeta(
        source_language="de",
        output_language="de",
        descriptor="de",
        target_language="de",
    )
    layout = build_output_layout(
        output_directory=tmp_path,
        filename="interview.v1.final.wav",
        model_name="large-v3",
        language_meta=language_meta,
    )

    assert "interview.v1.final" in layout.output_base_path.name


def test_create_output_files_directory_path_preserves_multiple_dots(tmp_path):
    """Ensure timestamp is appended without truncating dotted names."""
    result = create_output_files_directory_path(
        tmp_path, "PART2.Pagenstecher.vorstellung_de_large-v3_de_to_en"
    )
    assert result.name.startswith(
        "PART2.Pagenstecher.vorstellung_de_large-v3_de_to_en."
    )


def test_process_directory_skips_success_email_when_no_files(tmp_path, monkeypatch):
    """No files in input directory should not trigger a success email."""
    import socket

    monkeypatch.setattr(socket, "gethostbyname", lambda _name: "127.0.0.1")
    import asr_workflow

    called = {"count": 0}

    def _fake_send_success_email(**_kwargs):
        called["count"] += 1

    monkeypatch.setattr(asr_workflow, "send_success_email", _fake_send_success_email)

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    asr_workflow.process_directory(input_dir, output_dir)

    assert called["count"] == 0


def test_process_directory_sends_success_email_when_files_exist(tmp_path, monkeypatch):
    """At least one file should trigger a success email."""
    import socket

    monkeypatch.setattr(socket, "gethostbyname", lambda _name: "127.0.0.1")
    import asr_workflow

    called = {"count": 0}

    def _fake_send_success_email(**_kwargs):
        called["count"] += 1

    def _fake_process_file(_filepath, _output_directory):
        return None

    monkeypatch.setattr(asr_workflow, "send_success_email", _fake_send_success_email)
    monkeypatch.setattr(asr_workflow, "process_file", _fake_process_file)

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    (input_dir / "sample.wav").write_text("data", encoding="utf-8")

    asr_workflow.process_directory(input_dir, output_dir)

    assert called["count"] == 1


def test_llm_config_html_renders_all_llm_sections(monkeypatch):
    from config import app_config as app_config_module

    monkeypatch.setattr(
        app_config_module,
        "combined_config",
        {
            "system": {},
            "whisper": {},
            "llm_meta": {
                "use_summarization": True,
                "use_toc": False,
                "llm_languages": ["de", "en"],
                "verbose": False,
                "debug_file": "",
                "output_debug": "",
                "reasoning_log": "",
                "reasoning_log_max_chars": 0,
            },
            "email": {},
            "bag": {},
            "summarization": {
                "sum_model_path": "/models/sum.gguf",
                "sum_model_config": "",
            },
            "toc": {
                "toc_model_path": "",
                "toc_model_config": "/configs/toc.toml",
            },
            "translation": {
                "translation_model_path": "/models/translate.gguf",
                "translation_model_config": "",
            },
        },
    )

    html = app_config_module.llm_config_html()

    assert "LLM meta:<br>" in html
    assert "Summarization:<br>" in html
    assert "TOC:<br>" in html
    assert "Translation:<br>" in html
    assert "Use_summarization: True<br>" in html
    assert "Use_toc: False<br>" in html
    assert "Llm_languages: de, en<br>" in html
    assert "Reasoning_log_max_chars: 0<br>" in html
    assert "Sum_model_path: /models/sum.gguf<br>" in html
    assert "Sum_model_config: <br>" in html
    assert "Toc_model_path: <br>" in html
    assert "Toc_model_config: /configs/toc.toml<br>" in html
    assert "Translation_model_path: /models/translate.gguf<br>" in html
    assert "Translation_model_config: <br>" in html


def test_send_success_email_includes_full_llm_configuration(monkeypatch):
    import importlib
    import socket

    monkeypatch.setattr(socket, "gethostbyname", lambda _name: "127.0.0.1")
    from config import app_config as app_config_module
    from utils import email_notifications as email_notifications_module

    email_notifications_module = importlib.reload(email_notifications_module)

    monkeypatch.setattr(
        app_config_module,
        "combined_config",
        {
            "system": {"email_notifications": True},
            "whisper": {
                "model": "large-v3",
                "device": "cuda",
                "thread_count": 4,
                "batch_size": 16,
                "beam_size": 5,
                "compute_type": "float16",
                "language": "es",
                "translation_enabled": True,
                "translation_target_language": "en",
                "translation_model": "large-v3",
                "use_initial_prompt": False,
                "initial_prompt": "",
                "max_sentence_length": 80,
                "use_speaker_diarization": True,
                "min_speakers": 1,
                "max_speakers": 3,
                "hf_token": None,
                "pause_marker_threshold": 2.0,
                "api_key": None,
            },
            "llm_meta": {
                "use_summarization": True,
                "use_toc": False,
                "llm_languages": ["de", "en"],
                "verbose": False,
                "debug_file": "",
                "output_debug": "",
                "reasoning_log": "",
                "reasoning_log_max_chars": 0,
            },
            "email": {},
            "bag": {
                "group_identifier": "asr-transcribe-bags",
                "bag_count": "1 of 1",
                "internal_sender_identifier": "internal-identifier",
                "internal_sender_description": "Automatic Transcription by ASR4Memory",
            },
            "summarization": {
                "sum_model_path": "/models/sum.gguf",
                "sum_model_config": "",
            },
            "toc": {
                "toc_model_path": "",
                "toc_model_config": "/configs/toc.toml",
            },
            "translation": {
                "translation_model_path": "/models/translate.gguf",
                "translation_model_config": "",
            },
        },
    )

    sent_email = {}

    def _fake_send_email(subject, body, type):
        sent_email["subject"] = subject
        sent_email["body"] = body
        sent_email["type"] = type

    monkeypatch.setattr(email_notifications_module, "send_email", _fake_send_email)

    process_info = SimpleNamespace(
        filename="sample.wav",
        formatted_audio_length=lambda: "00:00:10",
        formatted_process_duration=lambda: "00:00:02",
        realtime_factor=lambda: 0.20,
    )

    email_notifications_module.send_success_email(
        [process_info], warning_count=0, warning_audio_inputs=[]
    )

    body = sent_email["body"]
    assert sent_email["type"] == "success"
    assert "LLM configuration:</b><br>LLM meta:<br>" in body
    assert "Use_summarization: True<br>" in body
    assert "Use_toc: False<br>" in body
    assert "Summarization:<br>" in body
    assert "Sum_model_path: /models/sum.gguf<br>" in body
    assert "TOC:<br>" in body
    assert "Toc_model_config: /configs/toc.toml<br>" in body
    assert "Translation:<br>" in body
    assert "Translation_model_path: /models/translate.gguf<br>" in body


# --- AI Act Art. 50 transparency notices -----------------------------------

SUMMARY_NOTICE = (
    "This summary was generated by AI from the transcript. It may contain errors."
)
TOC_NOTICE = (
    "This table of contents was generated by AI from the transcript. "
    "It may contain errors."
)
TRANSCRIPT_NOTICE = (
    "This transcript was generated by AI from the original audio. "
    "It may contain errors."
)
TRANSLATION_NOTICE = (
    "This translation was generated by AI from the original audio. "
    "It may contain errors."
)
# Prepared for the switch to translating from the transcript.
TRANSLATION_TRANSCRIPT_NOTICE = (
    "This translation was generated by AI from the original transcript. "
    "It may contain errors."
)

ALL_NOTICES = (
    SUMMARY_NOTICE,
    TOC_NOTICE,
    TRANSCRIPT_NOTICE,
    TRANSLATION_NOTICE,
    TRANSLATION_TRANSCRIPT_NOTICE,
)

TOC_CUES = [
    {"start": 0.0, "end": 12.0, "title": "Kindheit", "level": "H1"},
    {"start": 12.0, "end": 30.0, "title": "Schulzeit", "level": "H2"},
]


@pytest.fixture
def compliance(monkeypatch):
    """
    Sets the [compliance] section in place. An in-place change is required:
    rebinding combined_config would not reach modules holding the old
    reference, while disclosure.get_label() reads it lazily.
    """
    from config import app_config as app_config_module

    def _set(**overrides):
        section = dict(CONST_DEFAULT_CONFIG["compliance"]) | overrides
        monkeypatch.setitem(
            app_config_module.combined_config, "compliance", section
        )
        return section

    return _set


def _load_config_from(tmp_path, monkeypatch, toml_text):
    """Loads a real config.toml through initialize_config() and restores state."""
    from config import app_config as app_config_module

    (tmp_path / "config.toml").write_text(toml_text, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    original = app_config_module.combined_config
    try:
        app_config_module.initialize_config()
        return copy.deepcopy(app_config_module.combined_config)
    finally:
        app_config_module.combined_config = original


# C - config loading, through real TOML files rather than a dict monkeypatch


def test_compliance_section_is_merged_from_toml(tmp_path, monkeypatch):
    loaded = _load_config_from(
        tmp_path,
        monkeypatch,
        '[compliance]\nsummary_label = "Custom notice."\n',
    )

    assert loaded["compliance"]["summary_label"] == "Custom notice."
    assert loaded["compliance"]["toc_label"] == TOC_NOTICE


def test_scalar_section_falls_back_to_defaults_without_crashing(
    tmp_path, monkeypatch, caplog
):
    with caplog.at_level("WARNING"):
        loaded = _load_config_from(tmp_path, monkeypatch, "compliance = 42\n")

    assert loaded["compliance"] == CONST_DEFAULT_CONFIG["compliance"]
    assert "[compliance] is not a table" in caplog.text


def test_all_default_sections_are_present_after_load(tmp_path, monkeypatch):
    loaded = _load_config_from(tmp_path, monkeypatch, "")

    assert set(loaded) == set(CONST_DEFAULT_CONFIG)


def test_notice_defaults_match_required_wording():
    defaults = CONST_DEFAULT_CONFIG["compliance"]

    assert defaults["summary_label"] == SUMMARY_NOTICE
    assert defaults["toc_label"] == TOC_NOTICE
    assert defaults["transcript_label"] == TRANSCRIPT_NOTICE
    # Says "from the original audio" because that is how translation works
    # today; the transcript variant is prepared but not active.
    assert defaults["translation_label"] == TRANSLATION_NOTICE
    assert TRANSLATION_TRANSCRIPT_NOTICE not in defaults.values()


# D - output/disclosure.py


def test_get_label_returns_configured_string(compliance):
    compliance(summary_label="Configured.")

    assert disclosure.get_label(disclosure.SUMMARY) == "Configured."


def test_get_label_empty_string_disables(compliance):
    compliance(summary_label="")

    assert disclosure.get_label(disclosure.SUMMARY) == ""


def test_get_label_whitespace_only_disables(compliance):
    compliance(summary_label="   \n\t ")

    assert disclosure.get_label(disclosure.SUMMARY) == ""


def test_get_label_collapses_whitespace(compliance):
    compliance(summary_label="  first\nsecond\tthird  ")

    assert disclosure.get_label(disclosure.SUMMARY) == "first second third"


def test_get_label_missing_section_falls_back_to_default(monkeypatch):
    from config import app_config as app_config_module

    monkeypatch.delitem(
        app_config_module.combined_config, "compliance", raising=False
    )

    assert disclosure.get_label(disclosure.SUMMARY) == SUMMARY_NOTICE


def test_get_label_non_string_falls_back_to_default_and_warns(compliance, caplog):
    compliance(summary_label=42)

    with caplog.at_level("WARNING"):
        label = disclosure.get_label(disclosure.SUMMARY)

    assert label == SUMMARY_NOTICE
    assert "compliance.summary_label is not a string" in caplog.text


def test_get_label_unknown_kind_raises():
    with pytest.raises(ValueError, match="Unknown disclosure kind"):
        disclosure.get_label("nonsense")


def test_prefix_block_is_idempotent():
    once = disclosure.prefix_block("Body.", SUMMARY_NOTICE)
    twice = disclosure.prefix_block(once, SUMMARY_NOTICE)

    assert twice == once
    assert twice.count(SUMMARY_NOTICE) == 1


def test_prefix_block_leaves_empty_text_unlabelled():
    assert disclosure.prefix_block("", SUMMARY_NOTICE) == ""
    assert disclosure.prefix_block("  \n ", SUMMARY_NOTICE) == "  \n "


def test_prefix_block_without_label_returns_input():
    assert disclosure.prefix_block("Body.", "") == "Body."


# S - summary text files


def _summary_base_path(tmp_path):
    transcripts = tmp_path / "bag" / "data" / "transcripts"
    transcripts.mkdir(parents=True, exist_ok=True)
    return transcripts / "sample"


def test_write_summary_prepends_exact_notice(tmp_path):
    base_path = _summary_base_path(tmp_path)

    written = write_summary(
        base_path, "Zusammenfassung.", disclosure_label=SUMMARY_NOTICE
    )

    lines = written.read_text(encoding="utf-8").split("\n")
    assert lines[0] == SUMMARY_NOTICE
    assert lines[1] == ""
    assert "\n".join(lines[2:]) == "Zusammenfassung."


def test_write_summary_notice_appears_exactly_once(tmp_path):
    base_path = _summary_base_path(tmp_path)
    prelabelled = f"{SUMMARY_NOTICE}\n\nZusammenfassung."

    written = write_summary(base_path, prelabelled, disclosure_label=SUMMARY_NOTICE)

    assert written.read_text(encoding="utf-8").count(SUMMARY_NOTICE) == 1


def test_write_summary_returns_written_path(tmp_path):
    base_path = _summary_base_path(tmp_path)

    written = write_summary(base_path, "Zusammenfassung.", language_code="en")

    assert written.name == "sample_summary_en.txt"
    assert written.exists()


def test_write_summary_without_label_is_unchanged(tmp_path):
    base_path = _summary_base_path(tmp_path)

    written = write_summary(base_path, "Zusammenfassung.")

    assert written.read_text(encoding="utf-8") == "Zusammenfassung."


# T - table of contents VTT files


def test_write_toc_puts_notice_in_webvtt_header(tmp_path):
    base_path = _summary_base_path(tmp_path)

    written = writers_module.write_toc(
        base_path, TOC_CUES, disclosure_label=TOC_NOTICE
    )

    lines = written.read_text(encoding="utf-8").split("\n")
    assert lines[0] == f"WEBVTT - {TOC_NOTICE}"
    assert lines[1] == ""
    assert lines[2] == "1"


def test_write_toc_without_label_writes_plain_signature(tmp_path):
    base_path = _summary_base_path(tmp_path)

    written = writers_module.write_toc(base_path, TOC_CUES)

    assert written.read_text(encoding="utf-8").startswith("WEBVTT\n\n1\n")


def test_write_toc_header_strips_arrow_sequence(tmp_path):
    base_path = _summary_base_path(tmp_path)

    written = writers_module.write_toc(
        base_path, TOC_CUES, disclosure_label="Bad --> notice"
    )

    header = written.read_text(encoding="utf-8").split("\n")[0]
    assert header == "WEBVTT - Bad -> notice"
    assert "-->" not in header


def test_write_toc_cue_numbering_is_unchanged(tmp_path):
    base_path = _summary_base_path(tmp_path)

    labelled = writers_module.write_toc(
        base_path, TOC_CUES, disclosure_label=TOC_NOTICE
    ).read_text(encoding="utf-8")
    plain = writers_module.write_toc(base_path, TOC_CUES).read_text(encoding="utf-8")

    assert labelled.split("\n")[1:] == plain.split("\n")[1:]


def test_write_toc_returns_none_for_error_payload(tmp_path):
    base_path = _summary_base_path(tmp_path)

    result = writers_module.write_toc(
        base_path, {"_error": "skipped"}, disclosure_label=TOC_NOTICE
    )

    assert result is None
    assert not (tmp_path / "bag" / "data" / "content_extraction").exists()


def test_write_toc_returns_none_for_non_list_payload(tmp_path):
    base_path = _summary_base_path(tmp_path)

    assert writers_module.write_toc(base_path, "not a list") is None
    assert writers_module.write_toc(base_path, None) is None


def test_write_toc_returns_written_path_on_success(tmp_path):
    base_path = _summary_base_path(tmp_path)

    written = writers_module.write_toc(base_path, TOC_CUES, language_code="en")

    assert written.name == "sample_toc_en.vtt"


# I - integration through write_output_files


@pytest.fixture
def write_outputs(tmp_path, monkeypatch):
    """Calls write_output_files with a minimal payload and stubbed PDF rendering."""
    monkeypatch.setattr(
        writers_module, "_write_pdfa_2a_from_html", lambda *args, **kwargs: None
    )

    def _call(llm_output=None):
        base_path = tmp_path / "bag" / "data" / "transcripts" / "sample"
        base_path.parent.mkdir(parents=True, exist_ok=True)
        segments = [
            {"start": 0.0, "end": 2.0, "text": "Erster Satz.", "speaker": "SPK_A"},
            {"start": 2.0, "end": 4.0, "text": "Zweiter Satz.", "speaker": "SPK_B"},
        ]
        word_segments = [
            {"word": "Erster", "start": 0.0, "end": 0.9, "score": 0.9},
            {"word": "Satz.", "start": 0.9, "end": 2.0, "score": 0.9},
            {"word": "Zweiter", "start": 2.0, "end": 3.0, "score": 0.9},
            {"word": "Satz.", "start": 3.0, "end": 4.0, "score": 0.9},
        ]
        payload = {"segments": segments, "word_segments": word_segments}
        writers_module.write_output_files(
            base_path=base_path,
            unprocessed_whisperx_output=copy.deepcopy(payload),
            processed_whisperx_output=copy.deepcopy(payload),
            llm_output=llm_output,
        )
        return base_path

    return _call


def _read_llm_output(base_path):
    path = (
        base_path.parent.parent
        / "content_extraction"
        / f"{base_path.name}_llm_output.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _extraction_dir(base_path):
    return base_path.parent.parent / "content_extraction"


def test_failed_toc_language_is_not_claimed_in_applies_to(write_outputs, compliance):
    compliance()

    base_path = write_outputs(
        {
            "toc": {
                "de": TOC_CUES,
                "en": {"_error": "skipped: German TOC failed"},
            }
        }
    )

    extraction = _extraction_dir(base_path)
    assert (extraction / "sample_toc_de.vtt").exists()
    assert not (extraction / "sample_toc_en.vtt").exists()

    blocks = _read_llm_output(base_path)["ai_disclosure"]
    assert blocks == [{"notice": TOC_NOTICE, "applies_to": ["toc.de"]}]


def test_empty_summary_writes_no_file_and_no_applies_to(write_outputs, compliance):
    compliance()

    base_path = write_outputs({"summaries": {"de": "Zusammenfassung.", "en": ""}})

    extraction = _extraction_dir(base_path)
    assert (extraction / "sample_summary_de.txt").exists()
    assert not (extraction / "sample_summary_en.txt").exists()

    blocks = _read_llm_output(base_path)["ai_disclosure"]
    assert blocks == [{"notice": SUMMARY_NOTICE, "applies_to": ["summaries.de"]}]


def test_whitespace_only_summary_writes_no_file_and_no_applies_to(
    write_outputs, compliance
):
    compliance()

    base_path = write_outputs({"summaries": {"de": "Zusammenfassung.", "en": "  \n"}})

    assert not (_extraction_dir(base_path) / "sample_summary_en.txt").exists()
    blocks = _read_llm_output(base_path)["ai_disclosure"]
    assert blocks[0]["applies_to"] == ["summaries.de"]


def test_non_string_summary_is_skipped_without_crashing(write_outputs, compliance):
    compliance()

    base_path = write_outputs({"summaries": {"de": "Zusammenfassung.", "en": None}})

    assert not (_extraction_dir(base_path) / "sample_summary_en.txt").exists()
    blocks = _read_llm_output(base_path)["ai_disclosure"]
    assert blocks[0]["applies_to"] == ["summaries.de"]


def test_toc_only_run_writes_toc_with_toc_disclosure_only(write_outputs, compliance):
    compliance()

    base_path = write_outputs({"toc": {"de": TOC_CUES}})

    extraction = _extraction_dir(base_path)
    assert (extraction / "sample_toc_de.vtt").exists()
    assert not list(extraction.glob("*_summary_*.txt"))

    blocks = _read_llm_output(base_path)["ai_disclosure"]
    assert [block["notice"] for block in blocks] == [TOC_NOTICE]


def test_summary_and_toc_run_writes_both_disclosure_entries(
    write_outputs, compliance
):
    compliance()

    base_path = write_outputs(
        {
            "summaries": {"de": "Zusammenfassung.", "en": "Summary."},
            "toc": {"de": TOC_CUES, "en": TOC_CUES},
        }
    )

    blocks = _read_llm_output(base_path)["ai_disclosure"]
    assert blocks == [
        {"notice": SUMMARY_NOTICE, "applies_to": ["summaries.de", "summaries.en"]},
        {"notice": TOC_NOTICE, "applies_to": ["toc.de", "toc.en"]},
    ]


def test_summary_de_and_en_use_identical_notice(write_outputs, compliance):
    compliance()

    base_path = write_outputs(
        {"summaries": {"de": "Zusammenfassung.", "en": "Summary."}}
    )

    extraction = _extraction_dir(base_path)
    for language_code in ("de", "en"):
        content = (extraction / f"sample_summary_{language_code}.txt").read_text(
            encoding="utf-8"
        )
        assert content.startswith(f"{SUMMARY_NOTICE}\n\n")
        assert content.count(SUMMARY_NOTICE) == 1


def test_all_llm_output_empty_writes_no_disclosure_key(write_outputs, compliance):
    compliance()

    base_path = write_outputs({"summaries": {"de": ""}, "toc": {}})

    assert "ai_disclosure" not in _read_llm_output(base_path)


def test_applies_to_matches_the_files_actually_written(write_outputs, compliance):
    compliance()

    base_path = write_outputs(
        {
            "summaries": {"de": "Zusammenfassung.", "en": "   "},
            "toc": {"de": TOC_CUES, "en": {"_error": "boom"}},
        }
    )

    extraction = _extraction_dir(base_path)
    claimed = {
        target
        for block in _read_llm_output(base_path)["ai_disclosure"]
        for target in block["applies_to"]
    }
    written = {
        f"summaries.{path.stem.rsplit('_', 1)[-1]}"
        for path in extraction.glob("*_summary_*.txt")
    } | {
        f"toc.{path.stem.rsplit('_', 1)[-1]}"
        for path in extraction.glob("*_toc_*.vtt")
    }

    assert claimed == written


def test_broken_compliance_section_still_labels_summaries_and_toc(
    write_outputs, compliance
):
    compliance(summary_label=42, toc_label=None)

    base_path = write_outputs(
        {"summaries": {"de": "Zusammenfassung."}, "toc": {"de": TOC_CUES}}
    )

    extraction = _extraction_dir(base_path)
    summary = (extraction / "sample_summary_de.txt").read_text(encoding="utf-8")
    toc = (extraction / "sample_toc_de.vtt").read_text(encoding="utf-8")

    assert summary.startswith(f"{SUMMARY_NOTICE}\n\n")
    assert toc.startswith(f"WEBVTT - {TOC_NOTICE}\n\n")


def test_llm_output_json_keeps_summaries_and_toc_unchanged(
    write_outputs, compliance
):
    compliance()
    llm_output = {
        "summaries": {"de": "Zusammenfassung.", "en": ""},
        "toc": {"de": TOC_CUES, "en": {"_error": "boom"}},
    }
    original = copy.deepcopy(llm_output)

    base_path = write_outputs(llm_output)

    written = _read_llm_output(base_path)
    assert written["summaries"] == original["summaries"]
    assert written["toc"] == original["toc"]
    assert llm_output == original


def test_with_ai_disclosure_is_idempotent_and_non_mutating():
    llm_output = {
        "ai_disclosure": [{"notice": "stale", "applies_to": ["summaries.de"]}],
        "summaries": {"de": "Zusammenfassung."},
    }
    original = copy.deepcopy(llm_output)

    result = writers_module._with_ai_disclosure(
        llm_output, [(SUMMARY_NOTICE, ["summaries.de"])]
    )

    assert result["ai_disclosure"] == [
        {"notice": SUMMARY_NOTICE, "applies_to": ["summaries.de"]}
    ]
    assert list(result)[0] == "ai_disclosure"
    assert llm_output == original


def test_with_ai_disclosure_returns_input_when_nothing_applies():
    llm_output = {"summaries": {}}

    assert writers_module._with_ai_disclosure(llm_output, [("", [])]) is llm_output
    assert (
        writers_module._with_ai_disclosure(llm_output, [(SUMMARY_NOTICE, [])])
        is llm_output
    )


# G - scope guard: transcripts must stay untouched


def _file_payloads(directory):
    """Yields (name, text) for every file, unpacking zip members for odt/ods."""
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix in (".odt", ".ods"):
            with zipfile.ZipFile(path) as archive:
                for member in archive.namelist():
                    yield f"{path.name}:{member}", archive.read(member).decode(
                        "utf-8", errors="replace"
                    )
            continue
        yield path.name, path.read_text(encoding="utf-8", errors="replace")


def test_transcript_exports_carry_no_notice(write_outputs, compliance):
    compliance()

    base_path = write_outputs(
        {"summaries": {"de": "Zusammenfassung."}, "toc": {"de": TOC_CUES}}
    )

    for name, payload in _file_payloads(base_path.parent):
        for notice in ALL_NOTICES:
            assert notice not in payload, f"{notice!r} leaked into {name}"


def test_segment_text_and_inputs_are_never_modified(write_outputs, compliance):
    compliance(transcript_label=TRANSCRIPT_NOTICE)

    base_path = write_outputs({"summaries": {"de": "Zusammenfassung."}})

    plain = append_affix(base_path, "", ".txt").read_text(encoding="utf-8")
    assert plain.startswith("Erster Satz.\n")

    speaker_csv = append_affix(base_path, "_speaker", ".csv").read_text(
        encoding="utf-8"
    )
    first_row = speaker_csv.split("\n")[1]
    assert first_row.endswith("\tErster Satz.")


# B - BagIt metadata


def _finalize_bag_with(tmp_path, relative_paths, extra_info=None):
    bag_root = tmp_path / "bag"
    payload_files = []
    for relative_path in relative_paths:
        path = bag_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("payload", encoding="utf-8")
        payload_files.append(path)

    finalize_bag(bag_root, payload_files, extra_info or {})
    return (bag_root / "bag-info.txt").read_text(encoding="utf-8")


def test_bag_info_contains_ai_disclosure_fields(tmp_path, compliance):
    compliance()

    bag_info = _finalize_bag_with(
        tmp_path,
        [
            "data/transcripts/sample.txt",
            "data/content_extraction/sample_summary_de.txt",
            "data/content_extraction/sample_toc_de.vtt",
        ],
    )

    assert f"AI-Disclosure-Transcript: {TRANSCRIPT_NOTICE}\n" in bag_info
    assert f"AI-Disclosure-Summary: {SUMMARY_NOTICE}\n" in bag_info
    assert f"AI-Disclosure-TOC: {TOC_NOTICE}\n" in bag_info
    assert "AI-Disclosure-Translation" not in bag_info


def test_bag_info_ignores_transcript_filenames_containing_summary_or_toc(
    tmp_path, compliance
):
    compliance()

    bag_info = _finalize_bag_with(
        tmp_path, ["data/transcripts/interview_summary_toc_01_de.txt"]
    )

    assert "AI-Disclosure-Transcript:" in bag_info
    assert "AI-Disclosure-Summary" not in bag_info
    assert "AI-Disclosure-TOC" not in bag_info


def test_bag_info_omits_fields_for_absent_content(tmp_path, compliance):
    compliance()

    bag_info = _finalize_bag_with(tmp_path, ["documentation/README.md"])

    for field in (
        "AI-Disclosure-Transcript",
        "AI-Disclosure-Translation",
        "AI-Disclosure-Summary",
        "AI-Disclosure-TOC",
    ):
        assert field not in bag_info


def test_bag_info_contains_translation_field_for_translated_bags(
    tmp_path, compliance
):
    compliance()

    bag_info = _finalize_bag_with(
        tmp_path,
        ["data/transcripts/sample.txt", "data/translations/sample_en.txt"],
    )

    assert f"AI-Disclosure-Translation: {TRANSLATION_NOTICE}\n" in bag_info


def test_bag_info_omits_translation_field_when_label_disabled(tmp_path, compliance):
    compliance(translation_label="")

    bag_info = _finalize_bag_with(
        tmp_path,
        ["data/transcripts/sample.txt", "data/translations/sample_en.txt"],
    )

    assert "AI-Disclosure-Translation" not in bag_info
    assert "\n\n" not in bag_info


def test_bag_info_translation_wording_switches_with_the_source(tmp_path, compliance):
    """Activating the transcript wording is config only, no code change."""
    compliance(translation_label=TRANSLATION_TRANSCRIPT_NOTICE)

    bag_info = _finalize_bag_with(
        tmp_path,
        ["data/transcripts/sample.txt", "data/translations/sample_en.txt"],
    )

    assert f"AI-Disclosure-Translation: {TRANSLATION_TRANSCRIPT_NOTICE}\n" in bag_info


def test_bag_info_field_can_be_overridden_by_extra_info(tmp_path, compliance):
    compliance()

    bag_info = _finalize_bag_with(
        tmp_path,
        ["data/transcripts/sample.txt"],
        extra_info={"AI-Disclosure-Transcript": "Explicit override."},
    )

    assert "AI-Disclosure-Transcript: Explicit override.\n" in bag_info
    assert TRANSCRIPT_NOTICE not in bag_info


def test_tagmanifest_and_bag_size_stay_consistent(tmp_path, compliance):
    compliance()

    bag_root = tmp_path / "bag"
    payload = bag_root / "data" / "transcripts" / "sample.txt"
    payload.parent.mkdir(parents=True)
    payload.write_text("payload", encoding="utf-8")

    finalize_bag(bag_root, [payload], {})

    bag_info_path = bag_root / "bag-info.txt"
    tag_manifest = (bag_root / "tagmanifest-sha512.txt").read_text(encoding="utf-8")

    assert "Bag-Size:" in bag_info_path.read_text(encoding="utf-8")
    assert f"{sha512(bag_info_path)}  bag-info.txt" in tag_manifest
