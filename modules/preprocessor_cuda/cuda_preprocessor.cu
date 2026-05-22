#include <cuda_runtime.h>

#include <algorithm>
#include <cfloat>
#include <cmath>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#define THREADS_PER_BLOCK 256

extern "C" {

typedef struct {
    int method;          /* 0=IQR, 1=Z-score */
    int treatment;       /* 0=remove, 1=cap, 2=flag */
    char **columns;
    int num_columns;
    double threshold;
} OutlierConfig;

typedef struct {
    int method;          /* 0=minmax, 1=zscore, 2=robust */
    char **columns;
    int num_columns;
} ScalingConfig;

typedef struct {
    int method;          /* 0=label, 1=onehot */
    char **columns;
    int num_columns;
} EncodingConfig;

typedef struct {
    char **data;
    int num_rows;
    int num_cols;
    char **headers;
    int duplicates_found;
    int missing_filled;
    int outliers_removed;
    int columns_scaled;
    int columns_encoded;
    double processing_time_ms;
} PreprocessedData;

}

struct NumericStats {
    double min_value = 0.0;
    double max_value = 0.0;
    double mean = 0.0;
    double stddev = 0.0;
    int valid_count = 0;
};

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

        for (auto &row : rows) {
            if (col >= (int)row.size()) row.resize(num_cols);
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
    if (!cfg || rows.empty()) return 0;

    std::vector<int> numeric_cols;
    for (int c = 0; c < (int)headers.size(); c++) {
        if (config_selects_column(c, headers, cfg->columns, cfg->num_columns) && is_numeric_column(rows, c)) {
            numeric_cols.push_back(c);
        }
    }
    if (numeric_cols.empty()) return 0;

    int rows_count = (int)rows.size();
    int gpu_cols = (int)numeric_cols.size();

    if (cfg->method == 2) {
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
    cudaEvent_t start, stop;
    check_cuda(cudaEventCreate(&start), "create start event");
    check_cuda(cudaEventCreate(&stop), "create stop event");
    check_cuda(cudaEventRecord(start), "record start event");

    PreprocessedData *result = (PreprocessedData*)calloc(1, sizeof(PreprocessedData));
    if (!result) return NULL;

    std::vector<std::string> header_vec;
    header_vec.reserve(num_cols);
    for (int c = 0; c < num_cols; c++) header_vec.push_back(headers[c] ? headers[c] : "");

    std::vector<std::vector<std::string>> rows(num_rows);
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

    for (int c = 0; c < result->num_cols; c++) result->headers[c] = dup_cstr(header_vec[c]);
    for (int r = 0; r < result->num_rows; r++) {
        rows[r].resize(result->num_cols);
        result->data[r] = dup_cstr(join_simple_csv(rows[r]));
    }

    cudaEventRecord(stop);
    cudaEventSynchronize(stop);
    float ms = 0.0f;
    cudaEventElapsedTime(&ms, start, stop);
    result->processing_time_ms = ms;
    cudaEventDestroy(start);
    cudaEventDestroy(stop);

    return result;
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
