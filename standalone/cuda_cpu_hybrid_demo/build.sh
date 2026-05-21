#!/bin/bash
set -e

cd "$(dirname "$0")"

if ! command -v nvcc >/dev/null 2>&1; then
    echo "Error: nvcc was not found in PATH."
    echo "Check CUDA with:"
    echo "  which nvcc"
    echo "  nvcc --version"
    echo ""
    echo "Common WSL fix:"
    echo "  export PATH=/usr/local/cuda/bin:\$PATH"
    echo "  export LD_LIBRARY_PATH=/usr/local/cuda/lib64:\$LD_LIBRARY_PATH"
    exit 1
fi

nvcc -O2 -std=c++17 -arch=sm_86 -Xcompiler -fopenmp hybrid_preprocess_demo.cu -o hybrid_preprocess_demo

echo "Built: standalone/cuda_cpu_hybrid_demo/hybrid_preprocess_demo"
