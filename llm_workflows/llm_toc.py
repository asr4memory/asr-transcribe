def system_prompt_toc(language: str) -> str:
    """Build system prompt instructions for table of contents based on language."""
    if language == "en":
        with open(
            "/home/kompiel/python_scripts/asr-transcribe/llm_workflows/prompts/toc/toc_en.md",
            "r",
        ) as f:
            system_prompt = f.read()
        return system_prompt

    else:
        with open(
            "/home/kompiel/python_scripts/asr-transcribe/llm_workflows/prompts/toc/toc_de.md",
            "r",
        ) as f:
            system_prompt = f.read()
        return system_prompt
