def system_prompt_summaries(language: str) -> str:
    """Build system prompt instructions for summaries based on language."""
    if language == "en":
        return (
            "Produce a concise summary (max. 200 words) in English.\n\n"
            "Processing:\n"
            "– Fix ASR issues silently; ignore filler words.\n"
            "– Focus on central topics and facts; omit small talk and repetition.\n"
            "– Mention each fact once; aggressively deduplicate.\n\n"
            "Style:\n"
            "– Use third person only, neutral register, present tense.\n"
            "– No quotes, no direct speech, no subjective judgments.\n"
            "– For unclear references, insert placeholders such as [PERSON] or [PLACE].\n\n"
            "Output: single paragraph, no heading, start directly with the content.\n"
        )

    # Default to German instructions.
    return (
        "Erstelle eine präzise Zusammenfassung (max. 200 Wörter) auf Deutsch.\n\n"
        "Verarbeitung:\n"
        "– Korrigiere ASR-Fehler stillschweigend; ignoriere Füllwörter.\n"
        "– Fokus auf Hauptthemen und zentrale Fakten; weglassen: Small Talk, Wiederholungen.\n"
        "– Jeder Fakt nur einmal; dedupliziere rigoros.\n\n"
        "Stil:\n"
        "– Nur 3. Person, keine direkte Anrede (kein 'du/Sie', keine Titel).\n"
        "– Neutral, Präsens, keine Zitate oder Wertungen.\n"
        "– Bei Unklarheit: Platzhalter ([PERSON], [ORT]) oder kurze Statusangabe.\n\n"
        "Ausgabe: Ein Absatz, ohne Überschrift, direkt mit Inhalt beginnen.\n"
    )
