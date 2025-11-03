"""
Subprocess wrapper for LLM summarization.
Runs LLM model in isolated subprocess to ensure memory is freed after processing.
This allows large models (20GB+) to be loaded and fully cleaned up between files.
"""

import sys
import pickle
from llama_cpp import Llama


def generate_summary(segments):
    """Generate summary using llama_cpp."""
    # Load model with GPU offloading    
    llm = Llama(
    model_path="/home/kompiel/python_scripts/llm-experiments/models/Llama-3.3-70B-Instruct-Q4_K_M.gguf",  # Need GGUF format
    n_gpu_layers=20,  # Number of layers to offload to GPU (adjust based on VRAM)
    n_ctx=32768,  # Context window
    n_batch=512,
    verbose=True,
    )

    # Build the system prompt
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

    # Generate
    output = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        max_tokens=512,
        temperature=0.3,
        top_p=0.9,
        repeat_penalty=1.2,
    )
    summary = output['choices'][0]['message']['content']

    return summary


def main():
    """Main subprocess entry point."""
    try:
        # Read pickled segments from stdin
        input_data = sys.stdin.buffer.read()
        segments = pickle.loads(input_data)

        # Generate summary
        summary = generate_summary(segments)

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
