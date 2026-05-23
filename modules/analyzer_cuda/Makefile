NVCC = nvcc
NVCCFLAGS = -O2 -std=c++17 -arch=sm_86 -Xcompiler -fPIC
LDFLAGS = -shared

LIB_DIR = ../../lib
TARGET = $(LIB_DIR)/libpreprocessor_cuda.so
STANDALONE_TARGET = cuda_preprocessor_hybrid_standalone
SOURCES = cuda_preprocessor.cu
STANDALONE_SOURCES = cuda_preprocessor.cu
HEADERS = cuda_preprocessor.h

all: $(TARGET)

$(TARGET): $(SOURCES) $(HEADERS)
	mkdir -p $(LIB_DIR)
	$(NVCC) $(NVCCFLAGS) -Xcompiler -fopenmp -DCUDA_HYBRID_LIBRARY $(LDFLAGS) -o $@ $(SOURCES)
	@echo "Built columnar CUDA preprocessor for app: $@"

standalone: $(STANDALONE_TARGET)

$(STANDALONE_TARGET): $(STANDALONE_SOURCES) $(HEADERS)
	$(NVCC) $(NVCCFLAGS) -Xcompiler -fopenmp -o $@ $(STANDALONE_SOURCES)
	@echo "Built columnar CUDA standalone analyzer: $@"

clean:
	rm -f $(TARGET) $(STANDALONE_TARGET)
	@echo "Cleaned CUDA preprocessor module"

.PHONY: all standalone clean
