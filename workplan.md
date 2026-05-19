# Project Workplan: HPC Data Preprocessing Application

## 1. Project Overview
This application is a high-performance data preprocessing tool featuring a modular C backend for heavy computation and a Python Tkinter GUI for user interaction. It supports multiple processing modes: Serial, OpenMP (parallel), MPI (distributed), and CUDA (GPU acceleration).

---

## 2. Completed Features (Done) ✅

### UI & UX
- [x] **Modern Modular UI**: Tabbed interface using a custom theme and `UnifiedPipelineTab`.
- [x] **Dynamic Method Selection**: Seamlessly switch between Serial, OpenMP, MPI, and CUDA modes.
- [x] **Import & Preview**: CSV file browser with a 20-row preview table using a dedicated C importer module.
- [x] **Benchmark Tab**: Performance comparison dashboard showing timing metrics across different backends.
- [x] **Export System**: Ability to save processed results back to CSV.

### Core Processing (Serial)
- [x] **C Preprocessor Library**: Fully implemented 5-stage pipeline in C:
    1. Duplicate Removal
    2. Missing Value Imputation (Mean/Mode)
    3. Outlier Detection (IQR Method)
    4. Scaling & Normalization (Min-Max)
    5. Categorical Encoding (Label Encoding)
- [x] **C Analyzer Library**: Statistical analysis for numeric and categorical columns.

### Parallel Processing (OpenMP)
- [x] **OpenMP Analysis**: Column-level parallelization for statistical analysis using `#pragma omp parallel for`.

---

## 3. In-Progress / Partially Implemented ⏳

### MPI Integration
- [x] **MPI Framework**: Interface and UI are ready.
- [ ] **Distributed Logic**: Current MPI backend is simulated/serial. Needs implementation of data distribution (scatter/gather) across multiple processes.

### Preprocessing Parallelization
- [x] **OpenMP/MPI Wiring**: The UI correctly calls the parallel entry points.
- [ ] **Parallel Stages**: Currently, `preprocess_openmp` and `preprocess_mpi` delegate to the serial implementation. Need to implement parallel versions of:
    - Outlier detection (parallelize across columns)
    - Scaling & Normalization (parallelize across columns)
    - Encoding (parallelize across columns)

---

## 4. Planned Features (To Do) 🚀

### GPU Acceleration
- [ ] **CUDA Backend**: Implement `modules/analyzer_cuda/` and `libcudaanalyzer.so`.
- [ ] **GPU Kernels**: Implement massively parallel kernels for data normalization and outlier detection.

### Advanced Data Handling
- [ ] **Excel Support**: Integration of libraries like `libxlsxwriter` for .xlsx import/export.
- [ ] **Database Integration**: Connectors for PostgreSQL/MySQL for direct data ingestion.
- [ ] **Batch Processing**: CLI mode for running pipelines on large directories of CSVs without the GUI.

### Analytics & Visualization
- [ ] **Enhanced Statistics**: Add skewness, kurtosis, and correlation matrices.
- [ ] **Data Visualization**: Integrated charts (histograms, box plots, scatter plots) using Matplotlib or a C-based graphics library.

---

## 5. Technical Debt & Improvements 🛠️

- [ ] **Dynamic Memory Management**: Replace fixed-size buffers (`char[4096]`) in C modules with dynamic allocation to support extremely wide CSV rows.
- [ ] **Error Propagation**: Improve error reporting from C shared libraries to the Python UI (currently uses simplified return codes).
- [ ] **Redundancy Cleanup**: Consolidate redundant stage files in `ui/pipeline_stages/` (many files across `series`, `openmp`, `mpi` are identical).
- [ ] **Logging**: Fully implement the logging system described in `ARCHITECTURE_AND_PERFORMANCE.md`.

---

## 6. Development Roadmap

1. **Phase 1 (Parallel Preprocessing)**: Implement OpenMP parallelization for the transformation stages in `preprocessor.c`.
2. **Phase 2 (Distributed MPI)**: Implement real MPI data distribution for the analyzer and preprocessor.
3. **Phase 3 (CUDA)**: Develop the CUDA backend for GPU acceleration.
4. **Phase 4 (Expansion)**: Add visualization and support for more file formats.
