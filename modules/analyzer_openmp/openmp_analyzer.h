#ifndef OPENMP_ANALYZER_H
#define OPENMP_ANALYZER_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <ctype.h>
#include <omp.h>

#define MAX_UNIQUE_VALUES 1000
#define MAX_OUTLIERS 100

typedef enum {
    TYPE_NUMERIC,
    TYPE_CATEGORICAL,
    TYPE_MIXED,
    TYPE_UNKNOWN
} DataType;

typedef enum {
    CAT_CONTINUOUS,
    CAT_DISCRETE,
    CAT_NOMINAL,
    CAT_ORDINAL,
    CAT_BINARY,
    CAT_UNKNOWN
} Category;

typedef struct {
    char *value;
    int count;
} ValueCount;

typedef struct {
    // Basic information
    char *column_name;
    DataType data_type;
    Category category;
    
    // Count statistics
    int total_count;
    int null_count;
    int unique_count;
    double null_percentage;
    
    // Numeric statistics (if applicable)
    double min_value;
    double max_value;
    double mean;
    double median;
    double std_dev;
    double *outliers;
    int outlier_count;
    
    // Categorical statistics
    ValueCount *value_counts;
    int value_count_size;
    
    // Data quality flags
    int has_nulls;
    int has_outliers;
    int has_duplicates;
    int type_consistent;
} ColumnStats;

typedef struct {
    ColumnStats *columns;
    int num_columns;
    double processing_time;
    int num_threads;
} DatasetStats;

// Function declarations
DatasetStats* analyzer_omp_create_stats(int num_columns);
void analyzer_omp_free_stats(DatasetStats *stats);
int analyzer_omp_analyze_dataset(char **data, char **headers, int num_rows, 
                                 int num_cols, DatasetStats *stats, int num_threads);
void analyzer_omp_print_stats(DatasetStats *stats);
char* analyzer_omp_get_stats_json(DatasetStats *stats);

#endif // OPENMP_ANALYZER_H
