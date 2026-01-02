FROM nvidia/cuda:13.1.1-cudnn9-devel-ubuntu22.04

# Umgebungsvariablen setzen
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    CUDA_HOME=/usr/local/cuda \
    PATH=/usr/local/cuda/bin:$PATH \
    LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH \
    CUDACXX=/usr/local/cuda/bin/nvcc

# System-Dependencies installieren
RUN apt-get update && apt-get install -y \
    python3.12 \
    python3.12-dev \
    python3-pip \
    ffmpeg \
    libcairo2-dev \
    pkg-config \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# UV Package Manager installieren
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Arbeitsverzeichnis setzen
WORKDIR /app

# Projekt-Dateien kopieren
COPY pyproject.toml uv.lock ./
COPY help/ ./help/
COPY . .

# Python-Dependencies mit UV installieren
RUN uv sync --frozen

# llama-cpp-python mit CUDA-Support neu kompilieren
RUN CMAKE_ARGS="-DGGML_CUDA=ON -DCUDAToolkit_ROOT=$CUDA_HOME -DCMAKE_CUDA_COMPILER=$CUDACXX" \
    uv pip install llama-cpp-python==0.3.16 --force-reinstall --no-cache-dir --no-binary llama-cpp-python

# Helper-Scripts ausführen (cuDNN-Fix und lightning_fabric-Patch)
RUN cd /app && \
    VENV_PATH=".venv" sh ./help/setup_cudnn.sh && \
    sh ./help/patch_lightning_fabric.sh

# LD_LIBRARY_PATH für cuDNN zur Laufzeit setzen
ENV LD_LIBRARY_PATH="/app/.venv/lib/python3.12/site-packages/nvidia/cudnn/lib:${LD_LIBRARY_PATH}"

# Verzeichnisse für Daten erstellen
RUN mkdir -p /app/data/_input /app/data/_output

# Standard-Command
CMD ["uv", "run", "asr_workflow.py"]
