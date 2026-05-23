#ifndef CUDA_PREPROCESSOR_H
#define CUDA_PREPROCESSOR_H

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    int method;          /* 0=IQR, 1=Z-score */
    int treatment;       /* 0=remove, 1=cap, 2=flag */
    char **columns;
    int num_columns;
    double threshold;
} OutlierConfig;

typedef struct {
    int method;          /* 0=minmax, 1=zscore, 2=robust */
    char **columns;
    int num_columns;
} ScalingConfig;

typedef struct {
    int method;          /* 0=label, 1=onehot */
    char **columns;
    int num_columns;
    int *methods;        /* Optional per-column methods: 0=label, 1=onehot */
    int drop_original;   /* For one-hot columns */
} EncodingConfig;

typedef struct {
    char *column_name;
    int strategy;        /* 0=drop row, 1=mean, 2=median, 3=mode, 4=constant, 5=forward-fill */
    char *fill_value;
} ColumnMissingConfig;

typedef struct {
    ColumnMissingConfig *configs;
    int num_configs;
    double drop_threshold;
} MissingConfig;

typedef struct {
    int action;          /* 0=exact row, 1=subset */
    int keep;            /* 0=first, 1=last, 2=none */
    char **columns;
    int num_columns;
} DuplicateConfig;

typedef struct {
    char **data;
    int num_rows;
    int num_cols;
    char **headers;
    int duplicates_found;
    int missing_filled;
    int outliers_removed;
    int columns_scaled;
    int columns_encoded;
    double processing_time_ms;
} PreprocessedData;

PreprocessedData* preprocess_cuda(
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
);

void free_preprocessed_data(PreprocessedData *data);
char* preprocess_to_json(PreprocessedData *data);

#ifdef __cplusplus
}
#endif

#endif /* CUDA_PREPROCESSOR_H */
