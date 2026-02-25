#ifndef CSV_IMPORTER_H
#define CSV_IMPORTER_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_COLUMNS 100
#define MAX_ROW_LENGTH 4096
#define MAX_CELL_LENGTH 512

typedef struct {
    char **data;           // 2D array for cell data
    char **headers;        // Column headers
    int num_rows;
    int num_cols;
    int capacity;          // Current capacity for rows
} CSVData;

// Function declarations
CSVData* csv_create();
void csv_free(CSVData *csv);
int csv_load_file(const char *filename, CSVData *csv);
char* csv_get_cell(CSVData *csv, int row, int col);
char* csv_get_header(CSVData *csv, int col);
int csv_get_preview(CSVData *csv, int num_rows, char ***preview_data);

#endif // CSV_IMPORTER_H
