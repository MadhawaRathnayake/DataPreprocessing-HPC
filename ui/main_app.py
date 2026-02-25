#!/usr/bin/env python3
"""
Data Preprocessing Application - Main Application
Modular application with C-based processing modules and Python Tkinter UI

This is the main entry point that coordinates all tab modules.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import ctypes
import sys
from pathlib import Path
import theme

# Import tab modules
from import_tab import ImportTab
from series_processing_tab import SeriesProcessingTab
from openmp_pipeline_tab import OpenMPPipelineTab
from mpi_pipeline_tab import MPIPipelineTab
from cuda_pipeline_tab import CUDAPipelineTab
from export_tab import ExportTab

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
LIB_DIR = PROJECT_ROOT / "lib"


class DataPreprocessingApp:
    """Main application class that manages the UI and coordinates tabs"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("HPC Data Preprocessing — Series · OpenMP · MPI · CUDA")
        self.root.geometry("1280x820")
        self.root.minsize(900, 600)

        # Apply modern theme BEFORE any widgets are created
        self.style = theme.apply(self.root)

        # Shared application data
        self.csv_data = None
        self.csv_handle = None
        self.current_file = None
        self.stats_data = None

        # C Library handles
        self.csv_lib = None
        self.serial_lib = None
        self.openmp_lib = None
        self.mpi_lib = None

        # UI components
        self.notebook = None
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")

        # Tab instances
        self.tabs = {}

        # Initialize
        self.load_libraries()
        self.create_ui()
        self.bind_events()
        
    def load_libraries(self):
        """Load C shared libraries"""
        print("\n" + "=" * 60)
        print("Loading C Libraries")
        print("=" * 60)
        
        try:
            # CSV Importer
            csv_lib_path = LIB_DIR / "libcsvimporter.so"
            if csv_lib_path.exists():
                self.csv_lib = ctypes.CDLL(str(csv_lib_path))
                self.setup_csv_lib()
                print(f"✓ CSV Importer: {csv_lib_path}")
            else:
                print(f"✗ CSV Importer: Not found at {csv_lib_path}")
            
            # Serial Analyzer
            serial_lib_path = LIB_DIR / "libserialanalyzer.so"
            if serial_lib_path.exists():
                self.serial_lib = ctypes.CDLL(str(serial_lib_path))
                self.setup_serial_lib()
                print(f"✓ Serial Analyzer: {serial_lib_path}")
            else:
                print(f"✗ Serial Analyzer: Not found")
            
            # OpenMP Analyzer
            openmp_lib_path = LIB_DIR / "libompanalyzer.so"
            if openmp_lib_path.exists():
                self.openmp_lib = ctypes.CDLL(str(openmp_lib_path))
                self.setup_openmp_lib()
                print(f"✓ OpenMP Analyzer: {openmp_lib_path}")
            else:
                print(f"✗ OpenMP Analyzer: Not found")
            
            # MPI Analyzer
            mpi_lib_path = LIB_DIR / "libmpianalyzer.so"
            if mpi_lib_path.exists():
                self.mpi_lib = ctypes.CDLL(str(mpi_lib_path))
                self.setup_mpi_lib()
                print(f"✓ MPI Analyzer: {mpi_lib_path}")
            else:
                print(f"✗ MPI Analyzer: Not found (Optional)")
                
        except Exception as e:
            messagebox.showerror("Library Error", f"Error loading libraries: {str(e)}")
            
        print("=" * 60 + "\n")
            
    def setup_csv_lib(self):
        """Setup CSV library function signatures"""
        if not self.csv_lib:
            return
            
        self.csv_lib.csv_create.argtypes = []
        self.csv_lib.csv_create.restype = ctypes.c_void_p
        
        self.csv_lib.csv_load_file.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
        self.csv_lib.csv_load_file.restype = ctypes.c_int
        
        self.csv_lib.csv_get_cell.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        self.csv_lib.csv_get_cell.restype = ctypes.c_char_p
        
        self.csv_lib.csv_get_header.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.csv_lib.csv_get_header.restype = ctypes.c_char_p
        
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
        """Create the main UI with modular tabs"""
        # ── Header bar ───────────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=theme.BG_ROOT, height=54)
        header.pack(fill='x', side=tk.TOP)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="⚡  HPC Data Preprocessing",
            bg=theme.BG_ROOT, fg=theme.ACCENT,
            font=("Segoe UI", 15, "bold"),
        ).pack(side=tk.LEFT, padx=18)

        tk.Label(
            header,
            text="Series · OpenMP · MPI · CUDA Parallel Analytics",
            bg=theme.BG_ROOT, fg=theme.TEXT_MUTED,
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, padx=4, pady=20, anchor='s')

        # thin accent line under header
        tk.Frame(self.root, bg=theme.ACCENT, height=2).pack(fill='x')

        # ── Status bar (packed BEFORE notebook so it stays at bottom) ────────
        status_frame = tk.Frame(self.root, bg=theme.BG_FRAME, height=28)
        status_frame.pack(side=tk.BOTTOM, fill='x')
        status_frame.pack_propagate(False)
        tk.Frame(status_frame, bg=theme.BORDER, height=1).pack(fill='x')
        self._status_label = tk.Label(
            status_frame,
            textvariable=self.status_var,
            bg=theme.BG_FRAME, fg=theme.TEXT_MUTED,
            font=("Segoe UI", 9),
            anchor=tk.W, padx=14,
        )
        self._status_label.pack(fill='x', expand=True)

        # ── Notebook (tabs) ───────────────────────────────────────────────────
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True)

        # Create all tabs using modular approach
        self.tabs['import'] = ImportTab(self.notebook, self)
        self.tabs['serial'] = SeriesProcessingTab(self.notebook, self)
        self.tabs['openmp'] = OpenMPPipelineTab(self.notebook, self)
        self.tabs['mpi']    = MPIPipelineTab(self.notebook, self)
        self.tabs['cuda']   = CUDAPipelineTab(self.notebook, self)
        self.tabs['export'] = ExportTab(self.notebook, self)

        # Add tabs to notebook
        self.notebook.add(self.tabs['import'].get_frame(),  text="  📂  Import  ")
        self.notebook.add(self.tabs['serial'].get_frame(),  text="  🔬  Series Processing  ")
        self.notebook.add(self.tabs['openmp'].get_frame(),  text="  ⚡  OpenMP Parallel  ")
        self.notebook.add(self.tabs['mpi'].get_frame(),     text="  🌐  MPI Parallel  ")
        self.notebook.add(self.tabs['cuda'].get_frame(),    text="  🚀  CUDA Parallel  ")
        self.notebook.add(self.tabs['export'].get_frame(),  text="  💾  Export  ")
        
    def bind_events(self):
        """Bind application-level events"""
        # Tab change event
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # Window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def on_tab_changed(self, event):
        """Handle tab change events"""
        # Get current tab index
        current_tab_index = self.notebook.index(self.notebook.select())
        
        # Get tab names in order
        tab_names = ['import', 'serial', 'openmp', 'mpi', 'cuda', 'export']
        
        if current_tab_index < len(tab_names):
            current_tab_name = tab_names[current_tab_index]
            
            # Call the selected tab's on_tab_selected method
            if current_tab_name in self.tabs:
                self.tabs[current_tab_name].on_tab_selected()
                
    def set_status(self, message):
        """Update status bar message"""
        self.status_var.set(message)
        self.root.update_idletasks()
        
    def on_closing(self):
        """Handle application closing"""
        # Cleanup
        if self.csv_handle and self.csv_lib:
            try:
                self.csv_lib.csv_free(self.csv_handle)
            except:
                pass
                
        self.root.destroy()
        
    def run(self):
        """Start the application main loop"""
        self.root.mainloop()


def main():
    """Main entry point"""
    print("\n" + "=" * 60)
    print("Data Preprocessing Application")
    print("Modular Architecture with Separate Tab Components")
    print("=" * 60)
    
    root = tk.Tk()
    app = DataPreprocessingApp(root)
    app.run()


if __name__ == "__main__":
    main()
