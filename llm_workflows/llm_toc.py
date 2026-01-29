from pathlib import Path


def system_prompt_toc(language: str) -> str:
    """Build system prompt instructions for table of contents based on language."""
    base = Path(__file__).parent / "prompts" / "toc"
    filename = "toc_en.md" if language == "en" else "toc_de.md"
    return (base / filename).read_text()
