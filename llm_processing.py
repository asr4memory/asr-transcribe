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

def llm_summarization(segments):
    """Summarize the given text using a pre-trained LLM model."""
    quantized_model, tokenizer = load_llm_model()
    # Build the system prompt
    system_prompt = (
        "Du bist ein Experte für Oral History und biografische Forschung. "
        "Deine Aufgabe ist es, lebensgeschichtliche Interviews präzise und strukturiert zusammenzufassen."
    )

    # Build the user prompt with the interview content
    user_content = (
        "Bitte fasse folgendes lebensgeschichtliches Interview so zusammen, dass:\n"
        "1) die wichtigsten biografischen Stationen erhalten bleiben,\n"
        "2) persönliche Erfahrungen und Deutungen betont werden,\n"
        "3) der rote Faden der Erzählung nachvollziehbar ist,\n"
        "4) eine sachlich-neutrale Sprache verwendet wird.\n\n"
        "Gliedere den Text bitte nach sinnvollen Themen oder Lebensphasen. Verwende Zwischenüberschriften.\n\n"
        "Interview-Transkript:\n\n"
    )

    for segment in segments:
        user_content += f"{segment['text']}\n"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    # Use the chat template to format the messages properly
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")

    output = quantized_model.generate(**inputs, max_new_tokens=10000, temperature=0.7)

    # Extract only the newly generated tokens (exclude the input prompt)
    input_length = inputs.input_ids.shape[1]
    generated_tokens = output[0][input_length:]
    assistant_content = tokenizer.decode(generated_tokens, skip_special_tokens=True)

    del tokenizer, quantized_model
    cleanup_cuda_memory()

    return assistant_content