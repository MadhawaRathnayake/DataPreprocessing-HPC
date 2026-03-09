/*
 * Serial Preprocessing Implementation
 * Performs all preprocessing operations sequentially
 */

#include "preprocessor.h"
#include <time.h>
#include <stdarg.h>

/* Simple logging function that writes to a file */
static void log_msg(const char *fmt, ...) {
    FILE *logfile = fopen("/tmp/preprocess.log", "a");
    if (!logfile) return;
    
    va_list args;
    va_start(args, fmt);
    vfprintf(logfile, fmt, args);
    va_end(args);
    fprintf(logfile, "\n");
    fflush(logfile);
    fclose(logfile);
}

/* Helper: Check if string is numeric */
static int is_numeric(const char *str) {
    if (!str || *str == '\0') return 0;
    if (*str == '-' || *str == '+') str++;
    int has_dot = 0;
    while (*str) {
        if (*str == '.') {
            if (has_dot) return 0;
            has_dot = 1;
        } else if (!(*str >= '0' && *str <= '9')) {
            return 0;
        }
        str++;
    }
    return 1;
}

/* Helper: Check if value is null/missing */
static int is_missing(const char *val) {
    if (!val || strlen(val) == 0) return 1;
    if (strcmp(val, "NA") == 0 || strcmp(val, "N/A") == 0) return 1;
    if (strcmp(val, "nan") == 0 || strcmp(val, "NaN") == 0) return 1;
    if (strcmp(val, "null") == 0) return 1;
    return 0;
}

/* Helper: Deep copy data array */
static char** copy_data(char **data, int num_rows, int num_cols) {
    log_msg("[copy_data] Starting: %d rows, %d cols", num_rows, num_cols);
    
    char **copy = (char**)malloc(num_rows * sizeof(char*));
    if (!copy) {
        log_msg("[copy_data ERROR] malloc failed for %d row pointers", num_rows);
        return NULL;
    }
    
    for (int i = 0; i < num_rows; i++) {
        if (i % 100000 == 0) {
            log_msg("[copy_data] Processing row %d/%d", i, num_rows);
        }
        
        if (!data || !data[i]) {
            copy[i] = (char*)malloc(1);
            if (copy[i]) copy[i][0] = '\0';
            continue;
        }
        
        /* Allocate based on actual string length, not fixed size */
        size_t len = strlen(data[i]) + 1;
        if (len > 8192) {
            log_msg("[copy_data] Row %d size: %zu bytes", i, len);
        }
        
        copy[i] = (char*)malloc(len);
        if (!copy[i]) {
            /* Memory allocation failed */
            log_msg("[copy_data ERROR] malloc failed at row %d (size %zu)", i, len);
            for (int j = 0; j < i; j++) free(copy[j]);
            free(copy);
            return NULL;
        }
        strcpy(copy[i], data[i]);
    }
    
    log_msg("[copy_data] Completed successfully");
    return copy;
}

/* Helper: Get column index by name */
static int get_column_index(char **headers, const char *col_name, int num_cols) {
    for (int i = 0; i < num_cols; i++) {
        if (strcmp(headers[i], col_name) == 0) return i;
    }
    return -1;
}

/* Stage 1: Remove duplicates */
static char** remove_duplicates(char **data, int *num_rows, int num_cols, int *dup_count) {
    log_msg("[remove_duplicates] Starting: %d rows", *num_rows);
    
    if (!data || !num_rows) {
        log_msg("[remove_duplicates ERROR] NULL data or num_rows");
        return NULL;
    }
    
    *dup_count = 0;
    char **unique = (char**)malloc(*num_rows * sizeof(char*));
    if (!unique) {
        log_msg("[remove_duplicates ERROR] malloc failed for unique array");
        return data;
    }
    
    int unique_count = 0;
    
    for (int i = 0; i < *num_rows; i++) {
        if (i % 100000 == 0) {
            log_msg("[remove_duplicates] Processing row %d/%d, unique so far: %d", i, *num_rows, unique_count);
        }
        
        if (!data[i]) {
            log_msg("[remove_duplicates] Row %d is NULL, skipping", i);
            continue;
        }
        
        int is_duplicate = 0;
        
        /* Check against all previously seen rows */
        for (int j = 0; j < unique_count; j++) {
            if (!unique[j]) continue;
            if (strcmp(data[i], unique[j]) == 0) {
                is_duplicate = 1;
                break;
            }
        }
        
        if (!is_duplicate) {
            unique[unique_count] = (char*)malloc(4096);  /* Safe fixed size */
            if (unique[unique_count]) {
                if (strlen(data[i]) < 4000) {
                    strcpy(unique[unique_count], data[i]);
                    unique_count++;
                } else {
                    log_msg("[remove_duplicates] Row %d too large (%zu bytes)", i, strlen(data[i]));
                    (*dup_count)++;
                }
            } else {
                log_msg("[remove_duplicates ERROR] malloc failed at row %d", i);
                (*dup_count)++;
            }
        } else {
            (*dup_count)++;
        }
    }
    
    log_msg("[remove_duplicates] Completed: %d unique rows from %d total", unique_count, *num_rows);
    
    *num_rows = unique_count;
    return unique;
}

/* Stage 2: Impute missing values with mean/mode */
static void impute_missing_values(char **data, int num_rows, char **headers, 
                                   int num_cols, int *missing_count) {
    *missing_count = 0;
    
    for (int col = 0; col < num_cols; col++) {
        /* Calculate mean for numeric columns */
        double sum = 0.0;
        int numeric_count = 0;
        int has_missing = 0;
        
        for (int row = 0; row < num_rows; row++) {
            if (!data[row]) continue;
            char temp[4096];
            if (strlen(data[row]) >= 4000) continue;
            strcpy(temp, data[row]);  /* IMPORTANT: Make a copy before strtok() */
            
            char *val = strtok(temp, ",");
            for (int c = 0; c < col; c++) val = strtok(NULL, ",");
            
            if (is_missing(val)) {
                has_missing = 1;
            } else if (is_numeric(val)) {
                sum += atof(val);
                numeric_count++;
            }
        }
        
        if (!has_missing) continue;
        
        double mean = (numeric_count > 0) ? sum / numeric_count : 0.0;
        
        /* Impute missing values */
        for (int row = 0; row < num_rows; row++) {
            if (!data[row]) continue;
            char temp[4096];  /* Safe fixed size */
            if (strlen(data[row]) >= 4000) continue;  /* Skip oversized rows */
            strcpy(temp, data[row]);
            
            char *val = strtok(temp, ",");
            for (int c = 0; c < col; c++) val = strtok(NULL, ",");
            
            if (is_missing(val)) {
                /* Replace with mean (simplified approach) */
                char replacement[50];
                snprintf(replacement, sizeof(replacement), "%.2f", mean);
                
                /* Reconstruct row with replacement */
                char new_row[4096];
                new_row[0] = '\0';
                strcpy(temp, data[row]);
                val = strtok(temp, ",");
                
                for (int c = 0; c < col; c++) {
                    if (strlen(new_row) + strlen(val) + 2 < 4090) {
                        strcat(new_row, val);
                        strcat(new_row, ",");
                    }
                    val = strtok(NULL, ",");
                }
                if (strlen(new_row) + strlen(replacement) + 1 < 4090) {
                    strcat(new_row, replacement);
                    val = strtok(NULL, ",");
                    if (val && strlen(new_row) + strlen(val) + 2 < 4090) {
                        strcat(new_row, ",");
                        strcat(new_row, val);
                    }
                }
                
                if (strlen(new_row) < 4000) strcpy(data[row], new_row);
                (*missing_count)++;
            }
        }
    }
}

/* Stage 3: Detect and remove outliers using IQR method */
static char** remove_outliers(char **data, int *num_rows, char **headers, 
                              int num_cols, OutlierConfig *cfg, int *outlier_count) {
    *outlier_count = 0;
    
    if (!cfg || !cfg->columns || cfg->num_columns == 0) {
        return data;
    }
    
    char **filtered = (char**)malloc(*num_rows * sizeof(char*));
    int filtered_count = 0;
    
    /* Mark rows as outliers */
    int *is_outlier = (int*)calloc(*num_rows, sizeof(int));
    
    for (int col_idx = 0; col_idx < cfg->num_columns; col_idx++) {
        int col = get_column_index(headers, cfg->columns[col_idx], num_cols);
        if (col < 0) continue;
        
        /* Get numeric values */
        double *values = (double*)malloc(*num_rows * sizeof(double));
        int *value_rows = (int*)malloc(*num_rows * sizeof(int));
        int count = 0;
        
        for (int row = 0; row < *num_rows; row++) {
            if (!data[row]) continue;
            char temp[4096];  /* Safe fixed size instead of VLA */
            if (strlen(data[row]) >= 4000) continue;
            strcpy(temp, data[row]);
            char *val = strtok(temp, ",");
            
            for (int c = 0; c < col; c++) val = strtok(NULL, ",");
            
            if (is_numeric(val)) {
                values[count] = atof(val);
                value_rows[count] = row;
                count++;
            }
        }
        
        if (count < 4) {
            free(values);
            free(value_rows);
            continue;
        }
        
        /* Sort to find quartiles */
        for (int i = 0; i < count - 1; i++) {
            for (int j = i + 1; j < count; j++) {
                if (values[i] > values[j]) {
                    double tmp = values[i];
                    values[i] = values[j];
                    values[j] = tmp;
                    
                    int tmp_row = value_rows[i];
                    value_rows[i] = value_rows[j];
                    value_rows[j] = tmp_row;
                }
            }
        }
        
        /* Calculate Q1, Q3, IQR */
        double q1 = values[count / 4];
        double q3 = values[3 * count / 4];
        double iqr = q3 - q1;
        double lower = q1 - 1.5 * iqr;
        double upper = q3 + 1.5 * iqr;
        
        /* Mark outliers */
        for (int i = 0; i < count; i++) {
            if (values[i] < lower || values[i] > upper) {
                is_outlier[value_rows[i]] = 1;
            }
        }
        
        free(values);
        free(value_rows);
    }
    
    /* Keep only non-outlier rows */
    for (int row = 0; row < *num_rows; row++) {
        if (!is_outlier[row]) {
            filtered[filtered_count] = (char*)malloc(4096);  /* Safe fixed buffer */
            if (filtered[filtered_count] && strlen(data[row]) < 4000) {
                strcpy(filtered[filtered_count], data[row]);
                filtered_count++;
            } else {
                log_msg("[remove_outliers] Row %d too large or malloc failed", row);
            }
        } else {
            (*outlier_count)++;
        }
    }
    
    *num_rows = filtered_count;
    free(is_outlier);
    return filtered;
}

/* Stage 4: Scale numeric columns (min-max normalization) */
static void scale_columns(char **data, int num_rows, char **headers, 
                          int num_cols, ScalingConfig *cfg, int *cols_scaled) {
    *cols_scaled = 0;
    
    if (!cfg || !cfg->columns || cfg->num_columns == 0) {
        return;
    }
    
    for (int col_idx = 0; col_idx < cfg->num_columns; col_idx++) {
        int col = get_column_index(headers, cfg->columns[col_idx], num_cols);
        if (col < 0) continue;
        
        /* Find min/max */
        double min_val = 1e10, max_val = -1e10;
        for (int row = 0; row < num_rows; row++) {
            if (!data[row]) continue;
            char temp[4096];  /* Safe fixed size instead of VLA */
            if (strlen(data[row]) >= 4000) continue;
            strcpy(temp, data[row]);
            char *val = strtok(temp, ",");
            
            for (int c = 0; c < col; c++) val = strtok(NULL, ",");
            
            if (is_numeric(val)) {
                double v = atof(val);
                if (v < min_val) min_val = v;
                if (v > max_val) max_val = v;
            }
        }
        
        if (min_val >= max_val) continue; /* Skip if all same values */
        
        /* Normalize (min-max scaling to [0,1]) */
        double range = max_val - min_val;
        for (int row = 0; row < num_rows; row++) {
            if (!data[row]) continue;
            char temp[4096];  /* Safe fixed size */
            if (strlen(data[row]) >= 4000) continue;
            strcpy(temp, data[row]);
            char *val = strtok(temp, ",");
            
            for (int c = 0; c < col - 1; c++) {
                val = strtok(NULL, ",");
            }
            
            if (is_numeric(val)) {
                double v = atof(val);
                double normalized = (v - min_val) / range;
                
                /* Reconstruct row with scaled value */
                char new_row[4096];  /* Larger buffer for safety */
                new_row[0] = '\0';
                if (strlen(data[row]) >= 4000) continue;  /* Skip if row too large */
                strcpy(temp, data[row]);
                val = strtok(temp, ",");
                
                for (int c = 0; c < col; c++) {
                    strcat(new_row, val);
                    strcat(new_row, ",");
                    val = strtok(NULL, ",");
                }
                
                char scaled[50];
                snprintf(scaled, sizeof(scaled), "%.4f", normalized);
                strcat(new_row, scaled);
                
                val = strtok(NULL, ",");
                if (val) {
                    strcat(new_row, ",");
                    strcat(new_row, val);
                }
                
                strcpy(data[row], new_row);
            }
        }
        
        (*cols_scaled)++;
    }
}

/* Stage 5: Encode categorical columns (simple label encoding) */
static void encode_columns(char **data, int num_rows, char **headers, 
                           int num_cols, EncodingConfig *cfg, int *cols_encoded) {
    *cols_encoded = 0;
    
    if (!cfg || !cfg->columns || cfg->num_columns == 0) {
        return;
    }
    
    for (int col_idx = 0; col_idx < cfg->num_columns; col_idx++) {
        int col = get_column_index(headers, cfg->columns[col_idx], num_cols);
        if (col < 0) continue;
        
        /* Build unique value mapping */
        char **unique_vals = (char**)malloc(num_rows * sizeof(char*));
        int unique_count = 0;
        int *encoding = (int*)malloc(num_rows * sizeof(int));
        
        for (int row = 0; row < num_rows; row++) {
            if (!data[row]) continue;
            char temp[4096];  /* Safe fixed size */
            if (strlen(data[row]) >= 4000) continue;  /* Skip oversized rows */
            strcpy(temp, data[row]);
            char *val = strtok(temp, ",");
            
            for (int c = 0; c < col; c++) val = strtok(NULL, ",");
            
            /* Find or create encoding for this value */
            int found = -1;
            for (int i = 0; i < unique_count; i++) {
                if (strcmp(unique_vals[i], val) == 0) {
                    found = i;
                    break;
                }
            }
            
            if (found >= 0) {
                encoding[row] = found;
            } else {
                unique_vals[unique_count] = (char*)malloc((strlen(val) + 1) * sizeof(char));
                strcpy(unique_vals[unique_count], val);
                encoding[row] = unique_count;
                unique_count++;
            }
        }
        
        /* Replace values with numeric encodings */
        for (int row = 0; row < num_rows; row++) {
            if (!data[row] || strlen(data[row]) >= 4000) continue;  /* Skip invalid rows */
            char temp[4096];  /* Larger buffer for safety */
            strcpy(temp, data[row]);
            char *val = strtok(temp, ",");
            
            char new_row[4096];  /* Larger buffer for safety */
            new_row[0] = '\0';
            for (int c = 0; c < col; c++) {
                strcat(new_row, val);
                strcat(new_row, ",");
                val = strtok(NULL, ",");
            }
            
            char encoded[50];
            snprintf(encoded, sizeof(encoded), "%d", encoding[row]);
            strcat(new_row, encoded);
            
            val = strtok(NULL, ",");
            if (val) {
                strcat(new_row, ",");
                strcat(new_row, val);
            }
            
            strcpy(data[row], new_row);
        }
        
        /* Free temporary storage */
        for (int i = 0; i < unique_count; i++) {
            free(unique_vals[i]);
        }
        free(unique_vals);
        free(encoding);
        
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
    OutlierConfig *outlier_cfg,
    ScalingConfig *scaling_cfg,
    EncodingConfig *encoding_cfg
) {
    clock_t start = clock();
    
    /* Allocate result structure */
    PreprocessedData *result = (PreprocessedData*)malloc(sizeof(PreprocessedData));
    result->num_rows = num_rows;
    result->num_cols = num_cols;
    result->rows_removed = 0;
    result->duplicates_found = 0;
    result->missing_filled = 0;
    result->outliers_removed = 0;
    result->columns_scaled = 0;
    result->columns_encoded = 0;
    
    /* Copy headers */
    result->headers = (char**)malloc(num_cols * sizeof(char*));
    for (int i = 0; i < num_cols; i++) {
        result->headers[i] = (char*)malloc((strlen(headers[i]) + 1) * sizeof(char));
        strcpy(result->headers[i], headers[i]);
    }
    
    /* Copy data */
    log_msg("[PREPROCESS] Copying data: %d rows x %d cols", num_rows, num_cols);
    char **data = copy_data(raw_data, num_rows, num_cols);
    if (!data) {
        log_msg("[ERROR] copy_data() failed");
        result->num_rows = 0;
        return result;
    }
    log_msg("[PREPROCESS] Data copied successfully");
    
    /* Stage 1: Remove duplicates */
    if (should_remove_duplicates) {
        log_msg("[STAGE1] Starting remove_duplicates: %d rows", result->num_rows);
        data = remove_duplicates(data, &result->num_rows, num_cols, &result->duplicates_found);
        log_msg("[STAGE1] Completed: %d rows remaining, %d duplicates found", result->num_rows, result->duplicates_found);
        result->rows_removed += result->duplicates_found;
    }
    
    /* Stage 2: Impute missing values */
    log_msg("[STAGE2] Starting impute_missing_values: %d rows", result->num_rows);
    impute_missing_values(data, result->num_rows, headers, num_cols, &result->missing_filled);
    log_msg("[STAGE2] Completed: %d values filled", result->missing_filled);
    
    /* Stage 3: Remove outliers */
    if (outlier_cfg) {
        log_msg("[STAGE3] Starting remove_outliers: %d rows", result->num_rows);
        data = remove_outliers(data, &result->num_rows, headers, num_cols, outlier_cfg, &result->outliers_removed);
        log_msg("[STAGE3] Completed: %d rows remaining, %d outliers removed", result->num_rows, result->outliers_removed);
        result->rows_removed += result->outliers_removed;
    }
    
    /* Stage 4: Scale columns */
    if (scaling_cfg) {
        log_msg("[STAGE4] Starting scale_columns: %d rows", result->num_rows);
        scale_columns(data, result->num_rows, headers, num_cols, scaling_cfg, &result->columns_scaled);
        log_msg("[STAGE4] Completed: %d columns scaled", result->columns_scaled);
    }
    
    /* Stage 5: Encode categorical columns */
    if (encoding_cfg) {
        log_msg("[STAGE5] Starting encode_columns: %d rows", result->num_rows);
        encode_columns(data, result->num_rows, headers, num_cols, encoding_cfg, &result->columns_encoded);
        log_msg("[STAGE5] Completed: %d columns encoded", result->columns_encoded);
    }
    
    result->data = data;
    result->processing_time_ms = (clock() - start) * 1000.0 / CLOCKS_PER_SEC;
    
    return result;
}

/* Free memory */
void free_preprocessed_data(PreprocessedData *data) {
    if (!data) return;
    
    for (int i = 0; i < data->num_rows; i++) {
        free(data->data[i]);
    }
    free(data->data);
    
    for (int i = 0; i < data->num_cols; i++) {
        free(data->headers[i]);
    }
    free(data->headers);
    
    free(data);
}

/* Convert to JSON for reporting */
char* preprocess_to_json(PreprocessedData *data) {
    char *json = (char*)malloc(2048 * sizeof(char));
    snprintf(json, 2048,
        "{"
        "\"rows_after\": %d, "
        "\"rows_removed\": %d, "
        "\"duplicates_found\": %d, "
        "\"missing_filled\": %d, "
        "\"outliers_removed\": %d, "
        "\"columns_scaled\": %d, "
        "\"columns_encoded\": %d, "
        "\"processing_time_ms\": %.2f"
        "}",
        data->num_rows,
        data->rows_removed,
        data->duplicates_found,
        data->missing_filled,
        data->outliers_removed,
        data->columns_scaled,
        data->columns_encoded,
        data->processing_time_ms
    );
    return json;
}

/* OpenMP version (placeholder for now) */
PreprocessedData* preprocess_openmp(
    char **raw_data,
    char **headers,
    int num_rows,
    int num_cols,
    int num_threads,
    int should_remove_duplicates,
    OutlierConfig *outlier_cfg,
    ScalingConfig *scaling_cfg,
    EncodingConfig *encoding_cfg
) {
    /* For now, delegate to serial version */
    /* TODO: Implement OpenMP parallelization for stages 3, 4, 5 */
    return preprocess_serial(raw_data, headers, num_rows, num_cols,
                           should_remove_duplicates, outlier_cfg, scaling_cfg, encoding_cfg);
}

/* MPI version (placeholder for now) */
PreprocessedData* preprocess_mpi(
    char **raw_data,
    char **headers,
    int num_rows,
    int num_cols,
    int num_processes,
    int should_remove_duplicates,
    OutlierConfig *outlier_cfg,
    ScalingConfig *scaling_cfg,
    EncodingConfig *encoding_cfg
) {
    /* For now, delegate to serial version */
    /* TODO: Implement MPI parallelization for large datasets */
    return preprocess_serial(raw_data, headers, num_rows, num_cols,
                           should_remove_duplicates, outlier_cfg, scaling_cfg, encoding_cfg);
}
