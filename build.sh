#!/bin/bash
# Build script for Data Preprocessing Application
# Compiles all C modules into shared libraries

set -e  # Exit on error

echo "================================"
echo "Building Data Preprocessing App"
echo "================================"
echo ""

# Check if running from project root
if [ ! -d "modules" ]; then
    echo "Error: Please run this script from the project root directory"
    exit 1
fi

# Create lib directory
mkdir -p lib

# Build CSV Importer
echo "Building CSV Importer module..."
cd modules/importer
make clean
make
cd ../..
echo "✓ CSV Importer built successfully"
echo ""

# Build Series Processing (Serial Analyzer)
echo "Building Series Processing (Serial) module..."
cd modules/series_processing
make clean
make
cd ../..
echo "✓ Series Processing (Serial) built successfully"
echo ""

# Build OpenMP Analyzer
echo "Building OpenMP Analyzer module..."
cd modules/analyzer_openmp
make clean
make
cd ../..
echo "✓ OpenMP Analyzer built successfully"
echo ""

# Build MPI Analyzer (optional, requires MPI)
echo "Building MPI Analyzer module..."
if command -v mpicc &> /dev/null; then
    cd modules/analyzer_mpi
    make clean
    make
    cd ../..
    echo "✓ MPI Analyzer built successfully"
else
    echo "⚠ Warning: mpicc not found. Skipping MPI Analyzer."
    echo "  Install OpenMPI or MPICH to build MPI support."
fi
echo ""

# List built libraries
echo "Built libraries:"
ls -lh lib/
echo ""

echo "================================"
echo "Build completed successfully!"
echo "================================"
echo ""
echo "To run the application:"
echo "  cd ui"
echo "  python3 main_app.py"
echo ""
