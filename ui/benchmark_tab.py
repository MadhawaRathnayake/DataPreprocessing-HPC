"""
Benchmark Comparison Tab
Shows performance metrics comparison across Serial, OpenMP, and MPI backends
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import theme
from metrics import BenchmarkComparison, PipelineMetrics


class BenchmarkComparisonTab:
    """Tab for viewing and comparing benchmark results"""

    LABEL = "Benchmark Comparison"
    INDEX = 5

    def __init__(self, parent_frame, app):
        """
        Parameters
        ----------
        parent_frame : tk parent widget
        app : DataPreprocessingApp instance
        """
        self.app = app
        self.frame = ttk.Frame(parent_frame)
        self._comparison = BenchmarkComparison()
        self._metrics_history = {}  # backend -> list of metrics
        self._build()

    # ── public API ───────────────────────────────────────────────────────────

    def get_frame(self):
        return self.frame
    def on_tab_selected(self):
        """Called when tab is selected"""
        self._update_display()
    def refresh(self):
        self._update_display()

    def add_metrics(self, metrics: PipelineMetrics):
        """Add metrics from a pipeline execution"""
        self._comparison.add_result(metrics)
        
        # Store in history
        if metrics.backend not in self._metrics_history:
            self._metrics_history[metrics.backend] = []
        self._metrics_history[metrics.backend].append(metrics)
        
        # Update display
        self._update_display()

    # ── private — UI ─────────────────────────────────────────────────────────

    def _build(self):
        pad = dict(padx=14, pady=6)

        ttk.Label(self.frame, text="Benchmark Comparison",
                  font=theme.FONT_TITLE, foreground=theme.HIGHLIGHT
                  ).pack(anchor="w", padx=14, pady=(12, 2))
        ttk.Label(self.frame,
                  text="Compare performance metrics across Serial, OpenMP, and MPI backends.",
                  style="Muted.TLabel"
                  ).pack(anchor="w", padx=14, pady=(0, 10))
        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", padx=14, pady=(0, 14))

        # ── Control buttons ──────────────────────────────────────────────────
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill="x", padx=14, pady=6)

        ttk.Button(btn_frame, text="📊  Refresh",
                   command=self._update_display).pack(side="left", padx=2)

        ttk.Button(btn_frame, text="💾  Export as CSV",
                   command=self._export_csv).pack(side="left", padx=2)

        ttk.Button(btn_frame, text="📄  Export as JSON",
                   command=self._export_json).pack(side="left", padx=2)

        ttk.Button(btn_frame, text="🗑️  Clear Results",
                   command=self._clear_results).pack(side="left", padx=2)

        # ── Metrics display ──────────────────────────────────────────────────
        display_frame = ttk.LabelFrame(self.frame, text="Comparison Results", padding=10)
        display_frame.pack(fill="both", expand=True, **pad)

        # Text widget with scrollbar
        self._text = scrolledtext.ScrolledText(display_frame, height=25, wrap="word",
                                               font=("Courier", 9),
                                               bg=theme.BG_INPUT, fg=theme.TEXT)
        self._text.pack(fill="both", expand=True)
        self._text.config(state="disabled")

        # ── Summary stats ────────────────────────────────────────────────────
        summary_frame = ttk.LabelFrame(self.frame, text="Quick Stats", padding=10)
        summary_frame.pack(fill="x", **pad)

        self._summary_text = tk.Text(summary_frame, height=4, wrap="word",
                                     state="disabled", font=("Courier", 9),
                                     bg=theme.BG_INPUT, fg=theme.TEXT)
        self._summary_text.pack(fill="x")

    def _update_display(self):
        """Update the comparison display"""
        if not self._comparison.results:
            text = "No benchmark results yet.\n\nRun the pipeline on at least one backend to see comparison results."
        else:
            text = self._comparison.get_comparison_table()

        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert("1.0", text)
        self._text.config(state="disabled")

        # Update summary
        self._update_summary()

    def _update_summary(self):
        """Update summary statistics"""
        lines = []

        if not self._comparison.results:
            summary = "No results to summarize"
        else:
            lines.append("EXECUTION SUMMARY")
            lines.append("=" * 80)
            
            num_backends = len(self._comparison.results)
            lines.append(f"Backends tested: {num_backends}")

            if "serial" in self._comparison.results:
                serial = self._comparison.results["serial"]
                lines.append(f"Serial execution: {serial.total_time*1000:.1f} ms (baseline)")

            if "openmp" in self._comparison.results:
                omp = self._comparison.results["openmp"]
                lines.append(f"OpenMP execution: {omp.total_time*1000:.1f} ms "
                           f"(speedup: {omp.speedup_vs_serial:.2f}x)")

            if "mpi" in self._comparison.results:
                mpi = self._comparison.results["mpi"]
                lines.append(f"MPI execution: {mpi.total_time*1000:.1f} ms "
                           f"(speedup: {mpi.speedup_vs_serial:.2f}x)")

            summary = "\n".join(lines)

        self._summary_text.config(state="normal")
        self._summary_text.delete("1.0", "end")
        self._summary_text.insert("1.0", summary)
        self._summary_text.config(state="disabled")

    def _export_csv(self):
        """Export comparison as CSV"""
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Benchmark Results as CSV",
        )
        if not path:
            return

        try:
            csv_data = self._comparison.to_csv()
            with open(path, "w") as f:
                f.write(csv_data)
            messagebox.showinfo("Saved", f"Benchmark results exported to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _export_json(self):
        """Export comparison as JSON"""
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export Benchmark Results as JSON",
        )
        if not path:
            return

        try:
            json_data = self._comparison.to_json()
            with open(path, "w") as f:
                f.write(json_data)
            messagebox.showinfo("Saved", f"Benchmark results exported to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _clear_results(self):
        """Clear all benchmark results"""
        if messagebox.askyesno("Clear Results", "Clear all benchmark results?"):
            self._comparison = BenchmarkComparison()
            self._metrics_history = {}
            self._update_display()
