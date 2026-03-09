#ifndef CUDA_ANALYZER_H
#define CUDA_ANALYZER_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <math.h>
#include <ctype.h>
#include <cuda_runtime.h>

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
    char *column_name;
    DataType data_type;
    Category category;

    int total_count;
    int null_count;
    int unique_count;
    double null_percentage;

    double min_value;
    double max_value;
    double mean;
    double median;
    double std_dev;
    double *outliers;
    int outlier_count;

    ValueCount *value_counts;
    int value_count_size;

    int has_nulls;
    int has_outliers;
    int has_duplicates;
    int type_consistent;
} ColumnStats;

typedef struct {
    ColumnStats *columns;
    int num_columns;
    double processing_time;
    int gpu_used;
} DatasetStats;

DatasetStats* analyzer_cuda_create_stats(int num_columns);
void analyzer_cuda_free_stats(DatasetStats *stats);
int analyzer_cuda_analyze_dataset(char **data, char **headers, int num_rows,
                                  int num_cols, DatasetStats *stats);
void analyzer_cuda_print_stats(DatasetStats *stats);
char* analyzer_cuda_get_stats_json(DatasetStats *stats);

#endif
