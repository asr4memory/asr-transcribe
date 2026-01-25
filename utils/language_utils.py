"""
Language utilities for ASR workflow.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Tuple
from config.app_config import get_config

config = get_config()


@dataclass(frozen=True)
class LanguageMeta:
    source_language: str
    output_language: str
    descriptor: str
    target_language: str


def get_llm_languages() -> List[str]:
    """Get configured LLM languages from config."""
    languages = config["llm"].get("llm_languages", ["de", "en"])
    if isinstance(languages, str):
        languages = [languages]
    cleaned = []
    for lang in languages:
        if isinstance(lang, str) and lang.strip():
            cleaned.append(lang.strip().lower())
    return cleaned


LLM_LANGUAGES = get_llm_languages()


def _normalize_language(value, default="auto") -> str:
    """Normalize language value, returning default if empty."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def get_language_descriptor(result: dict) -> Tuple[str, str, str, str]:
    """
    Build language metadata for filenames/bag info.
    Returns (source_language, output_language, descriptor_string, target_language).
    """
    configured_language = config["whisper"].get("language")
    translation_enabled = result.get("translation_enabled", False)
    source_language = result.get("source_language") or configured_language
    output_language = result.get("output_language") or source_language
    target_language = (
        result.get("translation_target_language")
        or result.get("translation_output_language")
        or output_language
    )

    normalized_source = _normalize_language(source_language)
    normalized_output = _normalize_language(output_language, default=normalized_source)
    normalized_target = _normalize_language(target_language, default=normalized_output)

    descriptor = normalized_output
    if translation_enabled:
        descriptor = f"{normalized_source}_to_{normalized_target}"

    return normalized_source, normalized_output, descriptor, normalized_target


def build_language_meta(result: Dict[str, Any]) -> LanguageMeta:
    """Build LanguageMeta from whisper result dict."""
    src, out, desc, tgt = get_language_descriptor(result)
    return LanguageMeta(source_language=src, output_language=out, descriptor=desc, target_language=tgt)


def derive_model_name(result: Dict[str, Any]) -> str:
    """Extract model name from result or config."""
    model_used = result.get("model_name") or config["whisper"]["model"]
    return Path(str(model_used)).name if model_used else "unknown-model"
