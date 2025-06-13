import torch
import transformers

def load_llm_model():
    """Load an LLM model for summarization."""
    model_id = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    pipeline = transformers.pipeline(
        "text-generation",
        model=model_id,
        model_kwargs={"torch_dtype": torch.bfloat16},
        device_map="auto",   
    )
    return pipeline


def llm_summarization(segments):
    """Summarize the given text using a pre-trained LLM model."""
    pipeline = load_llm_model()
    prompt_system = (
        "Bitte fasse folgendes lebensgeschichtliches Interview so zusammen, dass:\n"
	    "1) die wichtigsten biografischen Stationen erhalten bleiben,\n"
        "2) persönliche Erfahrungen und Deutungen betont werden,\n"
        "3) der rote Faden der Erzählung nachvollziehbar ist,\n"
	    "4) eine sachlich-neutrale Sprache verwendet wird.\n"
        "Gliedere den Text bitte nach sinnvollen Themen oder Lebensphasen. Verwende Zwischenüberschriften.\n"
    )

    prompt_content = ""
    for segment in segments:
        prompt_content += f"{segment['text']}\n"

    messages = [
        {"role": "system", "content": prompt_system},
        {"role": "user", "content": prompt_content},
        ]
    
    outputs = pipeline(
    messages,
    max_new_tokens=10000,
    )

    output = outputs[0]['generated_text']
    assistant_dict = output[2]
    assistant_content = assistant_dict["content"]

    return assistant_content