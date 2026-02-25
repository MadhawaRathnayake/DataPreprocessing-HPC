---
name: data-preprocessing-app
description: >
  Complete architecture and codebase reference for the HPC Data Preprocessing
  Application — a hybrid Python (Tkinter UI) + C (OpenMP/MPI backend) desktop
  app for analyzing CSV datasets with serial and parallel processing modes.
  Read this file before making any changes to understand the full system.
---

# HPC Data Preprocessing Application — Full Architecture Reference

## 1. Project Overview

A **desktop data-preprocessing application** targeting High Performance Computing
education. The architecture intentionally separates concerns across two languages:

| Layer     | Language | Role                                        |
|-----------|----------|---------------------------------------------|
| Frontend  | Python 3 | Tkinter GUI, user interaction, orchestration |
| Backend   | C        | High-performance computation, shared libs   |
| Bridge    | ctypes   | Python loads and calls `.so` shared libraries |
| Parallel  | OpenMP   | Shared-memory multi-threading inside C      |
| Distributed | MPI    | Framework for multi-process/multi-node (simplified) |

**Run environment**: WSL (Ubuntu 24.04) on Windows. The project lives at
`/mnt/d/Projects/HPC/data_preprocessing_app` inside WSL.

---

## 2. Directory Structure

```
data_preprocessing_app/
├── SKILL.md                        ← This file
├── build.sh                        ← Builds all C modules → .so files in lib/
├── run.sh                          ← Checks lib/, then launches python3 ui/main_app.py
│
├── modules/                        ← C source code (one subfolder per module)
│   ├── importer/
│   │   ├── csv_importer.h          ← Public API header
│   │   ├── csv_importer.c          ← Implementation
│   │   └── Makefile                ← Compiles → ../../lib/libcsvimporter.so
│   ├── series_processing/          ← Serial/single-threaded backend [renamed from analyzer_serial]
│   │   ├── serial_analyzer.h
│   │   ├── serial_analyzer.c
│   │   └── Makefile                ← → lib/libserialanalyzer.so
│   ├── analyzer_openmp/
│   │   ├── openmp_analyzer.h
│   │   ├── openmp_analyzer.c       ← Uses #pragma omp parallel
│   │   └── Makefile                ← -fopenmp flag → lib/libompanalyzer.so
│   ├── analyzer_mpi/
│   │   ├── mpi_analyzer.h
│   │   ├── mpi_analyzer.c          ← Uses mpi.h (simplified, single-process)
│   │   └── Makefile                ← mpicc → lib/libmpianalyzer.so
│   └── analyzer_cuda/              ← [PLANNED — not yet implemented]
│       ├── cuda_analyzer.h
│       ├── cuda_analyzer.cu        ← CUDA kernels
│       └── Makefile                ← nvcc → lib/libcudaanalyzer.so
│
├── lib/                            ← Compiled shared libraries (.so)
│   ├── libcsvimporter.so
│   ├── libserialanalyzer.so
│   ├── libompanalyzer.so
│   └── libmpianalyzer.so
│
├── ui/                             ← Python Tkinter interface (modular tabs)
│   ├── main_app.py                 ← Entry point + app coordinator
│   ├── base_tab.py                 ← Abstract BaseTab class
│   ├── theme.py                    ← Dark theme colours + font constants
│   ├── import_tab.py               ← "Import" tab
│   ├── series_processing_tab.py    ← "Series Processing" tab (7-stage pipeline)
│   ├── openmp_pipeline_tab.py      ← "OpenMP Parallel" tab (7-stage pipeline)
│   ├── mpi_pipeline_tab.py         ← "MPI Parallel" tab (7-stage pipeline)
│   ├── cuda_pipeline_tab.py        ← "CUDA Parallel" tab (UI only — backend planned)
│   ├── export_tab.py               ← "Export" tab (placeholder)
│   ├── __init__.py
│   └── pipeline_stages/            ← Pipeline stage UI components
│       ├── series/                 ← Serial stage classes (UI + Python placeholder logic)
│       │   ├── __init__.py
│       │   ├── stage_overview.py   ← Stage 1: Data Overview & Profile
│       │   ├── stage_duplicates.py ← Stage 2: Duplicate Removal
│       │   ├── stage_missing.py    ← Stage 3: Missing Value Handling
│       │   ├── stage_outliers.py   ← Stage 4: Outlier Detection & Treatment
│       │   ├── stage_scaling.py    ← Stage 5: Scaling & Normalisation
│       │   ├── stage_encoding.py   ← Stage 6: Categorical Encoding
│       │   └── stage_apply.py      ← Stage 7: Apply & Preview (runs pipeline)
│       ├── openmp/                 ← OpenMP stage classes (TODO: call libompanalyzer.so)
│       │   ├── __init__.py
│       │   └── stage_*.py          ← Same UI; stage_apply has OpenMP ctypes TODO stub
│       ├── mpi/                    ← MPI stage classes (TODO: call libmpianalyzer.so)
│       │   ├── __init__.py
│       │   └── stage_*.py          ← Same UI; stage_apply has MPI ctypes TODO stub
│       └── cuda/                   ← CUDA stage classes (backend NOT YET IMPLEMENTED)
│           ├── __init__.py
│           └── stage_*.py          ← Same UI; stage_apply shows "not implemented" dialog
│
└── data/
    └── sample_employees.csv        ← 30 rows × 6 cols test dataset
                                       (Name, Age, Salary, Department,
                                        Experience, Performance)
```

---

> **Backend vs Frontend separation rule**  
> All *compute logic* (statistics, transformations) belongs in C shared libraries.  
> Python stage files are **UI only** — they define form controls and call C libs via ctypes.
> The `stage_apply.py` in each sub-package contains `# TODO:` comments showing exactly
> where the corresponding C library call goes once the backend is wired up.

## 3. Build System

### build.sh
Compiles all C modules in order:
1. `modules/importer/` → `lib/libcsvimporter.so`
2. `modules/series_processing/` → `lib/libserialanalyzer.so`  *(was `analyzer_serial/`)*
3. `modules/analyzer_openmp/` → `lib/libompanalyzer.so`
4. `modules/analyzer_mpi/` → `lib/libmpianalyzer.so` (skipped if `mpicc` absent)
5. `modules/analyzer_cuda/` → `lib/libcudaanalyzer.so` (planned — not yet present)

**GCC Flags used**: `-Wall -O2 -fPIC -fopenmp -lm`
- `-fPIC` is required for shared libraries
- `-fopenmp` enables OpenMP pragma directives
- MPI modules compiled with `mpicc` wrapper

### run.sh
1. Checks if `lib/` is empty → if so, calls `./build.sh`
2. Runs `python3 ui/main_app.py`

---

## 4. C Backend — Module APIs

### 4.1 CSV Importer (`libcsvimporter.so`)

**Header**: `modules/importer/csv_importer.h`

**Core struct**:
```c
typedef struct {
    char **data;      // 2D flat array [row * MAX_COLUMNS + col]
    char **headers;   // Column name strings
    int num_rows;
    int num_cols;
    int capacity;     // Current allocated row capacity
} CSVData;
```

**Public API** (called via Python ctypes):
```c
CSVData* csv_create();                                  // Allocate new CSVData
void     csv_free(CSVData *csv);                        // Free all memory
int      csv_load_file(const char *filename, CSVData *csv); // Parse CSV, returns 0=ok
char*    csv_get_cell(CSVData *csv, int row, int col);  // Get single cell value
char*    csv_get_header(CSVData *csv, int col);         // Get column header
int      csv_get_preview(CSVData *csv, int num_rows, char ***preview_data); // First N rows
```

**Limits**: MAX_COLUMNS=100, MAX_ROW_LENGTH=4096, MAX_CELL_LENGTH=512

---

### 4.2 Serial Analyzer (`libserialanalyzer.so`)

**Header**: `modules/analyzer_serial/serial_analyzer.h`

**Core structs**:
```c
typedef enum { TYPE_NUMERIC, TYPE_CATEGORICAL, TYPE_MIXED, TYPE_UNKNOWN } DataType;
typedef enum { CAT_CONTINUOUS, CAT_DISCRETE, CAT_NOMINAL, CAT_ORDINAL,
               CAT_BINARY, CAT_UNKNOWN } Category;

typedef struct { char *value; int count; } ValueCount;

typedef struct {
    char     *column_name;
    DataType  data_type;
    Category  category;
    int       total_count, null_count, unique_count;
    double    null_percentage;
    double    min_value, max_value, mean, median, std_dev;
    double   *outliers;
    int       outlier_count;
    ValueCount *value_counts;
    int       value_count_size;
    int       has_nulls, has_outliers, has_duplicates, type_consistent; // flags
} ColumnStats;

typedef struct {
    ColumnStats *columns;
    int          num_columns;
} DatasetStats;
```

**Public API**:
```c
DatasetStats* analyzer_create_stats(int num_columns);
void          analyzer_free_stats(DatasetStats *stats);
int           analyzer_analyze_dataset(char **data, char **headers,
                                       int num_rows, int num_cols,
                                       DatasetStats *stats);
void          analyzer_print_stats(DatasetStats *stats);
char*         analyzer_get_stats_json(DatasetStats *stats);  // Returns JSON string
```

Algorithm: Single-threaded, iterates all columns → for each column: sorts values
for median, IQR-based outlier detection (Q1 - 1.5×IQR, Q3 + 1.5×IQR).

---

### 4.3 OpenMP Analyzer (`libompanalyzer.so`)

**Header**: `modules/analyzer_openmp/openmp_analyzer.h`

Identical `ColumnStats` struct as serial, but `DatasetStats` adds:
```c
typedef struct {
    ColumnStats *columns;
    int          num_columns;
    double       processing_time;  // wall-clock seconds (omp_get_wtime)
    int          num_threads;
} DatasetStats;
```

**Public API**:
```c
DatasetStats* analyzer_omp_create_stats(int num_columns);
void          analyzer_omp_free_stats(DatasetStats *stats);
int           analyzer_omp_analyze_dataset(char **data, char **headers,
                                           int num_rows, int num_cols,
                                           DatasetStats *stats, int num_threads);
void          analyzer_omp_print_stats(DatasetStats *stats);
char*         analyzer_omp_get_stats_json(DatasetStats *stats);
```

**Parallelism**: `#pragma omp parallel for` at column level with
`schedule(dynamic)`. Each thread handles one column at a time.
Critical sections guard the shared output structure. Thread count is
configurable (1–16) from Python UI.

---

### 4.4 MPI Analyzer (`libmpianalyzer.so`)

**Header**: `modules/analyzer_mpi/mpi_analyzer.h`

`DatasetStats` adds `num_processes` instead of `num_threads`:
```c
typedef struct {
    ColumnStats *columns;
    int          num_columns;
    double       processing_time;
    int          num_processes;
} DatasetStats;
```

**Public API**:
```c
DatasetStats* analyzer_mpi_create_stats(int num_columns);
void          analyzer_mpi_free_stats(DatasetStats *stats);
int           analyzer_mpi_analyze_dataset(char **data, char **headers,
                                           int num_rows, int num_cols,
                                           DatasetStats *stats);
void          analyzer_mpi_print_stats(DatasetStats *stats);
char*         analyzer_mpi_get_stats_json(DatasetStats *stats);
```

**Current state**: Simplified single-process implementation. The framework and
structs are in place for full `MPI_Send`/`MPI_Recv` multi-process distribution,
but as a `.so` loaded by Python it currently runs in one process. Full MPI
deployment would require `mpirun/mpiexec` launcher.

---

## 5. Python Frontend — UI Layer

### 5.1 Entry Point: `ui/main_app.py`

**Class**: `DataPreprocessingApp`

**Startup sequence** (called in `__init__`):
1. `load_libraries()` — uses `ctypes.CDLL()` to load all four `.so` files from `lib/`
2. `setup_*_lib()` — sets `argtypes`/`restype` for each C function
3. `create_ui()` — creates `ttk.Notebook`, instantiates all 5 tabs
4. `bind_events()` — binds tab-change and window-close events

**Shared application state** (accessible to all tabs via `self.app`):
```python
self.csv_data    = None   # dict: {headers, data, num_rows, num_cols}
self.csv_handle  = None   # ctypes pointer to CSVData C struct
self.current_file = None  # str: absolute path of loaded file
self.csv_lib     = None   # ctypes handle to libcsvimporter.so
self.serial_lib  = None   # ctypes handle to libserialanalyzer.so
self.openmp_lib  = None   # ctypes handle to libompanalyzer.so
self.mpi_lib     = None   # ctypes handle to libmpianalyzer.so
self.status_var  = tk.StringVar()  # drives status bar label
```

**Key methods**:
- `set_status(msg)` — updates bottom status bar, calls `update_idletasks()`
- `on_tab_changed(event)` — dispatches `on_tab_selected()` to active tab
- `on_closing()` — calls `csv_free()` on C handle before destroying window

**ctypes signatures set up in `setup_csv_lib()`**:
```python
csv_lib.csv_create.argtypes = [];           csv_lib.csv_create.restype = c_void_p
csv_lib.csv_load_file.argtypes = [c_char_p, c_void_p]; restype = c_int
csv_lib.csv_get_cell.argtypes = [c_void_p, c_int, c_int]; restype = c_char_p
csv_lib.csv_get_header.argtypes = [c_void_p, c_int]; restype = c_char_p
csv_lib.csv_free.argtypes = [c_void_p];    csv_lib.csv_free.restype = None
```

---

### 5.2 BaseTab — `ui/base_tab.py`

Abstract base class all tabs inherit from:

```python
class BaseTab:
    def __init__(self, parent, app_context):
        self.parent = parent
        self.app    = app_context   # reference to DataPreprocessingApp
        self.frame  = ttk.Frame(parent)

    def get_frame(self)         # returns self.frame (added to notebook)
    def build_ui(self)          # MUST override — raises NotImplementedError
    def on_tab_selected(self)   # optional hook, called on tab switch
    def on_tab_deselected(self) # optional hook
```

---

### 5.3 ImportTab — `ui/import_tab.py`

**Purpose**: CSV file selection, C-library import, and data preview.

**UI layout**:
- `LabelFrame("File Selection")` — Entry (file path) + Browse button + Import button
- `LabelFrame("Data Preview (First 15 Rows)")` — `ttk.Treeview` with vertical + horizontal scrollbars

**Key methods**:
```python
browse_file()       # filedialog.askopenfilename → sets file_path_var
import_file()       # calls csv_create(), csv_load_file(), load_csv_data(), display_preview()
load_csv_data(path) # Python csv.reader → populates self.app.csv_data dict
display_preview()   # refreshes Treeview with first 15 rows
```

**Data flow on import**:
1. C library: `csv_create()` → handle stored in `self.app.csv_handle`
2. C library: `csv_load_file(path, handle)` → parses file in C
3. Python: `csv.reader` reads same file → stores in `self.app.csv_data`
4. UI: first 15 rows rendered in Treeview

> **Note**: Both the C library AND Python's `csv` module read the file.
> The C library owns the data for analysis; Python's dict is used for the UI display.

---

### 5.4 SeriesProcessingTab — `ui/series_processing_tab.py`

**UI**: 7-stage milstone pipeline (left stage rail + right config panel).  
**Imports**: `pipeline_stages.series.*` — Stage 1–7 classes.  
**Backend**: `serial_lib` (libserialanalyzer.so) via ctypes (Python placeholder currently active).

---

### 5.5 OpenMPPipelineTab — `ui/openmp_pipeline_tab.py`

**UI**: Identical 7-stage pipeline layout to SeriesProcessingTab.  
Left rail label shows `[OpenMP]`. `stage_apply.py` banner shows OpenMP backend info + timing.  
**Backend**: `openmp_lib` (libompanalyzer.so) — **TODO stub in `stage_apply._run_pipeline()`**.  

---

### 5.6 MPIPipelineTab — `ui/mpi_pipeline_tab.py`

**UI**: Identical 7-stage pipeline layout.  
Left rail label shows `[MPI]`. `stage_apply.py` banner shows MPI backend info + timing.  
**Backend**: `mpi_lib` (libmpianalyzer.so) — **TODO stub in `stage_apply._run_pipeline()`**.

---

### 5.7 CUDAPipelineTab — `ui/cuda_pipeline_tab.py`

**UI**: Identical 7-stage pipeline layout.  
Left rail label shows `[CUDA]`. `stage_apply.py` banner shows CUDA backend planned status.  
**Backend**: NOT YET IMPLEMENTED — clicking "Run CUDA Pipeline" shows an informational  
dialog with planned implementation details (modules/analyzer_cuda/, nvcc compile flags).  

---

### 5.8 ExportTab — `ui/export_tab.py`

**Placeholder only**. Shows planned features list with disabled buttons.
Planned: Export to CSV, Excel, JSON; PDF report generation.

---

## 6. Data Flow (End-to-End)

```
User clicks "Browse"
    → filedialog.askopenfilename()
    → file_path_var set

User clicks "Import"
    → csv_create()                     [C: allocates CSVData struct]
    → csv_load_file(path, handle)      [C: parses CSV into CSVData.data[][]]
    → csv.reader(path)                 [Python: builds app.csv_data dict]
    → display_preview()                [Python: renders Treeview, first 15 rows]
    → app.current_file = path
    → app.csv_handle = C pointer

User clicks "Run Serial Analysis"
    → _build_analysis_results()        [Python: iterates app.csv_data]
        for each column:
            → count nulls, uniques
            → detect type (numeric vs categorical)
            → compute min/max/mean/median  (numeric)
            → top-5 Counter             (categorical)
    → ScrolledText.insert(result_text)

User clicks "Run OpenMP Analysis"
    → same as serial but:
        → num_threads from Spinbox
        → shows Thread assignment
        → also computes std_dev

User clicks "Run MPI Analysis"
    → same as serial but:
        → shows Process 0 for each column
        → prints MPI notes
```

---

## 7. Python ↔ C Integration Details

All C libraries are loaded with `ctypes.CDLL`. Pointers are typed as
`ctypes.c_void_p` (opaque handles). Strings pass as `c_char_p`; Python strings
must be `.encode('utf-8')` before passing.

**Pattern used every time a C function is called**:
```python
# Pointer returned as integer (c_void_p)
handle = self.app.csv_lib.csv_create()

# Pass encoded bytes for strings
result = self.app.csv_lib.csv_load_file(
    filepath.encode('utf-8'),  # c_char_p
    self.app.csv_handle        # c_void_p
)

# Always free C memory on close
self.app.csv_lib.csv_free(self.app.csv_handle)
```

---

## 8. Shared Data Structure (`app.csv_data`)

After a successful import, `self.app.csv_data` is a Python dict:
```python
{
    'headers':  ['Name', 'Age', 'Salary', 'Department', 'Experience', 'Performance'],
    'data':     [['Alice', '30', '55000', 'Engineering', '5', 'A'], ...],  # list of lists
    'num_rows': 30,
    'num_cols': 6
}
```
All tab modules access this via `self.app.csv_data`. Any tab that needs data
checks `if not self.app.csv_data` and shows an error to "Import first".

---

## 9. HPC Concepts Used

| Concept           | Where Used                          | Details                                  |
|-------------------|-------------------------------------|------------------------------------------|
| OpenMP            | `analyzer_openmp.c`                 | `#pragma omp parallel for schedule(dynamic)`, column-level parallelism |
| MPI               | `analyzer_mpi.c`                    | Framework ready, `mpi.h` included, single-process currently |
| Shared Libraries  | All C modules → `.so` files         | `-fPIC`, `ctypes.CDLL` loading           |
| ctypes bridge     | `main_app.py`                       | `argtypes`/`restype` for type-safe ABI   |
| IQR Outlier detection | serial + openmp + mpi analyzers | Q1 - 1.5×IQR, Q3 + 1.5×IQR             |
| Dynamic scheduling| OpenMP analyzer                     | `schedule(dynamic)` balances uneven column workloads |

---

## 10. How to Run

```bash
# Inside WSL (Ubuntu), navigate to project
cd /mnt/d/Projects/HPC/data_preprocessing_app

# Step 1: Build all C shared libraries
./build.sh

# Step 2: Launch the application (GUI opens via WSLg)
./run.sh

# Alternative direct launch
cd ui && python3 main_app.py
```

**Dependencies** (Ubuntu):
```bash
sudo apt-get install build-essential python3 python3-tk libopenmpi-dev
```

---

## 11. How to Add a New Feature (Standard Pattern)

### Adding a New Analysis Module (C + UI)

1. **Create C module** in `modules/new_feature/`
   - Write `new_feature.h` with public API
   - Implement `new_feature.c`
   - Write `Makefile` targeting `../../lib/libnewfeature.so`

2. **Register in `build.sh`**:
   ```bash
   cd modules/new_feature && make clean && make && cd ../..
   ```

3. **Load in `main_app.py`**:
   ```python
   self.new_lib = ctypes.CDLL(str(LIB_DIR / "libnewfeature.so"))
   # set up argtypes/restype
   ```

4. **Create UI tab** `ui/new_tab.py`:
   ```python
   from base_tab import BaseTab
   class NewTab(BaseTab):
       def __init__(self, parent, app_context):
           super().__init__(parent, app_context)
           self.build_ui()
       def build_ui(self): ...
       def run_analysis(self): ...
       def on_tab_selected(self): ...
   ```

5. **Register tab in `main_app.py`**:
   ```python
   from new_tab import NewTab
   self.tabs['new'] = NewTab(self.notebook, self)
   self.notebook.add(self.tabs['new'].get_frame(), text="New Tab")
   ```

### Adding a New Column Statistic

- **C side**: Add field to `ColumnStats` struct in the relevant `.h` file, compute in `.c`
- **Python side**: Read from `app.csv_data` or parse from the JSON returned by `*_get_stats_json()`
- **UI side**: Append to `_build_analysis_results()` output string in the relevant tab

---

## 12. Key Constraints & Known Limitations

1. **MPI is single-process**: `libmpianalyzer.so` loaded by Python cannot span processes.
   Full MPI needs `mpirun -n 4 python3 ...` or a subprocess-based launcher.
2. **Analysis currently in Python**: `_run_pipeline()` in each `stage_apply.py` does
   computation in Python as a placeholder. Each file contains a clearly marked `# TODO:`
   block showing exactly where the C ctypes call goes. See the `stage_apply.py` in
   `pipeline_stages/series/`, `pipeline_stages/openmp/`, and `pipeline_stages/mpi/`.
3. **CUDA backend not implemented**: `pipeline_stages/cuda/stage_apply.py` shows a
   "not implemented" dialog. Requires `modules/analyzer_cuda/`, nvcc, and CUDA toolkit.
4. **Memory**: Entire CSV loaded into RAM — no streaming support.
5. **CSV only**: No Excel/JSON import yet.
6. **Export tab**: Placeholder only, no export implemented.
7. **Display limit**: Preview shows first 15 rows only (C `csv_get_preview` takes `num_rows` param).
