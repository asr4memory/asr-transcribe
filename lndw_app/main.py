from flask import Flask, request, jsonify, render_template
import os
from datetime import datetime

from extending_audio_workflow import create_extended_output_file
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
        # Save the uploaded file
        input_path = '/Users/peterkompiel/python_scripts/asr4memory/processing_files/lndw-pipeline/_input/'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # input_file = os.listdir(path=input_path)
        # os.makedirs(input_file, exist_ok=True)
        input_file = os.path.join(input_path, f'{timestamp}_input_audio.wav')
        file.save(input_file)

        base_output_path = '/Users/peterkompiel/python_scripts/asr4memory/processing_files/lndw-pipeline/_output/'
        output_directory = os.path.join(base_output_path, timestamp)
        os.makedirs(output_directory, exist_ok=True)

        # Run the workflow
        try:
            create_extended_output_file(output_directory, input_file, timestamp)
            transcribe_audio(input_file, output_directory, timestamp)
            translate_transcriptions(output_directory)
            generate_llm_responses(output_directory)
            text_to_speech(output_directory)
            print('====> Overall workflow is finished. <====')
            return jsonify({"message": "Processing completed successfully!", "output_directory": output_directory})
        except Exception as e:
            print('====> Overall workflow is failed. <====')
            return jsonify({"message": f"Error: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)