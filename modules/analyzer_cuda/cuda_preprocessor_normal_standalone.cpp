#include "cuda_preprocessor.h"

#include <cstdlib>
#include <chrono>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

extern "C" double cuda_preprocessor_get_last_cuda_work_time_ms();
extern "C" void cuda_preprocessor_configure_routing(int mode, long long cpu_threshold, long long hybrid_threshold, int cpu_threads);
extern "C" const char* cuda_preprocessor_get_last_backend();
extern "C" long long cuda_preprocessor_get_last_numeric_work();

static std::vector<std::string> split_simple_csv(const std::string &row) {
    std::vector<std::string> cells;
    std::string cell;
    bool in_quotes = false;

    for (char c : row) {
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
    headers = split_simple_csv(line);

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

static int scaling_method_from_name(const std::string &name) {
    if (name == "none") return -1;
    if (name == "zscore") return 1;
    if (name == "robust") return 2;
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        std::cerr
            << "Usage: " << argv[0]
            << " input.csv output.csv [scale: none|minmax|zscore|robust] [remove_duplicates: 0|1]"
            << " [mode: auto|cpu|normal|hybrid] [threads] [cpu_threshold] [hybrid_threshold]\n";
        return 1;
    }

    std::string input_path = argv[1];
    std::string output_path = argv[2];
    std::string scale_name = argc >= 4 ? argv[3] : "minmax";
    int remove_duplicates = argc >= 5 ? std::atoi(argv[4]) : 0;
    std::string mode_name = argc >= 6 ? argv[5] : "auto";
    int threads = argc >= 7 ? std::atoi(argv[6]) : 8;
    long long cpu_threshold = argc >= 8 ? std::atoll(argv[7]) : 250000;
    long long hybrid_threshold = argc >= 9 ? std::atoll(argv[8]) : 700000;

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

    int route_mode = 0;
    if (mode_name == "cpu") route_mode = 1;
    else if (mode_name == "normal") route_mode = 2;
    else if (mode_name == "hybrid") route_mode = 3;
    cuda_preprocessor_configure_routing(route_mode, cpu_threshold, hybrid_threshold, threads);

    auto preprocess_start = std::chrono::high_resolution_clock::now();
    PreprocessedData *result = preprocess_cuda(
        row_ptrs.data(),
        header_ptrs.data(),
        (int)row_ptrs.size(),
        (int)header_ptrs.size(),
        remove_duplicates,
        NULL,
        scaling_ptr,
        NULL
    );
    auto preprocess_stop = std::chrono::high_resolution_clock::now();
    double preprocess_wall_ms = std::chrono::duration<double, std::milli>(
        preprocess_stop - preprocess_start
    ).count();

    if (!result) {
        std::cerr << "Normal CUDA preprocessing failed.\n";
        return 1;
    }

    if (!write_preprocessed_csv(output_path, result)) {
        std::cerr << "Failed to write CSV: " << output_path << "\n";
        free_preprocessed_data(result);
        return 1;
    }

    char *json = preprocess_to_json(result);
    std::cout << "Merged CUDA standalone preprocessor\n";
    std::cout << "Input rows: " << row_vec.size() << ", input columns: " << header_vec.size() << "\n";
    std::cout << "Output: " << output_path << "\n";
    std::cout << "Backend used: " << cuda_preprocessor_get_last_backend() << "\n";
    std::cout << "Numeric work: " << cuda_preprocessor_get_last_numeric_work() << "\n";
    std::cout << "Preprocess wall time ms: " << preprocess_wall_ms << "\n";
    std::cout << "CUDA work time ms: " << cuda_preprocessor_get_last_cuda_work_time_ms() << "\n";
    std::cout << "Reported processing time ms: " << result->processing_time_ms << "\n";
    if (json) {
        std::cout << json << "\n";
        free(json);
    }

    free_preprocessed_data(result);
    return 0;
}
