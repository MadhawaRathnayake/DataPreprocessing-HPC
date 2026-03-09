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
} PreprocessedData;

typedef struct {
    char *method;          /* "iqr" or "zscore" */
    char *treatment;       /* "remove", "cap", or "flag" */
    char **columns;        /* Columns to apply to */
    int num_columns;
} OutlierConfig;

typedef struct {
    char *method;          /* "minmax", "zscore", etc */
    char **columns;        /* Columns to scale */
    int num_columns;
} ScalingConfig;

typedef struct {
    char **columns;        /* Columns to encode */
    int num_columns;
} EncodingConfig;

/* Function declarations */

/* Serial preprocessing */
PreprocessedData* preprocess_serial(
    char **raw_data,
    char **headers,
    int num_rows,
    int num_cols,
    int should_remove_duplicates,
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
    OutlierConfig *outlier_cfg,
    ScalingConfig *scaling_cfg,
    EncodingConfig *encoding_cfg
);

/* Utility functions */
void free_preprocessed_data(PreprocessedData *data);
char* preprocess_to_json(PreprocessedData *data);

#endif /* PREPROCESSOR_H */
