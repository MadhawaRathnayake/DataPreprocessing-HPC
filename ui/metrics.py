"""
Metrics Collection and Benchmarking System
Tracks performance metrics for Serial, OpenMP, and MPI backends
"""

import time
import json
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class PipelineMetrics:
    """Performance metrics for a single pipeline execution"""
    
    # Identification
    backend: str  # "serial", "openmp", "mpi"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Input data
    input_rows: int = 0
    input_columns: int = 0
    
    # Output data
    output_rows: int = 0
    output_columns: int = 0
    
    # Processing timing (all in seconds)
    total_time: float = 0.0
    duplicates_time: float = 0.0
    missing_time: float = 0.0
    outliers_time: float = 0.0
    scaling_time: float = 0.0
    encoding_time: float = 0.0
    
    # System configuration
    num_threads: Optional[int] = None  # For OpenMP
    num_processes: Optional[int] = None  # For MPI
    num_cores: Optional[int] = None  # CPU count
    
    # Memory usage (in MB)
    memory_mb: float = 0.0
    
    # Operations counts
    rows_removed: int = 0
    duplicates_found: int = 0
    missing_values_filled: int = 0
    outliers_detected: int = 0
    columns_scaled: int = 0
    columns_encoded: int = 0
    
    # Estimated speedup metrics
    speedup_vs_serial: float = 1.0
    efficiency: float = 100.0  # threads/processes utilization
    
    def __post_init__(self):
        """Calculate derived metrics"""
        self.rows_removed = self.input_rows - self.output_rows
        
    def get_stage_times(self) -> Dict[str, float]:
        """Return timing for each stage"""
        return {
            "duplicates": self.duplicates_time,
            "missing": self.missing_time,
            "outliers": self.outliers_time,
            "scaling": self.scaling_time,
            "encoding": self.encoding_time,
        }
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


class MetricsCollector:
    """Collects metrics for pipeline execution"""
    
    def __init__(self, backend: str):
        self.backend = backend
        self.metrics = PipelineMetrics(backend=backend)
        self.stage_timers: Dict[str, float] = {}
        self.current_stage: Optional[str] = None
        self.stage_start_time: float = 0.0
        
    def set_input_shape(self, rows: int, columns: int):
        """Record input data dimensions"""
        self.metrics.input_rows = rows
        self.metrics.input_columns = columns
        
    def set_output_shape(self, rows: int, columns: int):
        """Record output data dimensions"""
        self.metrics.output_rows = rows
        self.metrics.output_columns = columns
        
    def set_system_config(self, num_threads: Optional[int] = None, 
                         num_processes: Optional[int] = None, 
                         num_cores: Optional[int] = None):
        """Record system configuration"""
        self.metrics.num_threads = num_threads
        self.metrics.num_processes = num_processes
        self.metrics.num_cores = num_cores
        
    def start_stage(self, stage_name: str):
        """Start timing a processing stage"""
        self.current_stage = stage_name
        self.stage_start_time = time.perf_counter()
        
    def end_stage(self) -> float:
        """End timing a processing stage, return elapsed time"""
        if not self.current_stage:
            return 0.0
        
        elapsed = time.perf_counter() - self.stage_start_time
        self.stage_timers[self.current_stage] = elapsed
        
        # Update metrics based on stage
        if self.current_stage == "duplicates":
            self.metrics.duplicates_time = elapsed
        elif self.current_stage == "missing":
            self.metrics.missing_time = elapsed
        elif self.current_stage == "outliers":
            self.metrics.outliers_time = elapsed
        elif self.current_stage == "scaling":
            self.metrics.scaling_time = elapsed
        elif self.current_stage == "encoding":
            self.metrics.encoding_time = elapsed
        
        self.current_stage = None
        return elapsed
    
    def start_timer(self) -> float:
        """Start overall pipeline timer"""
        return time.perf_counter()
    
    def end_timer(self, start_time: float) -> float:
        """End overall pipeline timer"""
        total = time.perf_counter() - start_time
        self.metrics.total_time = total
        return total
    
    def record_duplicates(self, found: int):
        """Record duplicates statistics"""
        self.metrics.duplicates_found = found
    
    def record_missing(self, filled: int):
        """Record missing values statistics"""
        self.metrics.missing_values_filled = filled
    
    def record_outliers(self, detected: int):
        """Record outliers statistics"""
        self.metrics.outliers_detected = detected
    
    def record_scaling(self, columns: int):
        """Record scaling statistics"""
        self.metrics.columns_scaled = columns
    
    def record_encoding(self, columns: int):
        """Record encoding statistics"""
        self.metrics.columns_encoded = columns
    
    def get_metrics(self) -> PipelineMetrics:
        """Get collected metrics"""
        return self.metrics


class BenchmarkComparison:
    """Compares metrics across multiple backends"""
    
    def __init__(self):
        self.results: Dict[str, PipelineMetrics] = {}
        
    def add_result(self, metrics: PipelineMetrics):
        """Add metrics result for a backend"""
        self.results[metrics.backend] = metrics
        self._calculate_speedups()
    
    def _calculate_speedups(self):
        """Calculate speedup relative to serial backend"""
        if "serial" not in self.results:
            return
        
        serial_time = self.results["serial"].total_time
        
        for backend, metrics in self.results.items():
            if backend != "serial" and serial_time > 0:
                metrics.speedup_vs_serial = serial_time / metrics.total_time
                
                # Calculate efficiency
                if metrics.num_threads:
                    metrics.efficiency = (metrics.speedup_vs_serial / metrics.num_threads) * 100
                elif metrics.num_processes:
                    metrics.efficiency = (metrics.speedup_vs_serial / metrics.num_processes) * 100
    
    def get_comparison_table(self) -> str:
        """Generate text comparison table"""
        if not self.results:
            return "No results to compare"
        
        lines = []
        lines.append("\n" + "=" * 120)
        lines.append("BENCHMARK COMPARISON REPORT")
        lines.append("=" * 120)
        
        # Summary table
        lines.append("\n{:<12} {:<12} {:<12} {:<15} {:<12} {:<12}".format(
            "BACKEND", "TOTAL TIME", "ROWS IN", "ROWS OUT", "ROWS REMOVED", "SPEEDUP"))
        lines.append("-" * 120)
        
        for backend in ["serial", "openmp", "mpi"]:
            if backend not in self.results:
                continue
            
            m = self.results[backend]
            time_str = f"{m.total_time*1000:.1f}ms"
            speedup_str = f"{m.speedup_vs_serial:.2f}x" if backend != "serial" else "baseline"
            
            lines.append("{:<12} {:<12} {:<12} {:<15} {:<12} {:<12}".format(
                backend.upper(),
                time_str,
                str(m.input_rows),
                str(m.output_rows),
                str(m.rows_removed),
                speedup_str
            ))
        
        # Stage-by-stage breakdown
        lines.append("\n" + "=" * 120)
        lines.append("STAGE-BY-STAGE BREAKDOWN (milliseconds)")
        lines.append("=" * 120)
        lines.append("\n{:<12} {:<12} {:<12} {:<12} {:<12} {:<12}".format(
            "BACKEND", "DUPLICATES", "MISSING", "OUTLIERS", "SCALING", "ENCODING"))
        lines.append("-" * 120)
        
        for backend in ["serial", "openmp", "mpi"]:
            if backend not in self.results:
                continue
            
            m = self.results[backend]
            lines.append("{:<12} {:<12.2f} {:<12.2f} {:<12.2f} {:<12.2f} {:<12.2f}".format(
                backend.upper(),
                m.duplicates_time * 1000,
                m.missing_time * 1000,
                m.outliers_time * 1000,
                m.scaling_time * 1000,
                m.encoding_time * 1000
            ))
        
        # Configuration details
        lines.append("\n" + "=" * 120)
        lines.append("SYSTEM CONFIGURATION")
        lines.append("=" * 120)
        
        for backend in ["serial", "openmp", "mpi"]:
            if backend not in self.results:
                continue
            
            m = self.results[backend]
            lines.append(f"\n{backend.upper()}:")
            if m.num_threads:
                lines.append(f"  Threads: {m.num_threads}")
            if m.num_processes:
                lines.append(f"  Processes: {m.num_processes}")
            if m.num_cores:
                lines.append(f"  CPU Cores: {m.num_cores}")
            lines.append(f"  Efficiency: {m.efficiency:.1f}%")
        
        # Performance Analysis
        lines.append("\n" + "=" * 120)
        lines.append("PERFORMANCE ANALYSIS")
        lines.append("=" * 120)
        
        if "serial" in self.results and "openmp" in self.results:
            serial = self.results["serial"]
            omp = self.results["openmp"]
            speedup = omp.speedup_vs_serial
            lines.append(f"\nOpenMP vs Serial:")
            lines.append(f"  Speedup: {speedup:.2f}x")
            lines.append(f"  Time Saved: {(serial.total_time - omp.total_time)*1000:.1f} ms")
            if omp.num_threads:
                lines.append(f"  Per-thread Efficiency: {(speedup / omp.num_threads * 100):.1f}%")
        
        if "serial" in self.results and "mpi" in self.results:
            serial = self.results["serial"]
            mpi = self.results["mpi"]
            speedup = mpi.speedup_vs_serial
            lines.append(f"\nMPI vs Serial:")
            lines.append(f"  Speedup: {speedup:.2f}x")
            lines.append(f"  Time Saved: {(serial.total_time - mpi.total_time)*1000:.1f} ms")
            if mpi.num_processes:
                lines.append(f"  Per-process Efficiency: {(speedup / mpi.num_processes * 100):.1f}%")
        
        lines.append("\n" + "=" * 120 + "\n")
        return "\n".join(lines)
    
    def to_json(self) -> str:
        """Export comparison as JSON"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "results": {backend: metrics.to_dict() for backend, metrics in self.results.items()}
        }
        return json.dumps(data, indent=2)
    
    def to_csv(self) -> str:
        """Export comparison as CSV"""
        lines = []
        
        # Header
        headers = ["Backend", "Total Time (ms)", "Input Rows", "Output Rows", "Rows Removed",
                   "Duplicates", "Missing Filled", "Outliers", "Columns Scaled", "Columns Encoded",
                   "Threads/Processes", "Speedup vs Serial", "Efficiency %"]
        lines.append(",".join(headers))
        
        # Data rows
        for backend in ["serial", "openmp", "mpi"]:
            if backend not in self.results:
                continue
            
            m = self.results[backend]
            threads = m.num_threads or m.num_processes or "-"
            speedup = f"{m.speedup_vs_serial:.2f}x"
            
            row = [
                backend,
                f"{m.total_time*1000:.1f}",
                str(m.input_rows),
                str(m.output_rows),
                str(m.rows_removed),
                str(m.duplicates_found),
                str(m.missing_values_filled),
                str(m.outliers_detected),
                str(m.columns_scaled),
                str(m.columns_encoded),
                str(threads),
                speedup,
                f"{m.efficiency:.1f}%"
            ]
            lines.append(",".join(row))
        
        return "\n".join(lines)
