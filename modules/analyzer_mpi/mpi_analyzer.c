#include "mpi_analyzer.h"


// Helper functions (same as serial/OpenMP)
static int is_numeric(const char *str) {
    if (!str || strlen(str) == 0) return 0;

    char *endptr;
    strtod(str, &endptr);

    // Check if entire string was consumed and it's not just whitespace
    while (*endptr && isspace(*endptr)) endptr++;
    return *endptr == '\0';
}

// Helper function to check if value is null/empty
static int is_null(const char *str) {
    if (!str || strlen(str) == 0) return 1;

    // Check for common null representations
    if (strcasecmp(str, "null") == 0 || strcasecmp(str, "na") == 0 ||
        strcasecmp(str, "n/a") == 0 || strcasecmp(str, "nan") == 0) {
        return 1;
    }

    return 0;
}

// Comparison function for qsort (doubles)
static int compare_doubles(const void *a, const void *b) {
    double diff = *(double*)a - *(double*)b;
    return (diff > 0) - (diff < 0);
}

// Comparison function for value counts
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
        if (stats->columns[i].column_name) {
            free(stats->columns[i].column_name);
        }
        if (stats->columns[i].outliers) {
            free(stats->columns[i].outliers);
        }
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
    // Initialize statistics
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
    
    // Temporary storage for analysis
    double *numeric_values = (double*)malloc(num_rows * sizeof(double));
    char **unique_values = (char**)malloc(num_rows * sizeof(char*));
    int *unique_counts = (int*)calloc(num_rows, sizeof(int));
    int numeric_count = 0;
    int categorical_count = 0;
    
    // First pass: count nulls, determine type, collect values
    for (int i = 0; i < num_rows; i++) {
        char *value = column_data[i];
        
        if (is_null(value)) {
            stats->null_count++;
            continue;
        }
        
        // Check if numeric
        if (is_numeric(value)) {
            numeric_values[numeric_count++] = atof(value);
        } else {
            categorical_count++;
        }
        
        // Track unique values
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
    
    // Determine data type
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
    
    // Analyze numeric data
    if (stats->data_type == TYPE_NUMERIC && numeric_count > 0) {
        // Sort numeric values for median and outlier detection
        qsort(numeric_values, numeric_count, sizeof(double), compare_doubles);
        
        // Min and Max
        stats->min_value = numeric_values[0];
        stats->max_value = numeric_values[numeric_count - 1];
        
        // Mean
        double sum = 0.0;
        for (int i = 0; i < numeric_count; i++) {
            sum += numeric_values[i];
        }
        stats->mean = sum / numeric_count;
        
        // Median
        if (numeric_count % 2 == 0) {
            stats->median = (numeric_values[numeric_count/2 - 1] + 
                           numeric_values[numeric_count/2]) / 2.0;
        } else {
            stats->median = numeric_values[numeric_count/2];
        }
        
        // Standard deviation
        double variance = 0.0;
        for (int i = 0; i < numeric_count; i++) {
            variance += pow(numeric_values[i] - stats->mean, 2);
        }
        stats->std_dev = sqrt(variance / numeric_count);
        
        // Outlier detection using IQR method
        int q1_idx = numeric_count / 4;
        int q3_idx = (3 * numeric_count) / 4;
        double q1 = numeric_values[q1_idx];
        double q3 = numeric_values[q3_idx];
        double iqr = q3 - q1;
        double lower_bound = q1 - 1.5 * iqr;
        double upper_bound = q3 + 1.5 * iqr;
        
        // Count and store outliers
        stats->outliers = (double*)malloc(MAX_OUTLIERS * sizeof(double));
        for (int i = 0; i < numeric_count && stats->outlier_count < MAX_OUTLIERS; i++) {
            if (numeric_values[i] < lower_bound || numeric_values[i] > upper_bound) {
                stats->outliers[stats->outlier_count++] = numeric_values[i];
            }
        }
        stats->has_outliers = (stats->outlier_count > 0);
        
        // Determine category
        if (stats->unique_count == 2) {
            stats->category = CAT_BINARY;
        } else if (stats->unique_count < 10) {
            stats->category = CAT_DISCRETE;
        } else {
            stats->category = CAT_CONTINUOUS;
        }
    } else {
        // Default values for non-numeric columns
        stats->min_value = 0.0;
        stats->max_value = 0.0;
        stats->mean = 0.0;
        stats->median = 0.0;
        stats->std_dev = 0.0;
        stats->outliers = NULL;

        // Determine categorical type
        if (stats->unique_count == 2) {
            stats->category = CAT_BINARY;
        } else {
            stats->category = CAT_NOMINAL;
        }
    }
    
    // Store value counts (top values for categorical)
    stats->value_count_size = (stats->unique_count < 10) ? stats->unique_count : 10;
    stats->value_counts = (ValueCount*)malloc(stats->value_count_size * sizeof(ValueCount));
    
    // Create temporary array for sorting
    ValueCount *temp_counts = (ValueCount*)malloc(stats->unique_count * sizeof(ValueCount));
    for (int i = 0; i < stats->unique_count; i++) {
        temp_counts[i].value = unique_values[i];
        temp_counts[i].count = unique_counts[i];
    }
    
    // Sort by count descending
    qsort(temp_counts, stats->unique_count, sizeof(ValueCount), compare_value_counts);
    
    // Copy top values
    for (int i = 0; i < stats->value_count_size; i++) {
        stats->value_counts[i].value = malloc(strlen(temp_counts[i].value) + 1);
        strcpy(stats->value_counts[i].value, temp_counts[i].value);
        stats->value_counts[i].count = temp_counts[i].count;
    }
    
    // Cleanup
    for (int i = 0; i < stats->unique_count; i++) {
        free(unique_values[i]);
    }
    free(unique_values);
    free(unique_counts);
    free(temp_counts);
    free(numeric_values);
}

// Helper to send ColumnStats from non-root to root
static void send_column_results(ColumnStats *col, int dest) {
    // 1. Send basic fields (ints and doubles)
    int basic_ints[7] = {
        (int)col->data_type,
        (int)col->category,
        col->total_count,
        col->null_count,
        col->unique_count,
        col->outlier_count,
        col->value_count_size
    };
    MPI_Send(basic_ints, 7, MPI_INT, dest, 0, MPI_COMM_WORLD);

    double basic_doubles[6] = {
        col->null_percentage,
        col->min_value,
        col->max_value,
        col->mean,
        col->median,
        col->std_dev
    };
    MPI_Send(basic_doubles, 6, MPI_DOUBLE, dest, 1, MPI_COMM_WORLD);

    int flags[4] = {
        col->has_nulls,
        col->has_outliers,
        col->has_duplicates,
        col->type_consistent
    };
    MPI_Send(flags, 4, MPI_INT, dest, 2, MPI_COMM_WORLD);

    // 2. Send outliers
    if (col->outlier_count > 0) {
        MPI_Send(col->outliers, col->outlier_count, MPI_DOUBLE, dest, 3, MPI_COMM_WORLD);
    }

    // 3. Send value counts
    for (int i = 0; i < col->value_count_size; i++) {
        int val_len = strlen(col->value_counts[i].value) + 1;
        MPI_Send(&val_len, 1, MPI_INT, dest, 4, MPI_COMM_WORLD);
        MPI_Send(col->value_counts[i].value, val_len, MPI_CHAR, dest, 5, MPI_COMM_WORLD);
        MPI_Send(&col->value_counts[i].count, 1, MPI_INT, dest, 6, MPI_COMM_WORLD);
    }
}

// Helper to receive ColumnStats on root
static void recv_column_results(ColumnStats *col, int src) {
    int basic_ints[7];
    MPI_Recv(basic_ints, 7, MPI_INT, src, 0, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
    col->data_type = (DataType)basic_ints[0];
    col->category = (Category)basic_ints[1];
    col->total_count = basic_ints[2];
    col->null_count = basic_ints[3];
    col->unique_count = basic_ints[4];
    col->outlier_count = basic_ints[5];
    col->value_count_size = basic_ints[6];

    double basic_doubles[6];
    MPI_Recv(basic_doubles, 6, MPI_DOUBLE, src, 1, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
    col->null_percentage = basic_doubles[0];
    col->min_value = basic_doubles[1];
    col->max_value = basic_doubles[2];
    col->mean = basic_doubles[3];
    col->median = basic_doubles[4];
    col->std_dev = basic_doubles[5];

    int flags[4];
    MPI_Recv(flags, 4, MPI_INT, src, 2, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
    col->has_nulls = flags[0];
    col->has_outliers = flags[1];
    col->has_duplicates = flags[2];
    col->type_consistent = flags[3];

    if (col->outlier_count > 0) {
        col->outliers = (double*)malloc(col->outlier_count * sizeof(double));
        MPI_Recv(col->outliers, col->outlier_count, MPI_DOUBLE, src, 3, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
    } else {
        col->outliers = NULL;
    }

    if (col->value_count_size > 0) {
        col->value_counts = (ValueCount*)malloc(col->value_count_size * sizeof(ValueCount));
        for (int i = 0; i < col->value_count_size; i++) {
            int val_len;
            MPI_Recv(&val_len, 1, MPI_INT, src, 4, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            col->value_counts[i].value = (char*)malloc(val_len);
            MPI_Recv(col->value_counts[i].value, val_len, MPI_CHAR, src, 5, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            MPI_Recv(&col->value_counts[i].count, 1, MPI_INT, src, 6, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        }
    } else {
        col->value_counts = NULL;
    }
}

int analyzer_mpi_analyze_dataset(char **data, char **headers, int num_rows, 
                                 int num_cols, DatasetStats *stats) {
    if (!data || !headers || !stats) return -1;
    
    int rank, size;
    int initialized;
    
    MPI_Initialized(&initialized);
    if (!initialized) {
        MPI_Init(NULL, NULL);
    }
    
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    
    if (rank == 0) {
        printf("Starting MPI distributed analysis with %d processes on %d rows x %d columns...\n", 
               size, num_rows, num_cols);
    }
    
    double start = MPI_Wtime();
    
    // Distribute columns across processes using cyclic distribution
    for (int col = 0; col < num_cols; col++) {
        if (col % size == rank) {
            char **column_data = (char**)malloc(num_rows * sizeof(char*));
            for (int row = 0; row < num_rows; row++) {
                column_data[row] = data[row * num_cols + col];
            }
            
            analyze_column(column_data, num_rows, headers[col], &stats->columns[col]);
            free(column_data);
            
            printf("[Rank %d] Analyzed column %d/%d: %s\n", 
                   rank, col + 1, num_cols, headers[col]);
        }
    }
    
    // Synchronize processes before gathering
    MPI_Barrier(MPI_COMM_WORLD);
    
    // Gather all results to rank 0
    for (int col = 0; col < num_cols; col++) {
        int owner = col % size;
        if (rank == 0) {
            if (owner != 0) {
                recv_column_results(&stats->columns[col], owner);
                // Set column name on root since it wasn't analyzed here
                stats->columns[col].column_name = malloc(strlen(headers[col]) + 1);
                strcpy(stats->columns[col].column_name, headers[col]);
            }
        } else {
            if (owner == rank) {
                send_column_results(&stats->columns[col], 0);
            }
        }
    }
    
    double end = MPI_Wtime();
    stats->processing_time = end - start;
    stats->num_processes = size;
    
    if (rank == 0) {
        printf("MPI analysis completed in %.4f seconds using %d processes.\n", 
               stats->processing_time, stats->num_processes);
    }
    
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