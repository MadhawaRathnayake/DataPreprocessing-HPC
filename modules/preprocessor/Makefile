CC = gcc
CFLAGS = -fPIC -Wall -O3
LDFLAGS = -shared

# For OpenMP support
CFLAGS_OMP = $(CFLAGS) -fopenmp
LDFLAGS_OMP = $(LDFLAGS) -fopenmp

# For MPI support
CC_MPI = mpicc
CFLAGS_MPI = $(CFLAGS) -fopenmp
LDFLAGS_MPI = $(LDFLAGS) -fopenmp

LIB_DIR = ../../lib
TARGET_SERIAL = $(LIB_DIR)/libpreprocessor.so
TARGET_OMP = $(LIB_DIR)/libpreprocessor_omp.so
TARGET_MPI = $(LIB_DIR)/libpreprocessor_mpi.so

SOURCES = preprocessor.c
OBJECTS = $(SOURCES:.c=.o)

all: $(TARGET_SERIAL) $(TARGET_OMP) $(TARGET_MPI)

$(TARGET_SERIAL): $(OBJECTS)
	$(CC) $(LDFLAGS) -o $@ preprocessor.c
	@echo "✓ Serial preprocessor built: $@"

$(TARGET_OMP): preprocessor.c
	$(CC) $(CFLAGS_OMP) $(LDFLAGS_OMP) -o $@ preprocessor.c
	@echo "✓ OpenMP preprocessor built: $@"

$(TARGET_MPI): preprocessor.c
	if command -v mpicc &> /dev/null; then \
		$(CC_MPI) $(CFLAGS_MPI) $(LDFLAGS_MPI) -o $@ preprocessor.c; \
		echo "✓ MPI preprocessor built: $@"; \
	else \
		echo "⚠ mpicc not found, skipping MPI preprocessor"; \
	fi

clean:
	rm -f $(OBJECTS) $(TARGET_SERIAL) $(TARGET_OMP) $(TARGET_MPI)
	@echo "✓ Cleaned preprocessor module"

.PHONY: all clean
