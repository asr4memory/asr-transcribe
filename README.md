# asr-transcribe

[![linting: pylint](https://img.shields.io/badge/linting-pylint-yellowgreen)](https://github.com/pylint-dev/pylint)

## Requirements

- Python >= 3.10
- ffmpeg

## Installation

Install dependencies:

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

## Configuration

The `config.toml` file is used to configure the application. You can copy the `config.example.toml` to create your own `config.toml`.

### BagIt Options (`[bag]`)

The application uses the BagIt specification to package the output files. The following options are available to add metadata to the `bag-info.txt` file.

- **`group_identifier`**: A persistent, globally unique identifier for a logical set of bags.
- **`bag_count`**: The number of bags in a set (e.g., "1 of 3").
- **`internal_sender_identifier`**: An identifier for the creator of the bag.
- **`internal_sender_description`**: A description of the creator of the bag.

## Tests
- Run automated tests with pytest.

```shell
pytest
```

## Additional information about features?
- Avoids misinterpreting titles and dates as sentence endings.
- Merges segments that do not have punctuation with the following segments.
- Customisable segment splitting: Splits segments longer than specified number of characters at the next comma (default = 120 characters).
- Changes the lowercase letter of the first word of the segment to an uppercase letter (only in cases where the previous segment ends without a comma).
- Enables word lists for names, special terms or filler words (initial prompt).
- Embeds the code into an automated input/output folder workflow.
- Calculates audio duration, workflow duration and real time factor for transcribing an audio file.
- To speed up processing, it is possible to change the calculation type to "int8" and the beam size to 4 or less (default = 5), but there is a risk of quality loss.
- Sends an success or failed email if the workflow is (not) completed successfully.
- Captures the stdout/terminal output and sends an email if the word "failed" is found in the output.
