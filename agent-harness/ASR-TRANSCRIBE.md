# ASR-TRANSCRIBE: CLI Harness SOP

## Software Overview

**asr-transcribe** is an end-to-end Automatic Speech Recognition pipeline that:
- Transcribes audio files using WhisperX (Whisper + alignment + diarization)
- Optionally translates transcripts to other languages
- Optionally generates LLM-based summaries and table of contents
- Outputs results in 20+ formats (VTT, SRT, CSV, JSON, PDF, TEI-XML, ODT, ODS, RTF, TXT, etc.)
- Packages outputs as BagIt-compliant archives with metadata
- Supports speaker diarization and multi-language processing

## Backend Engine

The backend consists of:
- **WhisperX** — Whisper transcription + forced alignment + speaker diarization
- **llama-cpp-python** — Local LLM inference via GGUF models (summaries, TOC)
- **PyTorch + CUDA** — GPU acceleration for both pipelines
- **pyannote.audio** — Speaker diarization (optional, requires HuggingFace token)

These run in **isolated subprocesses** for memory management — each model loads
in its own process and all VRAM is freed on exit.

## Data Model

- **Input**: Audio files (WAV, MP3, FLAC, etc.) in a configured directory
- **Intermediate**: WhisperX JSON with segments, words, speakers, timestamps
- **Output**: 20+ format files packaged in BagIt archives (optionally zipped)
- **Configuration**: TOML file (`config.toml`) with sections for system, whisper, LLM, email, bag

## GUI Actions → CLI Mappings

| GUI/Script Action | CLI Command |
|---|---|
| Edit config.toml | `config show`, `config validate`, `config init` |
| Set config value | `config set <section.key> <value>` |
| Compare config to defaults | `config diff` |
| Run `asr_workflow.py` on a file | `transcribe file <path>` |
| Run `asr_workflow.py` on directory | `transcribe batch <dir>` |
| Inspect audio properties | `info audio <path>` |
| View WhisperX JSON stats | `info segments <json>` |
| View word-level confidence | `info words <json>` |
| View per-speaker breakdown | `info speakers <json>` |
| View language metadata | `info language <json>` |
| Check for hallucinations | `info hallucinations <json>` |
| List eligible input files | `info files <dir>` |
| Re-export from existing JSON | `export convert <json> [formats]` |
| List available formats | `export formats` |
| Run sentence buffering only | `process buffer <json>` |
| Run uppercasing only | `process uppercase <json>` |
| Run sentence splitting only | `process split <json>` |
| Run LLM summarization | `llm summarize <json>` |
| Run LLM TOC generation | `llm toc <json>` |
| Preview chunking for batched mode | `llm chunk <json>` |
| Inspect LLM model configs | `llm models` |
| Validate a TOC JSON file | `llm validate-toc <json>` |
| Validate BagIt archive | `bag validate <path>` |
| ZIP a bag directory | `bag zip <path>` |
| Create new bag structure | `bag create <dir>` |
| Test SMTP connectivity | `email test` |
| Debug LLM workflows | `llm debug` |

## CLI Command Groups

### config — Configuration management
- `config show` — Display current configuration (optionally as JSON)
- `config validate` — Check config.toml for errors
- `config init` — Create config.toml from example template
- `config set <key> <value>` — Set a config value (e.g. `whisper.device cuda`)
- `config diff` — Show differences between current config and defaults

### transcribe — Core transcription
- `transcribe file <audio_path>` — Transcribe a single audio file
- `transcribe batch <directory>` — Transcribe all eligible files in directory

### info — Inspection
- `info audio <path>` — Show audio file metadata (length, format)
- `info segments <json_path>` — Show segment statistics from WhisperX JSON
- `info words <json_path>` — Show word-level detail and confidence scores
- `info speakers <json_path>` — Show per-speaker statistics
- `info language <json_path>` — Show language metadata from WhisperX output
- `info hallucinations <json_path>` — Check for potential hallucination indicators
- `info files <directory>` — List eligible audio files in a directory
- `info bag <bag_path>` — Show BagIt archive metadata

### process — Post-processing
- `process segments <json_path>` — Run all post-processing steps (buffer + uppercase + split)
- `process buffer <json_path>` — Sentence-buffering only
- `process uppercase <json_path>` — First-letter uppercasing only
- `process split <json_path>` — Long-sentence splitting only (--max-length)

### export — Output format generation
- `export formats` — List all available output formats
- `export convert <json_path> [--formats fmt1,fmt2] [--output-dir dir]` — Export to specific formats

### llm — LLM workflows
- `llm summarize <json_path>` — Generate summaries from transcript
- `llm toc <json_path>` — Generate table of contents from transcript
- `llm chunk <json_path>` — Preview chunking for batched mode (--target-minutes, --max-chars)
- `llm models` — Inspect loaded model configurations and profiles
- `llm validate-toc <toc_path>` — Validate a TOC JSON file (--transcript-json for boundary check)
- `llm debug` — Run LLM debug mode using configured debug_file

### bag — BagIt operations
- `bag validate <path>` — Validate BagIt directory structure
- `bag zip <path>` — Create ZIP archive of bag directory
- `bag create <path>` — Create a new BagIt directory structure

### email — Email notifications
- `email test` — Test SMTP connectivity using config settings

## State Model

- **Configuration**: Loaded from `config.toml` at startup, read-only during session
- **Session state** (REPL): Current working project path, last loaded JSON, processing history
- **No persistent state between CLI invocations** — each command is self-contained
- **REPL mode**: Maintains session context for interactive use

## Output Format

- Human-readable: Colored tables, status messages, progress bars (default)
- Machine-readable: JSON via `--json` flag on all commands
- All commands support `--json` for agent consumption
