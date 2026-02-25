CC = gcc
CFLAGS = -Wall -O2 -fPIC
LDFLAGS = -shared -lm

TARGET = ../../lib/libserialanalyzer.so
SOURCES = serial_analyzer.c
OBJECTS = $(SOURCES:.c=.o)
HEADERS = serial_analyzer.h

all: $(TARGET)

$(TARGET): $(OBJECTS)
	mkdir -p ../../lib
	$(CC) $(LDFLAGS) -o $@ $^

%.o: %.c $(HEADERS)
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJECTS) $(TARGET)

.PHONY: all clean
