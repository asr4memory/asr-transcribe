def system_prompt_summaries(language: str) -> str:
    """Build system prompt instructions for summaries based on language."""
    if language == "en":
        with open(
            "/home/kompiel/python_scripts/asr-transcribe/llm_workflows/prompts/summarization/summary_en.md",
            "r",
        ) as f:
            system_prompt = f.read()
        return system_prompt

    else:
        with open(
            "/home/kompiel/python_scripts/asr-transcribe/llm_workflows/prompts/summarization/summary_de.md",
            "r",
        ) as f:
            system_prompt = f.read()
        return system_prompt
