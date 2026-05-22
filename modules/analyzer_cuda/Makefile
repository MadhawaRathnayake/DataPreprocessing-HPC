NVCC = nvcc
NVCCFLAGS = -O2 -std=c++17 -arch=sm_86 -Xcompiler -fPIC
LDFLAGS = -shared

LIB_DIR = ../../lib
TARGET = $(LIB_DIR)/libpreprocessor_cuda.so
SOURCES = cuda_preprocessor.cu
HEADERS = cuda_preprocessor.h

all: $(TARGET)

$(TARGET): $(SOURCES) $(HEADERS)
	mkdir -p $(LIB_DIR)
	$(NVCC) $(NVCCFLAGS) $(LDFLAGS) -o $@ $(SOURCES)
	@echo "Built CUDA preprocessor: $@"

clean:
	rm -f $(TARGET)
	@echo "Cleaned CUDA preprocessor module"

.PHONY: all clean
