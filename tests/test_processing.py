import copy
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
