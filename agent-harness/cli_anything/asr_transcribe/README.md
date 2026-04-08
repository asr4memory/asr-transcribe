# cli-anything-asr-transcribe

CLI harness for the **asr-transcribe** audio transcription pipeline. Provides
both one-shot subcommands and an interactive REPL for transcribing audio,
post-processing segments, exporting to 20+ formats, running LLM workflows,
and managing BagIt archives.

## Prerequisites

The following must be installed and available:

- **Python 3.12+**
- **asr-transcribe** project (this CLI wraps it)
- **WhisperX** — `pip install whisperx` or `uv sync` in the project
- **llama-cpp-python** — for LLM summarization/TOC (optional)
- **CUDA** — for GPU acceleration (optional but recommended)

## Installation

```bash
# From the asr-transcribe project root:
cd agent-harness
pip install -e .

# Verify installation:
which cli-anything-asr-transcribe
cli-anything-asr-transcribe --help
```

## Usage

### Interactive REPL (default)

```bash
cli-anything-asr-transcribe
```

Launches an interactive session with command history, auto-suggest, and
styled output. Type `help` for commands, `quit` to exit.

### One-shot commands

```bash
# Configuration
cli-anything-asr-transcribe config show
cli-anything-asr-transcribe config validate
cli-anything-asr-transcribe config init
cli-anything-asr-transcribe config set whisper.device cuda
cli-anything-asr-transcribe config diff

# Transcription
cli-anything-asr-transcribe transcribe file /path/to/audio.wav
cli-anything-asr-transcribe transcribe batch /path/to/input/

# Inspection
cli-anything-asr-transcribe info audio /path/to/audio.wav
cli-anything-asr-transcribe info segments /path/to/output.json
cli-anything-asr-transcribe info words /path/to/output.json
cli-anything-asr-transcribe info speakers /path/to/output.json
cli-anything-asr-transcribe info language /path/to/output.json
cli-anything-asr-transcribe info hallucinations /path/to/output.json
cli-anything-asr-transcribe info files /path/to/input/
cli-anything-asr-transcribe info bag /path/to/bag/

# Post-processing
cli-anything-asr-transcribe process segments /path/to/whisperx.json
cli-anything-asr-transcribe process buffer /path/to/whisperx.json
cli-anything-asr-transcribe process uppercase /path/to/whisperx.json
cli-anything-asr-transcribe process split /path/to/whisperx.json --max-length 120

# Export
cli-anything-asr-transcribe export formats
cli-anything-asr-transcribe export convert /path/to/segments.json -f vtt,srt,txt

# LLM workflows
cli-anything-asr-transcribe llm summarize /path/to/segments.json
cli-anything-asr-transcribe llm toc /path/to/segments.json
cli-anything-asr-transcribe llm chunk /path/to/segments.json
cli-anything-asr-transcribe llm chunk /path/to/segments.json --target-minutes 10 --max-chars 8000
cli-anything-asr-transcribe llm models
cli-anything-asr-transcribe llm validate-toc /path/to/toc.json
cli-anything-asr-transcribe llm validate-toc /path/to/toc.json --transcript-json /path/to/segments.json
cli-anything-asr-transcribe llm debug

# BagIt operations
cli-anything-asr-transcribe bag validate /path/to/bag/
cli-anything-asr-transcribe bag zip /path/to/bag/
cli-anything-asr-transcribe bag create /path/to/new_bag/ --files file1.txt,file2.txt

# Email
cli-anything-asr-transcribe email test

# Dependency check
cli-anything-asr-transcribe deps
```

### JSON output mode

All commands support `--json` for machine-readable output:

```bash
cli-anything-asr-transcribe --json config show
cli-anything-asr-transcribe --json info segments /path/to/output.json
cli-anything-asr-transcribe --json export formats
```

## Running Tests

```bash
cd agent-harness
pip install -e .
pip install pytest
python -m pytest cli_anything/asr_transcribe/tests/ -v -s

# Force installed CLI for subprocess tests:
CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest cli_anything/asr_transcribe/tests/ -v -s
```

## Export Formats

| Format | Description |
|--------|-------------|
| vtt | WebVTT subtitles |
| srt | SubRip subtitles |
| txt | Plain text transcript |
| txt_speaker | Text with speaker labels |
| csv | Tab-delimited CSV |
| csv_speaker | CSV with speaker + pause markers |
| rtf | Rich Text Format |
| pdf | PDF document |
| odt | OpenDocument Text |
| ods | OpenDocument Spreadsheet |
| tei_xml | TEI-XML with timeline |
| json | Segments JSON |
| ... | And more (see `export formats`) |
