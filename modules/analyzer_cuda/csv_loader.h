#ifndef CSV_LOADER_H
#define CSV_LOADER_H

typedef struct {
    char **headers;
    char **data;     // flattened row-major: data[row * num_cols + col]
    int num_rows;
    int num_cols;
} CSVData;

CSVData* load_csv(const char *filename);
void free_csv(CSVData *csv);

#endif
