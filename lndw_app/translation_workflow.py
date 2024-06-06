
import os
from transformers import MarianMTModel, MarianTokenizer
import glob
import wave

# Funktion zur Übersetzung eines Textes ins Englische
def translate_to_en(text, num_beams):
    return translate_text(text, "Helsinki-NLP/opus-mt-de-en", num_beams)

# Funktion zur Übersetzung eines Textes ins Spanische
def translate_to_es(text, num_beams):
    return translate_text(text, "Helsinki-NLP/opus-mt-en-es", num_beams)

# Funktion zur Übersetzung eines Textes ins Deutsche
def translate_to_de(text, num_beams):
    return translate_text(text, "Helsinki-NLP/opus-mt-es-de", num_beams)

# Funktion zur Übersetzung eines Textes ins Albanische
def translate_to_zh(text, num_beams):
    return translate_text(text, "Helsinki-NLP/opus-mt-en-zh", num_beams)

# Funktion zur Übersetzung eines Textes vom Albanischen ins Deutsche
def translate_to_de_from_zh(text, num_beams):
    return translate_text(text, "Helsinki-NLP/opus-mt-zh-de", num_beams)

# Allgemeine Funktion zur Übersetzung eines Textes
def translate_text(text, model_name, num_beams):
    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)
    encoded_text = tokenizer(text, return_tensors="pt", padding=True)
    translated_tokens = model.generate(**encoded_text, num_beams=num_beams)
    translated_text = tokenizer.decode(translated_tokens[0], skip_special_tokens=True)
    return translated_text

# Funktion zum Verarbeiten der VTT-Dateien in einem Verzeichnis
def process_vtt_file(input_dir, output_dir, translate_funcs, lang_codes, num_beams):
    os.makedirs(output_dir, exist_ok=True)
    processed_files = {}

    for vtt_file_path in glob.glob(os.path.join(input_dir, '*_de.vtt')):
        print(f"Verarbeite VTT-Datei: {vtt_file_path}")

        with open(vtt_file_path, 'r', encoding='utf-8') as vtt_file:
            vtt_lines = vtt_file.readlines()

        # Entferne die erste "WEBVTT" Zeile und die erste Leerzeile
        if vtt_lines[0].strip() == "WEBVTT":
            vtt_lines = vtt_lines[1:]
        if vtt_lines[0].strip() == "":
            vtt_lines = vtt_lines[1:]

        segments = []
        current_segment = []

        for line in vtt_lines:
            if line.strip() == "" and current_segment:
                segments.append(current_segment)
                current_segment = []
            else:
                current_segment.append(line)
        if current_segment:
            segments.append(current_segment)

        intermediate_translations = [segment[2].strip() for segment in segments if len(segment) > 2]

        # Speichere die Originaldatei
        original_file_path = os.path.join(output_dir, os.path.basename(vtt_file_path))
        with open(original_file_path, 'w', encoding='utf-8') as output_file:
            output_file.writelines(["WEBVTT\n\n"] + vtt_lines)
        processed_files['de'] = original_file_path

        for translate_func, lang_code in zip(translate_funcs, lang_codes):
            output_translations = []
            translated_lines = ["WEBVTT\n\n"]  # Initialize only once per output file
            for segment, translation in zip(segments, intermediate_translations):
                translated_lines.extend(segment[:2])
                translated_text = translate_func(translation, num_beams)
                output_translations.append(translated_text)
                translated_lines.append(translated_text + '\n\n')

            output_file_path = os.path.join(output_dir, os.path.basename(vtt_file_path).replace('_de.vtt', f'_{lang_code}.vtt'))
            with open(output_file_path, 'w', encoding='utf-8') as output_file:
                output_file.writelines(translated_lines)

            print(f"Die bearbeitete Datei wurde gespeichert unter: {output_file_path}")
            intermediate_translations = output_translations
            processed_files[lang_code] = output_file_path

    return processed_files

# Funktion zur Anpassung der Timecodes
def adjust_timecodes(vtt_lines, start_offset):
    adjusted_lines = []
    for line in vtt_lines:
        if '-->' in line:
            start_time, end_time = line.split(' --> ')
            new_start_time = adjust_time(start_time.strip(), start_offset)
            new_end_time = adjust_time(end_time.strip(), start_offset)
            adjusted_lines.append(f"{new_start_time} --> {new_end_time}\n")
        else:
            adjusted_lines.append(line)
    return adjusted_lines

def adjust_time(time_str, offset):
    h, m, s = map(float, time_str.split(':'))
    total_seconds = h * 3600 + m * 60 + s + offset
    new_h = int(total_seconds // 3600)
    new_m = int((total_seconds % 3600) // 60)
    new_s = total_seconds % 60
    return f"{new_h:02}:{new_m:02}:{new_s:06.3f}"

# Funktion zur Erstellung der kombinierten VTT-Datei mit fortlaufenden Segmentnummern
def create_combined_vtt(input_dir, output_dir, processed_files):
    # Suchen der WAV-Datei
    wav_files = glob.glob(os.path.join(input_dir, '*.wav'))
    if not wav_files:
        raise FileNotFoundError("Keine WAV-Datei im Eingabeverzeichnis gefunden.")
    audio_file = wav_files[0]
    audio_base_name = os.path.splitext(os.path.basename(audio_file))[0]
    
    # Berechne die Dauer der Audiodatei
    with wave.open(audio_file, 'r') as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        duration = frames / float(rate)
    segment_duration = duration / 4

    combined_lines = ["WEBVTT\n\n"]
    file_order = ['de', 'en', 'zh', 'de_final']
    segment_counter = 1
    
    for i, lang_code in enumerate(file_order):
        file_path = processed_files.get(lang_code)
        if not file_path:
            raise FileNotFoundError(f"Die Datei für {lang_code} wurde nicht gefunden.")
        with open(file_path, 'r', encoding='utf-8') as vtt_file:
            vtt_lines = vtt_file.readlines()[1:]  # Entferne "WEBVTT"
            if i > 0:
                start_offset = segment_duration * i
                vtt_lines = adjust_timecodes(vtt_lines, start_offset)
            
            for line in vtt_lines:
                if line.strip().isdigit():
                    combined_lines.append(f"{segment_counter}\n")
                    segment_counter += 1
                else:
                    combined_lines.append(line)
            combined_lines.append('\n')

    combined_output_file = os.path.join(output_dir, f'{audio_base_name}.vtt')
    with open(combined_output_file, 'w', encoding='utf-8') as output_file:
        output_file.writelines(combined_lines)
    
    print(f"Die kombinierte Datei wurde gespeichert unter: {combined_output_file}")

def translate_transcriptions(output_directory):
    input_dir = output_directory
    num_beams = 2
    translate_funcs = [translate_to_en, translate_to_zh, translate_to_de_from_zh]
    lang_codes = ["en", "zh", "de_final"]
    processed_files = process_vtt_file(input_dir, output_directory, translate_funcs, lang_codes, num_beams)
    create_combined_vtt(input_dir, output_directory, processed_files)

    print('====> Translation workflow is finished. <====')