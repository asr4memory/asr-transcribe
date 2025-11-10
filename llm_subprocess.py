"""
Subprocess wrapper for LLM summarization.
Runs LLM model in isolated subprocess to ensure memory is freed after processing.
This allows large models (20GB+) to be loaded and fully cleaned up between files.
"""

import sys
import pickle
from llama_cpp import Llama
from app_config import get_config

config = get_config()
n_gpu_layers = config["llm"]["n_gpu_layers"]
model_path = config["llm"]["model_path"] 

def generate_summary(segments, trials):
    """Generate summary using llama_cpp."""
    # Load model with GPU offloading
    if trials == 1:    
        llm = Llama(
        model_path=model_path,
        n_gpu_layers=n_gpu_layers,
        n_ctx=32768,  # Context window
        n_batch=512,
        verbose=True,
        )
    else:
        llm = Llama(
        model_path=model_path,  # Need GGUF format
        n_gpu_layers=n_gpu_layers,
        n_ctx=65536,  # Context window
        n_batch=256,
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
        max_tokens=4000,
        temperature=0.3,
        top_p=0.9,
        repeat_penalty=1.2,
    )
    summary = output['choices'][0]['message']['content']

    # Extract only the final message if the model includes reasoning/analysis
    # Look for the pattern: |end|><|start|>assistant<|channel|>final<|message|>
    if "|end|><|start|>assistant<|channel|>final<|message|>" in summary:
        summary_no_reasoning = summary.split("|end|><|start|>assistant<|channel|>final<|message|>")[1]

    return summary_no_reasoning.strip()


def main():
    """Main subprocess entry point."""
    max_trials = 2
    summary = None
    
    for trial in range(1, max_trials + 1):
        try:
            # Read pickled segments from stdin (nur beim ersten Versuch)
            if trial == 1:
                input_data = sys.stdin.buffer.read()
                segments = pickle.loads(input_data)
            
            # Generate summary
            summary = generate_summary(segments, trial)
            
            # Erfolgreich - Ergebnis ausgeben
            sys.stdout.buffer.write(pickle.dumps((summary, trial)))
            sys.exit(0)
            
        except Exception as e:
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
