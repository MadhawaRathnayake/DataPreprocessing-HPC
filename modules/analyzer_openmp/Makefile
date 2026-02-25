CC = gcc
CFLAGS = -Wall -O2 -fPIC -fopenmp
LDFLAGS = -shared -lm -fopenmp

TARGET = ../../lib/libompanalyzer.so
SOURCES = openmp_analyzer.c
OBJECTS = $(SOURCES:.c=.o)
HEADERS = openmp_analyzer.h

all: $(TARGET)

$(TARGET): $(OBJECTS)
	mkdir -p ../../lib
	$(CC) $(LDFLAGS) -o $@ $^

%.o: %.c $(HEADERS)
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJECTS) $(TARGET)

.PHONY: all clean
