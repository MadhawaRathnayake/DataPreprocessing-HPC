# Data Preprocessing Application - Project Overview

## Executive Summary

This is a **modular data preprocessing application** built with a hybrid architecture:
- **Backend**: High-performance C modules for data processing.
- **Frontend**: Python Tkinter GUI for user interaction, using a modern, unified pipeline architecture.
- **Parallel Processing**: OpenMP and MPI support for scalability (partially implemented, with full preprocessing parallelization planned).

The application demonstrates professional software engineering practices including modularity, parallel computing, and cross-language integration.

## Key Features Implemented

### 1. CSV Import Module (C)
- ✅ Fast CSV file parsing
- ✅ Handles quoted fields and escape sequences
- ✅ Dynamic memory allocation
- ✅ Preview functionality (first 15 rows)
- ✅ Shared library interface for Python integration

### 2. Serial Analyzer Module (C)
- ✅ Column-by-column data analysis
- ✅ Automatic data type detection (Numeric/Categorical/Mixed)
- ✅ Comprehensive statistics:
  - Count metrics (total, null, unique)
  - Numeric statistics (min, max, mean, median, std dev)
  - Outlier detection using IQR method
  - Value frequency distribution
- ✅ Data quality flags (nulls, outliers, duplicates, consistency)

### 3. OpenMP Analyzer Module (C)
- ✅ Parallel processing using OpenMP
- ✅ Column-level parallelization
- ✅ Configurable thread count
- ✅ Performance timing and metrics
- ✅ Same analysis as serial but parallelized

### 4. MPI Analyzer Module (C)
- ✅ Framework for distributed processing
- ✅ MPI integration structure (simplified serial implementation currently; full distributed scatter/gather planned)

### 5. C Preprocessor Module
- ✅ Full C implementation of the 5-stage transformation pipeline (Duplicates, Missing, Outliers, Scaling, Encoding).
- ✅ Memory-managed string processing for high performance.
- ⏳ OpenMP and MPI versions are wired up but currently delegate to the serial implementation (Parallelization is the next major milestone).

### 6. Python Tkinter UI
- ✅ Professional tabbed interface with a `UnifiedPipelineTab`.
- ✅ Dynamic backend switching (Serial, OpenMP, MPI, CUDA).
- ✅ File browser with CSV selection.
- ✅ Data preview table.
- ✅ Real-time status updates and benchmarking metrics.

## Architecture

```
┌─────────────────────────────────────────┐
│         Python Tkinter UI               │
│  (Unified Pipeline, Settings, Controls) │
└──────────────┬──────────────────────────┘
               │ ctypes
               │ (Python-C Interface)
               │
    ┌──────────┴──────────────────────┐
    │                                 │
    ▼                                 ▼
┌─────────────┐           ┌──────────────────┐
│   Import    │           │   Processors &   │
│   Module    │           │    Analyzers     │
│   (C lib)   │           │  ┌─────────────┐ │
│             │           │  │   Serial    │ │
└─────────────┘           │  │   (C lib)   │ │
                          │  └─────────────┘ │
                          │  ┌─────────────┐ │
                          │  │   OpenMP    │ │
                          │  │   (C lib)   │ │
                          │  └─────────────┘ │
                          │  ┌─────────────┐ │
                          │  │     MPI     │ │
                          │  │   (C lib)   │ │
                          │  └─────────────┘ │
                          └──────────────────┘
```

## Directory Structure

```
data_preprocessing_app/
├── modules/                    # C source code modules
│   ├── importer/
│   │   ├── csv_importer.h     # Header with API definitions
│   │   ├── csv_importer.c     # CSV parsing implementation
│   │   └── Makefile           # Build configuration
│   ├── analyzer_serial/
│   │   ├── serial_analyzer.h
│   │   ├── serial_analyzer.c  # Serial analysis logic
│   │   └── Makefile
│   ├── analyzer_openmp/
│   │   ├── openmp_analyzer.h
│   │   ├── openmp_analyzer.c  # Parallel analysis with OpenMP
│   │   └── Makefile
│   ├── analyzer_mpi/
│   │   ├── mpi_analyzer.h
│   │   ├── mpi_analyzer.c     # MPI-based analysis framework
│   │   └── Makefile
│   └── preprocessor/          # Full 5-stage transformation pipeline in C
├── ui/
│   ├── main_app.py            # Main application coordinator
│   ├── unified_pipeline_tab.py# Modern modular pipeline UI
│   └── pipeline_stages/       # UI configurations for pipeline steps
├── lib/                       # Compiled shared libraries (.so)
├── data/
│   └── sample_employees.csv   # Sample dataset for testing
├── build.sh                   # Automated build script
├── run.sh                     # Application launcher
├── README.md                  # Full documentation
├── QUICKSTART.md              # Getting started guide
└── workplan.md                # Comprehensive development roadmap
```

## Technology Stack

### Backend (C)
- **Language**: C (C99/C11)
- **Compiler**: GCC with optimization flags
- **Parallel**: OpenMP for shared-memory parallelism
- **Distributed**: MPI for distributed computing
- **Build**: Make build system
- **Libraries**: Standard C library, math library

### Frontend (Python)
- **Language**: Python 3.6+
- **GUI**: Tkinter (built-in)
- **Integration**: ctypes for C library loading

### Development Tools
- **Version Control**: Git
- **Documentation**: Markdown
- **Build System**: Shell scripts + Makefiles

## Analysis Capabilities

### Data Type Detection
- Automatically identifies numeric vs categorical data
- Detects mixed-type columns
- Handles null/missing values (NA, null, N/A, empty)

### Statistical Analysis

#### For Numeric Columns:
- **Central Tendency**: Mean, Median
- **Spread**: Min, Max, Standard Deviation
- **Outliers**: IQR-based detection (Q1 - 1.5*IQR, Q3 + 1.5*IQR)
- **Distribution**: All data points processed

#### For Categorical Columns:
- **Frequency**: Value counts for top values
- **Cardinality**: Unique value tracking
- **Distribution**: Most common values identified

#### Quality Metrics:
- Null percentage
- Duplicate detection
- Type consistency checking
- Data completeness

## Parallel Processing Features

### OpenMP Implementation
- **Strategy**: Column-level parallelization (currently implemented in analyzer; planned for preprocessor)
- **Scheduling**: Dynamic work distribution
- **Thread Safety**: Critical sections for output
- **Scalability**: Configurable thread count (1-16)
- **Performance**: Processing time measurement

### MPI Framework (Extensible)
- **Current**: Framework is loaded, but execution is simulated serially without true distributed logic.
- **Design**: Ready for multi-process distribution via `MPI_Scatter` and `MPI_Gather`.

## Build System

### Automated Build Process
```bash
./build.sh
```

Compiles all C modules into shared libraries in the `lib/` directory.

### Compilation Flags
- `-O3`: Maximum optimization level
- `-fPIC`: Position Independent Code (for shared libraries)
- `-fopenmp`: OpenMP support
- `-Wall`: All warnings
- `-lm`: Math library

## Testing & Usage

### Sample Data
Included: `data/sample_employees.csv`
- 30 rows
- 6 columns (Name, Age, Salary, Department, Experience, Performance)
- Mix of numeric and categorical data

### Typical Workflow
1. Build application: `./build.sh`
2. Launch: `./run.sh`
3. Import: Browse and select CSV file
4. Pipeline: Go to the Unified Pipeline tab, select a method (e.g., OpenMP), configure the 5 stages, and run.
5. Benchmark: View the performance metrics on the Benchmark tab.

## Future Development Roadmap

See `workplan.md` for a detailed breakdown of completed tasks, work-in-progress, and the backlog. Major upcoming milestones include:
1. True OpenMP parallelization inside `preprocessor.c`.
2. True MPI data distribution across multiple processes.
3. CUDA GPU kernel implementation for extreme scaling.

## Dependencies

### Required:
- GCC (with OpenMP)
- Python 3.6+
- Tkinter

### Optional:
- OpenMPI or MPICH (for MPI module)

## License

Educational/Demonstration project. Free to use and modify.
