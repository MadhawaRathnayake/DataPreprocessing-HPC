"""
Stage 4 — Outlier Detection & Treatment
Methods: IQR or Z-score. Treatment: remove, cap, flag, or skip.
"""

import tkinter as tk
from tkinter import ttk
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import theme


class StageOutliers:
    """Outlier Detection & Treatment stage."""

    LABEL = "Outlier Detection"
    INDEX = 3

    def __init__(self, parent_frame, app):
        self.app = app
        self.frame = ttk.Frame(parent_frame)
        self._method      = tk.StringVar(value="iqr")
        self._zscore_thr  = tk.DoubleVar(value=3.0)
        self._iqr_mult    = tk.DoubleVar(value=1.5)
        self._treatment   = tk.StringVar(value="remove")
        self._col_vars    = {}   # {col_name: BooleanVar}
        self._build_static()

    # ── public API ───────────────────────────────────────────────────────────

    def get_frame(self):
        return self.frame

    def refresh(self):
        self._rebuild_col_list()
        self._on_method_change()

    def get_config(self):
        return {
            "method":       self._method.get(),
            "zscore_thr":   self._zscore_thr.get(),
            "iqr_mult":     self._iqr_mult.get(),
            "treatment":    self._treatment.get(),
            "columns":      [c for c, v in self._col_vars.items() if v.get()],
        }

    def get_status(self):
        if self._treatment.get() == "skip":
            return "skipped"
        return "configured"

    # ── private ──────────────────────────────────────────────────────────────

    def _build_static(self):
        pad = dict(padx=14, pady=6)

        ttk.Label(self.frame, text="Outlier Detection & Treatment",
                  font=theme.FONT_TITLE, foreground=theme.HIGHLIGHT
                  ).pack(anchor="w", padx=14, pady=(12, 2))
        ttk.Label(self.frame,
                  text="Find and handle numeric outliers using IQR or Z-score methods.",
                  style="Muted.TLabel"
                  ).pack(anchor="w", padx=14, pady=(0, 10))
        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", padx=14, pady=(0, 14))

        # ── Detection method ─────────────────────────────────────────────────
        detect_frame = ttk.LabelFrame(self.frame, text="Detection Method", padding=12)
        detect_frame.pack(fill="x", **pad)

        inner = ttk.Frame(detect_frame)
        inner.pack(fill="x")

        iqr_rb = ttk.Radiobutton(inner, text="IQR rule  (Q1 − 1.5×IQR, Q3 + 1.5×IQR)",
                                 variable=self._method, value="iqr",
                                 command=self._on_method_change)
        iqr_rb.grid(row=0, column=0, sticky="w", pady=2)

        self._iqr_row = ttk.Frame(inner)
        self._iqr_row.grid(row=0, column=1, padx=20, sticky="w")
        ttk.Label(self._iqr_row, text="IQR multiplier:").pack(side="left")
        ttk.Spinbox(self._iqr_row, from_=0.5, to=5.0, increment=0.5,
                    textvariable=self._iqr_mult, width=7, format="%.1f"
                    ).pack(side="left", padx=4)

        z_rb = ttk.Radiobutton(inner, text="Z-score  (distance from mean in std devs)",
                               variable=self._method, value="zscore",
                               command=self._on_method_change)
        z_rb.grid(row=1, column=0, sticky="w", pady=2)

        self._z_row = ttk.Frame(inner)
        self._z_row.grid(row=1, column=1, padx=20, sticky="w")
        ttk.Label(self._z_row, text="Z-score threshold:").pack(side="left")
        ttk.Spinbox(self._z_row, from_=1.0, to=10.0, increment=0.5,
                    textvariable=self._zscore_thr, width=7, format="%.1f"
                    ).pack(side="left", padx=4)

        # ── Treatment ────────────────────────────────────────────────────────
        treat_frame = ttk.LabelFrame(self.frame, text="Treatment", padding=12)
        treat_frame.pack(fill="x", **pad)

        for text, val in [
            ("Remove rows containing outliers",                    "remove"),
            ("Cap (Winsorise) outliers to IQR / Z boundary",       "cap"),
            ("Flag only — add a boolean column for each outlier",   "flag"),
            ("Skip — leave all values unchanged",                   "skip"),
        ]:
            ttk.Radiobutton(treat_frame, text=text, variable=self._treatment,
                            value=val).pack(anchor="w", pady=2)

        # ── Apply to columns ─────────────────────────────────────────────────
        self._col_outer = ttk.LabelFrame(
            self.frame, text="Apply to Numeric Columns", padding=12)
        self._col_outer.pack(fill="x", **pad)

        self._col_inner = ttk.Frame(self._col_outer)
        self._col_inner.pack(fill="x")

        ttk.Label(self._col_inner,
                  text="Import a dataset to see numeric column list.",
                  style="Muted.TLabel").pack(anchor="w")

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
            var = tk.BooleanVar(value=True)   # default: all numeric cols selected
            self._col_vars[col] = var
            r, c = divmod(idx, 3)
            ttk.Checkbutton(self._col_inner, text=col, variable=var
                            ).grid(row=r, column=c, sticky="w", padx=8, pady=2)

    def _on_method_change(self):
        method = self._method.get()
        # Show correct parameter row
        for widget in self._iqr_row.winfo_children():
            widget.configure(state="normal" if method == "iqr" else "disabled")
        for widget in self._z_row.winfo_children():
            widget.configure(state="normal" if method == "zscore" else "disabled")

    @staticmethod
    def _get_numeric_cols(csv):
        numeric = []
        for i, col in enumerate(csv["headers"]):
            col_data = [row[i] for row in csv["data"] if i < len(row)]
            parsed = 0
            for v in col_data:
                if v and v.strip():
                    try:
                        float(v); parsed += 1
                    except ValueError:
                        pass
            if col_data and parsed / len(col_data) > 0.5:
                numeric.append(col)
        return numeric
