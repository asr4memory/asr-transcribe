"""
Subprocess wrapper for LLM summarization.
Runs LLM model in isolated subprocess to ensure memory is freed after processing.
This allows large models (20GB+) to be loaded and fully cleaned up between files.
"""

import sys
import pickle
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def load_llm_model():
    """Load LLM model for summarization."""
    model_id = "meta-llama/Llama-3.3-70B-Instruct"
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=False,  # Nested quantization for extra memory savings
        bnb_4bit_quant_type="nf4",  # Normal Float 4-bit
        llm_int8_enable_fp32_cpu_offload=True,  # Enable CPU offloading
    )

    # Load model with CPU offloading support
    quantized_model = AutoModelForCausalLM.from_pretrained(
        model_id,
        device_map="auto",  # Automatically distribute across GPU and CPU
        dtype=torch.bfloat16,  # Fixed: use 'dtype' instead of deprecated 'torch_dtype'
        quantization_config=quantization_config,
        low_cpu_mem_usage=True,  # Optimize CPU memory usage
        max_memory={0: "22GiB", "cpu": "70GiB"},  # Adjust based on your hardware
    )
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    return quantized_model, tokenizer


def generate_summary(segments, model, tokenizer):
    """Generate summary using the loaded model."""
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
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")

    output = model.generate(
        **inputs,
        max_new_tokens=512,  # ~200 words ≈ 300-400 tokens with buffer
        temperature=0.3,  # Lower temperature for more factual, consistent output
        top_p=0.9,  # Nucleus sampling for quality
        do_sample=True,
        repetition_penalty=1.2,  # Prevent repetitions
    )

    # Extract only the newly generated tokens (exclude the input prompt)
    input_length = inputs.input_ids.shape[1]
    generated_tokens = output[0][input_length:]
    assistant_content = tokenizer.decode(generated_tokens, skip_special_tokens=True)

    return assistant_content


def summarize_segments(segments):
    """
    Complete LLM pipeline: load model + generate summary.
    Subprocess exit will free all memory.
    """
    # Load model
    model, tokenizer = load_llm_model()

    # Generate summary
    summary = generate_summary(segments, model, tokenizer)

    # Cleanup (optional since subprocess will exit, but good practice)
    del model, tokenizer

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
