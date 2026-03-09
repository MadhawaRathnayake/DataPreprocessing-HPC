#include "csv_loader.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char* str_dup_local(const char *src) {
    if (!src) return NULL;
    char *dst = (char*)malloc(strlen(src) + 1);
    if (dst) strcpy(dst, src);
    return dst;
}

static void trim_newline(char *s) {
    if (!s) return;
    size_t len = strlen(s);
    while (len > 0 && (s[len - 1] == '\n' || s[len - 1] == '\r')) {
        s[len - 1] = '\0';
        len--;
    }
}

static int count_columns(const char *line) {
    int count = 1;
    for (const char *p = line; *p; p++) {
        if (*p == ',') count++;
    }
    return count;
}

CSVData* load_csv(const char *filename) {
    FILE *fp = fopen(filename, "r");
    if (!fp) {
        printf("Failed to open CSV file: %s\n", filename);
        return NULL;
    }

    char buffer[8192];

    if (!fgets(buffer, sizeof(buffer), fp)) {
        fclose(fp);
        return NULL;
    }

    trim_newline(buffer);

    int num_cols = count_columns(buffer);

    CSVData *csv = (CSVData*)malloc(sizeof(CSVData));
    if (!csv) {
        fclose(fp);
        return NULL;
    }

    csv->num_rows = 0;
    csv->num_cols = num_cols;
    csv->headers = (char**)malloc(num_cols * sizeof(char*));
    csv->data = NULL;

    if (!csv->headers) {
        free(csv);
        fclose(fp);
        return NULL;
    }

    // Parse header
    char *header_copy = str_dup_local(buffer);
    char *token = strtok(header_copy, ",");
    int col = 0;
    while (token && col < num_cols) {
        csv->headers[col++] = str_dup_local(token);
        token = strtok(NULL, ",");
    }
    free(header_copy);

    // Count rows
    long data_start = ftell(fp);
    while (fgets(buffer, sizeof(buffer), fp)) {
        csv->num_rows++;
    }

    // Allocate flattened data array
    csv->data = (char**)malloc(csv->num_rows * csv->num_cols * sizeof(char*));
    if (!csv->data) {
        for (int i = 0; i < csv->num_cols; i++) free(csv->headers[i]);
        free(csv->headers);
        free(csv);
        fclose(fp);
        return NULL;
    }

    // Rewind to start of data rows
    fseek(fp, data_start, SEEK_SET);

    int row = 0;
    while (fgets(buffer, sizeof(buffer), fp) && row < csv->num_rows) {
        trim_newline(buffer);

        char *line_copy = str_dup_local(buffer);
        char *tok = strtok(line_copy, ",");

        for (int c = 0; c < csv->num_cols; c++) {
            if (tok) {
                csv->data[row * csv->num_cols + c] = str_dup_local(tok);
                tok = strtok(NULL, ",");
            } else {
                csv->data[row * csv->num_cols + c] = str_dup_local("");
            }
        }

        free(line_copy);
        row++;
    }

    fclose(fp);
    return csv;
}

void free_csv(CSVData *csv) {
    if (!csv) return;

    if (csv->headers) {
        for (int i = 0; i < csv->num_cols; i++) {
            free(csv->headers[i]);
        }
        free(csv->headers);
    }

    if (csv->data) {
        for (int i = 0; i < csv->num_rows * csv->num_cols; i++) {
            free(csv->data[i]);
        }
        free(csv->data);
    }

    free(csv);
}
