#include <cuda_runtime.h>

#include <algorithm>
#include <chrono>
#include <cfloat>
#include <cmath>
#include <cctype>
#include <cstdlib>
#include <fstream>
#include <future>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>
#include <unordered_set>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

#define THREADS_PER_BLOCK 256

struct CsvData {
    std::vector<std::string> headers;
    std::vector<std::vector<std::string>> rows;
};

struct RunOptions {
    std::string csv_path;
    int generated_rows = 100000;
    bool debug_threads = false;
    int gpu_debug_limit = 32;
    int gpu_repeat = 1;
};

struct CpuColumnReport {
    std::string name;
    int unique_count = 0;
    int missing_count = 0;
};

struct GpuColumnReport {
    std::string name;
    double min_value = 0.0;
    double max_value = 0.0;
    double mean = 0.0;
    int valid_count = 0;
    int missing_count = 0;
};

static void check_cuda(cudaError_t status, const char *what) {
    if (status != cudaSuccess) {
        std::cerr << "CUDA error during " << what << ": "
                  << cudaGetErrorString(status) << "\n";
        std::exit(1);
    }
}

static RunOptions parse_args(int argc, char **argv) {
    RunOptions opts;
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--rows" && i + 1 < argc) {
            opts.generated_rows = std::max(1, std::atoi(argv[++i]));
        } else if (arg == "--debug-threads") {
            opts.debug_threads = true;
        } else if (arg == "--gpu-debug-limit" && i + 1 < argc) {
            opts.gpu_debug_limit = std::max(0, std::atoi(argv[++i]));
        } else if (arg == "--gpu-repeat" && i + 1 < argc) {
            opts.gpu_repeat = std::max(1, std::atoi(argv[++i]));
        } else {
            opts.csv_path = arg;
        }
    }
    return opts;
}

static bool is_missing(const std::string &value) {
    if (value.empty()) return true;
    std::string lower;
    lower.reserve(value.size());
    for (char c : value) lower.push_back((char)std::tolower((unsigned char)c));
    return lower == "na" || lower == "n/a" || lower == "nan" || lower == "null";
}

static bool parse_double(const std::string &value, double &out) {
    if (is_missing(value)) return false;
    char *end = nullptr;
    out = std::strtod(value.c_str(), &end);
    while (end && *end && std::isspace((unsigned char)*end)) end++;
    return end && *end == '\0';
}

static std::vector<std::string> split_csv_simple(const std::string &line) {
    std::vector<std::string> cells;
    std::string cell;
    bool in_quotes = false;

    for (char c : line) {
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

static CsvData read_csv(const std::string &path) {
    std::ifstream file(path);
    if (!file) {
        std::cerr << "Could not open CSV: " << path << "\n";
        std::exit(1);
    }

    CsvData data;
    std::string line;
    if (std::getline(file, line)) data.headers = split_csv_simple(line);

    while (std::getline(file, line)) {
        auto row = split_csv_simple(line);
        row.resize(data.headers.size());
        data.rows.push_back(std::move(row));
    }
    return data;
}

static CsvData generate_data(int rows) {
    CsvData data;
    data.headers = {"transaction_id", "customer_id", "age", "items_purchased",
                    "price_per_item", "discount_pct", "department", "city"};
    data.rows.reserve(rows);
    const char *departments[] = {"Electronics", "Grocery", "Fashion", "Home"};
    const char *cities[] = {"Colombo", "Kandy", "Galle", "Jaffna", "Matara"};

    for (int i = 0; i < rows; i++) {
        data.rows.push_back({
            std::to_string(i + 1),
            std::to_string(10000 + (i % 25000)),
            (i % 97 == 0) ? "NA" : std::to_string(18 + (i % 70)),
            std::to_string(1 + (i % 20)),
            std::to_string(10.0 + (i % 5000) / 10.0),
            (i % 131 == 0) ? "null" : std::to_string((i % 50) / 100.0),
            departments[i % 4],
            cities[i % 5]
        });
    }
    return data;
}

static std::vector<int> detect_numeric_columns(const CsvData &data) {
    std::vector<int> numeric_flags(data.headers.size(), 0);

    #pragma omp parallel for schedule(dynamic)
    for (int col = 0; col < (int)data.headers.size(); col++) {
        int numeric_seen = 0;
        int text_seen = 0;
        for (const auto &row : data.rows) {
            double value = 0.0;
            if (parse_double(row[col], value)) numeric_seen++;
            else if (!is_missing(row[col])) text_seen++;
        }
        numeric_flags[col] = (numeric_seen > 0 && text_seen == 0) ? 1 : 0;
    }

    return numeric_flags;
}

static std::vector<int> collect_numeric_columns(const std::vector<int> &numeric_flags) {
    std::vector<int> numeric_cols;
    for (int i = 0; i < (int)numeric_flags.size(); i++) {
        if (numeric_flags[i]) numeric_cols.push_back(i);
    }
    return numeric_cols;
}

static std::vector<double> make_numeric_matrix(
    const CsvData &data,
    const std::vector<int> &numeric_cols
) {
    const int rows = (int)data.rows.size();
    const int cols = (int)numeric_cols.size();
    std::vector<double> matrix((size_t)rows * cols, std::numeric_limits<double>::quiet_NaN());

    #pragma omp parallel for collapse(2) schedule(static)
    for (int c = 0; c < cols; c++) {
        for (int r = 0; r < rows; r++) {
            double value = 0.0;
            if (parse_double(data.rows[r][numeric_cols[c]], value)) {
                matrix[(size_t)c * rows + r] = value;
            }
        }
    }

    return matrix;
}

static std::vector<CpuColumnReport> process_categorical_cpu(
    const CsvData &data,
    const std::vector<int> &numeric_flags,
    bool debug_threads
) {
    std::vector<CpuColumnReport> reports(data.headers.size());

    #pragma omp parallel for schedule(dynamic)
    for (int col = 0; col < (int)data.headers.size(); col++) {
        if (numeric_flags[col]) continue;

        int thread_id = 0;
        #ifdef _OPENMP
        thread_id = omp_get_thread_num();
        #endif

        std::unordered_set<std::string> unique_values;
        int missing_count = 0;

        for (const auto &row : data.rows) {
            if (is_missing(row[col])) missing_count++;
            else unique_values.insert(row[col]);
        }

        reports[col].name = data.headers[col];
        reports[col].unique_count = (int)unique_values.size();
        reports[col].missing_count = missing_count;

        if (debug_threads) {
            #pragma omp critical
            std::cout << "[CPU/OpenMP] thread " << thread_id
                      << " processed categorical column " << col
                      << " (" << data.headers[col] << ")\n";
        }
    }

    return reports;
}

__global__ void partial_stats_kernel(
    const double *values,
    int rows,
    int cols,
    int blocks_per_col,
    double *partial_mins,
    double *partial_maxs,
    double *partial_sums,
    int *partial_valids,
    int *partial_missings,
    int debug_threads,
    int debug_limit
) {
    int col = blockIdx.x / blocks_per_col;
    int segment = blockIdx.x % blocks_per_col;
    int tid = threadIdx.x;

    __shared__ double s_min[THREADS_PER_BLOCK];
    __shared__ double s_max[THREADS_PER_BLOCK];
    __shared__ double s_sum[THREADS_PER_BLOCK];
    __shared__ int s_valid[THREADS_PER_BLOCK];
    __shared__ int s_missing[THREADS_PER_BLOCK];

    double local_min = DBL_MAX;
    double local_max = -DBL_MAX;
    double local_sum = 0.0;
    int local_valid = 0;
    int local_missing = 0;

    for (int row = segment * blockDim.x + tid; row < rows; row += blockDim.x * blocks_per_col) {
        double value = values[(size_t)col * rows + row];
        int global_item = col * rows + row;

        if (debug_threads && global_item < debug_limit) {
            printf("[GPU partial] block=%d thread=%d -> col=%d row=%d value=%f\n",
                   blockIdx.x, tid, col, row, value);
        }

        if (isnan(value)) {
            local_missing++;
        } else {
            local_min = fmin(local_min, value);
            local_max = fmax(local_max, value);
            local_sum += value;
            local_valid++;
        }
    }

    s_min[tid] = local_min;
    s_max[tid] = local_max;
    s_sum[tid] = local_sum;
    s_valid[tid] = local_valid;
    s_missing[tid] = local_missing;
    __syncthreads();

    for (int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            s_min[tid] = fmin(s_min[tid], s_min[tid + stride]);
            s_max[tid] = fmax(s_max[tid], s_max[tid + stride]);
            s_sum[tid] += s_sum[tid + stride];
            s_valid[tid] += s_valid[tid + stride];
            s_missing[tid] += s_missing[tid + stride];
        }
        __syncthreads();
    }

    if (tid == 0) {
        int out = col * blocks_per_col + segment;
        partial_mins[out] = s_min[0];
        partial_maxs[out] = s_max[0];
        partial_sums[out] = s_sum[0];
        partial_valids[out] = s_valid[0];
        partial_missings[out] = s_missing[0];
    }
}

__global__ void final_stats_kernel(
    int cols,
    int blocks_per_col,
    const double *partial_mins,
    const double *partial_maxs,
    const double *partial_sums,
    const int *partial_valids,
    const int *partial_missings,
    double *mins,
    double *maxs,
    double *sums,
    int *valids,
    int *missings
) {
    int col = blockIdx.x;
    int tid = threadIdx.x;

    __shared__ double s_min[THREADS_PER_BLOCK];
    __shared__ double s_max[THREADS_PER_BLOCK];
    __shared__ double s_sum[THREADS_PER_BLOCK];
    __shared__ int s_valid[THREADS_PER_BLOCK];
    __shared__ int s_missing[THREADS_PER_BLOCK];

    double local_min = DBL_MAX;
    double local_max = -DBL_MAX;
    double local_sum = 0.0;
    int local_valid = 0;
    int local_missing = 0;

    for (int i = tid; i < blocks_per_col; i += blockDim.x) {
        int idx = col * blocks_per_col + i;
        local_min = fmin(local_min, partial_mins[idx]);
        local_max = fmax(local_max, partial_maxs[idx]);
        local_sum += partial_sums[idx];
        local_valid += partial_valids[idx];
        local_missing += partial_missings[idx];
    }

    s_min[tid] = local_min;
    s_max[tid] = local_max;
    s_sum[tid] = local_sum;
    s_valid[tid] = local_valid;
    s_missing[tid] = local_missing;
    __syncthreads();

    for (int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            s_min[tid] = fmin(s_min[tid], s_min[tid + stride]);
            s_max[tid] = fmax(s_max[tid], s_max[tid + stride]);
            s_sum[tid] += s_sum[tid + stride];
            s_valid[tid] += s_valid[tid + stride];
            s_missing[tid] += s_missing[tid + stride];
        }
        __syncthreads();
    }

    if (tid == 0) {
        mins[col] = s_min[0];
        maxs[col] = s_max[0];
        sums[col] = s_sum[0];
        valids[col] = s_valid[0];
        missings[col] = s_missing[0];
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

static std::vector<GpuColumnReport> process_numeric_gpu_optimized(
    const CsvData &data,
    const std::vector<int> &numeric_cols,
    const std::vector<double> &matrix,
    float &gpu_ms,
    bool debug_threads,
    int gpu_debug_limit,
    int gpu_repeat
) {
    const int rows = (int)data.rows.size();
    const int cols = (int)numeric_cols.size();
    std::vector<GpuColumnReport> reports(cols);
    if (rows == 0 || cols == 0) return reports;

    int blocks_per_col = std::min(1024, std::max(1, (rows + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK));
    int partial_count = cols * blocks_per_col;

    double *d_values = nullptr;
    double *d_partial_mins = nullptr;
    double *d_partial_maxs = nullptr;
    double *d_partial_sums = nullptr;
    int *d_partial_valids = nullptr;
    int *d_partial_missings = nullptr;
    double *d_mins = nullptr;
    double *d_maxs = nullptr;
    double *d_sums = nullptr;
    int *d_valids = nullptr;
    int *d_missings = nullptr;

    check_cuda(cudaMalloc(&d_values, matrix.size() * sizeof(double)), "alloc values");
    check_cuda(cudaMalloc(&d_partial_mins, partial_count * sizeof(double)), "alloc partial mins");
    check_cuda(cudaMalloc(&d_partial_maxs, partial_count * sizeof(double)), "alloc partial maxs");
    check_cuda(cudaMalloc(&d_partial_sums, partial_count * sizeof(double)), "alloc partial sums");
    check_cuda(cudaMalloc(&d_partial_valids, partial_count * sizeof(int)), "alloc partial valids");
    check_cuda(cudaMalloc(&d_partial_missings, partial_count * sizeof(int)), "alloc partial missings");
    check_cuda(cudaMalloc(&d_mins, cols * sizeof(double)), "alloc mins");
    check_cuda(cudaMalloc(&d_maxs, cols * sizeof(double)), "alloc maxs");
    check_cuda(cudaMalloc(&d_sums, cols * sizeof(double)), "alloc sums");
    check_cuda(cudaMalloc(&d_valids, cols * sizeof(int)), "alloc valids");
    check_cuda(cudaMalloc(&d_missings, cols * sizeof(int)), "alloc missings");

    cudaEvent_t start, stop;
    check_cuda(cudaEventCreate(&start), "create start event");
    check_cuda(cudaEventCreate(&stop), "create stop event");
    check_cuda(cudaEventRecord(start), "record start");

    check_cuda(cudaMemcpy(d_values, matrix.data(), matrix.size() * sizeof(double), cudaMemcpyHostToDevice), "copy values");

    int total = rows * cols;
    int scale_blocks = (total + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;

    for (int repeat = 0; repeat < gpu_repeat; repeat++) {
        check_cuda(cudaMemcpy(d_values, matrix.data(), matrix.size() * sizeof(double), cudaMemcpyHostToDevice), "reset values");

        partial_stats_kernel<<<cols * blocks_per_col, THREADS_PER_BLOCK>>>(
            d_values, rows, cols, blocks_per_col,
            d_partial_mins, d_partial_maxs, d_partial_sums, d_partial_valids, d_partial_missings,
            debug_threads ? 1 : 0, gpu_debug_limit
        );
        check_cuda(cudaGetLastError(), "partial stats kernel");

        final_stats_kernel<<<cols, THREADS_PER_BLOCK>>>(
            cols, blocks_per_col,
            d_partial_mins, d_partial_maxs, d_partial_sums, d_partial_valids, d_partial_missings,
            d_mins, d_maxs, d_sums, d_valids, d_missings
        );
        check_cuda(cudaGetLastError(), "final stats kernel");

        scale_kernel<<<scale_blocks, THREADS_PER_BLOCK>>>(d_values, rows, cols, d_mins, d_maxs);
        check_cuda(cudaGetLastError(), "scale kernel");
    }

    std::vector<double> mins(cols), maxs(cols), sums(cols);
    std::vector<int> valids(cols), missings(cols);
    check_cuda(cudaMemcpy(mins.data(), d_mins, cols * sizeof(double), cudaMemcpyDeviceToHost), "copy mins back");
    check_cuda(cudaMemcpy(maxs.data(), d_maxs, cols * sizeof(double), cudaMemcpyDeviceToHost), "copy maxs back");
    check_cuda(cudaMemcpy(sums.data(), d_sums, cols * sizeof(double), cudaMemcpyDeviceToHost), "copy sums back");
    check_cuda(cudaMemcpy(valids.data(), d_valids, cols * sizeof(int), cudaMemcpyDeviceToHost), "copy valids back");
    check_cuda(cudaMemcpy(missings.data(), d_missings, cols * sizeof(int), cudaMemcpyDeviceToHost), "copy missings back");

    check_cuda(cudaEventRecord(stop), "record stop");
    check_cuda(cudaEventSynchronize(stop), "sync stop");
    check_cuda(cudaEventElapsedTime(&gpu_ms, start, stop), "elapsed time");

    for (int c = 0; c < cols; c++) {
        reports[c].name = data.headers[numeric_cols[c]].empty()
            ? std::string("(empty header)")
            : data.headers[numeric_cols[c]];
        reports[c].min_value = mins[c];
        reports[c].max_value = maxs[c];
        reports[c].valid_count = valids[c];
        reports[c].missing_count = missings[c];
        reports[c].mean = valids[c] > 0 ? sums[c] / valids[c] : 0.0;
    }

    cudaEventDestroy(start);
    cudaEventDestroy(stop);
    cudaFree(d_values);
    cudaFree(d_partial_mins);
    cudaFree(d_partial_maxs);
    cudaFree(d_partial_sums);
    cudaFree(d_partial_valids);
    cudaFree(d_partial_missings);
    cudaFree(d_mins);
    cudaFree(d_maxs);
    cudaFree(d_sums);
    cudaFree(d_valids);
    cudaFree(d_missings);

    return reports;
}

int main(int argc, char **argv) {
    RunOptions opts = parse_args(argc, argv);

    int device_count = 0;
    check_cuda(cudaGetDeviceCount(&device_count), "get device count");
    if (device_count == 0) {
        std::cerr << "No CUDA GPU found.\n";
        return 1;
    }

    cudaDeviceProp prop{};
    check_cuda(cudaGetDeviceProperties(&prop, 0), "get device properties");
    check_cuda(cudaSetDevice(0), "set device");

    CsvData data = !opts.csv_path.empty() ? read_csv(opts.csv_path) : generate_data(opts.generated_rows);
    if (data.headers.empty() || data.rows.empty()) {
        std::cerr << "No usable data.\n";
        return 1;
    }

    auto total_start = std::chrono::high_resolution_clock::now();

    auto numeric_flags = detect_numeric_columns(data);
    auto numeric_cols = collect_numeric_columns(numeric_flags);
    auto matrix = make_numeric_matrix(data, numeric_cols);

    auto cpu_future = std::async(std::launch::async, [&]() {
        return process_categorical_cpu(data, numeric_flags, opts.debug_threads);
    });

    float gpu_ms = 0.0f;
    auto gpu_reports = process_numeric_gpu_optimized(
        data, numeric_cols, matrix, gpu_ms, opts.debug_threads, opts.gpu_debug_limit, opts.gpu_repeat
    );

    auto cpu_reports = cpu_future.get();
    auto total_end = std::chrono::high_resolution_clock::now();
    double total_ms = std::chrono::duration<double, std::milli>(total_end - total_start).count();

    int cpu_threads = 1;
    #ifdef _OPENMP
    cpu_threads = omp_get_max_threads();
    #endif

    std::cout << "\n=== Optimized Hybrid CPU + GPU Preprocessing Demo ===\n";
    std::cout << "Rows: " << data.rows.size() << ", Columns: " << data.headers.size() << "\n";
    std::cout << "CUDA GPU: " << prop.name << "\n";
    std::cout << "CPU OpenMP threads: " << cpu_threads << "\n";
    std::cout << "Numeric columns on GPU: " << numeric_cols.size() << "\n";
    std::cout << "GPU repeat count: " << opts.gpu_repeat << "\n";

    std::cout << "\nGPU numeric processing, optimized reductions:\n";
    for (const auto &r : gpu_reports) {
        std::cout << "  " << r.name
                  << " | valid=" << r.valid_count
                  << " missing=" << r.missing_count
                  << " min=" << std::fixed << std::setprecision(3) << r.min_value
                  << " max=" << r.max_value
                  << " mean=" << r.mean << "\n";
    }

    std::cout << "\nCPU categorical processing:\n";
    for (const auto &r : cpu_reports) {
        if (r.name.empty()) continue;
        std::cout << "  " << r.name
                  << " | unique=" << r.unique_count
                  << " missing=" << r.missing_count << "\n";
    }

    std::cout << "\nTiming:\n";
    std::cout << "  GPU numeric time:      " << std::fixed << std::setprecision(2) << gpu_ms << " ms\n";
    std::cout << "  Total hybrid wall time:" << total_ms << " ms\n";
    std::cout << "\nDesign: CPU handles CSV/categorical work while GPU handles dense numeric arrays.\n";

    return 0;
}
