# asr-transcribe

## Requirements
- Python >= 3.10
- WhisperX v3.1.1 (https://github.com/m-bain/whisperX)
- ffmpeg

## Done/Fixed:
- Avoids misinterpreting titles and dates as sentence endings.
- Merges segments that do not have punctuation with the following segments.
- Splits segments longer than 120 characters at the next comma.
- Changes the lowercase letter of the first word of the segment to an uppercase letter (only in cases where the previous segment ends without a comma).
- Enables word lists for names, special terms or filler words.
- Embeds the code into an automated input/output folder workflow.
- Calculates audio duration, workflow duration and real time factor for transcribing an audio file.
- To speed up processing, it is possible to change the calculation type to "int8" and the beam size to 4 or less (default = 5), but there is a risk of quality loss.
- Sends an success or failed email if the workflow is (not) completed successfully.
- Captures the stdout/terminal output and sends an email if the word "failed" is found in the output.

## Installation instructions...
- Clone this repository.
- Install whisperx per its installation instructions.
- Install dependencies with `pip install -r requirements.txt`
- Copy config.example.toml to config.toml and customize it.
- Run `python asr_workflow.py`

## Tests
- Run automated tests with `pytest`
