#include "mpi_analyzer.h"

/*
 * Note: This is a simplified MPI analyzer implementation.
 * For production use, MPI would distribute columns across processes.
 * This version provides the interface but runs serially.
 * Full MPI implementation requires proper data distribution and gathering.
 */

// Helper functions (same as serial/OpenMP)
static int is_numeric(const char *str) {
    if (!str || strlen(str) == 0) return 0;
    char *endptr;
    strtod(str, &endptr);
    while (*endptr && isspace(*endptr)) endptr++;
    return *endptr == '\0';
}

static int is_null(const char *str) {
    if (!str || strlen(str) == 0) return 1;
    if (strcasecmp(str, "null") == 0 || strcasecmp(str, "na") == 0 ||
        strcasecmp(str, "n/a") == 0 || strcasecmp(str, "nan") == 0) {
        return 1;
    }
    return 0;
}

static int compare_doubles(const void *a, const void *b) {
    double diff = *(double*)a - *(double*)b;
    return (diff > 0) - (diff < 0);
}

static int compare_value_counts(const void *a, const void *b) {
    return ((ValueCount*)b)->count - ((ValueCount*)a)->count;
}

DatasetStats* analyzer_mpi_create_stats(int num_columns) {
    DatasetStats *stats = (DatasetStats*)malloc(sizeof(DatasetStats));
    if (!stats) return NULL;
    
    stats->num_columns = num_columns;
    stats->columns = (ColumnStats*)calloc(num_columns, sizeof(ColumnStats));
    stats->processing_time = 0.0;
    stats->num_processes = 1;
    
    if (!stats->columns) {
        free(stats);
        return NULL;
    }
    
    return stats;
}

void analyzer_mpi_free_stats(DatasetStats *stats) {
    if (!stats) return;
    
    for (int i = 0; i < stats->num_columns; i++) {
        if (stats->columns[i].column_name) free(stats->columns[i].column_name);
        if (stats->columns[i].outliers) free(stats->columns[i].outliers);
        if (stats->columns[i].value_counts) {
            for (int j = 0; j < stats->columns[i].value_count_size; j++) {
                if (stats->columns[i].value_counts[j].value) {
                    free(stats->columns[i].value_counts[j].value);
                }
            }
            free(stats->columns[i].value_counts);
        }
    }
    
    free(stats->columns);
    free(stats);
}

// Simplified analysis (would be distributed in full MPI version)
static void analyze_column(char **column_data, int num_rows, 
                          const char *col_name, ColumnStats *stats) {
    stats->column_name = malloc(strlen(col_name) + 1);
    strcpy(stats->column_name, col_name);
    
    stats->total_count = num_rows;
    stats->null_count = 0;
    stats->unique_count = 0;
    stats->outlier_count = 0;
    stats->has_nulls = 0;
    stats->has_outliers = 0;
    stats->has_duplicates = 0;
    stats->type_consistent = 1;
    
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
        
        if (!found && stats->unique_count < num_rows) {
            unique_values[stats->unique_count] = malloc(strlen(value) + 1);
            strcpy(unique_values[stats->unique_count], value);
            unique_counts[stats->unique_count] = 1;
            stats->unique_count++;
        }
    }
    
    stats->null_percentage = (double)stats->null_count / stats->total_count * 100.0;
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
        qsort(numeric_values, numeric_count, sizeof(double), compare_doubles);
        
        stats->min_value = numeric_values[0];
        stats->max_value = numeric_values[numeric_count - 1];
        
        double sum = 0.0;
        for (int i = 0; i < numeric_count; i++) sum += numeric_values[i];
        stats->mean = sum / numeric_count;
        
        if (numeric_count % 2 == 0) {
            stats->median = (numeric_values[numeric_count/2 - 1] + 
                           numeric_values[numeric_count/2]) / 2.0;
        } else {
            stats->median = numeric_values[numeric_count/2];
        }
        
        double variance = 0.0;
        for (int i = 0; i < numeric_count; i++) {
            variance += pow(numeric_values[i] - stats->mean, 2);
        }
        stats->std_dev = sqrt(variance / numeric_count);
        
        int q1_idx = numeric_count / 4;
        int q3_idx = (3 * numeric_count) / 4;
        double q1 = numeric_values[q1_idx];
        double q3 = numeric_values[q3_idx];
        double iqr = q3 - q1;
        double lower_bound = q1 - 1.5 * iqr;
        double upper_bound = q3 + 1.5 * iqr;
        
        stats->outliers = (double*)malloc(MAX_OUTLIERS * sizeof(double));
        for (int i = 0; i < numeric_count && stats->outlier_count < MAX_OUTLIERS; i++) {
            if (numeric_values[i] < lower_bound || numeric_values[i] > upper_bound) {
                stats->outliers[stats->outlier_count++] = numeric_values[i];
            }
        }
        stats->has_outliers = (stats->outlier_count > 0);
        
        stats->category = (stats->unique_count == 2) ? CAT_BINARY :
                         (stats->unique_count < 10) ? CAT_DISCRETE : CAT_CONTINUOUS;
    } else {
        stats->min_value = 0.0;
        stats->max_value = 0.0;
        stats->mean = 0.0;
        stats->median = 0.0;
        stats->std_dev = 0.0;
        stats->outliers = NULL;
        stats->category = (stats->unique_count == 2) ? CAT_BINARY : CAT_NOMINAL;
    }
    
    stats->value_count_size = (stats->unique_count < 10) ? stats->unique_count : 10;
    stats->value_counts = (ValueCount*)malloc(stats->value_count_size * sizeof(ValueCount));
    
    ValueCount *temp_counts = (ValueCount*)malloc(stats->unique_count * sizeof(ValueCount));
    for (int i = 0; i < stats->unique_count; i++) {
        temp_counts[i].value = unique_values[i];
        temp_counts[i].count = unique_counts[i];
    }
    
    qsort(temp_counts, stats->unique_count, sizeof(ValueCount), compare_value_counts);
    
    for (int i = 0; i < stats->value_count_size; i++) {
        stats->value_counts[i].value = malloc(strlen(temp_counts[i].value) + 1);
        strcpy(stats->value_counts[i].value, temp_counts[i].value);
        stats->value_counts[i].count = temp_counts[i].count;
    }
    
    for (int i = 0; i < stats->unique_count; i++) free(unique_values[i]);
    free(unique_values);
    free(unique_counts);
    free(temp_counts);
    free(numeric_values);
}

int analyzer_mpi_analyze_dataset(char **data, char **headers, int num_rows, 
                                 int num_cols, DatasetStats *stats) {
    if (!data || !headers || !stats) return -1;
    
    // Note: In a full MPI implementation, we would:
    // 1. MPI_Init() - Initialize MPI
    // 2. Get rank and size
    // 3. Distribute columns across processes
    // 4. Each process analyzes its columns
    // 5. Gather results back to root
    // 6. MPI_Finalize()
    
    // For this placeholder, we'll just simulate with timing
    printf("Starting MPI analysis (simulated) on %d rows x %d columns...\n", 
           num_rows, num_cols);
    
    double start = MPI_Wtime();
    
    for (int col = 0; col < num_cols; col++) {
        char **column_data = (char**)malloc(num_rows * sizeof(char*));
        for (int row = 0; row < num_rows; row++) {
            column_data[row] = data[row * num_cols + col];
        }
        
        analyze_column(column_data, num_rows, headers[col], &stats->columns[col]);
        free(column_data);
        
        printf("Analyzed column %d/%d: %s\n", col + 1, num_cols, headers[col]);
    }
    
    double end = MPI_Wtime();
    stats->processing_time = end - start;
    stats->num_processes = 1;  // Would be MPI_Comm_size in full implementation
    
    printf("MPI analysis completed in %.4f seconds.\n", stats->processing_time);
    return 0;
}

void analyzer_mpi_print_stats(DatasetStats *stats) {
    if (!stats) return;
    
    printf("\n=== Dataset Statistics (MPI) ===\n");
    printf("Total columns: %d\n", stats->num_columns);
    printf("Processing time: %.4f seconds\n", stats->processing_time);
    printf("Processes used: %d\n\n", stats->num_processes);
    
    for (int i = 0; i < stats->num_columns; i++) {
        ColumnStats *col = &stats->columns[i];
        printf("Column: %s\n", col->column_name);
        printf("  Data Type: ");
        switch(col->data_type) {
            case TYPE_NUMERIC: printf("Numeric\n"); break;
            case TYPE_CATEGORICAL: printf("Categorical\n"); break;
            case TYPE_MIXED: printf("Mixed\n"); break;
            default: printf("Unknown\n");
        }
        printf("  Total: %d, Nulls: %d (%.2f%%), Unique: %d\n", 
               col->total_count, col->null_count, col->null_percentage, col->unique_count);
        if (col->data_type == TYPE_NUMERIC) {
            printf("  Min: %.2f, Max: %.2f, Mean: %.2f, Median: %.2f, StdDev: %.2f\n",
                   col->min_value, col->max_value, col->mean, col->median, col->std_dev);
        }
        printf("\n");
    }
}

char* analyzer_mpi_get_stats_json(DatasetStats *stats) {
    if (!stats) return NULL;
    
    char *json = (char*)malloc(1000000);
    char *ptr = json;
    
    ptr += sprintf(ptr, "{\n  \"processing_time\": %.4f,\n", stats->processing_time);
    ptr += sprintf(ptr, "  \"num_processes\": %d,\n", stats->num_processes);
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
        ptr += sprintf(ptr, "      \"unique_count\": %d\n", col->unique_count);
        ptr += sprintf(ptr, "    }%s\n", (i < stats->num_columns - 1) ? "," : "");
    }
    
    ptr += sprintf(ptr, "  ]\n}\n");
    return json;
}
