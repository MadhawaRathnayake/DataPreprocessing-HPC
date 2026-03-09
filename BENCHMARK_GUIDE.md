# Benchmark Metrics & Comparison Guide

## Overview

The HPC Data Preprocessing application now includes comprehensive **metrics collection** and **benchmarking capabilities** to measure and compare performance across Serial, OpenMP, and MPI backends.

## Metrics Collected

Each pipeline execution automatically collects the following metrics:

### Timing Metrics

| Metric              | Unit | Description                            |
| ------------------- | ---- | -------------------------------------- |
| **Total Time**      | ms   | Complete end-to-end pipeline execution |
| **Duplicates Time** | ms   | Time to detect and remove duplicates   |
| **Missing Time**    | ms   | Time to handle missing values          |
| **Outliers Time**   | ms   | Time to detect and treat outliers      |
| **Scaling Time**    | ms   | Time to normalize/scale columns        |
| **Encoding Time**   | ms   | Time to encode categorical variables   |

### Data Metrics

| Metric                    | Unit  | Description                           |
| ------------------------- | ----- | ------------------------------------- |
| **Input Rows**            | count | Number of rows in imported CSV        |
| **Input Columns**         | count | Number of columns in imported CSV     |
| **Output Rows**           | count | Number of rows after processing       |
| **Output Columns**        | count | Number of columns after processing    |
| **Rows Removed**          | count | Total rows deleted by pipeline        |
| **Duplicates Found**      | count | Number of duplicate rows detected     |
| **Missing Values Filled** | count | Number of missing values imputed      |
| **Outliers Detected**     | count | Number of outlier values found        |
| **Columns Scaled**        | count | Number of columns normalized          |
| **Columns Encoded**       | count | Number of categorical columns encoded |

### System Metrics

| Metric                | Details                                                   |
| --------------------- | --------------------------------------------------------- |
| **CPU Cores**         | Available system cores                                    |
| **Threads (OpenMP)**  | Number of parallel threads used                           |
| **Processes (MPI)**   | Number of distributed processes used                      |
| **Speedup vs Serial** | Performance gain relative to serial execution             |
| **Efficiency**        | Percentage utilization of parallelism (speedup / threads) |

## Backend Comparison

### What Gets Compared

When you run the pipeline on multiple backends, the **Benchmark Comparison** tab shows:

1. **Performance Comparison Table**
   - Total execution time for each backend
   - Side-by-side timing in milliseconds
   - Speedup factor (e.g., 2.5x faster)

2. **Stage-by-Stage Breakdown**
   - Timing for each of the 5 preprocessing stages
   - Identify which stages benefit most from parallelization
   - Example: Outlier detection might be 3x faster on OpenMP

3. **System Configuration**
   - How many threads/processes were used
   - Efficiency calculation
   - Speedup per thread/process

4. **Performance Analysis**
   - Speedup vs Serial baseline
   - Time saved in milliseconds
   - Per-thread/per-process efficiency
   - Identifies scalability bottlenecks

## How to Use Benchmarking

### Step 1: Import Data

1. Go to **📂 Import** tab
2. Select and import your CSV file
3. Confirm data preview

### Step 2: Configure Pipeline

Configure preprocessing stages as needed (in any Pipeline tab):

- Stages 1-6: Define your transformations
- Stage 7 (Apply & Preview): Runs the pipeline and collects metrics

### Step 3: Run on Serial Backend

1. Go to **🔬 Series Processing** tab
2. Click **Run Pipeline**
3. Wait for completion (displays timing)
4. ✅ Metrics automatically collected and shown in **📊 Benchmark** tab

### Step 4: Run on OpenMP Backend

1. Go to **⚡ OpenMP Parallel** tab
2. Click **Run OpenMP Pipeline** (auto-detects threads)
3. Wait for completion
4. ✅ Compare timing with Serial

### Step 5: Run on MPI Backend

1. Go to **🌐 MPI Parallel** tab
2. Click **Run MPI Pipeline** (auto-detects processes)
3. Wait for completion
4. ✅ MPI results added to comparison

### Step 6: View Benchmark Report

1. Click **📊 Benchmark** tab
2. See comprehensive comparison table with:
   - Stage-by-stage breakdown
   - Speedup metrics
   - System configuration details
   - Performance analysis

## Sample Benchmark Report

```
==================================================
BENCHMARK COMPARISON REPORT
==================================================

BACKEND       TOTAL TIME   ROWS IN      ROWS OUT       ROWS REMOVED   SPEEDUP
SERIAL        245.3ms      1000         980            20             baseline
OPENMP        68.2ms       1000         980            20             3.60x
MPI           71.5ms       1000         980            20             3.43x

==================================================
STAGE-BY-STAGE BREAKDOWN (milliseconds)
==================================================

BACKEND       DUPLICATES   MISSING      OUTLIERS       SCALING        ENCODING
SERIAL        12.30        45.60        105.20         67.40          14.80
OPENMP        4.50         15.20        32.10          11.20          5.10
MPI           5.10         16.80        33.50          12.40          5.20

==================================================
PERFORMANCE ANALYSIS
==================================================

OpenMP vs Serial:
  Speedup: 3.60x
  Time Saved: 177.1 ms
  Per-thread Efficiency: 45.0%

MPI vs Serial:
  Speedup: 3.43x
  Time Saved: 173.8 ms
  Per-process Efficiency: 85.8%
```

## Interpreting Results

### Speedup Factors

- **1.0x** = No improvement vs baseline (serial)
- **2.0x** = 2x faster (50% less time)
- **4.0x** = 4x faster (75% less time)

### Efficiency

- **100%** = Perfect scaling (if using 4 threads, get 4x speedup)
- **50%** = Acceptable (4 threads give 2x speedup)
- **25%** = Poor scaling (4 threads give 1x speedup) — likely memory-bound

### When to Use Each Backend

| Backend    | When to Use                                      | Expected Speedup |
| ---------- | ------------------------------------------------ | ---------------- |
| **Serial** | Baselines, debugging, small datasets             | 1.0x (baseline)  |
| **OpenMP** | Medium datasets, single machine, 4-8 cores       | 2-8x (typical)   |
| **MPI**    | Large datasets, multiple machines, 10+ processes | 5-100x (typical) |

## Exporting Results

### CSV Export

- Click **💾 Export as CSV**
- Opens file dialog
- Exports detailed metrics in tabular format
- Good for: Excel analysis, reports, archival

### JSON Export

- Click **📄 Export as JSON**
- Includes all metrics and timestamps
- Good for: Programmatic analysis, long-term storage, reproducibility

## Metrics File Structure (JSON)

```json
{
  "timestamp": "2026-03-08T14:32:15.123456",
  "results": {
    "serial": {
      "backend": "serial",
      "timestamp": "...",
      "total_time": 0.245,
      "input_rows": 1000,
      "output_rows": 980,
      "duplicates_time": 0.012,
      "missing_time": 0.046,
      "outliers_time": 0.105,
      "scaling_time": 0.067,
      "encoding_time": 0.015,
      "speedup_vs_serial": 1.0,
      "efficiency": 100.0
    },
    "openmp": {
      "backend": "openmp",
      "total_time": 0.068,
      "num_threads": 4,
      "speedup_vs_serial": 3.60,
      "efficiency": 45.0,
      ...
    },
    "mpi": {
      "backend": "mpi",
      "total_time": 0.072,
      "num_processes": 4,
      "speedup_vs_serial": 3.43,
      "efficiency": 85.8,
      ...
    }
  }
}
```

## Troubleshooting Metrics

### No Metrics Showing

- ✅ Make sure you run the pipeline (click Run button)
- ✅ Check status bar for completion message
- ✅ Click **Benchmark** tab to view

### Unexpected Speedups

- If OpenMP is slower than Serial: Check system load, memory pressure
- If MPI is slower than expected: Check inter-process communication overhead
- Speedup depends on: dataset size, CPU cores available, backend implementation

### Missing Data in Export

- JSON export includes all fields (even if 0)
- CSV export shows dashes (-) for optional metrics
- Historical runs preserved in metrics_history

## Integration with UI

### Automatic Metrics Collection

Every pipeline run automatically:

1. Records input/output shapes
2. Times each preprocessing stage
3. Counts operations (duplicates, missing values, outliers, etc.)
4. Detects system configuration (threads, processes, CPU cores)
5. Calculates speedup vs serial baseline

### Real-Time Updates

- **Benchmark** tab updates instantly after each pipeline run
- No manual refresh needed
- Comparison table recalculates when new metrics arrive

### Per-Backend Configuration

- **Serial**: Runs on 1 thread
- **OpenMP**: Auto-detects CPU count, capped at 8 threads
- **MPI**: Auto-detects CPU count, capped at 4 processes

## API for Programmatic Access

### Recording Metrics

```python
from metrics import MetricsCollector

# Create collector for backend
collector = MetricsCollector(backend="openmp")

# Record system config
collector.set_system_config(num_threads=4, num_cores=8)

# Record input data
collector.set_input_shape(rows=1000, columns=10)

# Time each stage
collector.start_stage("duplicates")
# ... run stage logic ...
collector.end_stage()

# Record output
collector.set_output_shape(rows=980, columns=10)

# Get metrics object
metrics = collector.get_metrics()
```

### Comparing Results

```python
from metrics import BenchmarkComparison

# Create comparison
comparison = BenchmarkComparison()

# Add results from each backend
comparison.add_result(serial_metrics)
comparison.add_result(openmp_metrics)
comparison.add_result(mpi_metrics)

# Generate reports
print(comparison.get_comparison_table())
csv_data = comparison.to_csv()
json_data = comparison.to_json()
```

## Performance Tips

### For Better Speedups

1. **Use large datasets** (100k+ rows): Parallelization overhead diminishes
2. **Use balanced workloads**: Similar processing time across preprocessing stages
3. **Monitor system load**: Close background applications
4. **Pin processes**: Set CPU affinity for MPI on NUMA systems
5. **Tune OpenMP threads**: Try --threads 2,4,6,8 to find sweet spot

### For Baseline Measurement

- Always run Serial first to establish baseline
- Run on idle system (close browsers, editors, etc.)
- Run multiple times and average results
- Warm up the system before benchmark runs

## Examples

### Example 1: Small Dataset (100 rows)

```
Serial:    5.2 ms
OpenMP:    3.1 ms (1.7x speedup, 42% efficiency)
MPI:       4.0 ms (1.3x speedup, 65% efficiency)
```

Conclusion: Overhead dominates. Serial might be better for small data.

### Example 2: Medium Dataset (10,000 rows)

```
Serial:    245.3 ms
OpenMP:    68.2 ms (3.6x speedup, 90% efficiency)
MPI:       71.5 ms (3.4x speedup, 85% efficiency)
```

Conclusion: OpenMP and MPI both excellent. OpenMP slightly better on single machine.

### Example 3: Large Dataset (1 million rows)

```
Serial:    12,543 ms
OpenMP:    3,205 ms (3.9x speedup, 98% efficiency)
MPI:       2,340 ms (5.4x speedup, 90% efficiency across 6 nodes)
```

Conclusion: MPI shines on very large data. Excellent scalability.
