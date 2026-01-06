FROM nvidia/cuda:13.1.0-devel-ubuntu24.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    CUDA_HOME=/usr/local/cuda \
    PATH=/usr/local/cuda/bin:$PATH \
    LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH \
    CUDACXX=/usr/local/cuda/bin/nvcc

# Install system dependencies
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

# Install UV package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:/root/.cargo/bin:$PATH"
RUN uv --version

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY help/ ./help/
COPY . .

# Install Python dependencies with UV
RUN uv sync --frozen

# Recompile llama-cpp-python with CUDA support
RUN CMAKE_ARGS="-DGGML_CUDA=ON -DCUDAToolkit_ROOT=$CUDA_HOME -DCMAKE_CUDA_COMPILER=$CUDACXX" \
    uv pip install llama-cpp-python==0.3.16 --force-reinstall --no-cache-dir --no-binary llama-cpp-python

# Run helper scripts (cuDNN fix and lightning_fabric patch)
RUN cd /app && \
    VENV_PATH=".venv" bash ./help/setup_cudnn.sh && \
    bash ./help/patch_lightning_fabric.sh

# Set LD_LIBRARY_PATH for cuDNN at runtime
ENV LD_LIBRARY_PATH="/app/.venv/lib/python3.12/site-packages/nvidia/cudnn/lib:${LD_LIBRARY_PATH}"

# Create data directories
RUN mkdir -p /app/data/_input /app/data/_output

# Default command
CMD ["uv", "run", "asr_workflow.py"]
