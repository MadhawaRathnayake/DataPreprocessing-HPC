# Data Preprocessing Application

A modular data preprocessing application with parallel processing capabilities using OpenMP and MPI. Built with C modules for high-performance data processing and Python Tkinter for the user interface.

## Features

- **Modular Architecture**: Separate C modules for different functionalities
- **Modular UI**: Each tab implemented as independent module for better maintainability
- **CSV Import**: Fast CSV file reading and preview (first 15 rows)
- **Serial Analysis**: Traditional single-threaded data analysis
- **OpenMP Analysis**: Multi-threaded parallel processing
- **MPI Analysis**: Distributed parallel processing (simplified implementation)
- **Extensible Design**: Easy to add new preprocessing features

## Project Structure

```
data_preprocessing_app/
├── modules/                    # C modules for data processing
│   ├── importer/              # CSV import module
│   │   ├── csv_importer.h
│   │   ├── csv_importer.c
│   │   └── Makefile
│   ├── analyzer_serial/       # Serial analysis module
│   │   ├── serial_analyzer.h
│   │   ├── serial_analyzer.c
│   │   └── Makefile
│   ├── analyzer_openmp/       # OpenMP parallel analysis
│   │   ├── openmp_analyzer.h
│   │   ├── openmp_analyzer.c
│   │   └── Makefile
│   └── analyzer_mpi/          # MPI parallel analysis
│       ├── mpi_analyzer.h
│       ├── mpi_analyzer.c
│       └── Makefile
├── ui/                        # Python Tkinter UI (Modular)
│   ├── __init__.py           # Package initialization
│   ├── main_app.py           # Main application coordinator
│   ├── base_tab.py           # Base class for all tabs
│   ├── import_tab.py         # Import tab module
│   ├── serial_analyzer_tab.py    # Serial analyzer module
│   ├── openmp_analyzer_tab.py    # OpenMP analyzer module
│   ├── mpi_analyzer_tab.py       # MPI analyzer module
│   ├── export_tab.py         # Export tab module
│   └── UI_ARCHITECTURE.md    # UI architecture documentation
├── lib/                       # Compiled shared libraries (generated)
├── data/                      # Sample data files
│   └── sample_employees.csv
├── build.sh                   # Build script
└── README.md                  # This file
```

## Requirements

### System Requirements
- Linux (Ubuntu 20.04+ or similar)
- GCC compiler
- Python 3.6+
- Tkinter (python3-tk)
- OpenMP support (usually included with GCC)
- OpenMPI or MPICH (optional, for MPI module)

### Installation

#### On Ubuntu/Debian:
```bash
# Essential tools
sudo apt-get update
sudo apt-get install build-essential gcc python3 python3-tk

# For OpenMP (usually included with gcc)
# Already available with gcc

# For MPI support (optional)
sudo apt-get install openmpi-bin openmpi-common libopenmpi-dev
```

#### On Fedora/RHEL/CentOS:
```bash
sudo dnf install gcc gcc-c++ python3 python3-tkinter
# For MPI
sudo dnf install openmpi openmpi-devel
```

## Building the Application

1. Clone or extract the project to a directory
2. Navigate to the project root directory
3. Run the build script:

```bash
cd data_preprocessing_app
./build.sh
```

The build script will:
- Compile all C modules
- Create shared libraries in the `lib/` directory
- Display build status for each module

## Running the Application

After building, start the application:

```bash
cd ui
python3 main_app.py
```

Or from the project root:
```bash
python3 ui/main_app.py
```

## Using the Application

### 1. Import Tab
- Click **Browse** to select a CSV file
- Click **Import** to load the file
- View the first 15 rows in the preview table

### 2. Serial Analyzer Tab
- Click **Run Serial Analysis** to analyze the imported data
- View column-by-column statistics including:
  - Data type (Numeric/Categorical/Mixed)
  - Total count, null count, unique count
  - For numeric columns: min, max, mean, median, std dev, outliers
  - Data quality flags (nulls, outliers, duplicates, type consistency)

### 3. Parallel Analyzer - OpenMP Tab
- Set the number of threads (1-16)
- Click **Run OpenMP Analysis** for parallel processing
- View results similar to serial analysis but with performance metrics

### 4. Parallel Analyzer - MPI Tab
- Click **Run MPI Analysis**
- Note: This is a simplified MPI implementation
- Full MPI requires running with mpirun/mpiexec

### 5. Export Tab
- Placeholder for future export functionality

## Data Analysis Features

The analyzer modules compute the following statistics for each column:

### Basic Information
- Column name
- Data type (Numeric, Categorical, Mixed, Unknown)
- Category (Continuous, Discrete, Binary, Nominal, Ordinal)

### Count Statistics
- Total count
- Null count and percentage
- Unique value count

### Numeric Statistics (for numeric columns)
- Minimum and maximum values
- Mean (average)
- Median
- Standard deviation
- Outlier detection using IQR method
- List of outliers

### Categorical Statistics
- Value counts for top values
- Frequency distribution

### Data Quality Flags
- Has nulls: Whether column contains null/missing values
- Has outliers: Whether numeric column has statistical outliers
- Has duplicates: Whether column has duplicate values
- Type consistent: Whether all values match the expected type

## Module Architecture

### CSV Importer Module
- Pure C implementation
- Handles CSV parsing with quoted fields
- Supports dynamic memory allocation
- Provides preview functionality

### Analyzer Modules
All analyzer modules share the same analysis logic but differ in execution model:

- **Serial Analyzer**: Traditional sequential processing
- **OpenMP Analyzer**: Uses `#pragma omp parallel for` for column-level parallelism
- **MPI Analyzer**: Framework for distributed processing (simplified in this version)

## Extending the Application

### Adding New Preprocessing Features

1. **Create a new module** in `modules/` directory
2. **Define the interface** in a header file (.h)
3. **Implement functionality** in a C file (.c)
4. **Create a Makefile** following the pattern of existing modules
5. **Update the UI** in `ui/main_app.py` to call the new module
6. **Add to build script** in `build.sh`

Example features to add:
- Missing value imputation (mean, median, mode)
- Row removal based on criteria
- Data normalization/standardization
- Outlier removal
- Categorical encoding
- Feature selection
- Data transformation

### Adding New File Formats

To support Excel files (.xlsx):
1. Add a new module using a library like libxlsxwriter
2. Extend the importer interface
3. Update the UI file picker to accept .xlsx files

## Testing

A sample CSV file is included in `data/sample_employees.csv` for testing the application.

## Performance Considerations

- **Serial Analysis**: Best for small datasets (< 10,000 rows)
- **OpenMP Analysis**: Efficient for medium datasets (10,000 - 1,000,000 rows)
  - Parallelizes across columns
  - Configurable thread count
- **MPI Analysis**: Designed for very large datasets
  - Can distribute across multiple machines
  - Requires proper MPI setup

## Troubleshooting

### Libraries not loading
```
Error: Library not found
```
**Solution**: Run `./build.sh` to compile all modules

### OpenMP not working
```
Error: OpenMP analyzer library not loaded
```
**Solution**: Ensure GCC with OpenMP support is installed

### MPI compilation fails
```
Error: mpicc not found
```
**Solution**: Install OpenMPI or MPICH, or skip MPI module

### UI doesn't start
```
Error: No module named 'tkinter'
```
**Solution**: Install python3-tk package

## Future Enhancements

- [ ] Complete MPI implementation with proper data distribution
- [ ] Excel file support (.xlsx)
- [ ] Export functionality (CSV, JSON, Excel)
- [ ] Data visualization (charts and graphs)
- [ ] More preprocessing operations:
  - [ ] Missing value handling
  - [ ] Outlier removal
  - [ ] Data normalization
  - [ ] Feature engineering
- [ ] Batch processing
- [ ] Configuration file support
- [ ] Command-line interface
- [ ] Progress bars for long operations
- [ ] Undo/Redo functionality
- [ ] Data profiling reports

## License

This is an educational/demonstration project.

## Author

Created as a modular data preprocessing framework demonstrating:
- C/Python integration
- Parallel processing with OpenMP and MPI
- Modular software architecture
- Cross-platform development

## Contact

For questions or suggestions, please refer to the project documentation.
