import torch
import transformers
from openai import OpenAI
from app_config import get_config
import json
import logging
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

def load_llm_model():
    """Load an LLM model for summarization."""
    model_id = "meta-llama/Llama-3.3-70B-Instruct"
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
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
    

### USAGE OF KISSKI API FOR EXTRACTING BIOGRAPHICAL DATA ###
# def llm_summarization(segments):
#     config = get_config()
#     """Summarize the given text using KISSKI API."""
#     api_key = config["whisper"]["api_key"]
#     base_url = "https://chat-ai.academiccloud.de/v1"
#     model = "qwen2.5-vl-72b-instruct" # Choose any available model
#     # model = "llama-3.3-70b-instruct" # Choose any available model

#      # Start OpenAI client
#     client = OpenAI(
#     api_key = api_key,
#     base_url = base_url
#  )
#     prompt_system = (
#         "Du bist Forscher und Digital Humanist, der folgende harte biografische Fakten aus einem Oral History-Interview in einer JSON-Datei speichert:\n"
# 	    "1) Wie lautet der Vorname der interviewten Person?\n"
#         "2) Wie lautet der Nachname der interviewten Person?\n"
#         "3) Falls die Person einen vom Nachnamen abweichenden Geburtsnamen hat: Wie lautet der Geburtsname der interviewten Person?\n"
# 	    "4) Hat de Person weitere Nachnamen?\n"
#         "5) Hat die Person weitere Vornamen?\n"
#         "6) Wie lautet das Geburtsdatum der interviewten Person?\n"
#         "7) Wie lässt sich die Person mit einem Satz beschreiben?\n"
#         "8) Welches Geschlecht hat die interviewte Person?\n"
#         "9) Fasse die Biogafie des Interviewten als Fließtext zusammen in einem Absatz zusammen.\n"
#         "Die Informationen sollen in einem JSON-Format ausgegeben werden, das folgende Struktur hat und keine zusätzlichen Kommentare, Erklärungen oder Formatierungszeichen wie Backticks ('''/```) enthält:\n"
#         "{\n"
#         "  'Vorname': 'Vorname',\n"
#         "  'Nachname': 'Nachname',\n"
#         "  'Geburtsname': 'Geburtsname',\n"
#         "  'Weitere Namen': ['weiterer Nachname1', 'weiterer Nachname2'],\n"
#         "  'Weitere Vornamen': ['weiterer Vorname1', 'weiterer Vorname2'],\n"
#         "  'Geburtsdatum': 'Geburtsdatum',\n"
#         "  'Personenbeschreibung': 'Beschreibung der Person',\n" 
#         "  'Geschlecht': 'Geschlecht'\n"
#         "  'Biografie': 'Fließtext über die Biografie der Person'\n"
#         "Noch einmal: Gib ausschließlich gültiges JSON zurück. Keine zusätzlichen Kommentare, Erklärungen oder Formatierungszeichen wie Backticks ('''/```).\n"
#     )

#     prompt_content = ""
#     for segment in segments:
#         prompt_content += f"{segment['text']}\n"
        
#     # Get response
#     chat_completion = client.chat.completions.create(
#     messages=[{"role":"system","content":prompt_system},{"role":"user","content": prompt_content}],
#     model= model,
#   )
#     response = chat_completion.choices[0].message.content
#     print(response)
    
#     # Parse response as JSON
#     parsed_response = json_dictionary_parser(response)
    
#     trials = 0
#     while not parsed_response and trials < 3:
#         trials += 1
#         logging.warning("LLM response was not a valid JSON. Retrying with correction prompt.")
#         #Correct the output via LLM to ensure it is a dictionary
#         prompt_correction = (
#             "Die Antwort des LLM war kein gültiges JSON-Format. Bitte überprüfe deine Antwort und gib sie im korrekten JSON-Format zurück.\n"
#             "Hier ist die Antwort, die korrigiert werden muss:\n"
#             f"{response}\n"
#             "Gib ausschließlich gültiges JSON zurück. Keine zusätzlichen Kommentare, Erklärungen oder Formatierungszeichen wie Backticks ('''/```).\n"
#         )
#         chat_completion_correction = client.chat.completions.create(
#             messages=[{"role":"system","content":prompt_system},{"role":"user","content": prompt_correction}],
#             model= model,
#         )
#         corrected_response = chat_completion_correction.choices[0].message.content

#         parsed_response = json_dictionary_parser(corrected_response)

#     print(parsed_response)
#     with open("bio_data_eg051_qwen.json", "w", encoding="utf-8") as f:
#         json.dump(parsed_response, f, indent=4, ensure_ascii=False)

#     breakpoint()
#     return parsed_response


### USAGE OF KISSKI API FOR SUMMARIZATION ###
# def llm_summarization(segments):
#     config = get_config()
#     """Summarize the given text using KISSKI API."""
#     api_key = config["whisper"]["api_key"]
#     base_url = "https://chat-ai.academiccloud.de/v1"
#     model = "llama-3.3-70b-instruct" # Choose any available model

#      # Start OpenAI client
#     client = OpenAI(
#     api_key = api_key,
#     base_url = base_url
#  )
#     prompt_system = (
#         "Du bist Oral History-Experte. Bitte fasse folgendes narratives-lebensgeschichtliches Interview so zusammen, dass:\n"
# 	    "1) die wichtigsten biografischen Stationen erhalten bleiben,\n"
#         "2) persönliche Erfahrungen und Deutungen betont werden,\n"
#         "3) der rote Faden der Erzählung nachvollziehbar ist,\n"
# 	    "4) eine sachlich-neutrale Sprache verwendet wird.\n"
#         "Gliedere den Text bitte nach sinnvollen Themen oder Lebensphasen. Verwende Zwischenüberschriften.\n"
#     )

#     prompt_content = ""
#     for segment in segments:
#         prompt_content += f"{segment['text']}\n"
        
#     # Get response
#     chat_completion = client.chat.completions.create(
#     messages=[{"role":"system","content":prompt_system},{"role":"user","content": prompt_content}],
#     model= model,
#   )
#     print(chat_completion.choices[0].message.content)
#     return chat_completion.choices[0].message.content


### USAGE OF LOCAL LLM MODEL FOR SUMMARIZATION ###

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

    assistant_content = tokenizer.decode(output[0], skip_special_tokens=True)

    return assistant_content