# Comprehensive Project Workplan & Roadmap

## Overview
This document serves as the single source of truth for the project's development roadmap. It synthesizes the current architectural state with planned enhancements, structured specifically for tracking via GitHub Issues and Epics.

---

## Phase 1: Completing Core Parallelization (High Priority)
*Focus: Upgrading the existing C preprocessor placeholders to utilize true shared-memory and distributed-memory parallelization.*

### Epic: OpenMP Preprocessing Pipeline
Currently, the UI calls `preprocess_openmp`, but the C backend delegates to the serial implementation.
- [ ] **Issue 1.1**: Parallelize Outlier Detection using `#pragma omp parallel for` across columns.
- [ ] **Issue 1.2**: Parallelize Scaling & Normalization (Min-Max/Z-Score) using OpenMP.
- [ ] **Issue 1.3**: Parallelize Categorical Encoding across columns using OpenMP.

### Epic: MPI Distributed Processing
The MPI framework is wired up, but execution is currently simulated (runs serially on a single process).
- [ ] **Issue 1.4**: Implement `MPI_Scatter` to distribute CSV data columns across multiple processes in `mpi_analyzer.c`.
- [ ] **Issue 1.5**: Implement `MPI_Gather` to collect and merge analyzed statistics back to the root process.
- [ ] **Issue 1.6**: Extend MPI data distribution to the transformation stages in `preprocess_mpi` (Outliers, Scaling, Encoding).

---

## Phase 2: Technical Debt & Stability (Medium Priority)
*Focus: Resolving existing architectural limitations and cleaning up the codebase.*

### Epic: UI & Codebase Cleanup
- [ ] **Issue 2.1**: **Redundancy Cleanup**: Consolidate redundant pipeline stage configurations in `ui/pipeline_stages/`. Currently, `series`, `openmp`, and `mpi` folders contain nearly identical Python UI code. Implement a shared base UI stage architecture.
- [ ] **Issue 2.2**: **Logging Integration**: Fully integrate the file-based logging system (`ui/logging_config.py`) across all Python UI components and C library calls as described in `ARCHITECTURE_AND_PERFORMANCE.md`.

### Epic: C Backend Robustness
- [ ] **Issue 2.3**: **Dynamic Memory Management**: Replace fixed-size buffers (e.g., `char temp[4096]`) in `preprocessor.c` with dynamic memory allocation to support extremely wide CSV rows without buffer overflows.
- [ ] **Issue 2.4**: **Error Propagation**: Enhance error reporting from the C shared libraries to the Python UI. Replace simplified integer return codes with structured error messages.

---

## Phase 3: GPU Acceleration (Planned)
*Focus: Leveraging CUDA for massively parallel data transformations on NVIDIA GPUs.*

### Epic: CUDA Backend Implementation
The UI currently has a placeholder `UnifiedPipelineTab` option for CUDA.
- [ ] **Issue 3.1**: Create the core CUDA framework (`modules/analyzer_cuda/cuda_analyzer.cu`) and Makefile for building `libcudaanalyzer.so`.
- [ ] **Issue 3.2**: Implement CUDA kernels for Min-Max and Z-Score Normalization.
- [ ] **Issue 3.3**: Implement CUDA kernels for IQR-based Outlier Detection.
- [ ] **Issue 3.4**: Integrate `libcudaanalyzer.so` via `ctypes` into the Python UI (`ui/pipeline_stages/cuda/stage_apply.py`).

---

## Phase 4: Advanced Features & Analytics (Future)
*Focus: Expanding the application's capabilities beyond basic CSV processing.*

### Epic: Extended Data Handling
- [ ] **Issue 4.1**: **Excel Support**: Integrate a library like `libxlsxwriter` or a Python equivalent to support reading/writing `.xlsx` files.
- [ ] **Issue 4.2**: **Database Connectors**: Implement direct data ingestion from PostgreSQL and MySQL databases.
- [ ] **Issue 4.3**: **Batch CLI Mode**: Create a headless CLI script to run preprocessing pipelines on large directories of files without launching the Tkinter GUI.

### Epic: Enhanced Analytics
- [ ] **Issue 4.4**: **Advanced Statistics**: Expand the C analyzer to calculate skewness, kurtosis, and correlation matrices.
- [ ] **Issue 4.5**: **Data Visualization**: Integrate visual charts (histograms, box plots, scatter plots) into the UI using Matplotlib or a dedicated C-based graphics library.

---

## Summary of Current State (For Reference)
* **UI**: Modular Tkinter interface (`UnifiedPipelineTab`) with dynamic backend switching.
* **Serial Backend**: Fully implemented 5-stage pipeline in C (Duplicates, Missing, Outliers, Scaling, Encoding).
* **OpenMP Analyzer**: Implemented for statistical analysis.
* **Infrastructure**: Automated `build.sh` script creating `.so` libraries for `ctypes` integration.