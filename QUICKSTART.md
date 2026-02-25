# QUICK START GUIDE

## Get Started in 3 Steps

### 1. Build the Application
```bash
cd data_preprocessing_app
./build.sh
```

### 2. Run the Application
```bash
./run.sh
```
or
```bash
python3 ui/main_app.py
```

### 3. Try It Out

**Import Data:**
1. Click the "Import" tab
2. Click "Browse" button
3. Select `data/sample_employees.csv`
4. Click "Import" button
5. See the first 15 rows displayed

**Analyze Data (Serial):**
1. Switch to "Serial Analyzer" tab
2. Click "Run Serial Analysis"
3. View the statistics for each column

**Analyze Data (Parallel - OpenMP):**
1. Switch to "Parallel Analyzer - OpenMP" tab
2. Set number of threads (e.g., 4)
3. Click "Run OpenMP Analysis"
4. Compare performance with serial analysis

## Sample Workflow

```bash
# First time setup
cd data_preprocessing_app
./build.sh

# Run the application
./run.sh

# In the UI:
# 1. Import → Browse → Select sample_employees.csv → Import
# 2. Serial Analyzer → Run Serial Analysis
# 3. OpenMP Analyzer → Set threads to 4 → Run OpenMP Analysis
# 4. Compare the results
```

## What You'll See

### Import Tab
- File browser to select CSV files
- Data preview showing first 15 rows in a table
- Column headers displayed

### Analysis Results
For each column, you'll see:
- **Data Type**: Numeric, Categorical, or Mixed
- **Total Count**: Number of rows
- **Null Count**: Missing values and percentage
- **Unique Count**: Number of distinct values
- **Statistics** (for numeric columns):
  - Min, Max, Mean, Median, Standard Deviation
  - Outliers detected
- **Quality Flags**:
  - Has Nulls, Has Outliers, Has Duplicates
  - Type Consistency

## Troubleshooting

**Problem**: Libraries not loading
```bash
# Rebuild the modules
./build.sh
```

**Problem**: Python/Tkinter not found
```bash
# Install dependencies (Ubuntu/Debian)
sudo apt-get install python3 python3-tk

# Install dependencies (Fedora/RHEL)
sudo dnf install python3 python3-tkinter
```

**Problem**: GCC not found
```bash
# Install build tools (Ubuntu/Debian)
sudo apt-get install build-essential

# Install build tools (Fedora/RHEL)
sudo dnf install gcc gcc-c++
```

## Next Steps

1. **Try your own CSV files**: Import any CSV file and analyze it
2. **Experiment with thread counts**: See how OpenMP performance scales
3. **Extend the application**: Add new preprocessing features (see README.md)

## File Locations

- **Sample data**: `data/sample_employees.csv`
- **Main application**: `ui/main_app.py`
- **C modules**: `modules/*/`
- **Compiled libraries**: `lib/*.so`

## Support

See the full README.md for:
- Detailed architecture explanation
- How to add new features
- Performance considerations
- Complete API documentation
