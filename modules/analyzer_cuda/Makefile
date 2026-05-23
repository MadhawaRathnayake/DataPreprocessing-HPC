NVCC = nvcc
NVCCFLAGS = -O2 -std=c++17 -arch=sm_86 -Xcompiler -fPIC
LDFLAGS = -shared

LIB_DIR = ../../lib
TARGET = $(LIB_DIR)/libpreprocessor_cuda.so
STANDALONE_TARGET = cuda_preprocessor_hybrid_standalone
NORMAL_STANDALONE_TARGET = cuda_preprocessor_normal_standalone
ORIGINAL_SOURCES = cuda_preprocessor.cu
SOURCES = cuda_preprocessor.cu
STANDALONE_SOURCES = cuda_preprocessor_hybrid_standalone.cu
NORMAL_STANDALONE_SOURCES = cuda_preprocessor_normal_standalone.cpp
HEADERS = cuda_preprocessor.h

all: $(TARGET)

$(TARGET): $(SOURCES) $(HEADERS)
	mkdir -p $(LIB_DIR)
	$(NVCC) $(NVCCFLAGS) -Xcompiler -fopenmp $(LDFLAGS) -o $@ $(SOURCES)
	@echo "Built merged CUDA preprocessor for app: $@"

standalone: $(STANDALONE_TARGET)

$(STANDALONE_TARGET): $(STANDALONE_SOURCES) $(HEADERS)
	$(NVCC) $(NVCCFLAGS) -Xcompiler -fopenmp -o $@ $(STANDALONE_SOURCES)
	@echo "Built hybrid CUDA + CPU-threaded standalone analyzer: $@"

normal_standalone: $(NORMAL_STANDALONE_TARGET)

$(NORMAL_STANDALONE_TARGET): $(ORIGINAL_SOURCES) $(NORMAL_STANDALONE_SOURCES) $(HEADERS)
	$(NVCC) $(NVCCFLAGS) -Xcompiler -fopenmp -o $@ $(ORIGINAL_SOURCES) $(NORMAL_STANDALONE_SOURCES)
	@echo "Built merged CUDA standalone preprocessor: $@"

clean:
	rm -f $(TARGET) $(STANDALONE_TARGET) $(NORMAL_STANDALONE_TARGET)
	@echo "Cleaned CUDA preprocessor module"

.PHONY: all standalone normal_standalone clean
