"""
Subprocess wrapper for LLM summarization.
Runs LLM model in isolated subprocess to ensure memory is freed after processing.
This allows large models (20GB+) to be loaded and fully cleaned up between files.
"""

import sys
import pickle
import torch
from transformers import pipeline


def load_llm_model():
    """Load an LLM model for summarization."""
    model_id = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    pipe = pipeline(
        "text-generation",
        model=model_id,
        torch_dtype="auto",
        device_map="auto",
)
    return pipe



def generate_summary(segments, pipe): ## add: Mehrsprachigkeit
    """
    Generate a summary from the given text segments using the provided LLM pipeline.
    """
    system_prompt = (
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

    # Build the user prompt with the interview content
    user_content = ""

    for segment in segments:
        user_content += f"{segment['text']}\n"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    outputs = pipe(
            messages,
            max_new_tokens=500,
    )
    assistant_content = outputs[0]['generated_text'][-1]
    summarized_text = assistant_content["content"]

    return summarized_text


def summarize_segments(segments):
    """
    Complete LLM pipeline: load model + generate summary.
    Subprocess exit will free all memory.
    """
    # Load model
    pipe = load_llm_model()

    # Generate summary
    summary = generate_summary(segments, pipe)

    # Cleanup (optional since subprocess will exit, but good practice)
    del pipe

    return summary


def main():
    """Main subprocess entry point."""
    try:
        # Read pickled segments from stdin
        input_data = sys.stdin.buffer.read()
        segments = pickle.loads(input_data)

        # Generate summary
        summary = summarize_segments(segments)

        # Write result to stdout
        sys.stdout.buffer.write(pickle.dumps(summary))
        sys.exit(0)

    except Exception as e:
        # Write error to stderr and exit with error code
        print(f"LLM subprocess error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
