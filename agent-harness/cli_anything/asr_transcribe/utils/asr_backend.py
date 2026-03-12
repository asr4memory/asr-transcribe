"""Backend verification — checks that asr-transcribe and its dependencies are available."""

import importlib
import sys
from pathlib import Path


def _find_project_root() -> Path:
    """Locate the asr-transcribe project root by walking up from this file."""
    # agent-harness/cli_anything/asr_transcribe/utils/asr_backend.py
    # -> project root is 4 levels up
    candidate = Path(__file__).resolve().parents[4]
    if (candidate / "asr_workflow.py").exists():
        return candidate
    # Fallback: try CWD
    cwd = Path.cwd()
    if (cwd / "asr_workflow.py").exists():
        return cwd
    raise RuntimeError(
        "Cannot find asr-transcribe project root.\n"
        "Ensure you are running from the project directory or its agent-harness/ subdirectory.\n"
        "Expected to find asr_workflow.py in the project root."
    )


def ensure_project_importable():
    """Add the asr-transcribe project root to sys.path so its modules can be imported."""
    root = _find_project_root()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def check_dependencies() -> dict:
    """Check which backend dependencies are available.

    Returns a dict of dependency name -> {"available": bool, "version": str|None, "error": str|None}.
    """
    deps = {}

    for name, import_name in [
        ("whisperx", "whisperx"),
        ("torch", "torch"),
        ("llama-cpp-python", "llama_cpp"),
        ("toml", "toml"),
        ("jinja2", "jinja2"),
        ("xhtml2pdf", "xhtml2pdf"),
        ("pyexcel-ods3", "pyexcel_ods3"),
    ]:
        try:
            mod = importlib.import_module(import_name)
            version = getattr(mod, "__version__", None) or getattr(mod, "version", None)
            deps[name] = {"available": True, "version": str(version) if version else "unknown", "error": None}
        except ImportError as e:
            deps[name] = {"available": False, "version": None, "error": str(e)}

    return deps


def find_asr_transcribe() -> Path:
    """Find the asr-transcribe project root. Raises RuntimeError with install instructions if not found."""
    try:
        return _find_project_root()
    except RuntimeError:
        raise RuntimeError(
            "asr-transcribe project not found.\n"
            "Install/clone it and run this CLI from the project directory:\n"
            "  git clone <asr-transcribe-repo>\n"
            "  cd asr-transcribe\n"
            "  uv sync\n"
            "  pip install -e agent-harness/"
        )
