from TTS.api import TTS
import glob
import os

def text_to_speech(output_directory):
    device = "cpu"
    # Init TTS with the target model name
    tts = TTS(model_name="tts_models/de/thorsten/vits", progress_bar=False).to(device)
    for llm_txt_file_path in glob.glob(os.path.join(output_directory, '*_llm.txt')):
        print(f"Verarbeite TXT-Datei: {llm_txt_file_path}")

        with open(llm_txt_file_path, 'r', encoding='utf-8') as llm_txt_file:
            llm_transcript = llm_txt_file.read()
    
        text_to_speech_file_path = llm_txt_file_path.replace('.txt', '.wav')

        # Run TTS
        tts.tts_to_file(text=llm_transcript, file_path=text_to_speech_file_path)

        del tts

        print(f"Die bearbeitete Datei wurde gespeichert unter: {text_to_speech_file_path}") 

        print('====> Text-to-Speech workflow is finished. <====')