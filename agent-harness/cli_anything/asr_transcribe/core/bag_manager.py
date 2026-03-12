"""BagIt archive operations."""

import hashlib
from pathlib import Path

from cli_anything.asr_transcribe.utils.asr_backend import ensure_project_importable


def validate_bag(bag_path: str) -> dict:
    """Validate a BagIt directory structure.

    Checks for required files, manifest integrity, and directory structure.

    Returns:
        Dict with "valid" (bool), "errors" (list), "info" (dict).
    """
    path = Path(bag_path)
    errors = []
    info = {}

    if not path.exists():
        return {"valid": False, "errors": [f"Path does not exist: {bag_path}"], "info": {}}

    if not path.is_dir():
        return {"valid": False, "errors": [f"Not a directory: {bag_path}"], "info": {}}

    # Check required files
    bagit_txt = path / "bagit.txt"
    if not bagit_txt.exists():
        errors.append("Missing bagit.txt")
    else:
        content = bagit_txt.read_text(encoding="utf-8")
        if "BagIt-Version" not in content:
            errors.append("bagit.txt missing BagIt-Version")

    bag_info_txt = path / "bag-info.txt"
    if bag_info_txt.exists():
        info_content = bag_info_txt.read_text(encoding="utf-8")
        for line in info_content.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                info[key.strip()] = value.strip()

    manifest_path = path / "manifest-sha512.txt"
    if not manifest_path.exists():
        errors.append("Missing manifest-sha512.txt")
    else:
        # Verify checksums
        manifest_errors = _verify_manifest(path, manifest_path)
        errors.extend(manifest_errors)

    # Check data directory
    data_dir = path / "data"
    if not data_dir.exists():
        errors.append("Missing data/ directory")
    else:
        # Count payload files
        payload_files = list(data_dir.rglob("*"))
        payload_files = [f for f in payload_files if f.is_file()]
        info["payload_file_count"] = len(payload_files)
        info["payload_size_bytes"] = sum(f.stat().st_size for f in payload_files)

    # Check expected subdirectories
    expected_dirs = ["data/transcripts"]
    for d in expected_dirs:
        if not (path / d).exists():
            errors.append(f"Missing expected directory: {d}")

    info["bag_name"] = path.name

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "info": info,
    }


def _verify_manifest(bag_root: Path, manifest_path: Path) -> list[str]:
    """Verify SHA-512 checksums in the manifest."""
    errors = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("  ", 1)
            if len(parts) != 2:
                errors.append(f"Malformed manifest line: {line}")
                continue
            expected_hash, rel_path = parts
            file_path = bag_root / rel_path
            if not file_path.exists():
                errors.append(f"Missing payload file: {rel_path}")
                continue
            actual_hash = _sha512(file_path)
            if actual_hash != expected_hash:
                errors.append(f"Checksum mismatch for {rel_path}")
    return errors


def _sha512(path: Path) -> str:
    """Calculate SHA-512 checksum."""
    digest = hashlib.sha512()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def zip_bag(bag_path: str) -> dict:
    """Create a ZIP archive of a BagIt directory.

    Args:
        bag_path: Path to the bag directory.

    Returns:
        Dict with zip_path and size.
    """
    root = ensure_project_importable()

    path = Path(bag_path)
    if not path.exists():
        raise FileNotFoundError(f"Bag directory not found: {bag_path}")

    from utils.utilities import zip_bag_directory

    archive_path = zip_bag_directory(path)

    return {
        "zip_path": str(archive_path),
        "size_bytes": archive_path.stat().st_size,
        "message": f"Created ZIP archive: {archive_path}",
    }


def create_bag(output_dir: str, files: list[str] = None, metadata: dict = None) -> dict:
    """Create a new BagIt directory structure.

    Args:
        output_dir: Path where the bag directory will be created.
        files: Optional list of file paths to copy into data/transcripts/.
        metadata: Optional dict of extra bag-info.txt metadata.

    Returns:
        Dict with bag_path and file count.
    """
    import shutil

    path = Path(output_dir)
    if path.exists():
        return {"created": False, "message": f"Directory already exists: {output_dir}"}

    # Create bag structure
    path.mkdir(parents=True)
    data_dir = path / "data"
    data_dir.mkdir()
    transcripts_dir = data_dir / "transcripts"
    transcripts_dir.mkdir()

    # bagit.txt
    (path / "bagit.txt").write_text(
        "BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n",
        encoding="utf-8",
    )

    # Copy files into data/transcripts/
    payload_files = []
    if files:
        for fpath in files:
            src = Path(fpath)
            if not src.exists():
                continue
            dest = transcripts_dir / src.name
            shutil.copy2(src, dest)
            payload_files.append(dest)

    # Write manifest
    manifest_path = path / "manifest-sha512.txt"
    with open(manifest_path, "w", encoding="utf-8") as mf:
        for pf in sorted(payload_files, key=lambda p: p.relative_to(path).as_posix()):
            checksum = _sha512(pf)
            rel = pf.relative_to(path).as_posix()
            mf.write(f"{checksum}  {rel}\n")

    # Write bag-info.txt
    info = metadata or {}
    bag_info_path = path / "bag-info.txt"
    with open(bag_info_path, "w", encoding="utf-8") as bf:
        for key, value in info.items():
            bf.write(f"{key}: {value}\n")

    return {
        "created": True,
        "bag_path": str(path),
        "file_count": len(payload_files),
        "message": f"Created bag at {path} with {len(payload_files)} file(s).",
    }


def get_bag_info(bag_path: str) -> dict:
    """Get metadata from a BagIt bag-info.txt file.

    Args:
        bag_path: Path to the bag directory.

    Returns:
        Dict of bag-info metadata.
    """
    path = Path(bag_path)
    bag_info_path = path / "bag-info.txt"

    if not bag_info_path.exists():
        raise FileNotFoundError(f"bag-info.txt not found in: {bag_path}")

    info = {}
    with open(bag_info_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                info[key.strip()] = value.strip()

    # Add computed fields
    data_dir = path / "data"
    if data_dir.exists():
        payload_files = [f for f in data_dir.rglob("*") if f.is_file()]
        info["_payload_file_count"] = len(payload_files)
        info["_payload_size_bytes"] = sum(f.stat().st_size for f in payload_files)

        # List subdirectories
        subdirs = [d.name for d in data_dir.iterdir() if d.is_dir()]
        info["_data_subdirectories"] = sorted(subdirs)

    return info
