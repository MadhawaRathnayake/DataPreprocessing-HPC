#include "cuda_analyzer.h"
#include <float.h>
#include <thrust/device_vector.h>
#include <thrust/sort.h>

static int is_numeric(const char *str) {
    if (!str || *str == '\0') return 0;
    char *endptr;
    strtod(str, &endptr);
    while (*endptr && isspace((unsigned char)*endptr)) endptr++;
    return *endptr == '\0';
}

static int is_null(const char *str) {
    if (!str) return 1;
    while (*str && isspace((unsigned char)*str)) str++;
    if (*str == '\0') return 1;

    if (strcasecmp(str, "null") == 0 ||
        strcasecmp(str, "na") == 0 ||
        strcasecmp(str, "n/a") == 0 ||
        strcasecmp(str, "nan") == 0) {
        return 1;
    }
    return 0;
}

static int compare_value_counts(const void *a, const void *b) {
    return ((ValueCount*)b)->count - ((ValueCount*)a)->count;
}

__device__ double atomicMinDouble(double* address, double val) {
    unsigned long long int* address_as_ull = (unsigned long long int*)address;
    unsigned long long int old = *address_as_ull, assumed;

    do {
        assumed = old;
        old = atomicCAS(address_as_ull, assumed,
                        __double_as_longlong(fmin(val, __longlong_as_double(assumed))));
    } while (assumed != old);

    return __longlong_as_double(old);
}

__device__ double atomicMaxDouble(double* address, double val) {
    unsigned long long int* address_as_ull = (unsigned long long int*)address;
    unsigned long long int old = *address_as_ull, assumed;

    do {
        assumed = old;
        old = atomicCAS(address_as_ull, assumed,
                        __double_as_longlong(fmax(val, __longlong_as_double(assumed))));
    } while (assumed != old);

    return __longlong_as_double(old);
}

__global__ void reduce_stats_kernel(const double *data, int n,
                                    double *d_min, double *d_max,
                                    double *d_sum, double *d_sumsq) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) {
        double v = data[i];
        atomicMinDouble(d_min, v);
        atomicMaxDouble(d_max, v);
        atomicAdd(d_sum, v);
        atomicAdd(d_sumsq, v * v);
    }
}

DatasetStats* analyzer_cuda_create_stats(int num_columns) {
    if (num_columns <= 0) return NULL;

    DatasetStats *stats = (DatasetStats*)malloc(sizeof(DatasetStats));
    if (!stats) return NULL;

    stats->num_columns = num_columns;
    stats->columns = (ColumnStats*)calloc(num_columns, sizeof(ColumnStats));
    stats->processing_time = 0.0;
    stats->gpu_used = 0;

    if (!stats->columns) {
        free(stats);
        return NULL;
    }

    return stats;
}

void analyzer_cuda_free_stats(DatasetStats *stats) {
    if (!stats) return;

    for (int i = 0; i < stats->num_columns; i++) {
        free(stats->columns[i].column_name);
        free(stats->columns[i].outliers);

        if (stats->columns[i].value_counts) {
            for (int j = 0; j < stats->columns[i].value_count_size; j++) {
                free(stats->columns[i].value_counts[j].value);
            }
            free(stats->columns[i].value_counts);
        }
    }

    free(stats->columns);
    free(stats);
}

static int analyze_numeric_cuda(double *numeric_values, int numeric_count, ColumnStats *stats) {
    if (numeric_count <= 0) return -1;

    double *d_data = NULL, *d_min = NULL, *d_max = NULL, *d_sum = NULL, *d_sumsq = NULL;

    cudaMalloc((void**)&d_data, numeric_count * sizeof(double));
    cudaMalloc((void**)&d_min, sizeof(double));
    cudaMalloc((void**)&d_max, sizeof(double));
    cudaMalloc((void**)&d_sum, sizeof(double));
    cudaMalloc((void**)&d_sumsq, sizeof(double));

    double init_min = DBL_MAX;
    double init_max = -DBL_MAX;
    double init_zero = 0.0;

    cudaMemcpy(d_data, numeric_values, numeric_count * sizeof(double), cudaMemcpyHostToDevice);
    cudaMemcpy(d_min, &init_min, sizeof(double), cudaMemcpyHostToDevice);
    cudaMemcpy(d_max, &init_max, sizeof(double), cudaMemcpyHostToDevice);
    cudaMemcpy(d_sum, &init_zero, sizeof(double), cudaMemcpyHostToDevice);
    cudaMemcpy(d_sumsq, &init_zero, sizeof(double), cudaMemcpyHostToDevice);

    int threads = 256;
    int blocks = (numeric_count + threads - 1) / threads;
    reduce_stats_kernel<<<blocks, threads>>>(d_data, numeric_count, d_min, d_max, d_sum, d_sumsq);
    cudaDeviceSynchronize();

    double min_val, max_val, sum, sumsq;
    cudaMemcpy(&min_val, d_min, sizeof(double), cudaMemcpyDeviceToHost);
    cudaMemcpy(&max_val, d_max, sizeof(double), cudaMemcpyDeviceToHost);
    cudaMemcpy(&sum, d_sum, sizeof(double), cudaMemcpyDeviceToHost);
    cudaMemcpy(&sumsq, d_sumsq, sizeof(double), cudaMemcpyDeviceToHost);

    stats->min_value = min_val;
    stats->max_value = max_val;
    stats->mean = sum / numeric_count;

    double variance = (sumsq / numeric_count) - (stats->mean * stats->mean);
    if (variance < 0.0) variance = 0.0;
    stats->std_dev = sqrt(variance);

    thrust::device_vector<double> dvec(numeric_values, numeric_values + numeric_count);
    thrust::sort(dvec.begin(), dvec.end());
    thrust::copy(dvec.begin(), dvec.end(), numeric_values);

    if (numeric_count % 2 == 0) {
        stats->median = (numeric_values[numeric_count / 2 - 1] +
                         numeric_values[numeric_count / 2]) / 2.0;
    } else {
        stats->median = numeric_values[numeric_count / 2];
    }

    int q1_idx = numeric_count / 4;
    int q3_idx = (3 * numeric_count) / 4;
    double q1 = numeric_values[q1_idx];
    double q3 = numeric_values[q3_idx];
    double iqr = q3 - q1;
    double lower_bound = q1 - 1.5 * iqr;
    double upper_bound = q3 + 1.5 * iqr;

    stats->outliers = (double*)malloc(MAX_OUTLIERS * sizeof(double));
    stats->outlier_count = 0;
    stats->has_outliers = 0;

    if (stats->outliers) {
        for (int i = 0; i < numeric_count && stats->outlier_count < MAX_OUTLIERS; i++) {
            if (numeric_values[i] < lower_bound || numeric_values[i] > upper_bound) {
                stats->outliers[stats->outlier_count++] = numeric_values[i];
            }
        }
        stats->has_outliers = (stats->outlier_count > 0);
    }

    cudaFree(d_data);
    cudaFree(d_min);
    cudaFree(d_max);
    cudaFree(d_sum);
    cudaFree(d_sumsq);

    return 0;
}

static void analyze_column(char **column_data, int num_rows,
                           const char *col_name, ColumnStats *stats) {
    stats->column_name = (char*)malloc(strlen(col_name) + 1);
    strcpy(stats->column_name, col_name);

    stats->total_count = num_rows;
    stats->null_count = 0;
    stats->unique_count = 0;
    stats->outlier_count = 0;
    stats->has_nulls = 0;
    stats->has_outliers = 0;
    stats->has_duplicates = 0;
    stats->type_consistent = 1;
    stats->outliers = NULL;
    stats->value_counts = NULL;
    stats->value_count_size = 0;

    double *numeric_values = (double*)malloc(num_rows * sizeof(double));
    char **unique_values = (char**)malloc(num_rows * sizeof(char*));
    int *unique_counts = (int*)calloc(num_rows, sizeof(int));

    int numeric_count = 0;
    int categorical_count = 0;

    for (int i = 0; i < num_rows; i++) {
        char *value = column_data[i];

        if (is_null(value)) {
            stats->null_count++;
            continue;
        }

        if (is_numeric(value)) {
            numeric_values[numeric_count++] = atof(value);
        } else {
            categorical_count++;
        }

        int found = 0;
        for (int j = 0; j < stats->unique_count; j++) {
            if (strcmp(unique_values[j], value) == 0) {
                unique_counts[j]++;
                found = 1;
                break;
            }
        }

        if (!found) {
            unique_values[stats->unique_count] = (char*)malloc(strlen(value) + 1);
            strcpy(unique_values[stats->unique_count], value);
            unique_counts[stats->unique_count] = 1;
            stats->unique_count++;
        }
    }

    stats->null_percentage = (num_rows > 0) ? ((double)stats->null_count / num_rows) * 100.0 : 0.0;
    stats->has_nulls = (stats->null_count > 0);
    stats->has_duplicates = (stats->unique_count < (num_rows - stats->null_count));

    if (numeric_count > 0 && categorical_count == 0) {
        stats->data_type = TYPE_NUMERIC;
    } else if (categorical_count > 0 && numeric_count == 0) {
        stats->data_type = TYPE_CATEGORICAL;
    } else if (numeric_count > 0 && categorical_count > 0) {
        stats->data_type = TYPE_MIXED;
        stats->type_consistent = 0;
    } else {
        stats->data_type = TYPE_UNKNOWN;
    }

    if (stats->data_type == TYPE_NUMERIC && numeric_count > 0) {
        analyze_numeric_cuda(numeric_values, numeric_count, stats);

        if (stats->unique_count == 2) stats->category = CAT_BINARY;
        else if (stats->unique_count < 10) stats->category = CAT_DISCRETE;
        else stats->category = CAT_CONTINUOUS;
    } else {
        stats->min_value = 0.0;
        stats->max_value = 0.0;
        stats->mean = 0.0;
        stats->median = 0.0;
        stats->std_dev = 0.0;
        stats->outlier_count = 0;
        stats->has_outliers = 0;

        if (stats->unique_count == 2) stats->category = CAT_BINARY;
        else if (stats->data_type == TYPE_UNKNOWN) stats->category = CAT_UNKNOWN;
        else stats->category = CAT_NOMINAL;
    }

    stats->value_count_size = (stats->unique_count < 10) ? stats->unique_count : 10;

    if (stats->value_count_size > 0) {
        stats->value_counts = (ValueCount*)malloc(stats->value_count_size * sizeof(ValueCount));
        ValueCount *temp_counts = (ValueCount*)malloc(stats->unique_count * sizeof(ValueCount));

        for (int i = 0; i < stats->unique_count; i++) {
            temp_counts[i].value = unique_values[i];
            temp_counts[i].count = unique_counts[i];
        }

        qsort(temp_counts, stats->unique_count, sizeof(ValueCount), compare_value_counts);

        for (int i = 0; i < stats->value_count_size; i++) {
            stats->value_counts[i].value = (char*)malloc(strlen(temp_counts[i].value) + 1);
            strcpy(stats->value_counts[i].value, temp_counts[i].value);
            stats->value_counts[i].count = temp_counts[i].count;
        }

        free(temp_counts);
    }

    for (int i = 0; i < stats->unique_count; i++) free(unique_values[i]);
    free(unique_values);
    free(unique_counts);
    free(numeric_values);
}

int analyzer_cuda_analyze_dataset(char **data, char **headers, int num_rows,
                                  int num_cols, DatasetStats *stats) {
    if (!data || !headers || !stats) return -1;

    cudaEvent_t start, stop;
    cudaEventCreate(&start);
    cudaEventCreate(&stop);
    cudaEventRecord(start);

    int device_count = 0;
    cudaGetDeviceCount(&device_count);
    stats->gpu_used = (device_count > 0) ? 1 : 0;

    printf("Starting CUDA analysis on %d rows x %d columns...\n", num_rows, num_cols);

    for (int col = 0; col < num_cols; col++) {
        char **column_data = (char**)malloc(num_rows * sizeof(char*));
        for (int row = 0; row < num_rows; row++) {
            column_data[row] = data[row * num_cols + col];
        }

        analyze_column(column_data, num_rows, headers[col], &stats->columns[col]);
        free(column_data);

        printf("Analyzed column %d/%d: %s\n", col + 1, num_cols, headers[col]);
    }

    cudaEventRecord(stop);
    cudaEventSynchronize(stop);

    float ms = 0.0f;
    cudaEventElapsedTime(&ms, start, stop);
    stats->processing_time = ms / 1000.0;

    cudaEventDestroy(start);
    cudaEventDestroy(stop);

    printf("CUDA analysis completed in %.4f seconds. GPU used: %s\n",
           stats->processing_time, stats->gpu_used ? "Yes" : "No");

    return 0;
}

void analyzer_cuda_print_stats(DatasetStats *stats) {
    if (!stats) return;

    printf("\n=== Dataset Statistics (CUDA) ===\n");
    printf("Total columns: %d\n", stats->num_columns);
    printf("Processing time: %.4f seconds\n", stats->processing_time);
    printf("GPU used: %d\n\n", stats->gpu_used);

    for (int i = 0; i < stats->num_columns; i++) {
        ColumnStats *col = &stats->columns[i];

        printf("Column: %s\n", col->column_name);
        printf("  Data Type: ");
        switch (col->data_type) {
            case TYPE_NUMERIC: printf("Numeric\n"); break;
            case TYPE_CATEGORICAL: printf("Categorical\n"); break;
            case TYPE_MIXED: printf("Mixed\n"); break;
            default: printf("Unknown\n");
        }

        printf("  Total Count: %d\n", col->total_count);
        printf("  Null Count: %d (%.2f%%)\n", col->null_count, col->null_percentage);
        printf("  Unique Count: %d\n", col->unique_count);

        if (col->data_type == TYPE_NUMERIC) {
            printf("  Min: %.2f\n", col->min_value);
            printf("  Max: %.2f\n", col->max_value);
            printf("  Mean: %.2f\n", col->mean);
            printf("  Median: %.2f\n", col->median);
            printf("  Std Dev: %.2f\n", col->std_dev);
            printf("  Outliers: %d\n", col->outlier_count);
        }
        printf("\n");
    }
}

char* analyzer_cuda_get_stats_json(DatasetStats *stats) {
    if (!stats) return NULL;

    char *json = (char*)malloc(1000000);
    if (!json) return NULL;

    char *ptr = json;
    ptr += sprintf(ptr, "{\n");
    ptr += sprintf(ptr, "  \"processing_time\": %.4f,\n", stats->processing_time);
    ptr += sprintf(ptr, "  \"gpu_used\": %d,\n", stats->gpu_used);
    ptr += sprintf(ptr, "  \"columns\": [\n");

    for (int i = 0; i < stats->num_columns; i++) {
        ColumnStats *col = &stats->columns[i];

        ptr += sprintf(ptr, "    {\n");
        ptr += sprintf(ptr, "      \"column_name\": \"%s\",\n", col->column_name);
        ptr += sprintf(ptr, "      \"data_type\": \"%s\",\n",
                       col->data_type == TYPE_NUMERIC ? "Numeric" :
                       col->data_type == TYPE_CATEGORICAL ? "Categorical" :
                       col->data_type == TYPE_MIXED ? "Mixed" : "Unknown");
        ptr += sprintf(ptr, "      \"total_count\": %d,\n", col->total_count);
        ptr += sprintf(ptr, "      \"null_count\": %d,\n", col->null_count);
        ptr += sprintf(ptr, "      \"null_percentage\": %.2f,\n", col->null_percentage);
        ptr += sprintf(ptr, "      \"unique_count\": %d,\n", col->unique_count);

        if (col->data_type == TYPE_NUMERIC) {
            ptr += sprintf(ptr, "      \"min_value\": %.2f,\n", col->min_value);
            ptr += sprintf(ptr, "      \"max_value\": %.2f,\n", col->max_value);
            ptr += sprintf(ptr, "      \"mean\": %.2f,\n", col->mean);
            ptr += sprintf(ptr, "      \"median\": %.2f,\n", col->median);
            ptr += sprintf(ptr, "      \"std_dev\": %.2f,\n", col->std_dev);
            ptr += sprintf(ptr, "      \"outlier_count\": %d,\n", col->outlier_count);
        }

        ptr += sprintf(ptr, "      \"has_nulls\": %s,\n", col->has_nulls ? "true" : "false");
        ptr += sprintf(ptr, "      \"has_outliers\": %s,\n", col->has_outliers ? "true" : "false");
        ptr += sprintf(ptr, "      \"has_duplicates\": %s,\n", col->has_duplicates ? "true" : "false");
        ptr += sprintf(ptr, "      \"type_consistent\": %s\n", col->type_consistent ? "true" : "false");
        ptr += sprintf(ptr, "    }%s\n", (i < stats->num_columns - 1) ? "," : "");
    }

    ptr += sprintf(ptr, "  ]\n}\n");
    return json;
}
