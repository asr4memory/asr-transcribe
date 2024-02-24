# asr-transcribe

[![linting: pylint](https://img.shields.io/badge/linting-pylint-yellowgreen)](https://github.com/pylint-dev/pylint)

## Requirements

- Python >= 3.10
- ffmpeg

## Installation

Install Pytorch [according to your system,](https://pytorch.org/get-started/locally/) e.g. for Linux with only CPU support:

```shell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

Install the rest of the dependencies:

```shell
pip install -r requirements.txt
```

Create the configuration file.

```shell
cp config.example.toml config.toml
```

## Usage

Run the workflow script.

```shell
python asr_workflow.py
```

## Tests
- Run automated tests with pytest.

```shell
pytest
```

## Additional information about features?
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
