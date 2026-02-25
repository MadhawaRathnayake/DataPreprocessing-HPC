#include "csv_importer.h"
#include <ctype.h>

// Helper function to trim whitespace
static char* trim_whitespace(char *str) {
    char *end;
    
    // Trim leading space
    while(isspace((unsigned char)*str)) str++;
    
    if(*str == 0) return str;
    
    // Trim trailing space
    end = str + strlen(str) - 1;
    while(end > str && isspace((unsigned char)*end)) end--;
    
    end[1] = '\0';
    return str;
}

// Parse a CSV line considering quoted fields
static int parse_csv_line(char *line, char **fields, int max_fields) {
    int field_count = 0;
    char *ptr = line;
    char *field_start;
    int in_quotes = 0;
    int i = 0;
    
    char buffer[MAX_CELL_LENGTH];
    int buf_idx = 0;
    
    while (*ptr && field_count < max_fields) {
        buf_idx = 0;
        
        // Skip leading whitespace
        while (*ptr == ' ' || *ptr == '\t') ptr++;
        
        // Check if field starts with quote
        if (*ptr == '"') {
            in_quotes = 1;
            ptr++;
            
            while (*ptr) {
                if (*ptr == '"') {
                    if (*(ptr + 1) == '"') {
                        // Escaped quote
                        buffer[buf_idx++] = '"';
                        ptr += 2;
                    } else {
                        // End of quoted field
                        in_quotes = 0;
                        ptr++;
                        break;
                    }
                } else {
                    buffer[buf_idx++] = *ptr++;
                }
            }
            
            // Skip to comma or end
            while (*ptr && *ptr != ',') ptr++;
        } else {
            // Unquoted field
            while (*ptr && *ptr != ',') {
                buffer[buf_idx++] = *ptr++;
            }
        }
        
        buffer[buf_idx] = '\0';
        fields[field_count] = malloc(strlen(buffer) + 1);
        strcpy(fields[field_count], trim_whitespace(buffer));
        field_count++;
        
        if (*ptr == ',') ptr++;
    }
    
    return field_count;
}

CSVData* csv_create() {
    CSVData *csv = (CSVData*)malloc(sizeof(CSVData));
    if (!csv) return NULL;
    
    csv->capacity = 1000;  // Initial capacity
    csv->data = (char**)malloc(csv->capacity * MAX_COLUMNS * sizeof(char*));
    csv->headers = (char**)malloc(MAX_COLUMNS * sizeof(char*));
    csv->num_rows = 0;
    csv->num_cols = 0;
    
    // Initialize all pointers to NULL
    for (int i = 0; i < csv->capacity * MAX_COLUMNS; i++) {
        csv->data[i] = NULL;
    }
    for (int i = 0; i < MAX_COLUMNS; i++) {
        csv->headers[i] = NULL;
    }
    
    return csv;
}

void csv_free(CSVData *csv) {
    if (!csv) return;
    
    // Free headers
    for (int i = 0; i < csv->num_cols; i++) {
        if (csv->headers[i]) free(csv->headers[i]);
    }
    free(csv->headers);
    
    // Free data cells
    for (int i = 0; i < csv->num_rows * csv->num_cols; i++) {
        if (csv->data[i]) free(csv->data[i]);
    }
    free(csv->data);
    
    free(csv);
}

int csv_load_file(const char *filename, CSVData *csv) {
    FILE *file = fopen(filename, "r");
    if (!file) {
        fprintf(stderr, "Error: Cannot open file %s\n", filename);
        return -1;
    }
    
    char line[MAX_ROW_LENGTH];
    char *fields[MAX_COLUMNS];
    int line_num = 0;
    
    // Read header line
    if (fgets(line, sizeof(line), file)) {
        // Remove newline
        line[strcspn(line, "\r\n")] = 0;
        
        csv->num_cols = parse_csv_line(line, fields, MAX_COLUMNS);
        
        // Store headers
        for (int i = 0; i < csv->num_cols; i++) {
            csv->headers[i] = fields[i];
        }
        
        line_num++;
    }
    
    // Read data lines
    while (fgets(line, sizeof(line), file)) {
        // Remove newline
        line[strcspn(line, "\r\n")] = 0;
        
        // Skip empty lines
        if (strlen(trim_whitespace(line)) == 0) continue;
        
        // Expand capacity if needed
        if (csv->num_rows >= csv->capacity) {
            csv->capacity *= 2;
            csv->data = (char**)realloc(csv->data, 
                                        csv->capacity * MAX_COLUMNS * sizeof(char*));
            // Initialize new memory to NULL
            for (int i = csv->num_rows * MAX_COLUMNS; 
                 i < csv->capacity * MAX_COLUMNS; i++) {
                csv->data[i] = NULL;
            }
        }
        
        int num_fields = parse_csv_line(line, fields, MAX_COLUMNS);
        
        // Store row data
        for (int i = 0; i < csv->num_cols; i++) {
            int idx = csv->num_rows * csv->num_cols + i;
            if (i < num_fields) {
                csv->data[idx] = fields[i];
            } else {
                // Missing field - store empty string
                csv->data[idx] = malloc(1);
                csv->data[idx][0] = '\0';
            }
        }
        
        csv->num_rows++;
        line_num++;
    }
    
    fclose(file);
    
    printf("Loaded %d rows and %d columns from %s\n", 
           csv->num_rows, csv->num_cols, filename);
    
    return 0;
}

char* csv_get_cell(CSVData *csv, int row, int col) {
    if (!csv || row < 0 || row >= csv->num_rows || 
        col < 0 || col >= csv->num_cols) {
        return NULL;
    }
    
    return csv->data[row * csv->num_cols + col];
}

char* csv_get_header(CSVData *csv, int col) {
    if (!csv || col < 0 || col >= csv->num_cols) {
        return NULL;
    }
    
    return csv->headers[col];
}

int csv_get_preview(CSVData *csv, int num_rows, char ***preview_data) {
    if (!csv || num_rows <= 0) return -1;
    
    int preview_rows = (num_rows < csv->num_rows) ? num_rows : csv->num_rows;
    
    // Allocate preview data (including header row)
    *preview_data = (char**)malloc((preview_rows + 1) * csv->num_cols * sizeof(char*));
    
    // Copy headers
    for (int col = 0; col < csv->num_cols; col++) {
        (*preview_data)[col] = malloc(strlen(csv->headers[col]) + 1);
        strcpy((*preview_data)[col], csv->headers[col]);
    }
    
    // Copy data rows
    for (int row = 0; row < preview_rows; row++) {
        for (int col = 0; col < csv->num_cols; col++) {
            int src_idx = row * csv->num_cols + col;
            int dst_idx = (row + 1) * csv->num_cols + col;
            
            char *cell = csv->data[src_idx];
            (*preview_data)[dst_idx] = malloc(strlen(cell) + 1);
            strcpy((*preview_data)[dst_idx], cell);
        }
    }
    
    return preview_rows + 1; // Return total rows including header
}
