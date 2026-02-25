"""
Stage 6 — Categorical Encoding
Per-column method: Label encode / One-hot encode / Skip.
"""

import tkinter as tk
from tkinter import ttk
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import theme


_METHODS = ["Label encode", "One-hot encode", "Skip"]


class StageEncoding:
    """Categorical Encoding stage."""

    LABEL = "Categorical Encoding"
    INDEX = 5

    def __init__(self, parent_frame, app):
        self.app = app
        self.frame = ttk.Frame(parent_frame)
        self._drop_original = tk.BooleanVar(value=True)
        self._col_rows      = {}   # {col_name: StringVar (method)}
        self._build_static()

    # ── public API ───────────────────────────────────────────────────────────

    def get_frame(self):
        return self.frame

    def refresh(self):
        self._rebuild_col_table()

    def get_config(self):
        return {
            "drop_original": self._drop_original.get(),
            "column_methods": {c: v.get() for c, v in self._col_rows.items()},
        }

    def get_status(self):
        if not self._col_rows:
            return "pending"
        if all(v.get() == "Skip" for v in self._col_rows.values()):
            return "skipped"
        return "configured"

    # ── private ──────────────────────────────────────────────────────────────

    def _build_static(self):
        pad = dict(padx=14, pady=6)

        ttk.Label(self.frame, text="Categorical Encoding",
                  font=theme.FONT_TITLE, foreground=theme.HIGHLIGHT
                  ).pack(anchor="w", padx=14, pady=(12, 2))
        ttk.Label(self.frame,
                  text="Convert text / category columns to numbers for analysis.",
                  style="Muted.TLabel"
                  ).pack(anchor="w", padx=14, pady=(0, 10))
        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", padx=14, pady=(0, 14))

        # ── Options ──────────────────────────────────────────────────────────
        opt_frame = ttk.LabelFrame(self.frame, text="Options", padding=12)
        opt_frame.pack(fill="x", **pad)

        ttk.Checkbutton(opt_frame,
                        text="Drop original column after one-hot encoding",
                        variable=self._drop_original
                        ).pack(anchor="w")

        # ── Per-column table ─────────────────────────────────────────────────
        col_frame = ttk.LabelFrame(self.frame, text="Categorical Column Encoding", padding=10)
        col_frame.pack(fill="both", expand=True, **pad)

        # Header
        hdr = ttk.Frame(col_frame)
        hdr.pack(fill="x")
        ttk.Label(hdr, text="Column",  width=24, font=theme.FONT_BOLD).pack(side="left")
        ttk.Label(hdr, text="Method",  width=18, font=theme.FONT_BOLD).pack(side="left")
        ttk.Label(hdr, text="Unique values detected", font=theme.FONT_BOLD).pack(side="left")
        ttk.Separator(col_frame, orient="horizontal").pack(fill="x", pady=4)

        # Scrollable container
        canvas = tk.Canvas(col_frame, bg=theme.BG_CARD, highlightthickness=0, height=220)
        vsb    = ttk.Scrollbar(col_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._inner = ttk.Frame(canvas)
        self._canvas_win = canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>",
                         lambda _: canvas.configure(scrollregion=canvas.bbox("all")))

        ttk.Label(self._inner,
                  text="Import a dataset to see categorical column list.",
                  style="Muted.TLabel").pack(anchor="w", padx=4, pady=4)

    def _rebuild_col_table(self):
        for w in self._inner.winfo_children():
            w.destroy()
        self._col_rows.clear()

        csv = self.app.csv_data
        if not csv:
            ttk.Label(self._inner,
                      text="Import a dataset to see categorical column list.",
                      style="Muted.TLabel").pack(anchor="w", padx=4, pady=4)
            return

        cat_cols = self._get_categorical_cols(csv)
        if not cat_cols:
            ttk.Label(self._inner,
                      text="No categorical (text/object) columns detected.",
                      style="Muted.TLabel").pack(anchor="w", padx=4, pady=4)
            return

        for col, unique_count in cat_cols:
            row_frame = ttk.Frame(self._inner)
            row_frame.pack(fill="x", pady=2)

            method_var = tk.StringVar(value="Label encode")
            self._col_rows[col] = method_var

            ttk.Label(row_frame, text=col, width=24).pack(side="left")
            ttk.Combobox(row_frame, textvariable=method_var,
                         values=_METHODS, state="readonly", width=16
                         ).pack(side="left", padx=4)
            ttk.Label(row_frame, text=f"{unique_count} unique",
                      style="Muted.TLabel").pack(side="left", padx=8)

    @staticmethod
    def _get_categorical_cols(csv):
        cat = []
        for i, col in enumerate(csv["headers"]):
            col_data = [row[i] for row in csv["data"] if i < len(row)]
            if not col_data:
                continue
            parsed = sum(1 for v in col_data if v and v.strip() and _is_float(v))
            if parsed / len(col_data) <= 0.5:
                unique_count = len(set(v for v in col_data if v))
                cat.append((col, unique_count))
        return cat


def _is_float(v):
    try:
        float(v); return True
    except ValueError:
        return False
