/*
 * C Preprocessing Library
 * Handles: duplicates removal, missing value imputation, outlier treatment,
 * scaling, and categorical encoding
 * Supports: Serial, OpenMP, MPI backends
 */

#ifndef PREPROCESSOR_H
#define PREPROCESSOR_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* Data structures */
typedef struct {
    char **data;           /* Preprocessed data rows */
    int num_rows;          /* Number of rows after preprocessing */
    int num_cols;          /* Number of columns */
    char **headers;        /* Column headers */
    int rows_removed;      /* Rows removed during preprocessing */
    int duplicates_found;  /* Number of duplicates removed */
    int missing_filled;    /* Number of missing values filled */
    int outliers_removed;  /* Number of outliers removed */
    int columns_scaled;    /* Number of columns scaled */
    int columns_encoded;   /* Number of columns encoded */
    double processing_time_ms;
    double duplicates_time_ms;
    double missing_time_ms;
    double outliers_time_ms;
    double scaling_time_ms;
    double encoding_time_ms;
} PreprocessedData;

typedef struct {
    int method;            /* 0=IQR, 1=Z-score */
    int treatment;         /* 0=remove, 1=cap, 2=flag */
    char **columns;        /* Columns to apply to */
    int num_columns;
    double threshold;      /* IQR multiplier or Z-score threshold */
} OutlierConfig;

typedef struct {
    int method;            /* 0=min-max, 1=z-score, 2=standard */
    char **columns;        /* Columns to scale */
    int num_columns;
} ScalingConfig;

typedef struct {
    int method;            /* 0=label, 1=onehot */
    char **columns;        /* Columns to encode */
    int num_columns;
} EncodingConfig;

typedef struct {
    char *column_name;
    int strategy;          /* 0=drop row, 1=mean, 2=median, 3=mode, 4=constant, 5=forward-fill */
    char *fill_value;      /* For constant strategy */
} ColumnMissingConfig;

typedef struct {
    ColumnMissingConfig *configs;
    int num_configs;
    double drop_threshold;
} MissingConfig;

/* Function declarations */

/* Serial preprocessing */
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
);

/* OpenMP parallel preprocessing */
PreprocessedData* preprocess_openmp(
    char **raw_data,
    char **headers,
    int num_rows,
    int num_cols,
    int num_threads,
    int should_remove_duplicates,
    MissingConfig *missing_cfg,
    OutlierConfig *outlier_cfg,
    ScalingConfig *scaling_cfg,
    EncodingConfig *encoding_cfg
);

/* MPI parallel preprocessing */
PreprocessedData* preprocess_mpi(
    char **raw_data,
    char **headers,
    int num_rows,
    int num_cols,
    int num_processes,
    int should_remove_duplicates,
    MissingConfig *missing_cfg,
    OutlierConfig *outlier_cfg,
    ScalingConfig *scaling_cfg,
    EncodingConfig *encoding_cfg
);

/* Utility functions */
void free_preprocessed_data(PreprocessedData *data);
char* preprocess_to_json(PreprocessedData *data);

#endif /* PREPROCESSOR_H */
