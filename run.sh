#!/bin/bash
# Launcher script for Data Preprocessing Application

cd "$(dirname "$0")"

# Check if libraries are built
if [ ! -d "lib" ] || [ -z "$(ls -A lib)" ]; then
    echo "Libraries not found. Building modules..."
    ./build.sh
    echo ""
fi

# Launch the application
echo "Starting Data Preprocessing Application..."
python3 ui/main_app.py
