/*
 * Serial Preprocessing Implementation
 * Performs all preprocessing operations sequentially
 * 
 * Memory Management Strategy:
 * - All rows are allocated with a uniform MAX_ROW_SIZE (16KB)
 * - This prevents buffer overflows during imputation/scaling/encoding
 * - String parsing uses manual strchr to handle empty cells (,,) correctly
 */

#include "preprocessor.h"
#include <time.h>
#include <stdarg.h>
#include <ctype.h>

#define MAX_ROW_SIZE 16384

/* Simple logging function that writes to a file in the current directory */
static void log_msg(const char *fmt, ...) {
    FILE *logfile = fopen("preprocess_debug.log", "a");
    if (!logfile) return;
    
    va_list args;
    va_start(args, fmt);
    vfprintf(logfile, fmt, args);
    va_end(args);
    fprintf(logfile, "\n");
    fflush(logfile);
    fclose(logfile);
}

/* Helper: Check if string is numeric (robust version) */
static int is_numeric(const char *str) {
    if (!str || *str == '\0') return 0;
    
    const char *p = str;
    /* Skip leading whitespace */
    while (isspace((unsigned char)*p)) p++;
    
    if (*p == '-' || *p == '+') p++;
    if (*p == '\0') return 0;
    
    int has_dot = 0;
    int has_digit = 0;
    while (*p) {
        if (*p == '.') {
            if (has_dot) return 0;
            has_dot = 1;
        } else if (isdigit((unsigned char)*p)) {
            has_digit = 1;
        } else {
            /* Check if we reached trailing whitespace or end of field */
            if (isspace((unsigned char)*p)) break;
            return 0;
        }
        p++;
    }
    return has_digit;
}

/* Helper: Check if value is null/missing (robust version) */
static int is_missing(const char *val) {
    if (!val) return 1;
    
    const char *p = val;
    /* Skip whitespace */
    while (isspace((unsigned char)*p)) p++;
    
    if (*p == '\0') return 1;
    if (strcmp(p, "NA") == 0 || strcmp(p, "N/A") == 0) return 1;
    
    /* Case-insensitive check for nan and null */
    if (strncasecmp(p, "nan", 3) == 0 || strncasecmp(p, "null", 4) == 0) return 1;
    
    return 0;
}

/* Helper: Deep copy data array with uniform large buffer sizes to prevent overflows */
static char** copy_data(char **data, int num_rows, int num_cols) {
    log_msg("[copy_data] Starting: %d rows, %d cols", num_rows, num_cols);
    
    char **copy = (char**)malloc(num_rows * sizeof(char*));
    if (!copy) {
        log_msg("[copy_data ERROR] malloc failed for %d row pointers", num_rows);
        return NULL;
    }
    
    for (int i = 0; i < num_rows; i++) {
        copy[i] = (char*)malloc(MAX_ROW_SIZE);
        if (!copy[i]) {
            log_msg("[copy_data ERROR] malloc failed at row %d", i);
            for (int j = 0; j < i; j++) free(copy[j]);
            free(copy);
            return NULL;
        }
        
        if (data && data[i]) {
            strncpy(copy[i], data[i], MAX_ROW_SIZE - 1);
            copy[i][MAX_ROW_SIZE - 1] = '\0';
        } else {
            copy[i][0] = '\0';
        }
    }
    
    log_msg("[copy_data] Completed successfully");
    return copy;
}

/* Helper: Get column index by name */
static int get_column_index(char **headers, const char *col_name, int num_cols) {
    if (!headers || !col_name) return -1;
    for (int i = 0; i < num_cols; i++) {
        if (headers[i] && strcmp(headers[i], col_name) == 0) return i;
    }
    return -1;
}

/* Helper: Get column value manually (handles empty cells ,,) */
static void get_column_value_manual(const char *row, int col, char *dest, int dest_size) {
    if (!row || !dest) {
        if (dest) dest[0] = '\0';
        return;
    }
    const char *curr = row;
    for (int c = 0; c < col; c++) {
        const char *next = strchr(curr, ',');
        if (next) curr = next + 1;
        else { curr = NULL; break; }
    }
    
    if (curr) {
        const char *end = strchr(curr, ',');
        int len = end ? (int)(end - curr) : (int)strlen(curr);
        if (len >= dest_size) len = dest_size - 1;
        strncpy(dest, curr, len);
        dest[len] = '\0';
    } else {
        dest[0] = '\0';
    }
}

/* Helper: Replace a specific column value in a CSV row string */
static void replace_column_value(char *row, int col, int num_cols, const char *new_val) {
    if (!row || !new_val) return;
    
    char *new_row = (char*)malloc(MAX_ROW_SIZE);
    if (!new_row) return;
    new_row[0] = '\0';
    
    const char *curr = row;
    int current_len = 0;
    
    for (int c = 0; c < num_cols; c++) {
        char val[MAX_ROW_SIZE];
        const char *end = strchr(curr, ',');
        int len = end ? (int)(end - curr) : (int)strlen(curr);
        
        const char *to_add = (c == col) ? new_val : NULL;
        if (!to_add) {
            strncpy(val, curr, len);
            val[len] = '\0';
            to_add = val;
        }
        
        int add_len = strlen(to_add);
        if (current_len + add_len + 2 < MAX_ROW_SIZE) {
            strcat(new_row, to_add);
            current_len += add_len;
        }
        
        if (c < num_cols - 1) {
            if (current_len + 1 < MAX_ROW_SIZE) {
                strcat(new_row, ",");
                current_len += 1;
            }
        }
        
        if (end) curr = end + 1;
        else curr += len;
    }
    
    strncpy(row, new_row, MAX_ROW_SIZE - 1);
    row[MAX_ROW_SIZE - 1] = '\0';
    free(new_row);
}

/* Stage 1: Remove duplicates */
static char** remove_duplicates(char **data, int *num_rows, int num_cols, int *dup_count) {
    log_msg("[remove_duplicates] Starting: %d rows", *num_rows);
    
    if (!data || !num_rows) return NULL;
    
    *dup_count = 0;
    char **unique = (char**)malloc(*num_rows * sizeof(char*));
    if (!unique) return data;
    
    int unique_count = 0;
    
    for (int i = 0; i < *num_rows; i++) {
        int is_duplicate = 0;
        for (int j = 0; j < unique_count; j++) {
            if (strcmp(data[i], unique[j]) == 0) {
                is_duplicate = 1;
                break;
            }
        }
        
        if (!is_duplicate) {
            unique[unique_count] = (char*)malloc(MAX_ROW_SIZE);
            if (unique[unique_count]) {
                strcpy(unique[unique_count], data[i]);
                unique_count++;
            }
        } else {
            (*dup_count)++;
        }
    }
    
    /* Cleanup old data */
    for (int i = 0; i < *num_rows; i++) free(data[i]);
    free(data);
    
    log_msg("[remove_duplicates] Completed: %d unique rows from %d total", unique_count, *num_rows);
    
    *num_rows = unique_count;
    return unique;
}

/* Stage 2: Handle missing values */
static char** handle_missing_values(char **data, int *num_rows, char **headers, 
                                     int num_cols, MissingConfig *cfg, int *missing_count) {
    log_msg("[handle_missing_values] Starting: %d rows", *num_rows);
    *missing_count = 0;
    
    if (!cfg || cfg->num_configs == 0) return data;

    int *should_drop = (int*)calloc(*num_rows, sizeof(int));
    int drop_count = 0;

    for (int i = 0; i < cfg->num_configs; i++) {
        int col = get_column_index(headers, cfg->configs[i].column_name, num_cols);
        if (col < 0) continue;

        if (cfg->configs[i].strategy == 0) { /* Drop row */
            for (int r = 0; r < *num_rows; r++) {
                if (should_drop[r]) continue;
                char val[MAX_ROW_SIZE];
                get_column_value_manual(data[r], col, val, sizeof(val));
                if (is_missing(val)) {
                    should_drop[r] = 1;
                    drop_count++;
                }
            }
        }
    }

    char **current_data = data;
    if (drop_count > 0) {
        char **filtered_data = (char**)malloc((*num_rows - drop_count) * sizeof(char*));
        int k = 0;
        for (int r = 0; r < *num_rows; r++) {
            if (!should_drop[r]) {
                filtered_data[k++] = data[r];
            } else {
                free(data[r]);
            }
        }
        free(data);
        *num_rows = k;
        current_data = filtered_data;
    }
    free(should_drop);

    for (int i = 0; i < cfg->num_configs; i++) {
        int col = get_column_index(headers, cfg->configs[i].column_name, num_cols);
        if (col < 0) continue;
        int strategy = cfg->configs[i].strategy;

        if (strategy == 1) { /* Mean */
            double sum = 0.0;
            int count = 0;
            for (int r = 0; r < *num_rows; r++) {
                char val[MAX_ROW_SIZE];
                get_column_value_manual(current_data[r], col, val, sizeof(val));
                if (is_numeric(val)) {
                    sum += atof(val);
                    count++;
                }
            }
            if (count > 0) {
                double mean = sum / count;
                char replacement[64];
                snprintf(replacement, sizeof(replacement), "%.4f", mean);
                for (int r = 0; r < *num_rows; r++) {
                    char val[MAX_ROW_SIZE];
                    get_column_value_manual(current_data[r], col, val, sizeof(val));
                    if (is_missing(val)) {
                        replace_column_value(current_data[r], col, num_cols, replacement);
                        (*missing_count)++;
                    }
                }
            }
        } else if (strategy == 4) { /* Constant */
            const char *replacement = cfg->configs[i].fill_value;
            for (int r = 0; r < *num_rows; r++) {
                char val[MAX_ROW_SIZE];
                get_column_value_manual(current_data[r], col, val, sizeof(val));
                if (is_missing(val)) {
                    replace_column_value(current_data[r], col, num_cols, replacement);
                    (*missing_count)++;
                }
            }
        }
    }

    return current_data;
}

/* Stage 3: Detect and remove outliers */
static char** remove_outliers(char **data, int *num_rows, char **headers, 
                              int num_cols, OutlierConfig *cfg, int *outlier_count) {
    *outlier_count = 0;
    if (!cfg || !cfg->columns || cfg->num_columns == 0 || *num_rows == 0) return data;
    
    int *is_outlier = (int*)calloc(*num_rows, sizeof(int));
    for (int col_idx = 0; col_idx < cfg->num_columns; col_idx++) {
        int col = get_column_index(headers, cfg->columns[col_idx], num_cols);
        if (col < 0) continue;
        
        double *values = (double*)malloc(*num_rows * sizeof(double));
        int *value_rows = (int*)malloc(*num_rows * sizeof(int));
        int count = 0;
        
        for (int r = 0; r < *num_rows; r++) {
            char val[MAX_ROW_SIZE];
            get_column_value_manual(data[r], col, val, sizeof(val));
            if (is_numeric(val)) {
                values[count] = atof(val);
                value_rows[count] = r;
                count++;
            }
        }
        
        if (count >= 4) {
            for (int i = 0; i < count - 1; i++) {
                for (int j = i + 1; j < count; j++) {
                    if (values[i] > values[j]) {
                        double tmp_v = values[i]; values[i] = values[j]; values[j] = tmp_v;
                        int tmp_r = value_rows[i]; value_rows[i] = value_rows[j]; value_rows[j] = tmp_r;
                    }
                }
            }
            double q1 = values[count / 4];
            double q3 = values[3 * count / 4];
            double iqr = q3 - q1;
            double lower = q1 - cfg->threshold * iqr;
            double upper = q3 + cfg->threshold * iqr;
            
            for (int i = 0; i < count; i++) {
                if (values[i] < lower || values[i] > upper) {
                    is_outlier[value_rows[i]] = 1;
                }
            }
        }
        free(values);
        free(value_rows);
    }
    
    int dropped = 0;
    for (int i = 0; i < *num_rows; i++) if (is_outlier[i]) dropped++;
    
    char **filtered = data;
    if (dropped > 0) {
        filtered = (char**)malloc((*num_rows - dropped) * sizeof(char*));
        int k = 0;
        for (int i = 0; i < *num_rows; i++) {
            if (!is_outlier[i]) {
                filtered[k++] = data[i];
            } else {
                free(data[i]);
                (*outlier_count)++;
            }
        }
        free(data);
        *num_rows = k;
    }
    free(is_outlier);
    return filtered;
}

/* Stage 4: Scale numeric columns */
static void scale_columns(char **data, int num_rows, char **headers, 
                          int num_cols, ScalingConfig *cfg, int *cols_scaled) {
    *cols_scaled = 0;
    if (!cfg || !cfg->columns || cfg->num_columns == 0 || num_rows == 0) return;
    
    for (int col_idx = 0; col_idx < cfg->num_columns; col_idx++) {
        int col = get_column_index(headers, cfg->columns[col_idx], num_cols);
        if (col < 0) continue;
        
        double min_v = 1e18, max_v = -1e18;
        int found = 0;
        for (int r = 0; r < num_rows; r++) {
            char val[MAX_ROW_SIZE];
            get_column_value_manual(data[r], col, val, sizeof(val));
            if (is_numeric(val)) {
                double v = atof(val);
                if (v < min_v) min_v = v;
                if (v > max_v) max_v = v;
                found = 1;
            }
        }
        
        if (found && max_v > min_v) {
            double range = max_v - min_v;
            for (int r = 0; r < num_rows; r++) {
                char val[MAX_ROW_SIZE];
                get_column_value_manual(data[r], col, val, sizeof(val));
                if (is_numeric(val)) {
                    double v = (atof(val) - min_v) / range;
                    char scaled[64];
                    snprintf(scaled, sizeof(scaled), "%.4f", v);
                    replace_column_value(data[r], col, num_cols, scaled);
                }
            }
            (*cols_scaled)++;
        }
    }
}

/* Stage 5: Encode categorical columns */
static void encode_columns(char **data, int num_rows, char **headers, 
                           int num_cols, EncodingConfig *cfg, int *cols_encoded) {
    *cols_encoded = 0;
    if (!cfg || !cfg->columns || cfg->num_columns == 0 || num_rows == 0) return;
    
    for (int col_idx = 0; col_idx < cfg->num_columns; col_idx++) {
        int col = get_column_index(headers, cfg->columns[col_idx], num_cols);
        if (col < 0) continue;
        
        char **unique_vals = (char**)malloc(num_rows * sizeof(char*));
        int unique_count = 0;
        int *encodings = (int*)malloc(num_rows * sizeof(int));
        
        for (int r = 0; r < num_rows; r++) {
            char val[MAX_ROW_SIZE];
            get_column_value_manual(data[r], col, val, sizeof(val));
            
            int found_idx = -1;
            for (int i = 0; i < unique_count; i++) {
                if (strcmp(unique_vals[i], val) == 0) {
                    found_idx = i;
                    break;
                }
            }
            
            if (found_idx >= 0) {
                encodings[r] = found_idx;
            } else {
                unique_vals[unique_count] = strdup(val);
                encodings[r] = unique_count;
                unique_count++;
            }
        }
        
        for (int r = 0; r < num_rows; r++) {
            char buf[32];
            snprintf(buf, sizeof(buf), "%d", encodings[r]);
            replace_column_value(data[r], col, num_cols, buf);
        }
        
        for (int i = 0; i < unique_count; i++) free(unique_vals[i]);
        free(unique_vals);
        free(encodings);
        (*cols_encoded)++;
    }
}

/* Main preprocessing function (serial) */
PreprocessedData* preprocess_serial(
    char **raw_data,
    char **headers,
    int num_rows,
    int num_cols,
    int should_remove_duplicates,
    MissingConfig *missing_cfg,
    OutlierConfig *outlier_cfg,
    ScalingConfig *scaling_cfg,
    EncodingConfig *encoding_cfg
) {
    clock_t start = clock();
    PreprocessedData *result = (PreprocessedData*)calloc(1, sizeof(PreprocessedData));
    result->num_rows = num_rows;
    result->num_cols = num_cols;
    
    result->headers = (char**)malloc(num_cols * sizeof(char*));
    for (int i = 0; i < num_cols; i++) {
        result->headers[i] = strdup(headers[i]);
    }
    
    char **data = copy_data(raw_data, num_rows, num_cols);
    if (!data) return result;
    
    if (should_remove_duplicates) {
        clock_t s = clock();
        data = remove_duplicates(data, &result->num_rows, num_cols, &result->duplicates_found);
        result->duplicates_time_ms = (clock() - s) * 1000.0 / CLOCKS_PER_SEC;
        result->rows_removed += result->duplicates_found;
    }
    
    clock_t s_m = clock();
    int old_r = result->num_rows;
    data = handle_missing_values(data, &result->num_rows, result->headers, num_cols, missing_cfg, &result->missing_filled);
    result->missing_time_ms = (clock() - s_m) * 1000.0 / CLOCKS_PER_SEC;
    result->rows_removed += (old_r - result->num_rows);
    
    if (outlier_cfg) {
        clock_t s = clock();
        int r_before = result->num_rows;
        data = remove_outliers(data, &result->num_rows, result->headers, num_cols, outlier_cfg, &result->outliers_removed);
        result->outliers_time_ms = (clock() - s) * 1000.0 / CLOCKS_PER_SEC;
        result->rows_removed += (r_before - result->num_rows);
    }
    
    if (scaling_cfg) {
        clock_t s = clock();
        scale_columns(data, result->num_rows, result->headers, num_cols, scaling_cfg, &result->columns_scaled);
        result->scaling_time_ms = (clock() - s) * 1000.0 / CLOCKS_PER_SEC;
    }
    
    if (encoding_cfg) {
        clock_t s = clock();
        encode_columns(data, result->num_rows, result->headers, num_cols, encoding_cfg, &result->columns_encoded);
        result->encoding_time_ms = (clock() - s) * 1000.0 / CLOCKS_PER_SEC;
    }
    
    result->data = data;
    result->processing_time_ms = (clock() - start) * 1000.0 / CLOCKS_PER_SEC;
    return result;
}

void free_preprocessed_data(PreprocessedData *data) {
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

char* preprocess_to_json(PreprocessedData *data) {
    char *json = (char*)malloc(4096);
    snprintf(json, 4096, "{\"rows_after\":%d,\"rows_removed\":%d}", data->num_rows, data->rows_removed);
    return json;
}

PreprocessedData* preprocess_openmp(char **raw_data, char **headers, int num_rows, int num_cols, int num_threads, int should_remove_duplicates, MissingConfig *missing_cfg, OutlierConfig *outlier_cfg, ScalingConfig *scaling_cfg, EncodingConfig *encoding_cfg) {
    return preprocess_serial(raw_data, headers, num_rows, num_cols, should_remove_duplicates, missing_cfg, outlier_cfg, scaling_cfg, encoding_cfg);
}

PreprocessedData* preprocess_mpi(char **raw_data, char **headers, int num_rows, int num_cols, int num_proc, int should_remove_duplicates, MissingConfig *missing_cfg, OutlierConfig *outlier_cfg, ScalingConfig *scaling_cfg, EncodingConfig *encoding_cfg) {
    return preprocess_serial(raw_data, headers, num_rows, num_cols, should_remove_duplicates, missing_cfg, outlier_cfg, scaling_cfg, encoding_cfg);
}