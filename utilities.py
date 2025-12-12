"""
Utilities and helper functions for the main ASR script.
"""

from datetime import datetime, timezone
import hashlib
import re
from pathlib import Path
from decimal import Decimal
import gc
import shutil
import torch
from app_config import get_config

config = get_config()
device = config["whisper"]["device"]


def should_be_processed(filepath: Path):
    "Checks whether the file should be processed. File has which type?"
    filename = filepath.name
    if filename.startswith("_"):
        return False
    elif filename.startswith("."):
        return False
    elif filename.endswith("backup"):
        return False
    elif filename.endswith("_test_"):
        return False
    else:
        return True


def format_timestamp(seconds, milli_separator="."):
    """
    Convert seconds to hh:mm:ss and hh:mm:ss.ms format and use decimal for precise arithmetic
    """
    time_in_seconds = Decimal(seconds)
    hours = time_in_seconds // 3600
    remainder = time_in_seconds % 3600
    minutes = remainder // 60
    seconds = remainder % 60
    milliseconds = (seconds - int(seconds)) * 1000

    formatted_time = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
    formatted_time_ms = f"{formatted_time}{milli_separator}{int(milliseconds):03}"

    return formatted_time, formatted_time_ms


def check_for_hallucination_warnings(text: str) -> list:
    """
    Check the output for the message "Failed to align segment" in the
    stdout/terminal output to identify AI hallucinations.
    """
    hallucination_regexp = r'Failed to align segment \((".*")\)'
    match = re.search(hallucination_regexp, text)

    if match:
        return list(match.groups())
    else:
        return None


def create_output_files_directory_path(
    output_directory: Path, filename_base: str
) -> Path:
    now = datetime.now(tz=timezone.utc)
    date_suffix = now.strftime(".%Y-%m-%dT%H%M%SZ")
    dir_path = output_directory / filename_base
    result = dir_path.with_suffix(date_suffix)
    return result


def cleanup_cuda_memory():
    """Aggressive CUDA memory cleanup."""
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()
        torch.cuda.synchronize()


def prepare_bag_directory(bag_root: Path) -> Path:
    """Create the BagIt directory structure and return the payload directory."""
    if bag_root.exists():
        raise FileExistsError(f"Bag directory already exists: {bag_root}")

    bag_root.mkdir(parents=True)
    data_dir = bag_root / "data"
    data_dir.mkdir()
    transcripts_dir = data_dir / "transcripts"
    transcripts_dir.mkdir()
    abstracts_dir = data_dir / "abstracts"
    abstracts_dir.mkdir()
    ohd_import_dir = data_dir / "ohd_import"
    ohd_import_dir.mkdir()
    documentation_dir = bag_root / "documentation"
    documentation_dir.mkdir()
    return transcripts_dir


def zip_bag_directory(bag_root: Path) -> Path:
    """Create a ZIP archive of the bag directory and return the archive path."""
    if not bag_root.exists():
        raise FileNotFoundError(f"Bag directory does not exist: {bag_root}")

    base_name = str(bag_root)
    archive_path = Path(f"{base_name}.zip")
    if archive_path.exists():
        archive_path.unlink()

    shutil.make_archive(
        base_name,
        "zip",
        root_dir=str(bag_root.parent),
        base_dir=bag_root.name,
    )
    return archive_path


def finalize_bag(
    bag_root: Path, payload_files: list[Path], extra_info: dict | None = None
):
    """Write BagIt tag files, manifests and metadata for the generated outputs."""
    payload_files_sorted = sorted(
        payload_files, key=lambda path: path.relative_to(bag_root).as_posix()
    )

    bagit_path = bag_root / "bagit.txt"
    bagit_path.write_text(
        "BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n",
        encoding="utf-8",
    )

    total_bytes = sum(p.stat().st_size for p in payload_files_sorted)
    file_count = len(payload_files_sorted)
    now = datetime.now(tz=timezone.utc)

    bag_info = {
        "Bagging-Date": now.strftime("%Y-%m-%d"),
        "Payload-Oxum": f"{total_bytes}.{file_count}",
    }
    if extra_info:
        bag_info.update(extra_info)

    bag_info.setdefault(
        "Bag-Description",
        (
            "The bag contains multiple transcript formats and derivatives "
            "for varied use scenarios in the /data directory: "
            "In the /abstracts directory, summaries in german and english are stored. "
            "The /ohd_import directory contains the transcript for import into Oral-History.Digital. "
            "The /transcripts directory contains all transcripts. "
            "More information can be found in the /documentation directory. Further details: "
            "https://www.fu-berlin.de/asr4memory"
        ),
    )

    bag_info_path = bag_root / "bag-info.txt"

    manifest_path = bag_root / "manifest-sha512.txt"
    with manifest_path.open("w", encoding="utf-8") as manifest_file:
        for path in payload_files_sorted:
            checksum = sha512(path)
            relative_path = path.relative_to(bag_root).as_posix()
            manifest_file.write(f"{checksum}  {relative_path}\n")

    tag_manifest_path = bag_root / "tagmanifest-sha512.txt"
    data_dir = bag_root / "data"

    def _current_tag_files(include_tag_manifest: bool = False) -> list[Path]:
        tag_files = []
        for file_path in sorted(bag_root.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path == tag_manifest_path:
                continue
            try:
                if file_path.is_relative_to(data_dir):
                    continue
            except AttributeError:
                # Fallback for Python < 3.9 (not expected but keeps compatibility)
                if str(file_path).startswith(str(data_dir) + "/"):
                    continue
            tag_files.append(file_path)

        if include_tag_manifest and tag_manifest_path.exists():
            tag_files.append(tag_manifest_path)
        return tag_files

    def _compute_bag_size(include_tag_manifest: bool = False) -> str:
        tag_files = _current_tag_files(include_tag_manifest)
        bag_size_bytes = total_bytes + sum(path.stat().st_size for path in tag_files)
        return _format_size(bag_size_bytes)

    bag_size_value = None
    # The Bag-Size influences the size of bag-info.txt and tagmanifest-sha512.txt.
    # This loop recalculates the total size until it is stable.
    while True:
        if bag_size_value is None:
            bag_info.pop("Bag-Size", None)
        else:
            bag_info["Bag-Size"] = bag_size_value

        _write_bag_info_file(bag_info_path, bag_info)
        _write_tag_manifest(tag_manifest_path, _current_tag_files())

        new_size = _compute_bag_size(include_tag_manifest=True)
        if new_size == bag_size_value:
            break
        bag_size_value = new_size


def _format_size(num_bytes: int) -> str:
    """Return human-readable size string for Bag-Size."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    size = float(num_bytes)
    units = ["KB", "MB", "GB", "TB", "PB"]
    for unit in units:
        size /= 1024.0
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.2f} {unit}"
    return f"{size:.2f} PB"


def _write_bag_info_file(path: Path, info: dict):
    """Write key/value pairs to bag-info.txt in insertion order."""
    with path.open("w", encoding="utf-8") as info_file:
        for key, value in info.items():
            info_file.write(f"{key}: {value}\n")


def _write_tag_manifest(path: Path, tag_files: list[Path]):
    """Write tagmanifest-sha512.txt for the given tag files."""
    with path.open("w", encoding="utf-8") as tag_manifest:
        for file_path in tag_files:
            checksum = sha512(file_path)
            relative_path = file_path.relative_to(path.parent).as_posix()
            tag_manifest.write(f"{checksum}  {relative_path}\n")


def sha512(path: Path) -> str:
    """Calculate the SHA-512 checksum for a file."""
    digest = hashlib.sha512()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()
