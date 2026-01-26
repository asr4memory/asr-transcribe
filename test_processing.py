import copy
import pytest
import zipfile
from output.post_processing import (
    sentence_is_incomplete,
    uppercase_sentences,
    split_long_sentences,
)
from utils.utilities import prepare_bag_directory, finalize_bag, sha512, zip_bag_directory
from output.writers import write_summary


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
    """Ensure summary files for DE and EN are written into llm_output."""
    bag_root = tmp_path / "bag"
    data_transcripts = bag_root / "data" / "transcripts"
    data_transcripts.mkdir(parents=True)
    base_path = data_transcripts / "sample"

    write_summary(base_path, "Zusammenfassung DE")
    write_summary(base_path, "Summary EN", language_code="en")

    llm_output_dir = bag_root / "data" / "llm_output"
    de_file = llm_output_dir / "sample_summary_de.txt"
    en_file = llm_output_dir / "sample_summary_en.txt"

    assert de_file.exists()
    assert en_file.exists()
    assert "Zusammenfassung" in de_file.read_text(encoding="utf-8")
    assert "Summary EN" in en_file.read_text(encoding="utf-8")
