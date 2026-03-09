"""
Stage 7 — Apply & Preview  [MPI Parallel]
Executes all configured pipeline stages using MPI-parallelized C backend.
Backend: libmpianalyzer.so (modules/analyzer_mpi/) via ctypes.

NOTE: Full MPI C integration is the next development phase.
Currently falls back to Python computation while the MPI C library is wired up.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os, csv as csv_mod, collections, time
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import theme
from preprocess import PreprocessingPipeline

class StageApply:
    """Apply & Preview stage — runs the full pipeline using MPI backend."""

    LABEL = "Apply & Preview"
    INDEX = 6

    def __init__(self, parent_frame, app, get_stage_configs_cb):
        self.app = app
        self._get_configs = get_stage_configs_cb
        self._processed_data = None
        self._processed_headers = None
        self.frame = ttk.Frame(parent_frame)
        self._build()

    # ── public API ───────────────────────────────────────────────────────────

    def get_frame(self):
        return self.frame

    def refresh(self):
        self._update_summary()

    def get_config(self):
        return {}

    def get_status(self):
        return "configured"

    # ── private — UI ─────────────────────────────────────────────────────────

    def _build(self):
        pad = dict(padx=14, pady=6)

        ttk.Label(self.frame, text="Apply & Preview  [MPI Parallel]",
                  font=theme.FONT_TITLE, foreground=theme.HIGHLIGHT
                  ).pack(anchor="w", padx=14, pady=(12, 2))
        ttk.Label(self.frame,
                  text="Runs preprocessing pipeline using MPI-parallelized C backend (libmpianalyzer.so).",
                  style="Muted.TLabel"
                  ).pack(anchor="w", padx=14, pady=(0, 2))

        # MPI info banner
        info = ttk.LabelFrame(self.frame, text="🌐 MPI Backend", padding=8)
        info.pack(fill="x", padx=14, pady=(0, 6))
        ttk.Label(info,
                  text=("Backend: modules/analyzer_mpi/ → libmpianalyzer.so\n"
                        "Parallelism: MPI_Send / MPI_Recv (column distribution across processes)\n"
                        "Status: C library framework ready — full ctypes integration is next phase."),
                  style="Muted.TLabel", justify="left"
                  ).pack(anchor="w")

        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", padx=14, pady=(0, 10))

        # ── Pipeline summary ─────────────────────────────────────────────────
        sum_frame = ttk.LabelFrame(self.frame, text="Pipeline Summary", padding=10)
        sum_frame.pack(fill="x", **pad)

        self._summary_text = tk.Text(sum_frame, height=8, wrap="word",
                                     state="disabled",
                                     **{k: v for k, v in theme.TEXT_WIDGET_CFG.items()
                                        if k not in ("padx", "pady", "relief")})
        self._summary_text.pack(fill="x")

        # ── Run button ───────────────────────────────────────────────────────
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill="x", padx=14, pady=8)

        self._run_btn = ttk.Button(btn_frame, text="▶  Run MPI Pipeline",
                                   command=self._run_pipeline)
        self._run_btn.pack(side="left", padx=(0, 10))

        self._save_btn = ttk.Button(btn_frame, text="💾  Save Processed CSV",
                                    command=self._save_csv, state="disabled")
        self._save_btn.pack(side="left")

        # ── Before / After stats ─────────────────────────────────────────────
        stats_frame = ttk.LabelFrame(self.frame, text="Before / After", padding=12)
        stats_frame.pack(fill="x", **pad)

        for col_offset, label, key in [(0, "Before", "before"), (1, "After", "after")]:
            cell = ttk.Frame(stats_frame)
            cell.grid(row=0, column=col_offset, padx=30, sticky="w")
            ttk.Label(cell, text=label, font=theme.FONT_BOLD,
                      foreground=theme.HIGHLIGHT).pack(anchor="w")
            self.__dict__[f"_{key}_rows"] = tk.StringVar(value="—")
            self.__dict__[f"_{key}_cols"] = tk.StringVar(value="—")
            ttk.Label(cell, textvariable=self.__dict__[f"_{key}_rows"],
                      font=theme.FONT_LARGE, foreground=theme.ACCENT).pack(anchor="w")
            ttk.Label(cell, textvariable=self.__dict__[f"_{key}_cols"],
                      style="Muted.TLabel").pack(anchor="w")

        # Timing
        timing_cell = ttk.Frame(stats_frame)
        timing_cell.grid(row=0, column=2, padx=30, sticky="w")
        ttk.Label(timing_cell, text="Processing Time", font=theme.FONT_BOLD,
                  foreground=theme.HIGHLIGHT).pack(anchor="w")
        self._timing_var = tk.StringVar(value="—")
        ttk.Label(timing_cell, textvariable=self._timing_var,
                  font=theme.FONT_LARGE, foreground=theme.ACCENT).pack(anchor="w")

        # ── Preview table ─────────────────────────────────────────────────────
        preview_frame = ttk.LabelFrame(self.frame, text="Output Preview (first 20 rows)", padding=10)
        preview_frame.pack(fill="both", expand=True, **pad)

        self._tree = ttk.Treeview(preview_frame, show="headings", height=10)
        vsb = ttk.Scrollbar(preview_frame, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(preview_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right",  fill="y")
        self._tree.pack(side="left", fill="both", expand=True)

    # ── private — pipeline logic ──────────────────────────────────────────────

    def _update_summary(self):
        lines = ["[MPI Parallel Mode]", ""]
        try:
            configs = self._get_configs()
            stage_names = [
                "1 · Overview & Profile",
                "2 · Duplicate Removal",
                "3 · Missing Values",
                "4 · Outlier Detection",
                "5 · Scaling & Normalisation",
                "6 · Categorical Encoding",
            ]
            for name, cfg in zip(stage_names, configs):
                if not cfg:
                    lines.append(f"  • {name}  →  (read-only / no config)")
                    continue
                action = cfg.get("action") or cfg.get("global_strategy") or \
                         cfg.get("method") or cfg.get("treatment") or "configured"
                lines.append(f"  • {name}  →  {action}")
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

        self.app.set_status("Running MPI distributed pipeline…")
        self.app.root.update()

        try:
            configs = self._get_configs()
            headers = list(self.app.csv_data["headers"])
            data    = [list(row) for row in self.app.csv_data["data"]]

            orig_rows = len(data)
            orig_cols = len(headers)

            # Create and run preprocessing pipeline with MPI backend
            # num_processes can be configured - defaults to optimal system processes
            import os
            num_processes = min(os.cpu_count() or 4, 4)  # Cap at 4 for MPI
            
            pipeline = PreprocessingPipeline(backend_type="mpi", num_processes=num_processes)
            t_start = time.perf_counter()
            data, headers, stats = pipeline.run_pipeline(data, headers, configs)
            t_elapsed = time.perf_counter() - t_start

            self._processed_data    = data
            self._processed_headers = headers

            self._before_rows.set(f"{orig_rows} rows")
            self._before_cols.set(f"{orig_cols} columns")
            self._after_rows.set(f"{len(data)} rows")
            self._after_cols.set(f"{len(headers)} columns")
            self._timing_var.set(f"{t_elapsed*1000:.1f} ms")

            self._refresh_preview(headers, data[:20])
            self._save_btn.configure(state="normal")

            # Add metrics to benchmark comparison if available
            if 'metrics' in stats and hasattr(self.app, 'benchmark_tab'):
                try:
                    self.app.benchmark_tab.add_metrics(stats['metrics'])
                except:
                    pass

            self.app.set_status(
                f"MPI pipeline complete — {orig_rows - len(data)} rows removed, "
                f"{len(headers)} columns remaining. ({t_elapsed*1000:.1f} ms)"
            )
        except Exception as e:
            messagebox.showerror("Pipeline Error", str(e))
            self.app.set_status("Pipeline error")
            import traceback; traceback.print_exc()

    # ── Stage processors (now in PreprocessingPipeline class) ──

    # NOTE: Processing functions now integrated in PreprocessingPipeline class
    # in preprocess.py module for better code organization and reusability.

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save_csv(self):
        if not self._processed_data:
            messagebox.showinfo("Nothing to save", "Run the pipeline first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Processed Data (MPI)",
        )
        if not path: return
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
