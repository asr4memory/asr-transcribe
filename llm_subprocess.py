"""
Subprocess wrapper for LLM summarization.
Runs LLM model in isolated subprocess to ensure memory is freed after processing.
This allows large models (20GB+) to be loaded and fully cleaned up between files.
"""

import sys
import pickle
from typing import Dict
from llama_cpp import Llama
from app_config import get_config
from utilities import cleanup_cuda_memory

config = get_config()
n_gpu_layers = config["llm"]["n_gpu_layers"]
model_path = config["llm"]["model_path"]
verbose = config["llm"].get("verbose", False)


def get_summary_languages() -> list[str]:
    languages = config["llm"].get("summary_languages", ["de", "en"])
    if isinstance(languages, str):
        languages = [languages]
    cleaned = []
    for lang in languages:
        if isinstance(lang, str) and lang.strip():
            cleaned.append(lang.strip().lower())
    return cleaned


def load_model(trial: int) -> Llama:
    """Initialise the Llama model with trial-specific context settings."""
    if trial == 1:
        return Llama(
            model_path=model_path,
            n_gpu_layers=n_gpu_layers,
            n_ctx=32768,
            n_batch=512,
            verbose=verbose,
        )
    return Llama(
        model_path=model_path,
        n_gpu_layers=n_gpu_layers,
        n_ctx=65536,
        n_batch=256,
        verbose=verbose,
    )


def build_system_prompt(language: str) -> str:
    """Create a language-specific system prompt."""
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


def build_user_prompt(segments) -> str:
    """Concatenate all segment texts for the user prompt."""
    return "\n".join(segment["text"] for segment in segments)


def generate_summary(llm: Llama, system_prompt: str, user_prompt: str) -> str:
    """Generate a summary using llama_cpp for a given prompt."""
    output = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=4000,
        temperature=0.3,
        top_p=0.9,
        repeat_penalty=1.2,
    )
    summary = output["choices"][0]["message"]["content"]

    delimiter = "|end|><|start|>assistant<|channel|>final<|message|>"
    if delimiter in summary:
        summary = summary.split(delimiter, 1)[1]

    return summary.strip()


def main():
    """Main subprocess entry point."""
    max_trials = 2
    summaries: Dict[str, str] | None = None
    languages = get_summary_languages()
    llm = None

    if not languages:
        sys.stdout.buffer.write(pickle.dumps(({}, 0)))
        sys.exit(0)

    for trial in range(1, max_trials + 1):
        try:
            # Read pickled segments from stdin (nur beim ersten Versuch)
            if trial == 1:
                input_data = sys.stdin.buffer.read()
                segments = pickle.loads(input_data)

            llm = load_model(trial)
            user_prompt = build_user_prompt(segments)
            summaries = {}
            for language in languages:
                system_prompt = build_system_prompt(language)
                summaries[language] = generate_summary(llm, system_prompt, user_prompt)

            # Erfolgreich - Ergebnis ausgeben
            sys.stdout.buffer.write(pickle.dumps((summaries, trial)))
            sys.exit(0)

        except Exception as e:
            # Cleanup the failed model and free GPU memory
            if llm is not None:
                del llm
            cleanup_cuda_memory()

            if trial < max_trials:
                print(f"LLM subprocess error on trial {trial}. Retrying with trial {trial + 1}...", file=sys.stderr)
            else:
                # Letzter Versuch fehlgeschlagen
                print(f"LLM subprocess error: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    main()
