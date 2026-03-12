"""Transcription operations — wraps the asr-transcribe pipeline."""

from pathlib import Path

from cli_anything.asr_transcribe.utils.asr_backend import ensure_project_importable


def transcribe_file(audio_path: str, output_dir: str = None) -> dict:
    """Transcribe a single audio file through the full pipeline.

    Args:
        audio_path: Path to the audio file.
        output_dir: Output directory. If None, uses config default.

    Returns:
        Dict with status, output paths, and processing info.
    """
    root = ensure_project_importable()
    filepath = Path(audio_path).resolve()

    if not filepath.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    from config.app_config import get_config

    config = get_config()

    if output_dir:
        out = Path(output_dir).resolve()
    else:
        out = Path(config["system"]["output_path"]).resolve()

    if not out.exists():
        out.mkdir(parents=True, exist_ok=True)

    # Import and run the workflow
    from asr_workflow import process_file

    try:
        process_file(filepath, out)
        return {
            "status": "success",
            "audio_file": str(filepath),
            "output_directory": str(out),
            "message": f"Transcription completed for {filepath.name}",
        }
    except Exception as e:
        return {
            "status": "error",
            "audio_file": str(filepath),
            "output_directory": str(out),
            "message": str(e),
        }


def transcribe_batch(input_dir: str, output_dir: str = None) -> dict:
    """Transcribe all eligible audio files in a directory.

    Args:
        input_dir: Directory containing audio files.
        output_dir: Output directory. If None, uses config default.

    Returns:
        Dict with status, file count, and output directory.
    """
    root = ensure_project_importable()
    input_path = Path(input_dir).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    from config.app_config import get_config
    from utils.utilities import should_be_processed

    config = get_config()

    if output_dir:
        out = Path(output_dir).resolve()
    else:
        out = Path(config["system"]["output_path"]).resolve()

    if not out.exists():
        out.mkdir(parents=True, exist_ok=True)

    # Count eligible files
    all_files = list(input_path.glob("*"))
    eligible = [p for p in all_files if should_be_processed(p)]
    eligible.sort()

    if not eligible:
        return {
            "status": "success",
            "file_count": 0,
            "input_directory": str(input_path),
            "output_directory": str(out),
            "message": "No eligible files found.",
        }

    from asr_workflow import process_directory

    try:
        process_directory(input_path, out)
        return {
            "status": "success",
            "file_count": len(eligible),
            "files": [f.name for f in eligible],
            "input_directory": str(input_path),
            "output_directory": str(out),
            "message": f"Batch transcription completed for {len(eligible)} file(s).",
        }
    except Exception as e:
        return {
            "status": "error",
            "file_count": len(eligible),
            "input_directory": str(input_path),
            "output_directory": str(out),
            "message": str(e),
        }
