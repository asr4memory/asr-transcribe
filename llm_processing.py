import torch
import json
import logging
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from utilities import cleanup_cuda_memory

def load_llm_model():
    """Load an LLM model for summarization."""
    model_id = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    quantization_config = BitsAndBytesConfig(
        load_in_8bit=True,
    )
    quantized_model = AutoModelForCausalLM.from_pretrained(
        model_id, device_map="auto", torch_dtype=torch.bfloat16, quantization_config=quantization_config)

    tokenizer = AutoTokenizer.from_pretrained(model_id)

    return quantized_model, tokenizer

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
    """Summarize the given text using a pre-trained LLM model."""
    quantized_model, tokenizer = load_llm_model()
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

    # Use the chat template to format the messages properly
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")

    output = quantized_model.generate(
        **inputs,
        max_new_tokens=512,  # ~200 words ≈ 300-400 tokens with buffer
        temperature=0.3,     # Lower temperature for more factual, consistent output
        top_p=0.9,           # Nucleus sampling for quality
        do_sample=True,
        repetition_penalty=1.2  # Prevent repetitions
    )

    # Extract only the newly generated tokens (exclude the input prompt)
    input_length = inputs.input_ids.shape[1]
    generated_tokens = output[0][input_length:]
    assistant_content = tokenizer.decode(generated_tokens, skip_special_tokens=True)

    del tokenizer, quantized_model
    cleanup_cuda_memory()

    return assistant_content