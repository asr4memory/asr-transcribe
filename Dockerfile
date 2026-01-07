FROM nvidia/cuda:13.1.0-devel-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    CUDA_HOME=/usr/local/cuda \
    PATH=/usr/local/cuda/bin:$PATH \
    LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH \
    CUDACXX=/usr/local/cuda/bin/nvcc

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

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:/root/.cargo/bin:$PATH"
RUN uv --version

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY help/ ./help/
COPY . .

RUN uv sync --frozen

RUN CMAKE_ARGS="-DGGML_CUDA=ON -DCUDAToolkit_ROOT=$CUDA_HOME -DCMAKE_CUDA_COMPILER=$CUDACXX" \
    uv pip install llama-cpp-python==0.3.16 --force-reinstall --no-cache-dir --no-binary llama-cpp-python

RUN cd /app && \
    VENV_PATH=".venv" bash ./help/setup_cudnn.sh && \
    bash ./help/patch_lightning_fabric.sh

ENV LD_LIBRARY_PATH="/app/.venv/lib/python3.12/site-packages/nvidia/cudnn/lib:${LD_LIBRARY_PATH}"

RUN mkdir -p /app/data/_input /app/data/_output

CMD ["uv", "run", "asr_workflow.py"]
