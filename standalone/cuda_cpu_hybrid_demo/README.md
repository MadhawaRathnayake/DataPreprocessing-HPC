# CUDA + CPU Hybrid Preprocessing Demo

This is a standalone experiment. It does not connect to the Tkinter app or the existing C shared libraries.

The goal is to prove that the project can split preprocessing work between:

- CPU parallelism with OpenMP
- GPU parallelism with CUDA

## What It Does

The demo loads a CSV file, or generates synthetic data if no file is provided.

CPU side:

- Parses CSV rows
- Detects numeric vs categorical columns
- Counts categorical unique values in parallel with OpenMP
- Counts missing values in parallel with OpenMP

GPU side:

- Copies numeric columns to the GPU
- Computes per-column min, max, sum, missing count, and mean
- Applies min-max scaling to numeric values

The CPU categorical work and GPU numeric work are launched together so both processors are active during the run.

## Build

```bash
cd standalone/cuda_cpu_hybrid_demo
./build.sh
```

If `nvcc` is not in your PATH, fix CUDA first:

```bash
which nvcc
nvcc --version
```

## Run With Generated Data

```bash
./hybrid_preprocess_demo
```

Generate a specific row count:

```bash
./hybrid_preprocess_demo --rows 100000
```

## Run With A CSV File

```bash
./hybrid_preprocess_demo ../../data/sample_employees.csv
```

## Print CPU And GPU Thread Activity

```bash
./hybrid_preprocess_demo --debug-threads
```

With a CSV:

```bash
./hybrid_preprocess_demo ../../data/sample_employees.csv --debug-threads
```

Limit how many CUDA global threads print per kernel:

```bash
./hybrid_preprocess_demo --debug-threads --gpu-debug-limit 32
```

Print every active CPU and GPU thread:

```bash
./hybrid_preprocess_demo ../../data/hpc_preprocessing_dataset_100k.csv --debug-all-threads
```

Note: GPU `printf` output becomes huge very quickly. The demo prints only the first N CUDA global threads per kernel by default.
With `--debug-all-threads`, expect a very large terminal output. Redirecting to a file is recommended:

```bash
./hybrid_preprocess_demo ../../data/hpc_preprocessing_dataset_100k.csv --debug-all-threads > thread_trace.txt
```

## Increase GPU Utilization

To keep the GPU busy longer, repeat the CUDA kernels:

```bash
./hybrid_preprocess_demo ../../data/hpc_preprocessing_dataset_100k.csv --gpu-repeat 1000
```

For the GPU-only demo:

```bash
./gpu_only_preprocess_demo ../../data/hpc_preprocessing_dataset_100k.csv --gpu-repeat 1000
```

Use `nvidia-smi dmon` in another terminal to observe `sm` utilization.
Avoid `--debug-all-threads` when measuring utilization, because GPU `printf` changes the workload heavily.

## Optimized Hybrid Demo

This version uses a better CPU/GPU split and avoids global atomic reductions on the GPU:

```bash
./build_optimized_hybrid.sh
./optimized_hybrid_preprocess_demo ../../data/hpc_preprocessing_dataset_100k.csv
```

CPU/OpenMP handles categorical columns while CUDA handles dense numeric columns with block-level reductions and scaling.

To repeat only the GPU numeric kernels:

```bash
./optimized_hybrid_preprocess_demo ../../data/hpc_preprocessing_dataset_100k.csv --gpu-repeat 100
```

## Expected Output

You should see:

- CUDA device name
- Number of CPU OpenMP threads
- Optional CPU thread IDs and CUDA block/thread/global IDs
- Numeric columns processed on GPU
- Categorical columns processed on CPU
- GPU timing
- CPU timing
- Total hybrid timing

This validates the execution model before adapting it into the main app.

## GPU-Only Demo

There is also a separate CUDA-only processing demo:

```bash
./build_gpu_only.sh
./gpu_only_preprocess_demo ../../data/hpc_preprocessing_dataset_100k.csv
```

Print GPU thread activity:

```bash
./gpu_only_preprocess_demo ../../data/hpc_preprocessing_dataset_100k.csv --debug-threads --gpu-debug-limit 32
```

Print all GPU thread activity:

```bash
./gpu_only_preprocess_demo ../../data/hpc_preprocessing_dataset_100k.csv --debug-all-threads > gpu_thread_trace.txt
```

Note: this version does not launch an OpenMP CPU processing worker. The CPU is still used for file reading and converting CSV strings into numeric arrays before copying them to the GPU.
