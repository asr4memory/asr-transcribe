import os
from jiwer import process_words, process_characters
import jiwer
from config_asr_evaluate import reference_directory, hypothesis_directory

# Function to get the base name of the files up to the first point:
def list_files(directory):
    files = {}
    for filename in os.listdir(directory):
        base_name = filename.split('.', 1)[0]  # Split the file name at the first point
        files[base_name] = filename
    return files

# List files in both directories:
reference_files = list_files(reference_directory)
hypothesis_files = list_files(hypothesis_directory)

# Iterate through the reference files and check for matches in the hypothesis files:
for ref_base, ref_filename in reference_files.items():
    if ref_base in hypothesis_files:
        # Construct complete path to the files:
        ref_file_path = os.path.join(reference_directory, ref_filename)
        hyp_file_path = os.path.join(hypothesis_directory, hypothesis_files[ref_base])

        # Read texts from the files:
        with open(ref_file_path, 'r', encoding='utf-8') as ref:
            reference_text = ref.read()
        with open(hyp_file_path, 'r', encoding='utf-8') as hyp:
            hypothesis_text = hyp.read()

        # Calculate WER, MER and WIL:
        metrics = process_words(reference_text, hypothesis_text)
        char_output = process_characters(reference_text, hypothesis_text)

        print(f"For the file pair: {ref_base}")
        print(f"WER: {metrics.wer}")
        print(f"MER: {metrics.mer}")
        print(f"WIL: {metrics.wil}")
        print(f"CER: {char_output.cer}")

        # Optional: Output alignments and visual representation of the alignment:
        #print(char_output.alignments)
        print(jiwer.visualize_alignment(char_output))
    else:
        print(f"No corresponding hypothesis file found for: {ref_base}")
