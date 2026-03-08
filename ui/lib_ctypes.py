"""
ctypes Wrapper Module for C Shared Libraries
Provides Python interfaces to:
- libcsvimporter.so (CSV import)
- libserialanalyzer.so (Serial analysis & preprocessing)
- libompanalyzer.so  (OpenMP parallel analysis)
- libmpianalyzer.so  (MPI parallel analysis)
"""

import ctypes
from ctypes import c_char_p, c_int, c_double, POINTER, Structure
from pathlib import Path
import json


# ─────────────────────────────────────────────────────────────────────────────
# Structure Definitions (matching C headers)
# ─────────────────────────────────────────────────────────────────────────────

class ValueCount(Structure):
    """C struct: typedef struct { char *value; int count; } ValueCount;"""
    pass

ValueCount._fields_ = [
    ("value", c_char_p),
    ("count", c_int),
]


class ColumnStats(Structure):
    """C struct for column statistics"""
    pass

ColumnStats._fields_ = [
    ("column_name", c_char_p),
    ("data_type", c_int),
    ("category", c_int),
    ("total_count", c_int),
    ("null_count", c_int),
    ("unique_count", c_int),
    ("null_percentage", c_double),
    ("min_value", c_double),
    ("max_value", c_double),
    ("mean", c_double),
    ("median", c_double),
    ("std_dev", c_double),
    ("outliers", POINTER(c_double)),
    ("outlier_count", c_int),
    ("value_counts", POINTER(ValueCount)),
    ("value_count_size", c_int),
    ("has_nulls", c_int),
    ("has_outliers", c_int),
    ("has_duplicates", c_int),
    ("type_consistent", c_int),
]


class DatasetStats(Structure):
    """C struct for dataset-level statistics"""
    pass

DatasetStats._fields_ = [
    ("columns", POINTER(ColumnStats)),
    ("num_columns", c_int),
]


class DatasetStatsOMP(Structure):
    """OpenMP version with timing info"""
    pass

DatasetStatsOMP._fields_ = [
    ("columns", POINTER(ColumnStats)),
    ("num_columns", c_int),
    ("processing_time", c_double),
    ("num_threads", c_int),
]


class DatasetStatsMPI(Structure):
    """MPI version with process info"""
    pass

DatasetStatsMPI._fields_ = [
    ("columns", POINTER(ColumnStats)),
    ("num_columns", c_int),
    ("processing_time", c_double),
    ("num_processes", c_int),
]


# ─────────────────────────────────────────────────────────────────────────────
# Preprocessing Structures (matching modules/preprocessor/preprocessor.h)
# ─────────────────────────────────────────────────────────────────────────────

class OutlierConfig(Structure):
    """Configuration for outlier detection"""
    pass

OutlierConfig._fields_ = [
    ("method", c_int),                    # 0=IQR, 1=Z-score
    ("treatment", c_int),                 # 0=remove, 1=cap, 2=flag
    ("columns", POINTER(c_char_p)),       # Column names to process
    ("num_columns", c_int),               # Number of columns
    ("threshold", c_double),              # IQR multiplier (1.5) or Z-score threshold (3.0)
]


class ScalingConfig(Structure):
    """Configuration for scaling/normalization"""
    pass

ScalingConfig._fields_ = [
    ("method", c_int),                    # 0=min-max, 1=z-score, 2=standard
    ("columns", POINTER(c_char_p)),       # Column names to scale
    ("num_columns", c_int),               # Number of columns
]


class EncodingConfig(Structure):
    """Configuration for categorical encoding"""
    pass

EncodingConfig._fields_ = [
    ("method", c_int),                    # 0=label, 1=onehot
    ("columns", POINTER(c_char_p)),       # Column names to encode
    ("num_columns", c_int),               # Number of columns
]


class PreprocessedData(Structure):
    """Result structure from C preprocessing"""
    pass

PreprocessedData._fields_ = [
    ("data", POINTER(c_char_p)),          # Processed data array
    ("num_rows", c_int),                  # Number of rows after processing
    ("num_cols", c_int),                  # Number of columns (unchanged)
    ("headers", POINTER(c_char_p)),       # Column headers
    ("duplicates_found", c_int),          # Metrics: rows removed as duplicates
    ("missing_filled", c_int),            # Metrics: missing values imputed
    ("outliers_removed", c_int),          # Metrics: outlier rows removed
    ("columns_scaled", c_int),            # Metrics: columns normalized
    ("columns_encoded", c_int),           # Metrics: columns with label encoding
    ("processing_time_ms", c_double),     # Total processing time in milliseconds
]


# ─────────────────────────────────────────────────────────────────────────────
# Library Loader
# ─────────────────────────────────────────────────────────────────────────────

class CAnalyzerLib:
    """Unified interface to C preprocessing libraries"""
    
    def __init__(self, lib_path):
        """Load a C shared library"""
        self.lib = None
        self.lib_path = lib_path
        self._setup_funcs = []
        
        try:
            self.lib = ctypes.CDLL(str(lib_path))
        except OSError:
            print(f"Warning: Could not load {lib_path}")
    
    def is_loaded(self):
        return self.lib is not None
    
    def _setup_serial(self):
        """Configure function signatures for serial analyzer"""
        if not self.lib:
            return
        
        # analyzer_create_stats(int num_columns) -> DatasetStats*
        self.lib.analyzer_create_stats.argtypes = [c_int]
        self.lib.analyzer_create_stats.restype = POINTER(DatasetStats)
        
        # analyzer_free_stats(DatasetStats *stats) -> void
        self.lib.analyzer_free_stats.argtypes = [POINTER(DatasetStats)]
        self.lib.analyzer_free_stats.restype = None
        
        # analyzer_analyze_dataset(char **data, char **headers, int num_rows, 
        #                          int num_cols, DatasetStats *stats) -> int
        self.lib.analyzer_analyze_dataset.argtypes = [
            POINTER(c_char_p), POINTER(c_char_p), c_int, c_int, POINTER(DatasetStats)
        ]
        self.lib.analyzer_analyze_dataset.restype = c_int
        
        # analyzer_get_stats_json(DatasetStats *stats) -> char*
        self.lib.analyzer_get_stats_json.argtypes = [POINTER(DatasetStats)]
        self.lib.analyzer_get_stats_json.restype = c_char_p
    
    def _setup_openmp(self):
        """Configure function signatures for OpenMP analyzer"""
        if not self.lib:
            return
        
        # analyzer_omp_create_stats(int num_columns) -> DatasetStats*
        self.lib.analyzer_omp_create_stats.argtypes = [c_int]
        self.lib.analyzer_omp_create_stats.restype = POINTER(DatasetStatsOMP)
        
        # analyzer_omp_free_stats(DatasetStats *stats) -> void
        self.lib.analyzer_omp_free_stats.argtypes = [POINTER(DatasetStatsOMP)]
        self.lib.analyzer_omp_free_stats.restype = None
        
        # analyzer_omp_analyze_dataset(char **data, char **headers, int num_rows,
        #                              int num_cols, DatasetStats *stats, int num_threads) -> int
        self.lib.analyzer_omp_analyze_dataset.argtypes = [
            POINTER(c_char_p), POINTER(c_char_p), c_int, c_int, POINTER(DatasetStatsOMP), c_int
        ]
        self.lib.analyzer_omp_analyze_dataset.restype = c_int
        
        # analyzer_omp_get_stats_json(DatasetStats *stats) -> char*
        self.lib.analyzer_omp_get_stats_json.argtypes = [POINTER(DatasetStatsOMP)]
        self.lib.analyzer_omp_get_stats_json.restype = c_char_p
    
    def _setup_mpi(self):
        """Configure function signatures for MPI analyzer"""
        if not self.lib:
            return
        
        # analyzer_mpi_create_stats(int num_columns) -> DatasetStats*
        self.lib.analyzer_mpi_create_stats.argtypes = [c_int]
        self.lib.analyzer_mpi_create_stats.restype = POINTER(DatasetStatsMPI)
        
        # analyzer_mpi_free_stats(DatasetStats *stats) -> void
        self.lib.analyzer_mpi_free_stats.argtypes = [POINTER(DatasetStatsMPI)]
        self.lib.analyzer_mpi_free_stats.restype = None
        
        # analyzer_mpi_analyze_dataset(char **data, char **headers, int num_rows,
        #                              int num_cols, DatasetStats *stats) -> int
        self.lib.analyzer_mpi_analyze_dataset.argtypes = [
            POINTER(c_char_p), POINTER(c_char_p), c_int, c_int, POINTER(DatasetStatsMPI)
        ]
        self.lib.analyzer_mpi_analyze_dataset.restype = c_int
        
        # analyzer_mpi_get_stats_json(DatasetStats *stats) -> char*
        self.lib.analyzer_mpi_get_stats_json.argtypes = [POINTER(DatasetStatsMPI)]
        self.lib.analyzer_mpi_get_stats_json.restype = c_char_p
    
    def _setup_preprocessor(self):
        """Configure function signatures for preprocessor (serial)"""
        if not self.lib:
            return
        
        # preprocess_serial(char **data, char **headers, int num_rows, int num_cols,
        #                   int remove_duplicates, OutlierConfig *outlier_cfg,
        #                   ScalingConfig *scaling_cfg, EncodingConfig *encoding_cfg) 
        #                   -> PreprocessedData*
        self.lib.preprocess_serial.argtypes = [
            POINTER(c_char_p), POINTER(c_char_p), c_int, c_int, c_int,
            POINTER(OutlierConfig), POINTER(ScalingConfig), POINTER(EncodingConfig)
        ]
        self.lib.preprocess_serial.restype = POINTER(PreprocessedData)
        
        # preprocess_openmp(char **data, char **headers, int num_rows, int num_cols,
        #                   int num_threads, int should_remove_duplicates,
        #                   OutlierConfig *outlier_cfg, ScalingConfig *scaling_cfg,
        #                   EncodingConfig *encoding_cfg) -> PreprocessedData*
        self.lib.preprocess_openmp.argtypes = [
            POINTER(c_char_p), POINTER(c_char_p), c_int, c_int, c_int, c_int,
            POINTER(OutlierConfig), POINTER(ScalingConfig), POINTER(EncodingConfig)
        ]
        self.lib.preprocess_openmp.restype = POINTER(PreprocessedData)
        
        # preprocess_mpi(char **data, char **headers, int num_rows, int num_cols,
        #                int num_processes, int should_remove_duplicates,
        #                OutlierConfig *outlier_cfg, ScalingConfig *scaling_cfg,
        #                EncodingConfig *encoding_cfg) -> PreprocessedData*
        self.lib.preprocess_mpi.argtypes = [
            POINTER(c_char_p), POINTER(c_char_p), c_int, c_int, c_int, c_int,
            POINTER(OutlierConfig), POINTER(ScalingConfig), POINTER(EncodingConfig)
        ]
        self.lib.preprocess_mpi.restype = POINTER(PreprocessedData)
        
        # free_preprocessed_data(PreprocessedData *data) -> void
        self.lib.free_preprocessed_data.argtypes = [POINTER(PreprocessedData)]
        self.lib.free_preprocessed_data.restype = None
        
        # preprocess_to_json(PreprocessedData *data) -> char*
        self.lib.preprocess_to_json.argtypes = [POINTER(PreprocessedData)]
        self.lib.preprocess_to_json.restype = c_char_p


# ─────────────────────────────────────────────────────────────────────────────
# Library Factories
# ─────────────────────────────────────────────────────────────────────────────

def load_serial_analyzer(lib_dir):
    """Load serial analyzer library"""
    lib = CAnalyzerLib(Path(lib_dir) / "libserialanalyzer.so")
    lib._setup_serial()
    return lib


def load_openmp_analyzer(lib_dir):
    """Load OpenMP analyzer library"""
    lib = CAnalyzerLib(Path(lib_dir) / "libompanalyzer.so")
    lib._setup_openmp()
    return lib


def load_mpi_analyzer(lib_dir):
    """Load MPI analyzer library"""
    lib = CAnalyzerLib(Path(lib_dir) / "libmpianalyzer.so")
    lib._setup_mpi()
    return lib


def load_preprocessor(lib_dir, variant="serial"):
    """Load preprocessor library (serial, openmp, or mpi)"""
    lib_map = {
        "serial": "libpreprocessor.so",
        "openmp": "libpreprocessor_omp.so",
        "mpi": "libpreprocessor_mpi.so",
    }
    lib_name = lib_map.get(variant, "libpreprocessor.so")
    lib = CAnalyzerLib(Path(lib_dir) / lib_name)
    lib._setup_preprocessor()
    return lib


def load_serial_preprocessor(lib_dir):
    """Load serial preprocessor library"""
    return load_preprocessor(lib_dir, "serial")


def load_openmp_preprocessor(lib_dir):
    """Load OpenMP preprocessor library"""
    return load_preprocessor(lib_dir, "openmp")


def load_mpi_preprocessor(lib_dir):
    """Load MPI preprocessor library"""
    return load_preprocessor(lib_dir, "mpi")


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions for Data Conversion
# ─────────────────────────────────────────────────────────────────────────────

def python_data_to_c(python_data, python_headers):
    """
    Convert Python lists to ctypes format for C library calls
    
    Parameters:
    -----------
    python_data : list of lists (rows)
    python_headers : list of strings
    
    Returns:
    --------
    (c_data, c_headers, num_rows, num_cols)
    """
    num_rows = len(python_data)
    num_cols = len(python_headers)
    
    # Convert headers to ctypes array of strings
    c_headers = (c_char_p * num_cols)()
    for i, h in enumerate(python_headers):
        c_headers[i] = h.encode('utf-8') if isinstance(h, str) else h
    
    # Flatten and convert data to ctypes array
    c_data = (c_char_p * (num_rows * num_cols))()
    idx = 0
    for row in python_data:
        for cell in row:
            c_data[idx] = cell.encode('utf-8') if isinstance(cell, str) else cell
            idx += 1
    
    return POINTER(c_char_p)(c_data), POINTER(c_char_p)(c_headers), num_rows, num_cols


def c_preprocessed_data_to_python(c_result):
    """
    Convert C PreprocessedData struct back to Python format
    
    Parameters:
    -----------
    c_result : PreprocessedData* (ctypes pointer)
    
    Returns:
    --------
    {
        'data': list of lists,
        'headers': list of strings,
        'num_rows': int,
        'num_cols': int,
        'metrics': {
            'duplicates_found': int,
            'missing_filled': int,
            'outliers_removed': int,
            'columns_scaled': int,
            'columns_encoded': int,
            'processing_time_ms': float
        }
    }
    """
    if not c_result:
        return None
    
    result = c_result.contents
    
    # Extract headers
    headers = []
    for i in range(result.num_cols):
        if result.headers and result.headers[i]:
            headers.append(result.headers[i].decode('utf-8'))
        else:
            headers.append('')
    
    # Extract data rows
    # NOTE: Each row in C is stored as a CSV-formatted string "val1,val2,val3,..."
    data = []
    if result.num_rows > 0 and result.data:
        for i in range(result.num_rows):
            if not result.data[i]:
                data.append([''] * result.num_cols)
                continue
            
            # Decode the CSV row string
            row_str = result.data[i].decode('utf-8') if isinstance(result.data[i], bytes) else result.data[i]
            
            # Split by comma to get individual cells
            cells = row_str.split(',')
            
            # Pad with empty strings if needed
            while len(cells) < result.num_cols:
                cells.append('')
            
            # Take only num_cols elements
            data.append(cells[:result.num_cols])
    
    return {
        'data': data,
        'headers': headers,
        'num_rows': result.num_rows,
        'num_cols': result.num_cols,
        'metrics': {
            'duplicates_found': result.duplicates_found,
            'missing_filled': result.missing_filled,
            'outliers_removed': result.outliers_removed,
            'columns_scaled': result.columns_scaled,
            'columns_encoded': result.columns_encoded,
            'processing_time_ms': result.processing_time_ms,
        }
    }


def parse_stats_json(json_bytes):
    """Parse JSON output from C library into Python dict"""
    if not json_bytes:
        return {}
    try:
        return json.loads(json_bytes.decode('utf-8'))
    except:
        return {}
