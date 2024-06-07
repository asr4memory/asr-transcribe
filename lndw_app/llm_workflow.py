import os
import glob
from mlx_lm import load, generate

def generate_llm_responses(output_directory):
    input_dir = output_directory
    for txt_file_path in glob.glob(os.path.join(input_dir, '*.txt')):
        with open(txt_file_path, 'r', encoding='utf-8') as txt_file:
            transcript = txt_file.read().strip()
        prompt = f"""
Bitte höre dir die folgende 30-sekündige Audioaufnahme nach dem Delimiter ### aufmerksam an. Analysiere den Inhalt und interpretiere die Aussage des Sprechers. Anschließend generiere eine an den Sprecher gerichtete Antwort von maximal 4 Sätzen, die folgende Kriterien erfüllt:
1 Die Antwort soll einen klugen, tiefgründigen Gedanken oder eine Erkenntnis in Bezug auf die Aussage des Sprechers enthalten. Zeige dein Verständnis für die Bedeutung und Implikationen der Aussage.
2 Gleichzeitig soll die Antwort einen humorvollen, witzigen oder kreativen Aspekt enthalten, der die Aussage auf unterhaltsame Weise aufgreift oder umdeutet.
3 Vermeide oberflächliche Scherze oder Kalauer. Der Humor soll intelligent und geistreich sein, ohne die Ernsthaftigkeit der Aussage zu untergraben.
4 Passe den Ton deiner Antwort an den Kontext der Aufnahme an, sei es formell, informell, philosophisch oder persönlich.
Deine Antwort soll den Zuhörer zum Nachdenken anregen und gleichzeitig unterhalten. Sei kreativ, aber respektvoll gegenüber dem Sprecher und seinem Standpunkt.

###

'{transcript}'
"""
        llm_model, llm_tokenizer = load("mlx-community/Mixtral-8x7B-Instruct-v0.1-4bit")
        response = generate(llm_model, llm_tokenizer, prompt=prompt, verbose=True, max_tokens=1000, temp=0.6).strip()
        transcribed_txt_file_path = txt_file_path.replace('.txt', '_llm.txt')
        with open(transcribed_txt_file_path, 'w', encoding='utf-8') as transcribed_txt_file:
            transcribed_txt_file.write(response)
        del llm_model, llm_tokenizer

    print('====> LLM workflow is finished. <====')