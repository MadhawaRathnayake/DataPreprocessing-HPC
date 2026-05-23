#include <cuda_runtime.h>

#include "cuda_preprocessor.h"

#include <algorithm>
#include <chrono>
#include <cfloat>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#define THREADS_PER_BLOCK 256

struct GpuColumnStats {
    double min_value;
    double max_value;
    double mean;
    double stddev;
    int valid_count;
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

static std::vector<std::string> split_simple_csv(const std::string &line) {
    std::vector<std::string> cells;
    std::string cell;
    std::stringstream ss(line);
    while (std::getline(ss, cell, ',')) {
        if (!cell.empty() && cell.back() == '\r') cell.pop_back();
        cells.push_back(cell);
    }
    if (!line.empty() && line.back() == ',') cells.push_back("");
    return cells;
}

static std::string join_simple_csv(const std::vector<std::string> &row) {
    std::ostringstream oss;
    for (size_t i = 0; i < row.size(); i++) {
        if (i) oss << ',';
        oss << row[i];
    }
    return oss.str();
}

static bool is_missing(const std::string &v) {
    if (v.empty()) return true;
    std::string lower;
    lower.reserve(v.size());
    for (char c : v) lower.push_back((char)tolower((unsigned char)c));
    return lower == "na" || lower == "n/a" || lower == "nan" || lower == "null";
}

static bool parse_double(const std::string &s, double &out) {
    if (is_missing(s)) return false;
    char *end = NULL;
    out = strtod(s.c_str(), &end);
    return end != s.c_str() && *end == '\0' && std::isfinite(out);
}

static std::string format_double(double value) {
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(6) << value;
    return oss.str();
}

static double percentile_sorted(const std::vector<double> &values, double p) {
    if (values.empty()) return 0.0;
    double pos = p * (values.size() - 1);
    int lo = (int)floor(pos);
    int hi = (int)ceil(pos);
    if (lo == hi) return values[lo];
    double frac = pos - lo;
    return values[lo] * (1.0 - frac) + values[hi] * frac;
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

static int header_index(const std::vector<std::string> &headers, const std::string &name) {
    for (int i = 0; i < (int)headers.size(); i++) {
        if (headers[i] == name) return i;
    }
    return -1;
}

static bool config_selects_column(int col, const std::vector<std::string> &headers, char **columns, int num_columns) {
    if (!columns || num_columns <= 0) return true;
    if (col < 0 || col >= (int)headers.size()) return false;
    for (int i = 0; i < num_columns; i++) {
        if (columns[i] && headers[col] == columns[i]) return true;
    }
    return false;
}

static bool is_numeric_column(const std::vector<std::vector<std::string>> &rows, int col) {
    int checked = 0;
    int parsed = 0;
    for (const auto &row : rows) {
        if (col >= (int)row.size()) continue;
        checked++;
        double v = 0.0;
        if (parse_double(row[col], v)) parsed++;
    }
    return checked > 0 && ((double)parsed / checked) > 0.5;
}

static std::string duplicate_key(const std::vector<std::string> &row, const std::vector<int> &cols, bool exact) {
    if (exact) return join_simple_csv(row);
    std::ostringstream oss;
    for (size_t i = 0; i < cols.size(); i++) {
        if (i) oss << '\x1f';
        int col = cols[i];
        if (col >= 0 && col < (int)row.size()) oss << row[col];
    }
    return oss.str();
}

static int remove_duplicates_configured(
    std::vector<std::vector<std::string>> &rows,
    const std::vector<std::string> &headers,
    DuplicateConfig *cfg
) {
    if (rows.empty()) return 0;

    bool exact = !cfg || cfg->action == 0 || !cfg->columns || cfg->num_columns <= 0;
    std::vector<int> cols;
    if (!exact) {
        for (int c = 0; c < (int)headers.size(); c++) {
            if (config_selects_column(c, headers, cfg->columns, cfg->num_columns)) cols.push_back(c);
        }
        if (cols.empty()) exact = true;
    }

    int keep = cfg ? cfg->keep : 0;
    std::unordered_map<std::string, int> counts;
    std::unordered_set<std::string> emitted;
    for (const auto &row : rows) counts[duplicate_key(row, cols, exact)]++;

    std::vector<std::vector<std::string>> out;
    out.reserve(rows.size());
    if (keep == 1) {
        for (int i = (int)rows.size() - 1; i >= 0; i--) {
            std::string key = duplicate_key(rows[i], cols, exact);
            if (emitted.insert(key).second) out.push_back(std::move(rows[i]));
        }
        std::reverse(out.begin(), out.end());
    } else if (keep == 2) {
        for (auto &row : rows) {
            if (counts[duplicate_key(row, cols, exact)] == 1) out.push_back(std::move(row));
        }
    } else {
        for (auto &row : rows) {
            std::string key = duplicate_key(row, cols, exact);
            if (emitted.insert(key).second) out.push_back(std::move(row));
        }
    }

    int removed = (int)rows.size() - (int)out.size();
    rows.swap(out);
    return removed;
}

static std::string mode_replacement(const std::vector<std::vector<std::string>> &rows, int col) {
    std::unordered_map<std::string, int> counts;
    std::string best;
    int best_count = -1;
    for (const auto &row : rows) {
        if (col >= (int)row.size() || is_missing(row[col])) continue;
        int count = ++counts[row[col]];
        if (count > best_count) {
            best = row[col];
            best_count = count;
        }
    }
    return best.empty() ? "UNKNOWN" : best;
}

static std::string mean_replacement(const std::vector<std::vector<std::string>> &rows, int col) {
    double sum = 0.0;
    int count = 0;
    for (const auto &row : rows) {
        double v = 0.0;
        if (col < (int)row.size() && parse_double(row[col], v)) {
            sum += v;
            count++;
        }
    }
    return count > 0 ? format_double(sum / count) : "0";
}

static std::string median_replacement(const std::vector<std::vector<std::string>> &rows, int col) {
    std::vector<double> values = collect_numeric_values(rows, col);
    if (values.empty()) return "0";
    std::sort(values.begin(), values.end());
    return format_double(percentile_sorted(values, 0.5));
}

static void drop_columns_by_index(
    std::vector<std::vector<std::string>> &rows,
    std::vector<std::string> &headers,
    const std::vector<int> &drop_cols
) {
    if (drop_cols.empty()) return;
    std::vector<int> drop(headers.size(), 0);
    for (int col : drop_cols) {
        if (col >= 0 && col < (int)drop.size()) drop[col] = 1;
    }

    std::vector<std::string> new_headers;
    for (int c = 0; c < (int)headers.size(); c++) {
        if (!drop[c]) new_headers.push_back(headers[c]);
    }

    for (auto &row : rows) {
        row.resize(headers.size());
        std::vector<std::string> new_row;
        new_row.reserve(new_headers.size());
        for (int c = 0; c < (int)headers.size(); c++) {
            if (!drop[c]) new_row.push_back(row[c]);
        }
        row.swap(new_row);
    }
    headers.swap(new_headers);
}

static int apply_missing_values(
    std::vector<std::vector<std::string>> &rows,
    std::vector<std::string> &headers,
    MissingConfig *cfg
) {
    if (!cfg || cfg->num_configs <= 0 || rows.empty()) return 0;
    int changed = 0;

    for (auto &row : rows) row.resize(headers.size());

    std::vector<int> drop_cols;
    if (cfg->drop_threshold >= 0.0 && cfg->drop_threshold <= 100.0) {
        for (int col = 0; col < (int)headers.size(); col++) {
            int missing = 0;
            for (const auto &row : rows) {
                if (col >= (int)row.size() || is_missing(row[col])) missing++;
            }
            double pct = rows.empty() ? 0.0 : (100.0 * missing / rows.size());
            if (pct > cfg->drop_threshold) drop_cols.push_back(col);
        }
    }
    drop_columns_by_index(rows, headers, drop_cols);

    std::vector<int> drop_rows(rows.size(), 0);
    for (int i = 0; i < cfg->num_configs; i++) {
        ColumnMissingConfig &mc = cfg->configs[i];
        if (!mc.column_name) continue;
        int col = header_index(headers, mc.column_name);
        if (col < 0 || mc.strategy != 0) continue;
        for (int r = 0; r < (int)rows.size(); r++) {
            if (col < (int)rows[r].size() && is_missing(rows[r][col])) drop_rows[r] = 1;
        }
    }

    std::vector<std::vector<std::string>> kept;
    kept.reserve(rows.size());
    for (int r = 0; r < (int)rows.size(); r++) {
        if (!drop_rows[r]) kept.push_back(std::move(rows[r]));
        else changed++;
    }
    rows.swap(kept);

    for (int i = 0; i < cfg->num_configs; i++) {
        ColumnMissingConfig &mc = cfg->configs[i];
        if (!mc.column_name || mc.strategy == 0) continue;
        int col = header_index(headers, mc.column_name);
        if (col < 0) continue;

        std::string replacement;
        if (mc.strategy == 1) replacement = mean_replacement(rows, col);
        else if (mc.strategy == 2) replacement = median_replacement(rows, col);
        else if (mc.strategy == 3) replacement = mode_replacement(rows, col);
        else if (mc.strategy == 4) replacement = mc.fill_value ? mc.fill_value : "";
        else if (mc.strategy == 5) replacement = mode_replacement(rows, col);
        else replacement = "";

        std::string previous;
        for (auto &row : rows) {
            row.resize(headers.size());
            if (is_missing(row[col])) {
                row[col] = (mc.strategy == 5 && !previous.empty()) ? previous : replacement;
                changed++;
            } else {
                previous = row[col];
            }
        }
    }
    return changed;
}

static int config_column_position(const std::string &name, char **columns, int num_columns) {
    if (!columns || num_columns <= 0) return -1;
    for (int i = 0; i < num_columns; i++) {
        if (columns[i] && name == columns[i]) return i;
    }
    return -1;
}

static int apply_encoding_columns(
    std::vector<std::vector<std::string>> &rows,
    std::vector<std::string> &headers,
    EncodingConfig *cfg
) {
    if (!cfg || !cfg->columns || cfg->num_columns <= 0) return 0;

    int original_cols = (int)headers.size();
    std::vector<int> selected_pos(original_cols, -1);
    for (int col = 0; col < original_cols; col++) {
        selected_pos[col] = config_column_position(headers[col], cfg->columns, cfg->num_columns);
    }

    std::vector<std::unordered_map<std::string, int>> label_maps(original_cols);
    std::vector<std::vector<std::string>> onehot_values(original_cols);
    int encoded = 0;

    for (int col = 0; col < original_cols; col++) {
        int pos = selected_pos[col];
        if (pos < 0) continue;
        int method = cfg->methods ? cfg->methods[pos] : cfg->method;
        encoded++;
        if (method == 1) {
            std::unordered_set<std::string> seen;
            for (const auto &row : rows) {
                std::string value = col < (int)row.size() ? row[col] : "";
                if (seen.insert(value).second) onehot_values[col].push_back(value);
            }
        } else {
            int next_id = 0;
            for (const auto &row : rows) {
                std::string value = col < (int)row.size() ? row[col] : "";
                if (label_maps[col].find(value) == label_maps[col].end()) {
                    label_maps[col][value] = next_id++;
                }
            }
        }
    }

    std::vector<std::string> new_headers;
    for (int col = 0; col < original_cols; col++) {
        int pos = selected_pos[col];
        int method = pos >= 0 && cfg->methods ? cfg->methods[pos] : cfg->method;
        if (pos < 0 || method == 0 || !cfg->drop_original) new_headers.push_back(headers[col]);
        if (pos >= 0 && method == 1) {
            for (const auto &value : onehot_values[col]) new_headers.push_back(headers[col] + "_" + value);
        }
    }

    for (auto &row : rows) {
        row.resize(original_cols);
        std::vector<std::string> new_row;
        new_row.reserve(new_headers.size());
        for (int col = 0; col < original_cols; col++) {
            int pos = selected_pos[col];
            int method = pos >= 0 && cfg->methods ? cfg->methods[pos] : cfg->method;
            std::string value = row[col];
            if (pos < 0) {
                new_row.push_back(value);
            } else if (method == 0) {
                new_row.push_back(std::to_string(label_maps[col][value]));
            } else {
                if (!cfg->drop_original) new_row.push_back(value);
                for (const auto &category : onehot_values[col]) {
                    new_row.push_back(value == category ? "1" : "0");
                }
            }
        }
        row.swap(new_row);
    }

    headers.swap(new_headers);
    return encoded;
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
            double sq = 0.0;
            for (double v : values) sq += (v - mean) * (v - mean);
            double stddev = sqrt(sq / values.size());
            double threshold = cfg->threshold > 0.0 ? cfg->threshold : 3.0;
            lower = mean - threshold * stddev;
            upper = mean + threshold * stddev;
        } else {
            std::sort(values.begin(), values.end());
            double q1 = percentile_sorted(values, 0.25);
            double q3 = percentile_sorted(values, 0.75);
            double iqr = q3 - q1;
            double threshold = cfg->threshold > 0.0 ? cfg->threshold : 1.5;
            lower = q1 - threshold * iqr;
            upper = q3 + threshold * iqr;
        }

        std::vector<int> col_flags(rows.size(), 0);
        for (int r = 0; r < (int)rows.size(); r++) {
            double v = 0.0;
            if (col >= (int)rows[r].size() || !parse_double(rows[r][col], v)) continue;
            if (v < lower || v > upper) {
                outlier_events++;
                if (cfg->treatment == 0) {
                    row_remove[r] = 1;
                } else if (cfg->treatment == 1) {
                    rows[r][col] = format_double(v < lower ? lower : upper);
                } else if (cfg->treatment == 2) {
                    col_flags[r] = 1;
                }
            }
        }

        if (cfg->treatment == 2) {
            flag_headers.push_back(headers[col] + "_outlier_flag");
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
    } else if (cfg->treatment == 2 && !flag_values.empty()) {
        for (const auto &h : flag_headers) headers.push_back(h);
        for (int r = 0; r < (int)rows.size(); r++) {
            for (const auto &flags : flag_values) {
                rows[r].push_back(flags[r] ? "1" : "0");
            }
        }
    }

    return outlier_events;
}

static int apply_cpu_robust_scaling(
    std::vector<std::vector<std::string>> &rows,
    const std::vector<std::string> &headers,
    ScalingConfig *cfg
) {
    if (!cfg || rows.empty()) return 0;
    int scaled = 0;
    for (int col = 0; col < (int)headers.size(); col++) {
        if (!config_selects_column(col, headers, cfg->columns, cfg->num_columns)) continue;
        if (!is_numeric_column(rows, col)) continue;

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
            if (col < (int)row.size() && parse_double(row[col], v)) {
                row[col] = format_double((v - median) / iqr);
            }
        }
        scaled++;
    }
    return scaled;
}

static std::vector<int> selected_numeric_columns(
    const std::vector<std::vector<std::string>> &rows,
    const std::vector<std::string> &headers,
    ScalingConfig *scaling_cfg
) {
    std::vector<int> cols;
    for (int c = 0; c < (int)headers.size(); c++) {
        if (config_selects_column(c, headers, scaling_cfg ? scaling_cfg->columns : NULL, scaling_cfg ? scaling_cfg->num_columns : 0)
            && is_numeric_column(rows, c)) {
            cols.push_back(c);
        }
    }
    return cols;
}

__global__ void stats_kernel(
    const double *values,
    int rows,
    int cols,
    double *mins,
    double *maxs,
    double *sums,
    double *sumsq,
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

    for (int r = tid; r < rows; r += blockDim.x) {
        double v = values[(size_t)col * rows + r];
        if (!isnan(v)) {
            local_min = fmin(local_min, v);
            local_max = fmax(local_max, v);
            local_sum += v;
            local_sumsq += v * v;
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
        mins[col] = s_valid[0] ? s_min[0] : 0.0;
        maxs[col] = s_valid[0] ? s_max[0] : 0.0;
        sums[col] = s_sum[0];
        sumsq[col] = s_sumsq[0];
        valids[col] = s_valid[0];
    }
}

__global__ void finalize_stats_kernel(
    int cols,
    const double *mins,
    const double *maxs,
    const double *sums,
    const double *sumsq,
    const int *valids,
    GpuColumnStats *stats
) {
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    if (col >= cols) return;
    int n = valids[col];
    double mean = n ? sums[col] / n : 0.0;
    double variance = n ? fmax(0.0, (sumsq[col] / n) - (mean * mean)) : 0.0;
    stats[col].min_value = mins[col];
    stats[col].max_value = maxs[col];
    stats[col].mean = mean;
    stats[col].stddev = sqrt(variance);
    stats[col].valid_count = n;
}

__global__ void impute_cap_scale_kernel(
    double *values,
    int rows,
    int cols,
    const GpuColumnStats *stats,
    double z_threshold,
    int scale_method,
    int *missing_filled,
    int *outliers_capped
) {
    (void)z_threshold;
    (void)missing_filled;
    (void)outliers_capped;
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int total = rows * cols;
    if (idx >= total) return;

    int col = idx / rows;
    GpuColumnStats st = stats[col];
    double v = values[idx];
    if (isnan(v)) return;

    if (scale_method == 1) {
        if (st.stddev > 0.0) v = (v - st.mean) / st.stddev;
    } else {
        double range = st.max_value - st.min_value;
        if (range > 0.0) v = (v - st.min_value) / range;
    }

    values[idx] = v;
}

static int apply_columnar_gpu_numeric(
    std::vector<std::vector<std::string>> &rows,
    const std::vector<std::string> &headers,
    ScalingConfig *scaling_cfg,
    int *missing_filled,
    int *outliers_capped
) {
    *missing_filled = 0;
    *outliers_capped = 0;
    if (!scaling_cfg || scaling_cfg->method == 2 || rows.empty()) return 0;

    std::vector<int> numeric_cols = selected_numeric_columns(rows, headers, scaling_cfg);
    if (numeric_cols.empty()) return 0;

    int row_count = (int)rows.size();
    int gpu_cols = (int)numeric_cols.size();
    std::vector<double> host_values((size_t)row_count * gpu_cols, std::numeric_limits<double>::quiet_NaN());

    for (int c = 0; c < gpu_cols; c++) {
        int source_col = numeric_cols[c];
        for (int r = 0; r < row_count; r++) {
            double v = 0.0;
            if (source_col < (int)rows[r].size() && parse_double(rows[r][source_col], v)) {
                host_values[(size_t)c * row_count + r] = v;
            }
        }
    }

    double *d_values = NULL;
    double *d_mins = NULL;
    double *d_maxs = NULL;
    double *d_sums = NULL;
    double *d_sumsq = NULL;
    int *d_valids = NULL;
    GpuColumnStats *d_stats = NULL;
    int *d_missing = NULL;
    int *d_outliers = NULL;

    check_cuda(cudaMalloc(&d_values, host_values.size() * sizeof(double)), "alloc values");
    check_cuda(cudaMalloc(&d_mins, gpu_cols * sizeof(double)), "alloc mins");
    check_cuda(cudaMalloc(&d_maxs, gpu_cols * sizeof(double)), "alloc maxs");
    check_cuda(cudaMalloc(&d_sums, gpu_cols * sizeof(double)), "alloc sums");
    check_cuda(cudaMalloc(&d_sumsq, gpu_cols * sizeof(double)), "alloc sumsq");
    check_cuda(cudaMalloc(&d_valids, gpu_cols * sizeof(int)), "alloc valids");
    check_cuda(cudaMalloc(&d_stats, gpu_cols * sizeof(GpuColumnStats)), "alloc stats");
    check_cuda(cudaMalloc(&d_missing, sizeof(int)), "alloc missing counter");
    check_cuda(cudaMalloc(&d_outliers, sizeof(int)), "alloc outlier counter");
    check_cuda(cudaMemset(d_missing, 0, sizeof(int)), "reset missing counter");
    check_cuda(cudaMemset(d_outliers, 0, sizeof(int)), "reset outlier counter");

    check_cuda(cudaMemcpy(d_values, host_values.data(), host_values.size() * sizeof(double), cudaMemcpyHostToDevice), "copy values h2d");
    stats_kernel<<<gpu_cols, THREADS_PER_BLOCK>>>(d_values, row_count, gpu_cols, d_mins, d_maxs, d_sums, d_sumsq, d_valids);
    check_cuda(cudaGetLastError(), "stats kernel");
    finalize_stats_kernel<<<1, THREADS_PER_BLOCK>>>(gpu_cols, d_mins, d_maxs, d_sums, d_sumsq, d_valids, d_stats);
    check_cuda(cudaGetLastError(), "finalize stats kernel");

    int scale_method = scaling_cfg->method == 1 ? 1 : 0;
    int total_values = row_count * gpu_cols;
    int blocks = (total_values + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
    impute_cap_scale_kernel<<<blocks, THREADS_PER_BLOCK>>>(
        d_values, row_count, gpu_cols, d_stats, 0.0, scale_method, d_missing, d_outliers
    );
    check_cuda(cudaGetLastError(), "impute cap scale kernel");
    check_cuda(cudaMemcpy(host_values.data(), d_values, host_values.size() * sizeof(double), cudaMemcpyDeviceToHost), "copy values d2h");
    check_cuda(cudaMemcpy(missing_filled, d_missing, sizeof(int), cudaMemcpyDeviceToHost), "copy missing counter");
    check_cuda(cudaMemcpy(outliers_capped, d_outliers, sizeof(int), cudaMemcpyDeviceToHost), "copy outlier counter");

    for (int c = 0; c < gpu_cols; c++) {
        int dest_col = numeric_cols[c];
        for (int r = 0; r < row_count; r++) {
            rows[r][dest_col] = format_double(host_values[(size_t)c * row_count + r]);
        }
    }

    cudaFree(d_values);
    cudaFree(d_mins);
    cudaFree(d_maxs);
    cudaFree(d_sums);
    cudaFree(d_sumsq);
    cudaFree(d_valids);
    cudaFree(d_stats);
    cudaFree(d_missing);
    cudaFree(d_outliers);
    return gpu_cols;
}

extern "C" PreprocessedData* preprocess_cuda(
    char **raw_data,
    char **headers,
    int num_rows,
    int num_cols,
    int should_remove_duplicates,
    DuplicateConfig *duplicate_cfg,
    MissingConfig *missing_cfg,
    OutlierConfig *outlier_cfg,
    ScalingConfig *scaling_cfg,
    EncodingConfig *encoding_cfg
) {
    auto start = std::chrono::high_resolution_clock::now();

    PreprocessedData *result = (PreprocessedData*)calloc(1, sizeof(PreprocessedData));
    if (!result) return NULL;

    std::vector<std::string> header_vec;
    header_vec.reserve(num_cols);
    for (int c = 0; c < num_cols; c++) header_vec.push_back(headers && headers[c] ? headers[c] : "");

    std::vector<std::vector<std::string>> rows(num_rows);
    for (int r = 0; r < num_rows; r++) {
        rows[r] = split_simple_csv(raw_data && raw_data[r] ? raw_data[r] : "");
        rows[r].resize(num_cols);
    }

    if (should_remove_duplicates) {
        result->duplicates_found = remove_duplicates_configured(rows, header_vec, duplicate_cfg);
    }

    result->missing_filled = apply_missing_values(rows, header_vec, missing_cfg);
    result->outliers_removed = apply_outliers(rows, header_vec, outlier_cfg);

    int gpu_missing = 0;
    int gpu_outliers = 0;
    if (scaling_cfg && scaling_cfg->method == 2) {
        result->columns_scaled = apply_cpu_robust_scaling(rows, header_vec, scaling_cfg);
    } else {
        result->columns_scaled = apply_columnar_gpu_numeric(
            rows, header_vec, scaling_cfg, &gpu_missing, &gpu_outliers
        );
    }
    result->columns_encoded = apply_encoding_columns(rows, header_vec, encoding_cfg);

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

    auto stop = std::chrono::high_resolution_clock::now();
    result->processing_time_ms = std::chrono::duration<double, std::milli>(stop - start).count();
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
