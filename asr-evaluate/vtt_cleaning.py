import glob
import re
import os
import string

from config_asr_evaluate import vtt_directory
from config_asr_evaluate import output_directory

def clean_vtt_content(content, remove_punctuation=False):
    # Remove the VTT heading, segment numbers, time codes and notes and comments in () and <>:
    cleaned_content = re.sub(r'WEBVTT\n\n|\d+\n\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}\n|\(.*?\)|<.*?>', '', content)
    # Corrected regular expression to remove the filler words "äh", "ähs", "ähm", "hm", und "hmm" including the following comma, semicolon, hyphen or period:
    cleaned_content = re.sub(r'\b(äh|ähs|ähm|hm|hmm)\b\s*[,;:\-\.]?\s*', '', cleaned_content, flags=re.IGNORECASE)
    # Remove underlines: 
    cleaned_content = re.sub(r'_', '', cleaned_content)
    # Removing quotation marks: 
    cleaned_content = re.sub(r'[\'"]', '', cleaned_content)
    # Remove all forms of blank lines: 
    cleaned_content = re.sub(r'^\s*$\n', '', cleaned_content, flags=re.MULTILINE)

    # Additional removal of all punctuation if requested: 
    if remove_punctuation:
        # Remove all punctuation except . and : after numbers: 
        punctuation_to_remove = string.punctuation.replace('.', '').replace(':', '')
        cleaned_content = re.sub(r'(?<!\d)[{}]+'.format(re.escape(punctuation_to_remove)), '', cleaned_content)
        # Additional removal of punctuation that does not follow numbers: 
        cleaned_content = re.sub(r'(?<=\D)[.:]+', '', cleaned_content)

    return cleaned_content

# Run through all VTT files in the specified directory: 
for vtt_file_path in glob.glob(os.path.join(vtt_directory, '*.vtt')):
    # Read the contents of the VTT file:
    with open(vtt_file_path, 'r', encoding='utf-8') as file:
        vtt_content = file.read()

    # Clean up the contents of the VTT file: 
    cleaned_text = clean_vtt_content(vtt_content)

    # Determine the name of the output file (replace .vtt with _cleared.txt): 
    base_filename = os.path.basename(vtt_file_path)
    output_file_name = base_filename.replace('.vtt', '.cleared.txt')
    output_file_path = os.path.join(output_directory, output_file_name)

    with open(output_file_path, 'w', encoding='utf-8') as file:
        file.write(cleaned_text)

    # Create another file without punctuation: 
    text_without_punctuation = clean_vtt_content(vtt_content, remove_punctuation=True)
    output_file_name_no_punct = base_filename.replace('.vtt', '.cleared_no_punctuation.txt')
    output_file_path_no_punct = os.path.join(output_directory, output_file_name_no_punct)

    with open(output_file_path_no_punct, 'w', encoding='utf-8') as file:
        file.write(text_without_punctuation)

    print(f"Cleaned text was saved in: {output_file_path}")
    print(f"Text without punctuation was saved in: {output_file_path_no_punct}")