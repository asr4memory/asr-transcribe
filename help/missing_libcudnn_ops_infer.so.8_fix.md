# WhisperX Installation with uv

Minimal-invasive fix for WhisperX 3.7.4 with uv (based on [Issue #1158](https://github.com/m-bain/whisperX/issues/1158))

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Create cuDNN symbolic links (one-time setup)
./setup_cudnn.sh
```

## Usage

Choose one of the following methods:

### Option 1: Manual Export (Simplest)

```bash
source .venv/bin/activate
export LD_LIBRARY_PATH=.venv/lib/python3.12/site-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH
python your_script.py
```

### Option 2: With direnv (Recommended)

```bash
# Install direnv (IMPORTANT: native version, NOT Snap!)
curl -sfL https://direnv.net/install.sh | bash
# Installs to ~/.local/bin (or set bin_path beforehand)

# Add to ~/.bashrc or ~/.zshrc:
eval "$(direnv hook bash)"  # or: eval "$(direnv hook zsh)"

# Reload shell:
exec bash

# Allow once:
direnv allow

# Now automatic when cd into directory
python your_script.py
```


## Notes

- Symbolic links must be recreated after every `uv sync` or `uv pip install`
- `ctranslate2==4.5.0` is already configured in [pyproject.toml](pyproject.toml:9)
- For Python versions ≠ 3.12, adjust paths in scripts accordingly
