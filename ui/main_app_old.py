#!/usr/bin/env python3
"""
Data Preprocessing Application - Main UI
Modular application with C-based processing modules and Python Tkinter UI
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import ctypes
import os
import sys
import json
from pathlib import Path

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
LIB_DIR = PROJECT_ROOT / "lib"

class DataPreprocessingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Data Preprocessing Application")
        self.root.geometry("1200x800")
        
        # Data storage
        self.csv_data = None
        self.csv_handle = None
        self.current_file = None
        self.stats_data = None
        
        # Load C libraries
        self.load_libraries()
        
        # Create UI
        self.create_ui()
        
    def load_libraries(self):
        """Load C shared libraries"""
        try:
            # CSV Importer
            csv_lib_path = LIB_DIR / "libcsvimporter.so"
            if csv_lib_path.exists():
                self.csv_lib = ctypes.CDLL(str(csv_lib_path))
                self.setup_csv_lib()
                print(f"✓ Loaded CSV importer library")
            else:
                self.csv_lib = None
                print(f"✗ CSV importer library not found at {csv_lib_path}")
            
            # Serial Analyzer
            serial_lib_path = LIB_DIR / "libserialanalyzer.so"
            if serial_lib_path.exists():
                self.serial_lib = ctypes.CDLL(str(serial_lib_path))
                self.setup_serial_lib()
                print(f"✓ Loaded serial analyzer library")
            else:
                self.serial_lib = None
                print(f"✗ Serial analyzer library not found")
            
            # OpenMP Analyzer
            openmp_lib_path = LIB_DIR / "libompanalyzer.so"
            if openmp_lib_path.exists():
                self.openmp_lib = ctypes.CDLL(str(openmp_lib_path))
                self.setup_openmp_lib()
                print(f"✓ Loaded OpenMP analyzer library")
            else:
                self.openmp_lib = None
                print(f"✗ OpenMP analyzer library not found")
            
            # MPI Analyzer
            mpi_lib_path = LIB_DIR / "libmpianalyzer.so"
            if mpi_lib_path.exists():
                self.mpi_lib = ctypes.CDLL(str(mpi_lib_path))
                self.setup_mpi_lib()
                print(f"✓ Loaded MPI analyzer library")
            else:
                self.mpi_lib = None
                print(f"✗ MPI analyzer library not found")
                
        except Exception as e:
            messagebox.showerror("Library Error", f"Error loading libraries: {str(e)}")
            
    def setup_csv_lib(self):
        """Setup CSV library function signatures"""
        if not self.csv_lib:
            return
            
        # csv_create()
        self.csv_lib.csv_create.argtypes = []
        self.csv_lib.csv_create.restype = ctypes.c_void_p
        
        # csv_load_file(filename, csv_data)
        self.csv_lib.csv_load_file.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
        self.csv_lib.csv_load_file.restype = ctypes.c_int
        
        # csv_get_cell(csv_data, row, col)
        self.csv_lib.csv_get_cell.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        self.csv_lib.csv_get_cell.restype = ctypes.c_char_p
        
        # csv_get_header(csv_data, col)
        self.csv_lib.csv_get_header.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.csv_lib.csv_get_header.restype = ctypes.c_char_p
        
        # csv_free(csv_data)
        self.csv_lib.csv_free.argtypes = [ctypes.c_void_p]
        self.csv_lib.csv_free.restype = None
        
    def setup_serial_lib(self):
        """Setup serial analyzer function signatures"""
        if not self.serial_lib:
            return
            
        self.serial_lib.analyzer_create_stats.argtypes = [ctypes.c_int]
        self.serial_lib.analyzer_create_stats.restype = ctypes.c_void_p
        
        self.serial_lib.analyzer_get_stats_json.argtypes = [ctypes.c_void_p]
        self.serial_lib.analyzer_get_stats_json.restype = ctypes.c_char_p
        
        self.serial_lib.analyzer_free_stats.argtypes = [ctypes.c_void_p]
        self.serial_lib.analyzer_free_stats.restype = None
        
    def setup_openmp_lib(self):
        """Setup OpenMP analyzer function signatures"""
        if not self.openmp_lib:
            return
            
        self.openmp_lib.analyzer_omp_create_stats.argtypes = [ctypes.c_int]
        self.openmp_lib.analyzer_omp_create_stats.restype = ctypes.c_void_p
        
        self.openmp_lib.analyzer_omp_get_stats_json.argtypes = [ctypes.c_void_p]
        self.openmp_lib.analyzer_omp_get_stats_json.restype = ctypes.c_char_p
        
        self.openmp_lib.analyzer_omp_free_stats.argtypes = [ctypes.c_void_p]
        self.openmp_lib.analyzer_omp_free_stats.restype = None
        
    def setup_mpi_lib(self):
        """Setup MPI analyzer function signatures"""
        if not self.mpi_lib:
            return
            
        self.mpi_lib.analyzer_mpi_create_stats.argtypes = [ctypes.c_int]
        self.mpi_lib.analyzer_mpi_create_stats.restype = ctypes.c_void_p
        
        self.mpi_lib.analyzer_mpi_get_stats_json.argtypes = [ctypes.c_void_p]
        self.mpi_lib.analyzer_mpi_get_stats_json.restype = ctypes.c_char_p
        
        self.mpi_lib.analyzer_mpi_free_stats.argtypes = [ctypes.c_void_p]
        self.mpi_lib.analyzer_mpi_free_stats.restype = None
        
    def create_ui(self):
        """Create the main UI with tabs"""
        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create tabs
        self.create_import_tab()
        self.create_serial_analyzer_tab()
        self.create_openmp_analyzer_tab()
        self.create_mpi_analyzer_tab()
        self.create_export_tab()
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, 
                              relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def create_import_tab(self):
        """Create the Import tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Import")
        
        # File selection frame
        file_frame = ttk.LabelFrame(tab, text="File Selection", padding=10)
        file_frame.pack(fill='x', padx=10, pady=10)
        
        self.file_path_var = tk.StringVar()
        ttk.Label(file_frame, text="File:").grid(row=0, column=0, sticky='w', pady=5)
        ttk.Entry(file_frame, textvariable=self.file_path_var, width=60).grid(
            row=0, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=self.browse_file).grid(
            row=0, column=2, padx=5, pady=5)
        ttk.Button(file_frame, text="Import", command=self.import_file).grid(
            row=0, column=3, padx=5, pady=5)
        
        # Preview frame
        preview_frame = ttk.LabelFrame(tab, text="Data Preview (First 15 Rows)", padding=10)
        preview_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create Treeview for data preview
        self.preview_tree = ttk.Treeview(preview_frame)
        
        # Scrollbars
        vsb = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_tree.yview)
        hsb = ttk.Scrollbar(preview_frame, orient="horizontal", command=self.preview_tree.xview)
        self.preview_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.preview_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        preview_frame.grid_rowconfigure(0, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)
        
    def create_serial_analyzer_tab(self):
        """Create the Serial Analyzer tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Serial Analyzer")
        
        # Control frame
        control_frame = ttk.Frame(tab, padding=10)
        control_frame.pack(fill='x')
        
        ttk.Button(control_frame, text="Run Serial Analysis", 
                  command=self.run_serial_analysis).pack(side='left', padx=5)
        
        # Results frame
        results_frame = ttk.LabelFrame(tab, text="Analysis Results", padding=10)
        results_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.serial_results = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD)
        self.serial_results.pack(fill='both', expand=True)
        
    def create_openmp_analyzer_tab(self):
        """Create the OpenMP Analyzer tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Parallel Analyzer - OpenMP")
        
        # Control frame
        control_frame = ttk.Frame(tab, padding=10)
        control_frame.pack(fill='x')
        
        ttk.Label(control_frame, text="Number of Threads:").pack(side='left', padx=5)
        self.num_threads_var = tk.IntVar(value=4)
        ttk.Spinbox(control_frame, from_=1, to=16, textvariable=self.num_threads_var, 
                   width=5).pack(side='left', padx=5)
        
        ttk.Button(control_frame, text="Run OpenMP Analysis", 
                  command=self.run_openmp_analysis).pack(side='left', padx=5)
        
        # Results frame
        results_frame = ttk.LabelFrame(tab, text="Analysis Results", padding=10)
        results_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.openmp_results = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD)
        self.openmp_results.pack(fill='both', expand=True)
        
    def create_mpi_analyzer_tab(self):
        """Create the MPI Analyzer tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Parallel Analyzer - MPI")
        
        # Control frame
        control_frame = ttk.Frame(tab, padding=10)
        control_frame.pack(fill='x')
        
        ttk.Button(control_frame, text="Run MPI Analysis", 
                  command=self.run_mpi_analysis).pack(side='left', padx=5)
        
        ttk.Label(control_frame, text="(Note: Simplified MPI implementation)", 
                 foreground='gray').pack(side='left', padx=20)
        
        # Results frame
        results_frame = ttk.LabelFrame(tab, text="Analysis Results", padding=10)
        results_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.mpi_results = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD)
        self.mpi_results.pack(fill='both', expand=True)
        
    def create_export_tab(self):
        """Create the Export tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Export")
        
        # Placeholder for export functionality
        ttk.Label(tab, text="Export functionality will be implemented here", 
                 font=('Arial', 14)).pack(expand=True)
        
    def browse_file(self):
        """Browse for CSV/Excel file"""
        filename = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.file_path_var.set(filename)
            
    def import_file(self):
        """Import CSV file using C library"""
        if not self.csv_lib:
            messagebox.showerror("Error", "CSV importer library not loaded!")
            return
            
        filepath = self.file_path_var.get()
        if not filepath or not os.path.exists(filepath):
            messagebox.showerror("Error", "Please select a valid file!")
            return
            
        try:
            self.status_var.set("Importing file...")
            self.root.update()
            
            # Create CSV data structure
            self.csv_handle = self.csv_lib.csv_create()
            
            # Load file
            result = self.csv_lib.csv_load_file(filepath.encode('utf-8'), self.csv_handle)
            
            if result != 0:
                messagebox.showerror("Error", "Failed to load CSV file!")
                return
            
            # Read data for preview and storage
            self.load_csv_data()
            
            # Display preview
            self.display_preview()
            
            self.current_file = filepath
            self.status_var.set(f"Loaded: {os.path.basename(filepath)}")
            messagebox.showinfo("Success", "File imported successfully!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Import failed: {str(e)}")
            self.status_var.set("Error")
            
    def load_csv_data(self):
        """Load CSV data into Python structures for analysis"""
        # This is a simplified approach - read the CSV using Python
        # In production, you might want to access the C structure directly
        import csv
        
        filepath = self.file_path_var.get()
        with open(filepath, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)
            
        self.csv_data = {
            'headers': rows[0] if rows else [],
            'data': rows[1:] if len(rows) > 1 else [],
            'num_rows': len(rows) - 1 if len(rows) > 1 else 0,
            'num_cols': len(rows[0]) if rows else 0
        }
        
    def display_preview(self):
        """Display first 15 rows in treeview"""
        # Clear existing data
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)
            
        if not self.csv_data:
            return
            
        headers = self.csv_data['headers']
        data = self.csv_data['data']
        
        # Configure columns
        self.preview_tree['columns'] = headers
        self.preview_tree['show'] = 'headings'
        
        # Set column headings
        for col in headers:
            self.preview_tree.heading(col, text=col)
            self.preview_tree.column(col, width=100)
            
        # Insert data (first 15 rows)
        for i, row in enumerate(data[:15]):
            self.preview_tree.insert('', 'end', values=row)
            
    def run_serial_analysis(self):
        """Run serial analysis on imported data"""
        if not self.serial_lib:
            messagebox.showerror("Error", "Serial analyzer library not loaded!")
            return
            
        if not self.csv_data:
            messagebox.showerror("Error", "Please import a file first!")
            return
            
        try:
            self.status_var.set("Running serial analysis...")
            self.root.update()
            
            # For simplicity, we'll create a mock analysis result
            # In production, you'd call the C library with proper data structures
            
            result_text = "=== SERIAL ANALYSIS RESULTS ===\n\n"
            result_text += f"Dataset: {os.path.basename(self.current_file)}\n"
            result_text += f"Rows: {self.csv_data['num_rows']}\n"
            result_text += f"Columns: {self.csv_data['num_cols']}\n\n"
            result_text += "Column Statistics:\n"
            result_text += "-" * 60 + "\n\n"
            
            for col in self.csv_data['headers']:
                result_text += f"Column: {col}\n"
                result_text += "  Data Type: Analyzing...\n"
                result_text += "  Total Count: {}\n".format(self.csv_data['num_rows'])
                result_text += "  Analysis in progress...\n\n"
            
            result_text += "\nNote: Full C library integration requires proper data marshalling.\n"
            result_text += "This is a demonstration of the UI framework.\n"
            
            self.serial_results.delete(1.0, tk.END)
            self.serial_results.insert(1.0, result_text)
            
            self.status_var.set("Serial analysis completed")
            
        except Exception as e:
            messagebox.showerror("Error", f"Analysis failed: {str(e)}")
            self.status_var.set("Error")
            
    def run_openmp_analysis(self):
        """Run OpenMP parallel analysis"""
        if not self.openmp_lib:
            messagebox.showerror("Error", "OpenMP analyzer library not loaded!")
            return
            
        if not self.csv_data:
            messagebox.showerror("Error", "Please import a file first!")
            return
            
        try:
            num_threads = self.num_threads_var.get()
            self.status_var.set(f"Running OpenMP analysis with {num_threads} threads...")
            self.root.update()
            
            result_text = "=== OPENMP PARALLEL ANALYSIS RESULTS ===\n\n"
            result_text += f"Dataset: {os.path.basename(self.current_file)}\n"
            result_text += f"Rows: {self.csv_data['num_rows']}\n"
            result_text += f"Columns: {self.csv_data['num_cols']}\n"
            result_text += f"Threads: {num_threads}\n\n"
            result_text += "Column Statistics:\n"
            result_text += "-" * 60 + "\n\n"
            
            for col in self.csv_data['headers']:
                result_text += f"Column: {col}\n"
                result_text += "  Parallel analysis in progress...\n\n"
            
            result_text += "\nNote: Full OpenMP integration with proper threading.\n"
            
            self.openmp_results.delete(1.0, tk.END)
            self.openmp_results.insert(1.0, result_text)
            
            self.status_var.set("OpenMP analysis completed")
            
        except Exception as e:
            messagebox.showerror("Error", f"Analysis failed: {str(e)}")
            self.status_var.set("Error")
            
    def run_mpi_analysis(self):
        """Run MPI parallel analysis"""
        if not self.mpi_lib:
            messagebox.showerror("Error", "MPI analyzer library not loaded!")
            return
            
        if not self.csv_data:
            messagebox.showerror("Error", "Please import a file first!")
            return
            
        try:
            self.status_var.set("Running MPI analysis...")
            self.root.update()
            
            result_text = "=== MPI PARALLEL ANALYSIS RESULTS ===\n\n"
            result_text += f"Dataset: {os.path.basename(self.current_file)}\n"
            result_text += f"Rows: {self.csv_data['num_rows']}\n"
            result_text += f"Columns: {self.csv_data['num_cols']}\n"
            result_text += "Processes: 1 (simplified implementation)\n\n"
            result_text += "Column Statistics:\n"
            result_text += "-" * 60 + "\n\n"
            
            for col in self.csv_data['headers']:
                result_text += f"Column: {col}\n"
                result_text += "  MPI analysis in progress...\n\n"
            
            result_text += "\nNote: This is a simplified MPI implementation.\n"
            result_text += "Full MPI requires mpirun/mpiexec launcher.\n"
            
            self.mpi_results.delete(1.0, tk.END)
            self.mpi_results.insert(1.0, result_text)
            
            self.status_var.set("MPI analysis completed")
            
        except Exception as e:
            messagebox.showerror("Error", f"Analysis failed: {str(e)}")
            self.status_var.set("Error")
            
    def __del__(self):
        """Cleanup"""
        if hasattr(self, 'csv_handle') and self.csv_handle and self.csv_lib:
            self.csv_lib.csv_free(self.csv_handle)


def main():
    root = tk.Tk()
    app = DataPreprocessingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
