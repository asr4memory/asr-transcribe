import torch
import json
import logging
from transformers import pipeline
from utilities import cleanup_cuda_memory

def load_llm_model():
    """Load an LLM model for summarization."""
    model_id = "meta-llama/Llama-3.1-8B-Instruct"
    pipe = pipeline(
        "text-generation",
        model=model_id,
        torch_dtype="auto",
        device_map="auto",
)
    return pipe

def json_dictionary_parser(llm_output):
    """Parse a JSON string and return a dictionary."""
    try:
        parsed_llm_output = json.loads(llm_output)
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing the JSON output: {e}")
        parsed_llm_output = {}
    
    if not isinstance(parsed_llm_output, dict):
        logging.warning("LLM output was not a dictionary. Returning empty dictionary.")
        parsed_llm_output = {}

    return parsed_llm_output

def llm_summarization(segments): ## add: Mehrsprachigkeit
    """
    Summarize the given text using a pre-trained LLM model.
    Note: In production, this is called from llm_subprocess.py which handles memory cleanup.
    """
    pipe = load_llm_model()
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

    del pipe
    cleanup_cuda_memory()

    return summarized_text