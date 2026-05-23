"""
Stage 7 - Apply & Preview [CUDA]

Runs the configured pipeline through the CUDA preprocessor backend.
The first integrated CUDA backend focuses on GPU scaling of numeric columns
and returns processed rows to the existing preview/export UI.
"""

import csv as csv_mod
import os
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import theme
from preprocess import PreprocessingPipeline


class StageApply:
    """Apply & Preview stage - runs the pipeline using the CUDA backend."""

    LABEL = "Apply & Preview"
    INDEX = 6

    def __init__(self, parent_frame, app, get_stage_configs_cb):
        self.app = app
        self._get_configs = get_stage_configs_cb
        self._processed_data = None
        self._processed_headers = None
        self.frame = ttk.Frame(parent_frame)
        self._build()

    def get_frame(self):
        return self.frame

    def refresh(self):
        self._update_summary()

    def get_config(self):
        return {}

    def get_status(self):
        return "configured"

    def _build(self):
        pad = dict(padx=14, pady=6)

        ttk.Label(
            self.frame,
            text="Apply & Preview [CUDA]",
            font=theme.FONT_TITLE,
            foreground=theme.HIGHLIGHT,
        ).pack(anchor="w", padx=14, pady=(12, 2))
        ttk.Label(
            self.frame,
            text="Runs numeric preprocessing on the GPU through libpreprocessor_cuda.so.",
            style="Muted.TLabel",
        ).pack(anchor="w", padx=14, pady=(0, 2))

        info = ttk.LabelFrame(self.frame, text="CUDA Backend", padding=8)
        info.pack(fill="x", padx=14, pady=(0, 6))
        ttk.Label(
            info,
            text=(
                "Backend: modules/analyzer_cuda -> libpreprocessor_cuda.so\n"
                "GPU path: numeric column reductions plus min-max / z-score scaling\n"
                "CPU path: CSV preparation, duplicates, missing values, outliers, robust scaling, encoding, and result assembly"
            ),
            style="Muted.TLabel",
            justify="left",
        ).pack(anchor="w")

        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", padx=14, pady=(0, 10))

        sum_frame = ttk.LabelFrame(self.frame, text="Pipeline Summary", padding=10)
        sum_frame.pack(fill="x", **pad)

        self._summary_text = tk.Text(
            sum_frame,
            height=8,
            wrap="word",
            state="disabled",
            **{k: v for k, v in theme.TEXT_WIDGET_CFG.items() if k not in ("padx", "pady", "relief")},
        )
        self._summary_text.pack(fill="x")

        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill="x", padx=14, pady=8)

        self._run_btn = ttk.Button(btn_frame, text="Run CUDA Pipeline", command=self._run_pipeline)
        self._run_btn.pack(side="left", padx=(0, 10))

        self._save_btn = ttk.Button(
            btn_frame,
            text="Save Processed CSV",
            command=self._save_csv,
            state="disabled",
        )
        self._save_btn.pack(side="left")

        stats_frame = ttk.LabelFrame(self.frame, text="Before / After", padding=12)
        stats_frame.pack(fill="x", **pad)

        for col_offset, label, key in [(0, "Before", "before"), (1, "After", "after")]:
            cell = ttk.Frame(stats_frame)
            cell.grid(row=0, column=col_offset, padx=30, sticky="w")
            ttk.Label(cell, text=label, font=theme.FONT_BOLD, foreground=theme.HIGHLIGHT).pack(anchor="w")
            self.__dict__[f"_{key}_rows"] = tk.StringVar(value="-")
            self.__dict__[f"_{key}_cols"] = tk.StringVar(value="-")
            ttk.Label(
                cell,
                textvariable=self.__dict__[f"_{key}_rows"],
                font=theme.FONT_LARGE,
                foreground=theme.ACCENT,
            ).pack(anchor="w")
            ttk.Label(
                cell,
                textvariable=self.__dict__[f"_{key}_cols"],
                style="Muted.TLabel",
            ).pack(anchor="w")

        timing_cell = ttk.Frame(stats_frame)
        timing_cell.grid(row=0, column=2, padx=30, sticky="w")
        ttk.Label(timing_cell, text="CUDA Time", font=theme.FONT_BOLD, foreground=theme.HIGHLIGHT).pack(anchor="w")
        self._timing_var = tk.StringVar(value="-")
        ttk.Label(timing_cell, textvariable=self._timing_var, font=theme.FONT_LARGE, foreground=theme.ACCENT).pack(anchor="w")

        preview_frame = ttk.LabelFrame(self.frame, text="Output Preview (first 20 rows)", padding=10)
        preview_frame.pack(fill="both", expand=True, **pad)

        self._tree = ttk.Treeview(preview_frame, show="headings", height=10)
        vsb = ttk.Scrollbar(preview_frame, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(preview_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right", fill="y")
        self._tree.pack(side="left", fill="both", expand=True)

    def _update_summary(self):
        lines = ["[CUDA Mode]", ""]
        try:
            configs = self._get_configs()
            stage_names = [
                "1 - Overview & Profile",
                "2 - Duplicate Removal",
                "3 - Missing Values",
                "4 - Outlier Detection",
                "5 - Scaling & Normalisation",
                "6 - Categorical Encoding",
            ]
            for name, cfg in zip(stage_names, configs):
                if not cfg:
                    lines.append(f"  - {name}: read-only / no config")
                    continue
                action = cfg.get("action") or cfg.get("global_strategy") or cfg.get("method") or cfg.get("treatment") or "configured"
                lines.append(f"  - {name}: {action}")
            lines.append("")
            lines.append("Current CUDA backend honors the configured preprocessing stages; GPU kernels accelerate numeric min-max and z-score scaling.")
        except Exception:
            lines = ["  (Import a dataset and configure stages first)"]

        self._summary_text.configure(state="normal")
        self._summary_text.delete("1.0", "end")
        self._summary_text.insert("1.0", "\n".join(lines))
        self._summary_text.configure(state="disabled")

    def _run_pipeline(self):
        if not self.app.csv_data:
            messagebox.showerror("Error", "Please import a dataset first.")
            return

        self.app.set_status("Running CUDA pipeline...")
        self.app.root.update()

        try:
            configs = self._get_configs()
            headers = list(self.app.csv_data["headers"])
            data = [list(row) for row in self.app.csv_data["data"]]

            orig_rows = len(data)
            orig_cols = len(headers)

            pipeline = PreprocessingPipeline(backend_type="cuda")
            t_start = time.perf_counter()
            data, headers, stats = pipeline.run_pipeline(data, headers, configs)
            t_elapsed = time.perf_counter() - t_start

            if "error" in stats:
                raise RuntimeError(stats["error"])

            self._processed_data = data
            self._processed_headers = headers

            self._before_rows.set(f"{orig_rows} rows")
            self._before_cols.set(f"{orig_cols} columns")
            self._after_rows.set(f"{len(data)} rows")
            self._after_cols.set(f"{len(headers)} columns")
            self._timing_var.set(f"{stats.get('c_processing_time_ms', t_elapsed * 1000):.1f} ms")

            self._refresh_preview(headers, data[:20])
            self._save_btn.configure(state="normal")

            if "metrics" in stats and hasattr(self.app, "benchmark_tab"):
                try:
                    self.app.benchmark_tab.add_metrics(stats["metrics"])
                except Exception:
                    pass

            self.app.set_status(
                f"CUDA pipeline complete - {len(data)} rows, {len(headers)} columns, {t_elapsed:.3f}s"
            )
        except Exception as e:
            messagebox.showerror("CUDA Pipeline Error", str(e))
            self.app.set_status("CUDA pipeline error")
            import traceback
            traceback.print_exc()

    def _save_csv(self):
        if not self._processed_data:
            messagebox.showinfo("Nothing to save", "Run the pipeline first.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Processed Data (CUDA)",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv_mod.writer(f)
                writer.writerow(self._processed_headers)
                writer.writerows(self._processed_data)
            self.app.set_status(f"Saved: {os.path.basename(path)}")
            messagebox.showinfo("Saved", f"Processed data saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def _refresh_preview(self, headers, rows):
        self._tree.delete(*self._tree.get_children())
        self._tree["columns"] = headers
        for col in headers:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=max(80, len(col) * 9), anchor="w")
        for row in rows:
            self._tree.insert("", "end", values=row)
