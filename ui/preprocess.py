"""
Preprocessing Pipeline Implementation
Implements the 5-stage data preprocessing pipeline using C.
No Python fallback - all transformations handled by C libraries.
"""

import json
import os
import ctypes
from ctypes import POINTER, c_char_p, c_int, byref
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path

from lib_ctypes import (
    load_preprocessor, 
    python_data_to_c, 
    c_preprocessed_data_to_python,
    OutlierConfig, ScalingConfig, EncodingConfig
)
from metrics import MetricsCollector
from logging_config import get_logger


class PreprocessingPipeline:
    """
    Main pipeline orchestrator that applies transformations using pure C code.
    Supports three backends: Serial, OpenMP (parallel), MPI (distributed).
    All transformations are performed in compiled C, bypassing Python GIL.
    """
    
    def __init__(self, backend_lib=None, backend_type="serial", num_threads=1, num_processes=1):
        """
        Parameters:
        -----------
        backend_lib : CAnalyzerLib (ignored - loads preprocessor library)
        backend_type : str
            One of: "serial", "openmp", "mpi"
        num_threads : int
            For OpenMP backend, number of threads to use
        num_processes : int
            For MPI backend, number of processes to use
        """
        self.logger = get_logger(f"PreprocessingPipeline.{backend_type}")
        self.backend_type = backend_type
        self.num_threads = num_threads
        self.num_processes = num_processes
        self.metrics = MetricsCollector(backend_type)
        self.metrics.set_system_config(
            num_threads=num_threads if backend_type == "openmp" else None,
            num_processes=num_processes if backend_type == "mpi" else None,
            num_cores=os.cpu_count()
        )
        
        # Load C preprocessing library
        lib_dir = Path(__file__).parent.parent / "lib"
        self.lib = load_preprocessor(str(lib_dir), backend_type)
        
        if not self.lib.is_loaded():
            raise RuntimeError(f"Failed to load preprocessor library for {backend_type}")
        
        self.logger.info(f"Initialized {backend_type.upper()} backend using C library (threads={num_threads}, processes={num_processes}, cores={os.cpu_count()})")
    
    def run_pipeline(self, data: List[List[str]], headers: List[str], 
                    configs: List[Dict]) -> Tuple[List[List[str]], List[str], Dict]:
        """
        Execute complete preprocessing pipeline using pure C code.
        
        Parameters:
        -----------
        data : list of lists
            Raw data (rows of strings)
        headers : list
            Column headers
        configs : list of dicts
            Configuration from each stage:
            [0] = overview (read-only)
            [1] = duplicates config
            [2] = missing config
            [3] = outliers config
            [4] = scaling config
            [5] = encoding config
        
        Returns:
        --------
        (processed_data, processed_headers, stats)
        """
        
        # Record input shape and start timer
        self.metrics.set_input_shape(len(data), len(headers))
        timer_start = self.metrics.start_timer()
        
        self.logger.info(f"Pipeline START: {len(data)} rows x {len(headers)} columns")
        self.logger.info("Debug logs available at /tmp/preprocess.log")
        
        # Convert data to ctypes format - STORE IN LOCAL VARIABLES TO KEEP ALIVE
        try:
            c_data, c_headers, num_rows, num_cols = self._prepare_c_data(data, headers)
        except Exception as e:
            self.logger.error(f"Failed to prepare C data: {e}")
            return data, headers, {'error': str(e)}
        
        # Build config structs for C library
        # configs is now a list from _collect_configs() where:
        # [0]=Overview, [1]=Duplicates, [2]=Missing, [3]=Outliers, [4]=Scaling, [5]=Encoding
        
        # Check if Duplicates stage is enabled (action != "skip")
        remove_duplicates = 0
        if configs and len(configs) > 1:
            dup_config = configs[1]
            if isinstance(dup_config, dict) and dup_config.get("action") != "skip":
                remove_duplicates = 1
        
        outlier_cfg = self._build_outlier_config(configs[3] if configs and len(configs) > 3 else None, headers)
        scaling_cfg = self._build_scaling_config(configs[4] if configs and len(configs) > 4 else None, headers)
        encoding_cfg = self._build_encoding_config(configs[5] if configs and len(configs) > 5 else None, headers)
        
        # Call appropriate C function
        # NOTE: c_data and c_headers MUST stay in scope during this call
        try:
            self.logger.debug(f"Calling C preprocessing function: preprocess_{self.backend_type}")
            
            # Convert ctypes arrays to pointers only at call time
            c_data_ptr = POINTER(c_char_p)(c_data)
            c_headers_ptr = POINTER(c_char_p)(c_headers)
            
            if self.backend_type == "serial":
                c_result = self.lib.lib.preprocess_serial(
                    c_data_ptr, c_headers_ptr, num_rows, num_cols, remove_duplicates,
                    byref(outlier_cfg) if outlier_cfg else None,
                    byref(scaling_cfg) if scaling_cfg else None,
                    byref(encoding_cfg) if encoding_cfg else None
                )
            
            elif self.backend_type == "openmp":
                c_result = self.lib.lib.preprocess_openmp(
                    c_data_ptr, c_headers_ptr, num_rows, num_cols, self.num_threads, remove_duplicates,
                    byref(outlier_cfg) if outlier_cfg else None,
                    byref(scaling_cfg) if scaling_cfg else None,
                    byref(encoding_cfg) if encoding_cfg else None
                )
            
            elif self.backend_type == "mpi":
                c_result = self.lib.lib.preprocess_mpi(
                    c_data_ptr, c_headers_ptr, num_rows, num_cols, self.num_processes, remove_duplicates,
                    byref(outlier_cfg) if outlier_cfg else None,
                    byref(scaling_cfg) if scaling_cfg else None,
                    byref(encoding_cfg) if encoding_cfg else None
                )
            
            else:
                raise ValueError(f"Unknown backend type: {self.backend_type}")
            
            # Convert result back to Python
            result_dict = c_preprocessed_data_to_python(c_result)
            
            # Free C memory
            self.lib.lib.free_preprocessed_data(c_result)
            
            if not result_dict:
                raise RuntimeError("C preprocessing returned null result")
            
            # Record metrics from C preprocessing
            metrics = result_dict['metrics']
            self.metrics.record_duplicates(metrics['duplicates_found'])
            self.metrics.record_outliers(metrics['outliers_removed'])
            self.metrics.record_scaling(metrics['columns_scaled'])
            self.metrics.record_encoding(metrics['columns_encoded'])
            
            # Record output shape and timing
            self.metrics.set_output_shape(result_dict['num_rows'], result_dict['num_cols'])
            self.metrics.end_timer(timer_start)
            
            stats = {
                'final_shape': f"{result_dict['num_rows']} rows × {result_dict['num_cols']} columns",
                'total_time': metrics['processing_time_ms'] / 1000.0,  # Convert ms to seconds
                'metrics': self.metrics.get_metrics(),
                'c_processing_time_ms': metrics['processing_time_ms']
            }
            
            self.logger.info(f"Pipeline COMPLETE: {result_dict['num_rows']} rows × {result_dict['num_cols']} columns")
            self.logger.info(f"C preprocessing time: {metrics['processing_time_ms']:.2f}ms")
            self.logger.info(f"Metrics: Duplicates={metrics['duplicates_found']}, Missing={metrics['missing_filled']}, Outliers={metrics['outliers_removed']}, Scaled={metrics['columns_scaled']}, Encoded={metrics['columns_encoded']}")
            self.logger.info("="*80)
            
            return result_dict['data'], result_dict['headers'], stats
        
        except Exception as e:
            self.logger.error(f"C preprocessing failed: {e}")
            return data, headers, {'error': str(e)}
    
    def _prepare_c_data(self, data: List[List[str]], headers: List[str]) -> Tuple:
        """Convert Python data to ctypes format (CSV-formatted strings)
        
        CRITICAL: Keep encoded strings alive by storing references in instance variables!
        Python will garbage collect the encoded bytes unless we keep them.
        """
        num_rows = len(data)
        num_cols = len(headers)
        
        # Store encoded strings to prevent garbage collection
        self._c_data_strings = []  # Keep references alive
        self._c_header_strings = []  # Keep references alive
        
        # Convert headers - MUST stay alive
        c_headers = (c_char_p * num_cols)()
        for i, h in enumerate(headers):
            encoded = h.encode('utf-8') if isinstance(h, str) else h
            self._c_header_strings.append(encoded)  # Keep reference alive
            c_headers[i] = encoded
        
        # Convert data - each row as comma-separated string
        # MUST stay alive until C function completes
        c_data = (c_char_p * num_rows)()
        for i, row in enumerate(data):
            # Join row cells with commas to create CSV string
            csv_row = ",".join(str(cell) if cell is not None else "" for cell in row)
            encoded = csv_row.encode('utf-8')
            self._c_data_strings.append(encoded)  # Keep reference alive
            c_data[i] = encoded
        
        # Return the arrays directly (not as pointers) so they stay alive
        return c_data, c_headers, num_rows, num_cols
    
    def _build_outlier_config(self, config: Optional[Dict], headers: List[str]) -> Optional[OutlierConfig]:
        """Build C outlier config struct from Python dict"""
        if not config:
            return None
        
        outlier_cfg = OutlierConfig()
        
        # Method: 0=IQR, 1=Z-score
        method_str = config.get('method', 'iqr').lower()
        outlier_cfg.method = 0 if method_str == 'iqr' else 1
        
        # Treatment: 0=remove, 1=cap, 2=flag
        treatment_str = config.get('treatment', 'remove').lower()
        outlier_cfg.treatment = {'remove': 0, 'cap': 1, 'flag': 2}.get(treatment_str, 0)
        
        # Threshold
        outlier_cfg.threshold = config.get('threshold', 1.5)
        
        # Columns to process
        columns = config.get('columns', headers)
        outlier_cfg.num_columns = len(columns)
        outlier_cfg.columns = (c_char_p * len(columns))()
        for i, col in enumerate(columns):
            outlier_cfg.columns[i] = col.encode('utf-8') if isinstance(col, str) else col
        
        return outlier_cfg
    
    def _build_scaling_config(self, config: Optional[Dict], headers: List[str]) -> Optional[ScalingConfig]:
        """Build C scaling config struct from Python dict"""
        if not config:
            return None
        
        scaling_cfg = ScalingConfig()
        
        # Method: 0=min-max, 1=z-score, 2=standard
        method_str = config.get('method', 'minmax').lower()
        scaling_cfg.method = {'minmax': 0, 'zscore': 1, 'standard': 2}.get(method_str, 0)
        
        # Columns to scale
        columns = config.get('columns', headers)
        scaling_cfg.num_columns = len(columns)
        scaling_cfg.columns = (c_char_p * len(columns))()
        for i, col in enumerate(columns):
            scaling_cfg.columns[i] = col.encode('utf-8') if isinstance(col, str) else col
        
        return scaling_cfg
    
    def _build_encoding_config(self, config: Optional[Dict], headers: List[str]) -> Optional[EncodingConfig]:
        """Build C encoding config struct from Python dict"""
        if not config:
            return None
        
        encoding_cfg = EncodingConfig()
        
        # Method: 0=label, 1=onehot
        method_str = config.get('method', 'label').lower()
        encoding_cfg.method = 0 if method_str == 'label' else 1
        
        # Columns to encode
        columns = config.get('columns', [])
        if not columns:
            columns = config.get('column_methods', {}).keys() if isinstance(config.get('column_methods'), dict) else []
        
        encoding_cfg.num_columns = len(columns)
        encoding_cfg.columns = (c_char_p * len(columns))()
        for i, col in enumerate(columns):
            encoding_cfg.columns[i] = col.encode('utf-8') if isinstance(col, str) else col
        
        return encoding_cfg
