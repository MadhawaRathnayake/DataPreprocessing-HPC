#include "cuda_analyzer.h"
#include "csv_loader.h"
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
    if (argc < 2) {
        printf("Usage: %s <csv_file>\n", argv[0]);
        return 1;
    }

    const char *filename = argv[1];

    CSVData *csv = load_csv(filename);
    if (!csv) {
        printf("Failed to load CSV: %s\n", filename);
        return 1;
    }

    printf("Loaded CSV successfully.\n");
    printf("Rows: %d, Columns: %d\n", csv->num_rows, csv->num_cols);

    DatasetStats *stats = analyzer_cuda_create_stats(csv->num_cols);
    if (!stats) {
        printf("Failed to create stats object.\n");
        free_csv(csv);
        return 1;
    }

    if (analyzer_cuda_analyze_dataset(csv->data, csv->headers,
                                      csv->num_rows, csv->num_cols, stats) != 0) {
        printf("Dataset analysis failed.\n");
        analyzer_cuda_free_stats(stats);
        free_csv(csv);
        return 1;
    }

    analyzer_cuda_print_stats(stats);

    char *json = analyzer_cuda_get_stats_json(stats);
    if (json) {
        FILE *fp = fopen("/content/output_stats.json", "w");
        if (fp) {
            fputs(json, fp);
            fclose(fp);
            printf("Saved JSON output to /content/output_stats.json\n");
        }
        free(json);
    }

    analyzer_cuda_free_stats(stats);
    free_csv(csv);
    return 0;
}
