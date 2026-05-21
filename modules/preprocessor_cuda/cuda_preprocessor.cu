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
#include <vector>

#define THREADS_PER_BLOCK 256

extern "C" {

typedef struct {
    int method;
    int treatment;
    char **columns;
    int num_columns;
    double threshold;
} OutlierConfig;

typedef struct {
    int method;
    char **columns;
    int num_columns;
} ScalingConfig;

typedef struct {
    int method;
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

static bool column_selected(int col, char **headers, ScalingConfig *cfg) {
    if (!cfg || !cfg->columns || cfg->num_columns <= 0) return true;
    for (int i = 0; i < cfg->num_columns; i++) {
        if (cfg->columns[i] && strcmp(headers[col], cfg->columns[i]) == 0) return true;
    }
    return false;
}

__global__ void partial_stats_kernel(
    const double *values,
    int rows,
    int cols,
    int blocks_per_col,
    double *partial_mins,
    double *partial_maxs,
    int *partial_valids
) {
    int col = blockIdx.x / blocks_per_col;
    int segment = blockIdx.x % blocks_per_col;
    int tid = threadIdx.x;

    __shared__ double s_min[THREADS_PER_BLOCK];
    __shared__ double s_max[THREADS_PER_BLOCK];
    __shared__ int s_valid[THREADS_PER_BLOCK];

    double local_min = DBL_MAX;
    double local_max = -DBL_MAX;
    int local_valid = 0;

    for (int row = segment * blockDim.x + tid; row < rows; row += blockDim.x * blocks_per_col) {
        double value = values[(size_t)col * rows + row];
        if (!isnan(value)) {
            local_min = fmin(local_min, value);
            local_max = fmax(local_max, value);
            local_valid++;
        }
    }

    s_min[tid] = local_min;
    s_max[tid] = local_max;
    s_valid[tid] = local_valid;
    __syncthreads();

    for (int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            s_min[tid] = fmin(s_min[tid], s_min[tid + stride]);
            s_max[tid] = fmax(s_max[tid], s_max[tid + stride]);
            s_valid[tid] += s_valid[tid + stride];
        }
        __syncthreads();
    }

    if (tid == 0) {
        int out = col * blocks_per_col + segment;
        partial_mins[out] = s_min[0];
        partial_maxs[out] = s_max[0];
        partial_valids[out] = s_valid[0];
    }
}

__global__ void final_stats_kernel(
    int cols,
    int blocks_per_col,
    const double *partial_mins,
    const double *partial_maxs,
    const int *partial_valids,
    double *mins,
    double *maxs,
    int *valids
) {
    int col = blockIdx.x;
    int tid = threadIdx.x;

    __shared__ double s_min[THREADS_PER_BLOCK];
    __shared__ double s_max[THREADS_PER_BLOCK];
    __shared__ int s_valid[THREADS_PER_BLOCK];

    double local_min = DBL_MAX;
    double local_max = -DBL_MAX;
    int local_valid = 0;

    for (int i = tid; i < blocks_per_col; i += blockDim.x) {
        int idx = col * blocks_per_col + i;
        local_min = fmin(local_min, partial_mins[idx]);
        local_max = fmax(local_max, partial_maxs[idx]);
        local_valid += partial_valids[idx];
    }

    s_min[tid] = local_min;
    s_max[tid] = local_max;
    s_valid[tid] = local_valid;
    __syncthreads();

    for (int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            s_min[tid] = fmin(s_min[tid], s_min[tid + stride]);
            s_max[tid] = fmax(s_max[tid], s_max[tid + stride]);
            s_valid[tid] += s_valid[tid + stride];
        }
        __syncthreads();
    }

    if (tid == 0) {
        mins[col] = s_min[0];
        maxs[col] = s_max[0];
        valids[col] = s_valid[0];
    }
}

__global__ void scale_kernel(
    double *values,
    int rows,
    int cols,
    const double *mins,
    const double *maxs
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int total = rows * cols;
    if (idx >= total) return;

    int col = idx / rows;
    double value = values[idx];
    double range = maxs[col] - mins[col];
    if (!isnan(value) && range > 0.0) {
        values[idx] = (value - mins[col]) / range;
    }
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
    (void)should_remove_duplicates;
    (void)outlier_cfg;
    (void)encoding_cfg;

    cudaEvent_t start, stop;
    check_cuda(cudaEventCreate(&start), "create start event");
    check_cuda(cudaEventCreate(&stop), "create stop event");
    check_cuda(cudaEventRecord(start), "record start event");

    PreprocessedData *result = (PreprocessedData*)calloc(1, sizeof(PreprocessedData));
    if (!result) return NULL;

    result->num_rows = num_rows;
    result->num_cols = num_cols;
    result->headers = (char**)calloc(num_cols, sizeof(char*));
    result->data = (char**)calloc(num_rows, sizeof(char*));
    if (!result->headers || !result->data) return result;

    for (int c = 0; c < num_cols; c++) {
        result->headers[c] = dup_cstr(headers[c] ? headers[c] : "");
    }

    std::vector<std::vector<std::string>> rows(num_rows);
    for (int r = 0; r < num_rows; r++) {
        rows[r] = split_simple_csv(raw_data ? raw_data[r] : "");
        rows[r].resize(num_cols);
    }

    std::vector<int> numeric_cols;
    for (int c = 0; c < num_cols; c++) {
        if (!column_selected(c, headers, scaling_cfg)) continue;

        int numeric_seen = 0;
        int text_seen = 0;
        for (int r = 0; r < num_rows; r++) {
            double v = 0.0;
            if (parse_double(rows[r][c], v)) numeric_seen++;
            else if (!is_missing(rows[r][c])) text_seen++;
        }
        if (numeric_seen > 0 && text_seen == 0) numeric_cols.push_back(c);
    }

    int gpu_cols = (int)numeric_cols.size();
    if (num_rows > 0 && gpu_cols > 0) {
        std::vector<double> matrix((size_t)num_rows * gpu_cols, NAN);
        for (int gc = 0; gc < gpu_cols; gc++) {
            int source_col = numeric_cols[gc];
            for (int r = 0; r < num_rows; r++) {
                double v = 0.0;
                if (parse_double(rows[r][source_col], v)) {
                    matrix[(size_t)gc * num_rows + r] = v;
                }
            }
        }

        int blocks_per_col = std::min(1024, std::max(1, (num_rows + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK));
        int partial_count = gpu_cols * blocks_per_col;
        int total_values = num_rows * gpu_cols;

        double *d_values = NULL, *d_partial_mins = NULL, *d_partial_maxs = NULL, *d_mins = NULL, *d_maxs = NULL;
        int *d_partial_valids = NULL, *d_valids = NULL;

        check_cuda(cudaMalloc(&d_values, matrix.size() * sizeof(double)), "alloc values");
        check_cuda(cudaMalloc(&d_partial_mins, partial_count * sizeof(double)), "alloc partial mins");
        check_cuda(cudaMalloc(&d_partial_maxs, partial_count * sizeof(double)), "alloc partial maxs");
        check_cuda(cudaMalloc(&d_partial_valids, partial_count * sizeof(int)), "alloc partial valids");
        check_cuda(cudaMalloc(&d_mins, gpu_cols * sizeof(double)), "alloc mins");
        check_cuda(cudaMalloc(&d_maxs, gpu_cols * sizeof(double)), "alloc maxs");
        check_cuda(cudaMalloc(&d_valids, gpu_cols * sizeof(int)), "alloc valids");

        check_cuda(cudaMemcpy(d_values, matrix.data(), matrix.size() * sizeof(double), cudaMemcpyHostToDevice), "copy values");

        partial_stats_kernel<<<gpu_cols * blocks_per_col, THREADS_PER_BLOCK>>>(
            d_values, num_rows, gpu_cols, blocks_per_col,
            d_partial_mins, d_partial_maxs, d_partial_valids
        );
        check_cuda(cudaGetLastError(), "partial stats kernel");

        final_stats_kernel<<<gpu_cols, THREADS_PER_BLOCK>>>(
            gpu_cols, blocks_per_col,
            d_partial_mins, d_partial_maxs, d_partial_valids,
            d_mins, d_maxs, d_valids
        );
        check_cuda(cudaGetLastError(), "final stats kernel");

        int scale_blocks = (total_values + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
        scale_kernel<<<scale_blocks, THREADS_PER_BLOCK>>>(d_values, num_rows, gpu_cols, d_mins, d_maxs);
        check_cuda(cudaGetLastError(), "scale kernel");

        check_cuda(cudaMemcpy(matrix.data(), d_values, matrix.size() * sizeof(double), cudaMemcpyDeviceToHost), "copy scaled values");

        for (int gc = 0; gc < gpu_cols; gc++) {
            int target_col = numeric_cols[gc];
            for (int r = 0; r < num_rows; r++) {
                double v = matrix[(size_t)gc * num_rows + r];
                if (!isnan(v)) {
                    char buf[64];
                    snprintf(buf, sizeof(buf), "%.6f", v);
                    rows[r][target_col] = buf;
                }
            }
        }

        result->columns_scaled = gpu_cols;

        cudaFree(d_values);
        cudaFree(d_partial_mins);
        cudaFree(d_partial_maxs);
        cudaFree(d_partial_valids);
        cudaFree(d_mins);
        cudaFree(d_maxs);
        cudaFree(d_valids);
    }

    for (int r = 0; r < num_rows; r++) {
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
    char *json = (char*)malloc(512);
    if (!json) return NULL;
    snprintf(json, 512,
        "{\"rows_after\":%d,\"columns_scaled\":%d,\"processing_time_ms\":%.2f}",
        data->num_rows, data->columns_scaled, data->processing_time_ms);
    return json;
}
