#include "cuda_analyzer.h"

int main() {
    int num_rows = 5;
    int num_cols = 3;

    char *headers[] = {
        (char*)"age",
        (char*)"salary",
        (char*)"city"
    };

    char *data[] = {
        (char*)"20", (char*)"50000",  (char*)"Colombo",
        (char*)"25", (char*)"60000",  (char*)"Kandy",
        (char*)"30", (char*)"55000",  (char*)"Colombo",
        (char*)"35", (char*)"200000", (char*)"Galle",
        (char*)"na", (char*)"62000",  (char*)"Jaffna"
    };

    DatasetStats *stats = analyzer_cuda_create_stats(num_cols);
    if (!stats) {
        printf("Failed to create stats\n");
        return 1;
    }

    analyzer_cuda_analyze_dataset(data, headers, num_rows, num_cols, stats);
    analyzer_cuda_print_stats(stats);

    char *json = analyzer_cuda_get_stats_json(stats);
    if (json) {
        printf("\nJSON Output:\n%s\n", json);
        free(json);
    }

    analyzer_cuda_free_stats(stats);
    return 0;
}
