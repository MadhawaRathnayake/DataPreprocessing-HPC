#include <cuda_runtime.h>

#include <chrono>
#include <cfloat>
#include <cmath>
#include <cctype>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

struct CsvData {
    std::vector<std::string> headers;
    std::vector<std::vector<std::string>> rows;
};

struct RunOptions {
    std::string csv_path;
    bool debug_threads = false;
    bool debug_all_threads = false;
    int gpu_debug_limit = 64;
    int generated_rows = 100000;
    int gpu_repeat = 1;
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
        if (arg == "--debug-threads") {
            opts.debug_threads = true;
        } else if (arg == "--debug-all-threads") {
            opts.debug_threads = true;
            opts.debug_all_threads = true;
            opts.gpu_debug_limit = -1;
        } else if (arg == "--gpu-debug-limit" && i + 1 < argc) {
            opts.gpu_debug_limit = std::max(0, std::atoi(argv[++i]));
        } else if (arg == "--rows" && i + 1 < argc) {
            opts.generated_rows = std::max(1, std::atoi(argv[++i]));
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
    data.headers = {"age", "salary", "experience"};
    data.rows.reserve(rows);

    for (int i = 0; i < rows; i++) {
        int age = 20 + (i % 45);
        double salary = 45000.0 + (i % 9000) * 7.25;
        double exp = (double)(i % 30);
        data.rows.push_back({
            (i % 97 == 0) ? "NA" : std::to_string(age),
            std::to_string(salary),
            std::to_string(exp)
        });
    }
    return data;
}

static std::vector<int> detect_numeric_columns_cpu(const CsvData &data) {
    std::vector<int> numeric_cols;

    for (int col = 0; col < (int)data.headers.size(); col++) {
        int numeric_seen = 0;
        int text_seen = 0;

        for (const auto &row : data.rows) {
            double value = 0.0;
            if (parse_double(row[col], value)) numeric_seen++;
            else if (!is_missing(row[col])) text_seen++;
        }

        if (numeric_seen > 0 && text_seen == 0) {
            numeric_cols.push_back(col);
        }
    }

    return numeric_cols;
}

static std::vector<double> make_numeric_matrix_cpu(
    const CsvData &data,
    const std::vector<int> &numeric_cols
) {
    const int rows = (int)data.rows.size();
    const int cols = (int)numeric_cols.size();
    std::vector<double> matrix((size_t)rows * cols, std::numeric_limits<double>::quiet_NaN());

    for (int r = 0; r < rows; r++) {
        for (int c = 0; c < cols; c++) {
            double value = 0.0;
            if (parse_double(data.rows[r][numeric_cols[c]], value)) {
                matrix[(size_t)c * rows + r] = value;
            }
        }
    }

    return matrix;
}

__device__ double atomic_min_double(double *address, double value) {
    unsigned long long *address_as_ull = (unsigned long long *)address;
    unsigned long long old = *address_as_ull;
    unsigned long long assumed;

    do {
        assumed = old;
        double current = __longlong_as_double((long long)assumed);
        double next = fmin(current, value);
        old = atomicCAS(address_as_ull, assumed, (unsigned long long)__double_as_longlong(next));
    } while (assumed != old);

    return __longlong_as_double((long long)old);
}

__device__ double atomic_max_double(double *address, double value) {
    unsigned long long *address_as_ull = (unsigned long long *)address;
    unsigned long long old = *address_as_ull;
    unsigned long long assumed;

    do {
        assumed = old;
        double current = __longlong_as_double((long long)assumed);
        double next = fmax(current, value);
        old = atomicCAS(address_as_ull, assumed, (unsigned long long)__double_as_longlong(next));
    } while (assumed != old);

    return __longlong_as_double((long long)old);
}

__device__ double atomic_add_double(double *address, double value) {
    unsigned long long *address_as_ull = (unsigned long long *)address;
    unsigned long long old = *address_as_ull;
    unsigned long long assumed;

    do {
        assumed = old;
        double current = __longlong_as_double((long long)assumed);
        double next = current + value;
        old = atomicCAS(address_as_ull, assumed, (unsigned long long)__double_as_longlong(next));
    } while (assumed != old);

    return __longlong_as_double((long long)old);
}

__global__ void numeric_stats_kernel(
    const double *values,
    int rows,
    int cols,
    double *mins,
    double *maxs,
    double *sums,
    int *valid_counts,
    int *missing_counts,
    int debug_threads,
    int debug_limit
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int total = rows * cols;
    if (idx >= total) return;

    int col = idx / rows;
    int row = idx % rows;
    double value = values[idx];

    if (debug_threads && (debug_limit < 0 || idx < debug_limit)) {
        printf("[GPU-ONLY stats] block=%d thread=%d global=%d -> column=%d row=%d value=%f\n",
               blockIdx.x, threadIdx.x, idx, col, row, value);
    }

    if (isnan(value)) {
        atomicAdd(&missing_counts[col], 1);
        return;
    }

    atomic_min_double(&mins[col], value);
    atomic_max_double(&maxs[col], value);
    atomic_add_double(&sums[col], value);
    atomicAdd(&valid_counts[col], 1);
}

__global__ void minmax_scale_kernel(
    double *values,
    int rows,
    int cols,
    const double *mins,
    const double *maxs,
    int debug_threads,
    int debug_limit
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int total = rows * cols;
    if (idx >= total) return;

    int col = idx / rows;
    int row = idx % rows;
    double value = values[idx];
    double range = maxs[col] - mins[col];

    if (debug_threads && (debug_limit < 0 || idx < debug_limit)) {
        printf("[GPU-ONLY scale] block=%d thread=%d global=%d -> column=%d row=%d before=%f\n",
               blockIdx.x, threadIdx.x, idx, col, row, value);
    }

    if (!isnan(value) && range > 0.0) {
        values[idx] = (value - mins[col]) / range;
    }
}

static std::vector<GpuColumnReport> process_numeric_gpu_only(
    const CsvData &data,
    const std::vector<int> &numeric_cols,
    const std::vector<double> &host_matrix,
    float &gpu_ms,
    bool debug_threads,
    int gpu_debug_limit,
    int gpu_repeat
) {
    const int rows = (int)data.rows.size();
    const int cols = (int)numeric_cols.size();
    std::vector<GpuColumnReport> reports(cols);

    if (rows == 0 || cols == 0) {
        gpu_ms = 0.0f;
        return reports;
    }

    double *d_values = nullptr;
    double *d_mins = nullptr;
    double *d_maxs = nullptr;
    double *d_sums = nullptr;
    int *d_valid_counts = nullptr;
    int *d_missing_counts = nullptr;

    size_t values_bytes = host_matrix.size() * sizeof(double);
    check_cuda(cudaMalloc(&d_values, values_bytes), "alloc values");
    check_cuda(cudaMalloc(&d_mins, cols * sizeof(double)), "alloc mins");
    check_cuda(cudaMalloc(&d_maxs, cols * sizeof(double)), "alloc maxs");
    check_cuda(cudaMalloc(&d_sums, cols * sizeof(double)), "alloc sums");
    check_cuda(cudaMalloc(&d_valid_counts, cols * sizeof(int)), "alloc valid counts");
    check_cuda(cudaMalloc(&d_missing_counts, cols * sizeof(int)), "alloc missing counts");

    std::vector<double> init_mins(cols, DBL_MAX);
    std::vector<double> init_maxs(cols, -DBL_MAX);
    std::vector<double> init_sums(cols, 0.0);
    std::vector<int> init_counts(cols, 0);

    cudaEvent_t start, stop;
    check_cuda(cudaEventCreate(&start), "create start event");
    check_cuda(cudaEventCreate(&stop), "create stop event");
    check_cuda(cudaEventRecord(start), "record start event");

    check_cuda(cudaMemcpy(d_values, host_matrix.data(), values_bytes, cudaMemcpyHostToDevice), "copy values to GPU");
    check_cuda(cudaMemcpy(d_mins, init_mins.data(), cols * sizeof(double), cudaMemcpyHostToDevice), "copy mins");
    check_cuda(cudaMemcpy(d_maxs, init_maxs.data(), cols * sizeof(double), cudaMemcpyHostToDevice), "copy maxs");
    check_cuda(cudaMemcpy(d_sums, init_sums.data(), cols * sizeof(double), cudaMemcpyHostToDevice), "copy sums");
    check_cuda(cudaMemcpy(d_valid_counts, init_counts.data(), cols * sizeof(int), cudaMemcpyHostToDevice), "copy valid counts");
    check_cuda(cudaMemcpy(d_missing_counts, init_counts.data(), cols * sizeof(int), cudaMemcpyHostToDevice), "copy missing counts");

    int total = rows * cols;
    int threads = 256;
    int blocks = (total + threads - 1) / threads;

    for (int repeat = 0; repeat < gpu_repeat; repeat++) {
        check_cuda(cudaMemcpy(d_mins, init_mins.data(), cols * sizeof(double), cudaMemcpyHostToDevice), "reset mins");
        check_cuda(cudaMemcpy(d_maxs, init_maxs.data(), cols * sizeof(double), cudaMemcpyHostToDevice), "reset maxs");
        check_cuda(cudaMemcpy(d_sums, init_sums.data(), cols * sizeof(double), cudaMemcpyHostToDevice), "reset sums");
        check_cuda(cudaMemcpy(d_valid_counts, init_counts.data(), cols * sizeof(int), cudaMemcpyHostToDevice), "reset valid counts");
        check_cuda(cudaMemcpy(d_missing_counts, init_counts.data(), cols * sizeof(int), cudaMemcpyHostToDevice), "reset missing counts");

        numeric_stats_kernel<<<blocks, threads>>>(
            d_values, rows, cols, d_mins, d_maxs, d_sums, d_valid_counts, d_missing_counts,
            debug_threads ? 1 : 0, gpu_debug_limit
        );
        check_cuda(cudaGetLastError(), "launch numeric stats kernel");

        minmax_scale_kernel<<<blocks, threads>>>(
            d_values, rows, cols, d_mins, d_maxs,
            debug_threads ? 1 : 0, gpu_debug_limit
        );
        check_cuda(cudaGetLastError(), "launch minmax scale kernel");
    }

    std::vector<double> mins(cols), maxs(cols), sums(cols);
    std::vector<int> valid_counts(cols), missing_counts(cols);

    check_cuda(cudaMemcpy(mins.data(), d_mins, cols * sizeof(double), cudaMemcpyDeviceToHost), "copy mins back");
    check_cuda(cudaMemcpy(maxs.data(), d_maxs, cols * sizeof(double), cudaMemcpyDeviceToHost), "copy maxs back");
    check_cuda(cudaMemcpy(sums.data(), d_sums, cols * sizeof(double), cudaMemcpyDeviceToHost), "copy sums back");
    check_cuda(cudaMemcpy(valid_counts.data(), d_valid_counts, cols * sizeof(int), cudaMemcpyDeviceToHost), "copy valid counts back");
    check_cuda(cudaMemcpy(missing_counts.data(), d_missing_counts, cols * sizeof(int), cudaMemcpyDeviceToHost), "copy missing counts back");

    check_cuda(cudaEventRecord(stop), "record stop event");
    check_cuda(cudaEventSynchronize(stop), "sync stop event");
    check_cuda(cudaEventElapsedTime(&gpu_ms, start, stop), "read GPU elapsed time");

    for (int c = 0; c < cols; c++) {
        reports[c].name = data.headers[numeric_cols[c]];
        reports[c].min_value = mins[c];
        reports[c].max_value = maxs[c];
        reports[c].valid_count = valid_counts[c];
        reports[c].missing_count = missing_counts[c];
        reports[c].mean = valid_counts[c] > 0 ? sums[c] / valid_counts[c] : 0.0;
    }

    cudaEventDestroy(start);
    cudaEventDestroy(stop);
    cudaFree(d_values);
    cudaFree(d_mins);
    cudaFree(d_maxs);
    cudaFree(d_sums);
    cudaFree(d_valid_counts);
    cudaFree(d_missing_counts);

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
    check_cuda(cudaSetDevice(0), "set CUDA device");
    if (opts.debug_threads) {
        check_cuda(cudaDeviceSetLimit(cudaLimitPrintfFifoSize, 256 * 1024 * 1024), "increase CUDA printf buffer");
    }

    CsvData data = !opts.csv_path.empty() ? read_csv(opts.csv_path) : generate_data(opts.generated_rows);
    if (data.headers.empty() || data.rows.empty()) {
        std::cerr << "No usable data found.\n";
        return 1;
    }

    auto total_start = std::chrono::high_resolution_clock::now();
    auto numeric_cols = detect_numeric_columns_cpu(data);
    auto matrix = make_numeric_matrix_cpu(data, numeric_cols);

    float gpu_ms = 0.0f;
    auto reports = process_numeric_gpu_only(
        data, numeric_cols, matrix, gpu_ms,
        opts.debug_threads, opts.gpu_debug_limit, opts.gpu_repeat
    );
    auto total_end = std::chrono::high_resolution_clock::now();
    double total_ms = std::chrono::duration<double, std::milli>(total_end - total_start).count();

    std::cout << "\n=== GPU Only CUDA Preprocessing Demo ===\n";
    std::cout << "Rows: " << data.rows.size() << ", Columns: " << data.headers.size() << "\n";
    std::cout << "CUDA GPU: " << prop.name << "\n";
    std::cout << "Numeric columns sent to GPU: " << numeric_cols.size() << "\n";
    std::cout << "GPU repeat count: " << opts.gpu_repeat << "\n";
    if (opts.debug_threads) {
        std::cout << "GPU thread debug: enabled, print limit="
                  << (opts.gpu_debug_limit < 0 ? std::string("ALL") : std::to_string(opts.gpu_debug_limit))
                  << " global threads per kernel\n";
    }

    std::cout << "\nGPU numeric processing:\n";
    for (const auto &r : reports) {
        std::cout << "  " << r.name
                  << " | valid=" << r.valid_count
                  << " missing=" << r.missing_count
                  << " min=" << std::fixed << std::setprecision(3) << r.min_value
                  << " max=" << r.max_value
                  << " mean=" << r.mean << "\n";
    }

    std::cout << "\nTiming:\n";
    std::cout << "  GPU kernel/copy time: " << std::fixed << std::setprecision(2) << gpu_ms << " ms\n";
    std::cout << "  Total wall time:      " << total_ms << " ms\n";
    std::cout << "\nResult: preprocessing computation path used CUDA GPU kernels only.\n";
    std::cout << "Note: CPU is still used for CSV reading and converting strings to numeric arrays.\n";

    return 0;
}
