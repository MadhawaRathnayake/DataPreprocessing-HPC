"""
MPI Analyzer Tab
Handles distributed parallel data analysis using MPI
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import os
from collections import Counter
from base_tab import BaseTab
import theme


class MPIAnalyzerTab(BaseTab):
    """Tab for MPI parallel analysis"""
    
    def __init__(self, parent, app_context):
        super().__init__(parent, app_context)
        self.results_text = None
        self.build_ui()
        
    def build_ui(self):
        """Build the MPI Analyzer tab UI"""
        # Control frame
        control_frame = ttk.Frame(self.frame, padding=10)
        control_frame.pack(fill='x')
        
        ttk.Button(control_frame, text="Run MPI Analysis", 
                  command=self.run_analysis).pack(side='left', padx=5)
        
        ttk.Button(control_frame, text="Clear Results", 
                  command=self.clear_results).pack(side='left', padx=5)
        
        # Info label
        info_label = ttk.Label(control_frame, 
                              text="Distributed parallel processing (simplified implementation)", 
                              foreground='gray')
        info_label.pack(side='left', padx=20)
        
        # Results frame
        results_frame = ttk.LabelFrame(self.frame, text="Analysis Results", padding=10)
        results_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD)
        self.results_text.pack(fill='both', expand=True)
        self.results_text.configure(**theme.TEXT_WIDGET_CFG)
        
    def run_analysis(self):
        """Run MPI parallel analysis"""
        if not self.app.mpi_lib:
            messagebox.showerror("Error", "MPI analyzer library not loaded!")
            return
            
        if not self.app.csv_data:
            messagebox.showerror("Error", "Please import a file first!")
            return
            
        try:
            self.app.set_status("Running MPI analysis...")
            self.app.root.update()
            
            # Build result text
            result_text = self._build_analysis_results()
            
            # Display results
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(1.0, result_text)
            
            self.app.set_status("MPI analysis completed")
            
        except Exception as e:
            messagebox.showerror("Error", f"Analysis failed: {str(e)}")
            self.app.set_status("Error")
            
    def _build_analysis_results(self):
        """Build the analysis results text"""
        result_text = "=" * 70 + "\n"
        result_text += "MPI PARALLEL ANALYSIS RESULTS\n"
        result_text += "=" * 70 + "\n\n"
        
        result_text += f"Dataset: {os.path.basename(self.app.current_file)}\n"
        result_text += f"Rows: {self.app.csv_data['num_rows']}\n"
        result_text += f"Columns: {self.app.csv_data['num_cols']}\n"
        result_text += f"Processing Mode: MPI Distributed\n"
        result_text += f"Processes: 1 (simplified implementation)\n\n"
        
        result_text += "COLUMN STATISTICS (MPI Processing)\n"
        result_text += "-" * 70 + "\n\n"
        
        result_text += "Note: This is a simplified MPI implementation for demonstration.\n"
        result_text += "Full MPI would distribute columns across multiple processes/nodes.\n\n"
        
        # Analyze each column
        for i, col in enumerate(self.app.csv_data['headers'], 1):
            result_text += f"[{i}] Column: {col} (Process 0)\n"
            
            # Get column data
            col_idx = i - 1
            col_data = [row[col_idx] for row in self.app.csv_data['data'] 
                       if col_idx < len(row)]
            
            # Basic stats
            total_count = len(col_data)
            null_count = sum(1 for val in col_data if not val or val.strip() == '')
            unique_values = len(set(col_data))
            
            result_text += f"    Total Count: {total_count}\n"
            result_text += f"    Null Count: {null_count} ({null_count/total_count*100:.2f}%)\n"
            result_text += f"    Unique Values: {unique_values}\n"
            
            # Try to determine if numeric
            try:
                numeric_values = []
                for val in col_data:
                    if val and val.strip():
                        try:
                            numeric_values.append(float(val))
                        except ValueError:
                            pass
                
                if numeric_values and len(numeric_values) > total_count * 0.5:
                    # Mostly numeric
                    result_text += f"    Data Type: Numeric\n"
                    result_text += f"    Min: {min(numeric_values):.2f}\n"
                    result_text += f"    Max: {max(numeric_values):.2f}\n"
                    result_text += f"    Mean: {sum(numeric_values)/len(numeric_values):.2f}\n"
                else:
                    result_text += f"    Data Type: Categorical\n"
                    # Show top 3 values
                    counter = Counter(col_data)
                    top_values = counter.most_common(3)
                    result_text += f"    Top Values:\n"
                    for val, count in top_values:
                        if val:
                            result_text += f"      '{val}': {count}\n"
            except Exception as e:
                result_text += f"    Data Type: Mixed/Unknown\n"
            
            result_text += "\n"
        
        result_text += "\n" + "=" * 70 + "\n"
        result_text += "MPI IMPLEMENTATION NOTES:\n"
        result_text += "-" * 70 + "\n"
        result_text += "• Current: Simplified single-process implementation\n"
        result_text += "• Full MPI: Would distribute columns across multiple processes\n"
        result_text += "• Deployment: Requires mpirun/mpiexec launcher\n"
        result_text += "• Use case: Very large datasets across multiple machines\n"
        result_text += "• Performance: Linear speedup with number of processes\n\n"
        
        return result_text
        
    def clear_results(self):
        """Clear the results text"""
        self.results_text.delete(1.0, tk.END)
        self.app.set_status("Results cleared")
        
    def on_tab_selected(self):
        """Called when tab is selected"""
        if self.app.csv_data:
            self.app.set_status("Ready to run MPI analysis")
        else:
            self.app.set_status("Please import a file first")
