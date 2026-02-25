"""
Import Tab
Handles CSV file import and data preview
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import csv
from base_tab import BaseTab


class ImportTab(BaseTab):
    """Tab for importing CSV files and previewing data"""
    
    def __init__(self, parent, app_context):
        super().__init__(parent, app_context)
        self.file_path_var = tk.StringVar()
        self.preview_rows_var = tk.StringVar(value="15")
        self.preview_tree = None
        self.build_ui()
        
    def build_ui(self):
        """Build the Import tab UI"""
        # File selection frame
        file_frame = ttk.LabelFrame(self.frame, text="File Selection", padding=10)
        file_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(file_frame, text="File:").grid(row=0, column=0, sticky='w', pady=5)
        ttk.Entry(file_frame, textvariable=self.file_path_var, width=60).grid(
            row=0, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=self.browse_file).grid(
            row=0, column=2, padx=5, pady=5)
        ttk.Button(file_frame, text="Import", command=self.import_file).grid(
            row=0, column=3, padx=5, pady=5)

        # Preview row count selector
        ttk.Label(file_frame, text="Preview Rows:").grid(
            row=0, column=4, padx=(20, 5), pady=5)
        preview_combo = ttk.Combobox(
            file_frame,
            textvariable=self.preview_rows_var,
            values=["15", "30", "60", "100", "250", "All"],
            state="readonly",
            width=6
        )
        preview_combo.grid(row=0, column=5, padx=5, pady=5)
        preview_combo.bind("<<ComboboxSelected>>", lambda e: self.display_preview())
        
        # Preview frame
        preview_frame = ttk.LabelFrame(self.frame, text="Data Preview", padding=10)
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
        if not self.app.csv_lib:
            messagebox.showerror("Error", "CSV importer library not loaded!")
            return
            
        filepath = self.file_path_var.get()
        if not filepath or not os.path.exists(filepath):
            messagebox.showerror("Error", "Please select a valid file!")
            return
            
        try:
            self.app.set_status("Importing file...")
            
            # Create CSV data structure
            self.app.csv_handle = self.app.csv_lib.csv_create()
            
            # Load file
            result = self.app.csv_lib.csv_load_file(filepath.encode('utf-8'), 
                                                     self.app.csv_handle)
            
            if result != 0:
                messagebox.showerror("Error", "Failed to load CSV file!")
                return
            
            # Load data for preview and storage
            self.load_csv_data(filepath)
            
            # Display preview
            self.display_preview()
            
            self.app.current_file = filepath
            self.app.set_status(f"Loaded: {os.path.basename(filepath)}")
            messagebox.showinfo("Success", "File imported successfully!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Import failed: {str(e)}")
            self.app.set_status("Error")
            
    def load_csv_data(self, filepath):
        """Load CSV data into Python structures for analysis"""
        with open(filepath, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)
            
        self.app.csv_data = {
            'headers': rows[0] if rows else [],
            'data': rows[1:] if len(rows) > 1 else [],
            'num_rows': len(rows) - 1 if len(rows) > 1 else 0,
            'num_cols': len(rows[0]) if rows else 0
        }
        
    def display_preview(self):
        """Display rows in treeview with row numbers"""
        # Clear existing data
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)

        if not self.app.csv_data:
            return

        headers = self.app.csv_data['headers']
        data    = self.app.csv_data['data']

        # Build column list with a leading row-number column
        all_columns = ['#'] + headers
        self.preview_tree['columns'] = all_columns
        self.preview_tree['show']    = 'headings'

        # Row-number column: fixed narrow width, centred
        self.preview_tree.heading('#', text='#')
        self.preview_tree.column('#', width=52, minwidth=40,
                                 anchor='center', stretch=False)

        # Data columns
        for col in headers:
            self.preview_tree.heading(col, text=col)
            self.preview_tree.column(col, width=110, anchor='w')

        # Insert rows based on dropdown selection
        selection   = self.preview_rows_var.get()
        rows_to_show = data if selection == 'All' else data[:int(selection)]
        for idx, row in enumerate(rows_to_show, start=1):
            self.preview_tree.insert('', 'end', values=[idx] + list(row))
