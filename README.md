# asr-transcribe

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## 1. Native installation and usage (for CUDA)

### Requirements

- Python >= 3.10
- [UV (tested)](https://docs.astral.sh/uv/getting-started/installation/)
- [ffmpeg](https://www.ffmpeg.org/)
- [Cairo](https://www.cairographics.org/)
- If CUDA is available (depending on you GPU): [CUDA Toolkit](https://developer.nvidia.com/cuda-downloads)
- [direnv](https://direnv.net/docs/installation.html) --> You need this to fix the "missing libcudnn_ops_infer.so.8_fix" bug, [see details](/help/missing_libcudnn_ops_infer.so.8_fix.md)


### 1. Clone repository

### 2. Install dependencies:

```shell
uv sync
```

### 3. You need to reinstall llama-cpp-python with CUDA support
```shell
CMAKE_ARGS="-DGGML_CUDA=ON -DCUDAToolkit_ROOT=$CUDA_HOME -DCMAKE_CUDA_COMPILER=$CUDACXX" \
uv pip install llama-cpp-python==0.3.16 --force-reinstall --no-cache-dir --no-binary llama-cpp-python
```

### 4. Usefull shell scripts for troubleshooting

#### 4.1. ["missing libcudnn_ops_infer.so.8_fix" bug](/help/missing_libcudnn_ops_infer.so.8_fix.md)

```shell
sh ./help/setup_cudnn.sh
```
```shell
direnv allow # direnv needs to be installed and set up.
```

#### 4.2. "Weights_only" bug
```shell
sh ./help/patch_lightning_fabric.sh
```

### 5. Create the configuration file.

```shell
cp config.example.toml config.toml
```

### 6. Usage

Run the workflow script.

```shell
uv run asr_workflow.py
```

## 2. Alternative: Docker installation (experimental)

Note: Works only with Cuda 13.1 or higher 

### Requirements

- Docker, e.g. [Docker Desktop](https://docs.docker.com/desktop/)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) 

### 2. Build Docker image

```shell
uv docker compose build
```

### 3. Set paths in config.toml 

In the config.toml set the container paths for the input and output paths as well as the model paths

```toml
[system]
input_path = "/app/data/_input"
output_path = "/app/data/_output"
```

```toml
[llm]
model_path = "/app/models/your-model.gguf"
```

### 4. Run container for single transcription job

```bash
docker-compose run --rm asr-transcribe
```

## Configuration

The `config.toml` file is used to configure the application. You can copy the `config.example.toml` to create your own `config.toml`.

### System Options (`[system]`)

- **`input_path` / `output_path`**: Source and destination folders the workflow watches and populates.
- **`email_notifications`**: Enables success/failure/warning emails via the settings in `[email]`.
- **`zip_bags`**: When `true`, each generated bag directory is also written as a `.zip` archive in the same output folder.

### Whisper Options (`[whisper]`)

- **`model` / `device` / `compute_type` / `beam_size` / `batch_size`**: Core WhisperX transcription settings.
- **`language`**: Force a language or omit the key for auto-detection (remove the entry entirely to let Whisper detect automatically).
- **`use_speaker_diarization`**, **`min_speakers`**, **`max_speakers`**: Control diarization; when enabled you must supply **`hf_token`** so WhisperX can download the diarization model from Hugging Face.
- **`use_initial_prompt`**, **`initial_prompt`**, **`max_sentence_length`**: Fine-tune segmentation and prompt injection.

### Email Options (`[email]`)

- **`smtp_server` / `smtp_port` / `username` / `password`**: SMTP host and credentials used for notifications.
- **`from` / `to`**: Sender and recipient list for success, warning, and failure emails triggered by the workflow.

### LLM Options (`[llm]`)

- **`use_summarization`**: Toggles the LLM subprocess that generates summaries after transcription finishes.
- **`model_path`**: Filesystem path to a llama-cpp-compatible GGUF model (e.g., stored under `models/`).
- **`n_gpu_layers`**: GPU offloading depth for llama-cpp; adjust based on your hardware.  
  The model is loaded inside `llm_subprocess.py`, so no additional services are required.
- **`summary_languages`**: List of language codes (currently `["de", "en"]`) that should receive summaries. Remove or limit entries to skip specific languages.

### BagIt Options (`[bag]`)

The application uses the BagIt specification to package the output files. The following options are available to add metadata to the `bag-info.txt` file.

- **`group_identifier`**: A persistent, globally unique identifier for a logical set of bags.
- **`bag_count`**: The number of bags in a set (e.g., "1 of 3").
- **`internal_sender_identifier`**: An identifier for the creator of the bag.
- **`internal_sender_description`**: A description of the creator of the bag.

## Summaries

If `llm.use_summarization` is enabled, the workflow runs an LLM subprocess that produces per-language summaries according to `llm.summary_languages`.

For example, with the default `["de", "en"]` configuration:

- `_summary_de.txt` contains the German abstract.
- `_summary_en.txt` contains the English abstract.

Both files are stored inside each bag’s `data/abstracts/` directory. The prompts favour concise, third-person prose and silently correct minor ASR issues. When the LLM step fails, transcription continues without summaries.

## Output

For every processed file a timestamped bag directory is created under the configured output path. Each bag contains:

- `data/transcripts/`: All transcript formats (TXT, RTF, CSV, VTT, SRT, JSON, ODT, PDF, etc.).
- `data/abstracts/`: Language-specific summaries (currently `_summary_de.txt` and `_summary_en.txt`).
- `data/ohd_import/`: Copies of the speaker CSV exports for downstream ingestion.
- `documentation/`: Reference material copied from `doc_files/` (export formats, citation text, upload instructions).
- `bagit.txt`, `bag-info.txt`, `manifest-sha512.txt`, `tagmanifest-sha512.txt`: Files required by the BagIt specification.

If `zip_bags` is `true`, the complete bag directory is additionally written as `<bag-name>.zip` alongside the folder.

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
- Automatically summarizes transcripts via LLMs
