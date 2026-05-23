#include <cuda_runtime.h>

#include "cuda_preprocessor.h"

/*
 * Hybrid CUDA + CPU-threaded preprocessing backend.
 * Defining CUDA_HYBRID_LIBRARY builds the app-facing shared library without
 * the standalone CLI entrypoint.
 */

#include <algorithm>
#include <cfloat>
#include <cmath>
#include <cctype>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

#define THREADS_PER_BLOCK 256

struct NumericStats {
    double min_value = 0.0;
    double max_value = 0.0;
    double mean = 0.0;
    double stddev = 0.0;
    int valid_count = 0;
};

static double g_last_cuda_work_time_ms = 0.0;

static void set_cpu_threads(int num_threads) {
#ifdef _OPENMP
    if (num_threads > 0) omp_set_num_threads(num_threads);
#else
    (void)num_threads;
#endif
}

static int get_cpu_threads() {
#ifdef _OPENMP
    return omp_get_max_threads();
#else
    return 1;
#endif
}

static void check_cuda(cudaError_t status, const char *what) {
    if (status != cudaSuccess) {
        fprintf(stderr, "CUDA error during %s: %s\n", what, cudaGetErrorString(status));
        exit(1);
    }
}

static char *dup_cstr(const std::string &s) {
    char *out = (char*)malloc(s.size() + 1);
    if (!out) return NULL;
    memcpy(out, s.c_str(), s.size() + 1);
    return out;
}

static bool is_missing(const std::string &v) {
    if (v.empty()) return true;
    std::string lower;
    lower.reserve(v.size());
    for (char c : v) lower.push_back((char)tolower((unsigned char)c));
    return lower == "na" || lower == "n/a" || lower == "nan" || lower == "null";
}

static bool parse_double(const std::string &v, double &out) {
    if (is_missing(v)) return false;
    char *end = NULL;
    out = strtod(v.c_str(), &end);
    while (end && *end && isspace((unsigned char)*end)) end++;
    return end && *end == '\0';
}

static std::string format_double(double v) {
    char buf[64];
    snprintf(buf, sizeof(buf), "%.6f", v);
    return std::string(buf);
}

static std::vector<std::string> split_simple_csv(const char *row) {
    std::vector<std::string> cells;
    std::string cell;
    bool in_quotes = false;

    if (!row) {
        cells.push_back("");
        return cells;
    }

    for (const char *p = row; *p; ++p) {
        char c = *p;
        if (c == '"') {
            in_quotes = !in_quotes;
        } else if (c == ',' && !in_quotes) {
            cells.push_back(cell);
            cell.clear();
        } else {
            cell.push_back(c);
        }
    }
    cells.push_back(cell);
    return cells;
}

static std::string join_simple_csv(const std::vector<std::string> &row) {
    std::ostringstream oss;
    for (size_t i = 0; i < row.size(); i++) {
        if (i) oss << ",";
        oss << row[i];
    }
    return oss.str();
}

static bool config_selects_column(int col, const std::vector<std::string> &headers, char **columns, int num_columns) {
    if (!columns || num_columns <= 0) return true;
    for (int i = 0; i < num_columns; i++) {
        if (columns[i] && headers[col] == columns[i]) return true;
    }
    return false;
}

static bool is_numeric_column(const std::vector<std::vector<std::string>> &rows, int col) {
    int numeric_seen = 0;
    int text_seen = 0;
    for (const auto &row : rows) {
        double v = 0.0;
        if (col >= (int)row.size()) continue;
        if (parse_double(row[col], v)) numeric_seen++;
        else if (!is_missing(row[col])) text_seen++;
    }
    return numeric_seen > 0 && text_seen == 0;
}

static std::vector<double> collect_numeric_values(const std::vector<std::vector<std::string>> &rows, int col) {
    std::vector<double> values;
    values.reserve(rows.size());
    for (const auto &row : rows) {
        double v = 0.0;
        if (col < (int)row.size() && parse_double(row[col], v)) values.push_back(v);
    }
    return values;
}

static double percentile_sorted(const std::vector<double> &sorted, double p) {
    if (sorted.empty()) return 0.0;
    double pos = p * (sorted.size() - 1);
    size_t lo = (size_t)floor(pos);
    size_t hi = (size_t)ceil(pos);
    if (lo == hi) return sorted[lo];
    double frac = pos - lo;
    return sorted[lo] * (1.0 - frac) + sorted[hi] * frac;
}

static int remove_duplicates_exact(std::vector<std::vector<std::string>> &rows) {
    std::unordered_set<std::string> seen;
    std::vector<std::vector<std::string>> unique_rows;
    unique_rows.reserve(rows.size());
    int duplicates = 0;

    for (const auto &row : rows) {
        std::string key = join_simple_csv(row);
        if (seen.insert(key).second) {
            unique_rows.push_back(row);
        } else {
            duplicates++;
        }
    }

    rows.swap(unique_rows);
    return duplicates;
}

static int fill_missing_values(std::vector<std::vector<std::string>> &rows, int num_cols) {
    int filled = 0;

    for (auto &row : rows) {
        if ((int)row.size() < num_cols) row.resize(num_cols);
    }

    #pragma omp parallel for reduction(+:filled) schedule(dynamic)
    for (int col = 0; col < num_cols; col++) {
        bool numeric = is_numeric_column(rows, col);
        std::string replacement = "";

        if (numeric) {
            double sum = 0.0;
            int count = 0;
            for (const auto &row : rows) {
                double v = 0.0;
                if (col < (int)row.size() && parse_double(row[col], v)) {
                    sum += v;
                    count++;
                }
            }
            replacement = count > 0 ? format_double(sum / count) : "0";
        } else {
            std::unordered_map<std::string, int> counts;
            for (const auto &row : rows) {
                if (col < (int)row.size() && !is_missing(row[col])) counts[row[col]]++;
            }
            int best_count = -1;
            for (const auto &kv : counts) {
                if (kv.second > best_count) {
                    replacement = kv.first;
                    best_count = kv.second;
                }
            }
            if (replacement.empty()) replacement = "UNKNOWN";
        }

        for (int r = 0; r < (int)rows.size(); r++) {
            auto &row = rows[r];
            if (is_missing(row[col])) {
                row[col] = replacement;
                filled++;
            }
        }
    }
    return filled;
}

static int apply_outliers(
    std::vector<std::vector<std::string>> &rows,
    std::vector<std::string> &headers,
    OutlierConfig *cfg
) {
    if (!cfg || !cfg->columns || cfg->num_columns <= 0 || rows.empty()) return 0;

    int outlier_events = 0;
    std::vector<int> row_remove(rows.size(), 0);
    std::vector<std::vector<int>> flag_values;
    std::vector<std::string> flag_headers;

    for (int col = 0; col < (int)headers.size(); col++) {
        if (!config_selects_column(col, headers, cfg->columns, cfg->num_columns)) continue;
        if (!is_numeric_column(rows, col)) continue;

        std::vector<double> values = collect_numeric_values(rows, col);
        if (values.size() < 4) continue;

        double lower = 0.0;
        double upper = 0.0;
        if (cfg->method == 1) {
            double sum = 0.0;
            for (double v : values) sum += v;
            double mean = sum / values.size();
            double var = 0.0;
            for (double v : values) var += (v - mean) * (v - mean);
            double stddev = sqrt(var / values.size());
            double threshold = cfg->threshold > 0 ? cfg->threshold : 3.0;
            lower = mean - threshold * stddev;
            upper = mean + threshold * stddev;
        } else {
            std::sort(values.begin(), values.end());
            double q1 = percentile_sorted(values, 0.25);
            double q3 = percentile_sorted(values, 0.75);
            double iqr = q3 - q1;
            double threshold = cfg->threshold > 0 ? cfg->threshold : 1.5;
            lower = q1 - threshold * iqr;
            upper = q3 + threshold * iqr;
        }

        std::vector<int> col_flags(rows.size(), 0);
        int col_had_flags = 0;
        for (int r = 0; r < (int)rows.size(); r++) {
            double v = 0.0;
            if (!parse_double(rows[r][col], v)) continue;
            if (v < lower || v > upper) {
                outlier_events++;
                col_had_flags = 1;
                col_flags[r] = 1;
                if (cfg->treatment == 0) {
                    row_remove[r] = 1;
                } else if (cfg->treatment == 1) {
                    rows[r][col] = format_double(std::min(std::max(v, lower), upper));
                }
            }
        }

        if (cfg->treatment == 2 && col_had_flags) {
            flag_headers.push_back(headers[col] + "_outlier");
            flag_values.push_back(std::move(col_flags));
        }
    }

    if (cfg->treatment == 0) {
        std::vector<std::vector<std::string>> kept;
        kept.reserve(rows.size());
        for (int r = 0; r < (int)rows.size(); r++) {
            if (!row_remove[r]) kept.push_back(std::move(rows[r]));
        }
        rows.swap(kept);
    } else if (cfg->treatment == 2) {
        for (const auto &h : flag_headers) headers.push_back(h);
        for (int r = 0; r < (int)rows.size(); r++) {
            for (const auto &flags : flag_values) {
                rows[r].push_back(flags[r] ? "1" : "0");
            }
        }
    }

    return outlier_events;
}

static int label_encode_columns(
    std::vector<std::vector<std::string>> &rows,
    const std::vector<std::string> &headers,
    EncodingConfig *cfg
) {
    if (!cfg || !cfg->columns || cfg->num_columns <= 0) return 0;
    int encoded = 0;

    for (int col = 0; col < (int)headers.size(); col++) {
        if (!config_selects_column(col, headers, cfg->columns, cfg->num_columns)) continue;
        std::unordered_map<std::string, int> mapping;
        int next_id = 0;
        for (auto &row : rows) {
            if (col >= (int)row.size()) continue;
            std::string value = row[col];
            auto it = mapping.find(value);
            if (it == mapping.end()) {
                mapping[value] = next_id;
                row[col] = std::to_string(next_id);
                next_id++;
            } else {
                row[col] = std::to_string(it->second);
            }
        }
        encoded++;
    }
    return encoded;
}

static int one_hot_encode_columns(
    std::vector<std::vector<std::string>> &rows,
    std::vector<std::string> &headers,
    EncodingConfig *cfg
) {
    if (!cfg || !cfg->columns || cfg->num_columns <= 0) return 0;
    int encoded = 0;
    int original_cols = (int)headers.size();

    for (int col = 0; col < original_cols; col++) {
        if (!config_selects_column(col, headers, cfg->columns, cfg->num_columns)) continue;

        std::vector<std::string> uniques;
        std::unordered_set<std::string> seen;
        for (const auto &row : rows) {
            if (col >= (int)row.size()) continue;
            if (seen.insert(row[col]).second) uniques.push_back(row[col]);
        }

        for (const auto &value : uniques) headers.push_back(headers[col] + "_" + value);
        for (auto &row : rows) {
            std::string current = col < (int)row.size() ? row[col] : "";
            for (const auto &value : uniques) row.push_back(current == value ? "1" : "0");
        }
        encoded++;
    }
    return encoded;
}

__global__ void partial_stats_kernel(
    const double *values,
    int rows,
    int cols,
    int blocks_per_col,
    double *partial_mins,
    double *partial_maxs,
    double *partial_sums,
    double *partial_sumsq,
    int *partial_valids
) {
    int col = blockIdx.x / blocks_per_col;
    int segment = blockIdx.x % blocks_per_col;
    int tid = threadIdx.x;

    __shared__ double s_min[THREADS_PER_BLOCK];
    __shared__ double s_max[THREADS_PER_BLOCK];
    __shared__ double s_sum[THREADS_PER_BLOCK];
    __shared__ double s_sumsq[THREADS_PER_BLOCK];
    __shared__ int s_valid[THREADS_PER_BLOCK];

    double local_min = DBL_MAX;
    double local_max = -DBL_MAX;
    double local_sum = 0.0;
    double local_sumsq = 0.0;
    int local_valid = 0;

    for (int row = segment * blockDim.x + tid; row < rows; row += blockDim.x * blocks_per_col) {
        double value = values[(size_t)col * rows + row];
        if (!isnan(value)) {
            local_min = fmin(local_min, value);
            local_max = fmax(local_max, value);
            local_sum += value;
            local_sumsq += value * value;
            local_valid++;
        }
    }

    s_min[tid] = local_min;
    s_max[tid] = local_max;
    s_sum[tid] = local_sum;
    s_sumsq[tid] = local_sumsq;
    s_valid[tid] = local_valid;
    __syncthreads();

    for (int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            s_min[tid] = fmin(s_min[tid], s_min[tid + stride]);
            s_max[tid] = fmax(s_max[tid], s_max[tid + stride]);
            s_sum[tid] += s_sum[tid + stride];
            s_sumsq[tid] += s_sumsq[tid + stride];
            s_valid[tid] += s_valid[tid + stride];
        }
        __syncthreads();
    }

    if (tid == 0) {
        int out = col * blocks_per_col + segment;
        partial_mins[out] = s_min[0];
        partial_maxs[out] = s_max[0];
        partial_sums[out] = s_sum[0];
        partial_sumsq[out] = s_sumsq[0];
        partial_valids[out] = s_valid[0];
    }
}

__global__ void final_stats_kernel(
    int cols,
    int blocks_per_col,
    const double *partial_mins,
    const double *partial_maxs,
    const double *partial_sums,
    const double *partial_sumsq,
    const int *partial_valids,
    double *mins,
    double *maxs,
    double *means,
    double *stddevs,
    int *valids
) {
    int col = blockIdx.x;
    int tid = threadIdx.x;

    __shared__ double s_min[THREADS_PER_BLOCK];
    __shared__ double s_max[THREADS_PER_BLOCK];
    __shared__ double s_sum[THREADS_PER_BLOCK];
    __shared__ double s_sumsq[THREADS_PER_BLOCK];
    __shared__ int s_valid[THREADS_PER_BLOCK];

    double local_min = DBL_MAX;
    double local_max = -DBL_MAX;
    double local_sum = 0.0;
    double local_sumsq = 0.0;
    int local_valid = 0;

    for (int i = tid; i < blocks_per_col; i += blockDim.x) {
        int idx = col * blocks_per_col + i;
        local_min = fmin(local_min, partial_mins[idx]);
        local_max = fmax(local_max, partial_maxs[idx]);
        local_sum += partial_sums[idx];
        local_sumsq += partial_sumsq[idx];
        local_valid += partial_valids[idx];
    }

    s_min[tid] = local_min;
    s_max[tid] = local_max;
    s_sum[tid] = local_sum;
    s_sumsq[tid] = local_sumsq;
    s_valid[tid] = local_valid;
    __syncthreads();

    for (int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            s_min[tid] = fmin(s_min[tid], s_min[tid + stride]);
            s_max[tid] = fmax(s_max[tid], s_max[tid + stride]);
            s_sum[tid] += s_sum[tid + stride];
            s_sumsq[tid] += s_sumsq[tid + stride];
            s_valid[tid] += s_valid[tid + stride];
        }
        __syncthreads();
    }

    if (tid == 0) {
        double mean = s_valid[0] > 0 ? s_sum[0] / s_valid[0] : 0.0;
        double variance = s_valid[0] > 0 ? (s_sumsq[0] / s_valid[0]) - (mean * mean) : 0.0;
        mins[col] = s_min[0];
        maxs[col] = s_max[0];
        means[col] = mean;
        stddevs[col] = sqrt(fmax(variance, 0.0));
        valids[col] = s_valid[0];
    }
}

__global__ void scale_kernel(
    double *values,
    int rows,
    int cols,
    const double *mins,
    const double *maxs,
    const double *means,
    const double *stddevs,
    int method
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int total = rows * cols;
    if (idx >= total) return;

    int col = idx / rows;
    double value = values[idx];
    if (isnan(value)) return;

    if (method == 1) {
        double stddev = stddevs[col];
        if (stddev > 0.0) values[idx] = (value - means[col]) / stddev;
    } else {
        double range = maxs[col] - mins[col];
        if (range > 0.0) values[idx] = (value - mins[col]) / range;
    }
}

static int apply_gpu_scaling(
    std::vector<std::vector<std::string>> &rows,
    const std::vector<std::string> &headers,
    ScalingConfig *cfg
) {
    g_last_cuda_work_time_ms = 0.0;
    if (!cfg || rows.empty()) return 0;

    std::vector<int> numeric_cols;
    std::vector<int> numeric_flags(headers.size(), 0);
    #pragma omp parallel for schedule(dynamic)
    for (int c = 0; c < (int)headers.size(); c++) {
        if (config_selects_column(c, headers, cfg->columns, cfg->num_columns) && is_numeric_column(rows, c)) {
            numeric_flags[c] = 1;
        }
    }
    for (int c = 0; c < (int)headers.size(); c++) {
        if (numeric_flags[c]) numeric_cols.push_back(c);
    }
    if (numeric_cols.empty()) return 0;

    int rows_count = (int)rows.size();
    int gpu_cols = (int)numeric_cols.size();

    if (cfg->method == 2) {
        #pragma omp parallel for schedule(dynamic)
        for (int gc = 0; gc < gpu_cols; gc++) {
            int col = numeric_cols[gc];
            std::vector<double> values = collect_numeric_values(rows, col);
            if (values.size() < 4) continue;
            std::sort(values.begin(), values.end());
            double median = percentile_sorted(values, 0.5);
            double q1 = percentile_sorted(values, 0.25);
            double q3 = percentile_sorted(values, 0.75);
            double iqr = q3 - q1;
            if (iqr == 0.0) continue;
            for (auto &row : rows) {
                double v = 0.0;
                if (parse_double(row[col], v)) row[col] = format_double((v - median) / iqr);
            }
        }
        return gpu_cols;
    }

    std::vector<double> matrix((size_t)rows_count * gpu_cols, NAN);
    #pragma omp parallel for schedule(dynamic)
    for (int gc = 0; gc < gpu_cols; gc++) {
        int col = numeric_cols[gc];
        for (int r = 0; r < rows_count; r++) {
            double v = 0.0;
            if (parse_double(rows[r][col], v)) matrix[(size_t)gc * rows_count + r] = v;
        }
    }

    int blocks_per_col = std::min(1024, std::max(1, (rows_count + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK));
    int partial_count = gpu_cols * blocks_per_col;
    int total_values = rows_count * gpu_cols;

    double *d_values = NULL, *d_partial_mins = NULL, *d_partial_maxs = NULL, *d_partial_sums = NULL, *d_partial_sumsq = NULL;
    double *d_mins = NULL, *d_maxs = NULL, *d_means = NULL, *d_stddevs = NULL;
    int *d_partial_valids = NULL, *d_valids = NULL;

    check_cuda(cudaMalloc(&d_values, matrix.size() * sizeof(double)), "alloc values");
    check_cuda(cudaMalloc(&d_partial_mins, partial_count * sizeof(double)), "alloc partial mins");
    check_cuda(cudaMalloc(&d_partial_maxs, partial_count * sizeof(double)), "alloc partial maxs");
    check_cuda(cudaMalloc(&d_partial_sums, partial_count * sizeof(double)), "alloc partial sums");
    check_cuda(cudaMalloc(&d_partial_sumsq, partial_count * sizeof(double)), "alloc partial sumsq");
    check_cuda(cudaMalloc(&d_partial_valids, partial_count * sizeof(int)), "alloc partial valids");
    check_cuda(cudaMalloc(&d_mins, gpu_cols * sizeof(double)), "alloc mins");
    check_cuda(cudaMalloc(&d_maxs, gpu_cols * sizeof(double)), "alloc maxs");
    check_cuda(cudaMalloc(&d_means, gpu_cols * sizeof(double)), "alloc means");
    check_cuda(cudaMalloc(&d_stddevs, gpu_cols * sizeof(double)), "alloc stddevs");
    check_cuda(cudaMalloc(&d_valids, gpu_cols * sizeof(int)), "alloc valids");

    cudaEvent_t cuda_start, cuda_stop;
    check_cuda(cudaEventCreate(&cuda_start), "create hybrid cuda start event");
    check_cuda(cudaEventCreate(&cuda_stop), "create hybrid cuda stop event");
    check_cuda(cudaEventRecord(cuda_start), "record hybrid cuda start event");

    check_cuda(cudaMemcpy(d_values, matrix.data(), matrix.size() * sizeof(double), cudaMemcpyHostToDevice), "copy values");

    partial_stats_kernel<<<gpu_cols * blocks_per_col, THREADS_PER_BLOCK>>>(
        d_values, rows_count, gpu_cols, blocks_per_col,
        d_partial_mins, d_partial_maxs, d_partial_sums, d_partial_sumsq, d_partial_valids
    );
    check_cuda(cudaGetLastError(), "partial stats kernel");

    final_stats_kernel<<<gpu_cols, THREADS_PER_BLOCK>>>(
        gpu_cols, blocks_per_col,
        d_partial_mins, d_partial_maxs, d_partial_sums, d_partial_sumsq, d_partial_valids,
        d_mins, d_maxs, d_means, d_stddevs, d_valids
    );
    check_cuda(cudaGetLastError(), "final stats kernel");

    int scale_blocks = (total_values + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
    scale_kernel<<<scale_blocks, THREADS_PER_BLOCK>>>(
        d_values, rows_count, gpu_cols, d_mins, d_maxs, d_means, d_stddevs, cfg->method
    );
    check_cuda(cudaGetLastError(), "scale kernel");

    check_cuda(cudaMemcpy(matrix.data(), d_values, matrix.size() * sizeof(double), cudaMemcpyDeviceToHost), "copy scaled values");

    check_cuda(cudaEventRecord(cuda_stop), "record hybrid cuda stop event");
    check_cuda(cudaEventSynchronize(cuda_stop), "sync hybrid cuda stop event");
    float cuda_ms = 0.0f;
    check_cuda(cudaEventElapsedTime(&cuda_ms, cuda_start, cuda_stop), "elapsed hybrid cuda work");
    g_last_cuda_work_time_ms = cuda_ms;
    cudaEventDestroy(cuda_start);
    cudaEventDestroy(cuda_stop);

    #pragma omp parallel for schedule(dynamic)
    for (int gc = 0; gc < gpu_cols; gc++) {
        int col = numeric_cols[gc];
        for (int r = 0; r < rows_count; r++) {
            double v = matrix[(size_t)gc * rows_count + r];
            if (!isnan(v)) rows[r][col] = format_double(v);
        }
    }

    cudaFree(d_values);
    cudaFree(d_partial_mins);
    cudaFree(d_partial_maxs);
    cudaFree(d_partial_sums);
    cudaFree(d_partial_sumsq);
    cudaFree(d_partial_valids);
    cudaFree(d_mins);
    cudaFree(d_maxs);
    cudaFree(d_means);
    cudaFree(d_stddevs);
    cudaFree(d_valids);

    return gpu_cols;
}

extern "C" PreprocessedData* preprocess_cuda_hybrid_standalone(
    char **raw_data,
    char **headers,
    int num_rows,
    int num_cols,
    int should_remove_duplicates,
    OutlierConfig *outlier_cfg,
    ScalingConfig *scaling_cfg,
    EncodingConfig *encoding_cfg,
    int num_cpu_threads
) {
    set_cpu_threads(num_cpu_threads);
    auto start = std::chrono::high_resolution_clock::now();

    PreprocessedData *result = (PreprocessedData*)calloc(1, sizeof(PreprocessedData));
    if (!result) return NULL;

    std::vector<std::string> header_vec;
    header_vec.reserve(num_cols);
    for (int c = 0; c < num_cols; c++) header_vec.push_back(headers[c] ? headers[c] : "");

    std::vector<std::vector<std::string>> rows(num_rows);
    #pragma omp parallel for schedule(static)
    for (int r = 0; r < num_rows; r++) {
        rows[r] = split_simple_csv(raw_data ? raw_data[r] : "");
        rows[r].resize(num_cols);
    }

    if (should_remove_duplicates) result->duplicates_found = remove_duplicates_exact(rows);
    result->missing_filled = fill_missing_values(rows, (int)header_vec.size());
    result->outliers_removed = apply_outliers(rows, header_vec, outlier_cfg);
    result->columns_scaled = apply_gpu_scaling(rows, header_vec, scaling_cfg);

    if (encoding_cfg) {
        result->columns_encoded = encoding_cfg->method == 1
            ? one_hot_encode_columns(rows, header_vec, encoding_cfg)
            : label_encode_columns(rows, header_vec, encoding_cfg);
    }

    result->num_rows = (int)rows.size();
    result->num_cols = (int)header_vec.size();
    result->headers = (char**)calloc(result->num_cols, sizeof(char*));
    result->data = (char**)calloc(result->num_rows, sizeof(char*));
    if (!result->headers || !result->data) return result;

    #pragma omp parallel for schedule(static)
    for (int c = 0; c < result->num_cols; c++) result->headers[c] = dup_cstr(header_vec[c]);
    #pragma omp parallel for schedule(static)
    for (int r = 0; r < result->num_rows; r++) {
        rows[r].resize(result->num_cols);
        result->data[r] = dup_cstr(join_simple_csv(rows[r]));
    }

    auto stop = std::chrono::high_resolution_clock::now();
    result->processing_time_ms = std::chrono::duration<double, std::milli>(stop - start).count();

    return result;
}

extern "C" PreprocessedData* preprocess_cuda(
    char **raw_data,
    char **headers,
    int num_rows,
    int num_cols,
    int should_remove_duplicates,
    OutlierConfig *outlier_cfg,
    ScalingConfig *scaling_cfg,
    EncodingConfig *encoding_cfg
) {
    int num_cpu_threads = 0;
    const char *env_threads = getenv("CUDA_HYBRID_CPU_THREADS");
    if (env_threads && *env_threads) num_cpu_threads = atoi(env_threads);

    return preprocess_cuda_hybrid_standalone(
        raw_data,
        headers,
        num_rows,
        num_cols,
        should_remove_duplicates,
        outlier_cfg,
        scaling_cfg,
        encoding_cfg,
        num_cpu_threads
    );
}

extern "C" void free_preprocessed_data(PreprocessedData *data) {
    if (!data) return;
    if (data->data) {
        for (int i = 0; i < data->num_rows; i++) free(data->data[i]);
        free(data->data);
    }
    if (data->headers) {
        for (int i = 0; i < data->num_cols; i++) free(data->headers[i]);
        free(data->headers);
    }
    free(data);
}

extern "C" char* preprocess_to_json(PreprocessedData *data) {
    if (!data) return NULL;
    char *json = (char*)malloc(768);
    if (!json) return NULL;
    snprintf(json, 768,
        "{\"rows_after\":%d,\"duplicates_found\":%d,\"missing_filled\":%d,"
        "\"outliers_removed\":%d,\"columns_scaled\":%d,\"columns_encoded\":%d,"
        "\"processing_time_ms\":%.2f}",
        data->num_rows, data->duplicates_found, data->missing_filled,
        data->outliers_removed, data->columns_scaled, data->columns_encoded,
        data->processing_time_ms);
    return json;
}

static int scaling_method_from_name(const std::string &name) {
    if (name == "none") return -1;
    if (name == "zscore") return 1;
    if (name == "robust") return 2;
    return 0;
}

static bool read_csv_lines(
    const std::string &path,
    std::vector<std::string> &headers,
    std::vector<std::string> &rows
) {
    std::ifstream in(path);
    if (!in) return false;

    std::string line;
    if (!std::getline(in, line)) return false;
    if (!line.empty() && line.back() == '\r') line.pop_back();
    headers = split_simple_csv(line.c_str());

    while (std::getline(in, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        rows.push_back(line);
    }
    return true;
}

static bool write_preprocessed_csv(const std::string &path, const PreprocessedData *data) {
    std::ofstream out(path);
    if (!out || !data) return false;

    for (int c = 0; c < data->num_cols; c++) {
        if (c) out << ",";
        out << (data->headers[c] ? data->headers[c] : "");
    }
    out << "\n";

    for (int r = 0; r < data->num_rows; r++) {
        out << (data->data[r] ? data->data[r] : "") << "\n";
    }
    return true;
}

#ifndef CUDA_HYBRID_LIBRARY
int main(int argc, char **argv) {
    if (argc < 3) {
        std::cerr
            << "Usage: " << argv[0]
            << " input.csv output.csv [cpu_threads] [scale: none|minmax|zscore|robust] [remove_duplicates: 0|1]\n";
        return 1;
    }

    std::string input_path = argv[1];
    std::string output_path = argv[2];
    int cpu_threads = argc >= 4 ? atoi(argv[3]) : 0;
    std::string scale_name = argc >= 5 ? argv[4] : "minmax";
    int remove_duplicates = argc >= 6 ? atoi(argv[5]) : 0;

    std::vector<std::string> header_vec;
    std::vector<std::string> row_vec;
    if (!read_csv_lines(input_path, header_vec, row_vec)) {
        std::cerr << "Failed to read CSV: " << input_path << "\n";
        return 1;
    }

    std::vector<char*> header_ptrs(header_vec.size());
    for (size_t i = 0; i < header_vec.size(); i++) header_ptrs[i] = (char*)header_vec[i].c_str();

    std::vector<char*> row_ptrs(row_vec.size());
    for (size_t i = 0; i < row_vec.size(); i++) row_ptrs[i] = (char*)row_vec[i].c_str();

    int scale_method = scaling_method_from_name(scale_name);
    ScalingConfig scaling_cfg;
    scaling_cfg.method = scale_method < 0 ? 0 : scale_method;
    scaling_cfg.columns = NULL;
    scaling_cfg.num_columns = 0;
    ScalingConfig *scaling_ptr = scale_method < 0 ? NULL : &scaling_cfg;

    PreprocessedData *result = preprocess_cuda_hybrid_standalone(
        row_ptrs.data(),
        header_ptrs.data(),
        (int)row_ptrs.size(),
        (int)header_ptrs.size(),
        remove_duplicates,
        NULL,
        scaling_ptr,
        NULL,
        cpu_threads
    );

    if (!result) {
        std::cerr << "Hybrid CUDA preprocessing failed.\n";
        return 1;
    }

    if (!write_preprocessed_csv(output_path, result)) {
        std::cerr << "Failed to write CSV: " << output_path << "\n";
        free_preprocessed_data(result);
        return 1;
    }

    char *json = preprocess_to_json(result);
    std::cout << "Hybrid CUDA + CPU-threaded standalone analyzer\n";
    std::cout << "CPU threads: " << get_cpu_threads() << "\n";
    std::cout << "Input rows: " << row_vec.size() << ", input columns: " << header_vec.size() << "\n";
    std::cout << "Output: " << output_path << "\n";
    std::cout << "Preprocess wall time ms: " << result->processing_time_ms << "\n";
    std::cout << "CUDA work time ms: " << g_last_cuda_work_time_ms << "\n";
    if (json) {
        std::cout << json << "\n";
        free(json);
    }

    free_preprocessed_data(result);
    return 0;
}
#endif
