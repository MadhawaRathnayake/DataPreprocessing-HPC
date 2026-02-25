CC = gcc
CFLAGS = -Wall -O2 -fPIC
LDFLAGS = -shared

TARGET = ../../lib/libcsvimporter.so
SOURCES = csv_importer.c
OBJECTS = $(SOURCES:.c=.o)
HEADERS = csv_importer.h

all: $(TARGET)

$(TARGET): $(OBJECTS)
	mkdir -p ../../lib
	$(CC) $(LDFLAGS) -o $@ $^

%.o: %.c $(HEADERS)
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJECTS) $(TARGET)

.PHONY: all clean
