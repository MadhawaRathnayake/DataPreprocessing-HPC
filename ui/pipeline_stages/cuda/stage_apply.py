"""
Stage 7 — Apply & Preview  [CUDA Parallel]
Backend: modules/analyzer_cuda/ (libcudaanalyzer.so) — NOT YET IMPLEMENTED.
This stage shows a "not yet implemented" message when Run is clicked.
The UI is fully built for when the CUDA backend is ready.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os, csv as csv_mod
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import theme


class StageApply:
    """Apply & Preview stage — CUDA backend not yet implemented."""

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

        ttk.Label(self.frame, text="Apply & Preview  [CUDA Parallel]",
                  font=theme.FONT_TITLE, foreground=theme.HIGHLIGHT
                  ).pack(anchor="w", padx=14, pady=(12, 2))
        ttk.Label(self.frame,
                  text="Preprocessing pipeline will use CUDA GPU-parallelized C backend (libcudaanalyzer.so).",
                  style="Muted.TLabel"
                  ).pack(anchor="w", padx=14, pady=(0, 2))

        # CUDA info banner
        info = ttk.LabelFrame(self.frame, text="🚀 CUDA Backend", padding=8)
        info.pack(fill="x", padx=14, pady=(0, 6))
        ttk.Label(info,
                  text=("Backend: modules/analyzer_cuda/ → libcudaanalyzer.so  [PLANNED]\n"
                        "Parallelism: CUDA kernels — massively parallel GPU thread blocks\n"
                        "Status: ⚠  Backend NOT YET IMPLEMENTED — UI is ready for integration."),
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

        self._run_btn = ttk.Button(btn_frame, text="▶  Run CUDA Pipeline",
                                   command=self._run_pipeline)
        self._run_btn.pack(side="left", padx=(0, 10))

        self._save_btn = ttk.Button(btn_frame, text="💾  Save Processed CSV",
                                    command=self._save_csv, state="disabled")
        self._save_btn.pack(side="left")

        # ── Before / After stats (placeholder) ──────────────────────────────
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

        timing_cell = ttk.Frame(stats_frame)
        timing_cell.grid(row=0, column=2, padx=30, sticky="w")
        ttk.Label(timing_cell, text="GPU Processing Time", font=theme.FONT_BOLD,
                  foreground=theme.HIGHLIGHT).pack(anchor="w")
        ttk.Label(timing_cell, text="—  (not implemented)",
                  font=theme.FONT_LARGE, foreground=theme.TEXT_MUTED).pack(anchor="w")

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
        lines = ["[CUDA Parallel Mode — Backend Not Yet Implemented]", ""]
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
            lines.append("")
            lines.append("⚠  CUDA backend (libcudaanalyzer.so) is not yet implemented.")
            lines.append("   Clicking 'Run CUDA Pipeline' will show a not-implemented notice.")
        except Exception:
            lines = ["  (Import a dataset and configure stages first)"]

        self._summary_text.configure(state="normal")
        self._summary_text.delete("1.0", "end")
        self._summary_text.insert("1.0", "\n".join(lines))
        self._summary_text.configure(state="disabled")

    def _run_pipeline(self):
        messagebox.showinfo(
            "CUDA Backend — Not Yet Implemented",
            "The CUDA GPU-parallel backend has not been implemented yet.\n\n"
            "Planned implementation:\n"
            "  • C source: modules/analyzer_cuda/\n"
            "  • Shared library: lib/libcudaanalyzer.so\n"
            "  • Compiled with: nvcc -shared -fPIC\n\n"
            "The UI pipeline stages are fully configured and ready.\n"
            "Use Series Processing or OpenMP/MPI tabs for available backends."
        )
        self.app.set_status("CUDA backend not yet implemented — see other tabs.")

    def _save_csv(self):
        messagebox.showinfo("Not available", "Run the pipeline first.")

    def _refresh_preview(self, headers, rows):
        self._tree.delete(*self._tree.get_children())
        self._tree["columns"] = headers
        for col in headers:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=max(80, len(col) * 9), anchor="w")
        for row in rows:
            self._tree.insert("", "end", values=row)
