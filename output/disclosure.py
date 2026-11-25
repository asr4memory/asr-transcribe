"""
AI Act Art. 50 transparency notices for exported artifacts.

Pure string resolution: this module knows the wordings, not the file formats.
It imports only from config.* and the stdlib, so it can be loaded from
anywhere - including utils.utilities, where importing output.* at module level
would create a cycle.
"""

from config.app_config import get_config
from config.default_config import CONST_DEFAULT_CONFIG
from config.logger import logger

SUMMARY = "summary"
TOC = "toc"
TRANSCRIPT = "transcript"
TRANSLATION = "translation"

_CONFIG_KEYS = {
    SUMMARY: "summary_label",
    TOC: "toc_label",
    TRANSCRIPT: "transcript_label",
    TRANSLATION: "translation_label",
}

_FALLBACK = CONST_DEFAULT_CONFIG.get("compliance", {})


def get_label(kind: str) -> str:
    """
    Resolves a configured notice. Returns '' only when explicitly disabled.
    A malformed value falls back to the default, because a typo must not
    silently switch off a mandatory notice.
    """
    try:
        key = _CONFIG_KEYS[kind]
    except KeyError:
        raise ValueError(f"Unknown disclosure kind: {kind!r}") from None

    section = get_config().get("compliance")
    if not isinstance(section, dict):
        section = _FALLBACK

    value = section.get(key, _FALLBACK.get(key, ""))
    if not isinstance(value, str):
        logger.warning(
            "Config compliance.%s is not a string (%r); using default.", key, value
        )
        value = _FALLBACK.get(key, "")

    # Collapse whitespace: a multi-line value would break the "first line plus
    # blank line" contract, the WEBVTT header line and bag-info.txt fields.
    return " ".join(value.split())


def prefix_block(text: str, label: str) -> str:
    """
    Prepends the notice plus a blank line.
    No-op when the notice is disabled, the text is empty or already prefixed.
    """
    if not label or not text.strip() or text.startswith(label):
        return text
    return f"{label}\n\n{text}"
