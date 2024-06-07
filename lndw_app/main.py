from flask import Flask, request, jsonify, render_template
import os
from datetime import datetime
import gc   
from audio_tools import create_extended_output_file, convert_to_wav
from transcription_workflow import transcribe_audio
from translation_workflow import translate_transcriptions
from llm_workflow import generate_llm_responses
from tts_workflow import text_to_speech

# The following lines are to capture the stdout/terminal output
import sys
import io

class Tee(io.StringIO):
    def __init__(self, terminal):
        self.terminal = terminal
        super().__init__()

    def write(self, message):
        self.terminal.write(message)
        super().write(message)

# Save a reference to the original stdout and stderr
original_stdout = sys.stdout
original_stderr = sys.stderr

# Redirect stdout and stderr to the buffer
stdout_buffer = Tee(original_stdout)
stderr_buffer = Tee(original_stderr)
sys.stdout = stdout_buffer
sys.stderr = stdout_buffer

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file part'
    file = request.files['file']
    if file.filename == '':
        return 'No selected file'
    if file:
        # Input and output directories/files
        input_path = '/Users/peterkompiel/python_scripts/asr4memory/processing_files/lndw-pipeline/_input/'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        input_file = os.path.join(input_path, f'{timestamp}_input_audio.wav')
        file.save(input_file)

        base_output_path = '/Users/peterkompiel/python_scripts/asr4memory/processing_files/lndw-pipeline/_output/'
        output_directory = os.path.join(base_output_path, timestamp)
        os.makedirs(output_directory, exist_ok=True)

        # Convert the file to a compatible WAV format using ffmpeg and overwrite the original file
        temp_converted_file = os.path.join(output_directory, 'temp_converted_audio.wav')
        convert_to_wav(input_file, temp_converted_file)

        # Replace the original file with the converted file
        os.replace(temp_converted_file, input_file)
        
        # Run the workflow
        try:
            create_extended_output_file(output_directory, input_file, timestamp)
            transcribe_audio(input_file, output_directory, timestamp)
            translate_transcriptions(output_directory)
            generate_llm_responses(output_directory)
            text_to_speech(output_directory)
            gc.collect()
            print('====> Overall workflow is finished. <====')
            return jsonify({"message": "Processing completed successfully!", "output_directory": output_directory})
        except Exception as e:
            gc.collect()
            print('====> Overall workflow is failed. <====')
            return jsonify({"message": f"Error: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)