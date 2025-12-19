#!/bin/bash
# Setup cuDNN symbolische Links für WhisperX
# Muss nur einmal nach Installation ausgeführt werden

set -e

VENV_PATH="../.venv"
CUDNN_PATH="${VENV_PATH}/lib/python3.12/site-packages/nvidia/cudnn/lib"

if [ ! -d "$CUDNN_PATH" ]; then
    echo "Error: cuDNN directory not found at $CUDNN_PATH"
    echo "Make sure you have run: uv sync"
    exit 1
fi

echo "Creating symbolic links in $CUDNN_PATH..."
cd "$CUDNN_PATH"

# Create symbolic links
ln -sf libcudnn_cnn.so.9 libcudnn_cnn.so.9.1.0
ln -sf libcudnn_cnn.so.9 libcudnn_cnn.so.9.1
ln -sf libcudnn_ops.so.9 libcudnn_ops.so.9.1.0
ln -sf libcudnn_ops.so.9 libcudnn_ops.so.9.1
ln -sf libcudnn_adv.so.9 libcudnn_adv.so.9.1.0
ln -sf libcudnn_adv.so.9 libcudnn_adv.so.9.1

echo "✓ Symbolic links created successfully"
echo ""
echo "To use WhisperX, set LD_LIBRARY_PATH before running:"
echo "export LD_LIBRARY_PATH=$(pwd):\$LD_LIBRARY_PATH"
