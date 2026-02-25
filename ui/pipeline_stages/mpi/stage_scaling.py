"""
Stage 5 — Scaling & Normalisation
Methods: Min-Max, Z-score Standardisation, Robust (IQR-based), Skip.
"""

import tkinter as tk
from tkinter import ttk
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import theme


class StageScaling:
    """Scaling & Normalisation stage."""

    LABEL = "Scaling & Normalisation"
    INDEX = 4

    def __init__(self, parent_frame, app):
        self.app = app
        self.frame = ttk.Frame(parent_frame)
        self._method   = tk.StringVar(value="minmax")
        self._col_vars = {}
        self._build_static()

    # ── public API ───────────────────────────────────────────────────────────

    def get_frame(self):
        return self.frame

    def refresh(self):
        self._rebuild_col_list()

    def get_config(self):
        return {
            "method":  self._method.get(),
            "columns": [c for c, v in self._col_vars.items() if v.get()],
        }

    def get_status(self):
        if self._method.get() == "skip":
            return "skipped"
        return "configured"

    # ── private ──────────────────────────────────────────────────────────────

    def _build_static(self):
        pad = dict(padx=14, pady=6)

        ttk.Label(self.frame, text="Scaling & Normalisation",
                  font=theme.FONT_TITLE, foreground=theme.HIGHLIGHT
                  ).pack(anchor="w", padx=14, pady=(12, 2))
        ttk.Label(self.frame,
                  text="Bring numeric features onto a common scale for fair comparison.",
                  style="Muted.TLabel"
                  ).pack(anchor="w", padx=14, pady=(0, 10))
        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", padx=14, pady=(0, 14))

        # ── Method ───────────────────────────────────────────────────────────
        method_frame = ttk.LabelFrame(self.frame, text="Scaling Method", padding=12)
        method_frame.pack(fill="x", **pad)

        methods = [
            ("Min-Max Normalisation  [0 – 1]",             "minmax",   "Sensitive to outliers — remove them first (Stage 4)."),
            ("Z-score Standardisation  (μ=0, σ=1)",        "zscore",   "Centers data around zero; useful for many ML algorithms."),
            ("Robust Scaling  (IQR-based, outlier-safe)", "robust",   "Uses median & IQR — best when outliers remain in data."),
            ("Skip — do not scale",                        "skip",     ""),
        ]
        for text, val, hint in methods:
            row = ttk.Frame(method_frame)
            row.pack(anchor="w", pady=3)
            ttk.Radiobutton(row, text=text, variable=self._method,
                            value=val).pack(side="left")
            if hint:
                ttk.Label(row, text=f"  ⓘ {hint}", style="Muted.TLabel"
                          ).pack(side="left", padx=8)

        # ── Column selector ──────────────────────────────────────────────────
        self._col_outer = ttk.LabelFrame(
            self.frame, text="Apply to Numeric Columns", padding=12)
        self._col_outer.pack(fill="x", **pad)

        self._col_inner = ttk.Frame(self._col_outer)
        self._col_inner.pack(fill="x")

        ttk.Label(self._col_inner,
                  text="Import a dataset to see numeric column list.",
                  style="Muted.TLabel").pack(anchor="w")

        # Context note
        note = ttk.LabelFrame(self.frame, text="💡 Note", padding=10)
        note.pack(fill="x", **pad)
        ttk.Label(note,
                  text=("Scaling is applied after outlier treatment (Stage 4).\n"
                        "Binary flag columns added by Stage 4 are excluded automatically."),
                  style="Muted.TLabel", justify="left"
                  ).pack(anchor="w")

    def _rebuild_col_list(self):
        for w in self._col_inner.winfo_children():
            w.destroy()
        self._col_vars.clear()

        csv = self.app.csv_data
        if not csv:
            ttk.Label(self._col_inner,
                      text="Import a dataset to see numeric column list.",
                      style="Muted.TLabel").pack(anchor="w")
            return

        numeric_cols = self._get_numeric_cols(csv)
        if not numeric_cols:
            ttk.Label(self._col_inner,
                      text="No numeric columns detected.",
                      style="Muted.TLabel").pack(anchor="w")
            return

        for idx, col in enumerate(numeric_cols):
            var = tk.BooleanVar(value=True)
            self._col_vars[col] = var
            r, c = divmod(idx, 3)
            ttk.Checkbutton(self._col_inner, text=col, variable=var
                            ).grid(row=r, column=c, sticky="w", padx=8, pady=2)

    @staticmethod
    def _get_numeric_cols(csv):
        numeric = []
        for i, col in enumerate(csv["headers"]):
            col_data = [row[i] for row in csv["data"] if i < len(row)]
            parsed = sum(1 for v in col_data if v and v.strip() and
                         _is_float(v))
            if col_data and parsed / len(col_data) > 0.5:
                numeric.append(col)
        return numeric


def _is_float(v):
    try:
        float(v); return True
    except ValueError:
        return False
