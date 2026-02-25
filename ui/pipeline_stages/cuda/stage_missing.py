"""
Stage 3 — Missing Value Handling
Strategy per column (drop row, mean, median, mode, fill constant, forward-fill).
Also: auto-drop columns threshold slider.
"""

import tkinter as tk
from tkinter import ttk
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import theme


_STRATEGIES = ["Drop row", "Mean", "Median", "Mode", "Fill constant", "Forward-fill"]

STRATEGY_DROP   = "Drop row"
STRATEGY_MEAN   = "Mean"
STRATEGY_MEDIAN = "Median"
STRATEGY_MODE   = "Mode"
STRATEGY_CONST  = "Fill constant"
STRATEGY_FFILL  = "Forward-fill"


class StageMissing:
    """Missing Value Handling stage."""

    LABEL = "Missing Values"
    INDEX = 2

    def __init__(self, parent_frame, app):
        self.app = app
        self.frame = ttk.Frame(parent_frame)
        self._global_strategy = tk.StringVar(value="per_column")
        self._global_common   = tk.StringVar(value=STRATEGY_DROP)
        self._threshold_var   = tk.IntVar(value=80)
        self._col_rows        = {}   # {col_name: {"strategy": StringVar, "fill": StringVar}}
        self._build_static()

    # ── public API ───────────────────────────────────────────────────────────

    def get_frame(self):
        return self.frame

    def refresh(self):
        self._rebuild_col_table()
        self._on_global_change()

    def get_config(self):
        col_cfg = {}
        for col, widgets in self._col_rows.items():
            col_cfg[col] = {
                "strategy": widgets["strategy"].get(),
                "fill_val": widgets["fill"].get(),
            }
        return {
            "global_strategy": self._global_strategy.get(),
            "global_common":   self._global_common.get(),
            "column_config":   col_cfg,
            "drop_threshold":  self._threshold_var.get(),
        }

    def get_status(self):
        if self._global_strategy.get() == "skip":
            return "skipped"
        return "configured"

    # ── private ──────────────────────────────────────────────────────────────

    def _build_static(self):
        pad = dict(padx=14, pady=6)

        ttk.Label(self.frame, text="Missing Value Handling",
                  font=theme.FONT_TITLE, foreground=theme.HIGHLIGHT
                  ).pack(anchor="w", padx=14, pady=(12, 2))
        ttk.Label(self.frame,
                  text="Decide what to do with blank / NaN cells, per column or globally.",
                  style="Muted.TLabel"
                  ).pack(anchor="w", padx=14, pady=(0, 10))
        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", padx=14, pady=(0, 14))

        # ── Global strategy ──────────────────────────────────────────────────
        glob_frame = ttk.LabelFrame(self.frame, text="Global Strategy", padding=12)
        glob_frame.pack(fill="x", **pad)

        for text, val in [
            ("Configure per column (use the table below)", "per_column"),
            ("Apply the same strategy to all columns",     "apply_all"),
            ("Skip — leave all missing values unchanged",  "skip"),
        ]:
            ttk.Radiobutton(glob_frame, text=text, variable=self._global_strategy,
                            value=val, command=self._on_global_change
                            ).pack(anchor="w", pady=2)

        # Inline strategy for "apply all"
        self._global_row = ttk.Frame(glob_frame)
        self._global_row.pack(anchor="w", padx=20, pady=(6, 0))
        ttk.Label(self._global_row, text="Strategy for all:").pack(side="left")
        ttk.Combobox(self._global_row, textvariable=self._global_common,
                     values=_STRATEGIES, state="readonly", width=18
                     ).pack(side="left", padx=6)

        # ── Column threshold ─────────────────────────────────────────────────
        thresh_frame = ttk.LabelFrame(
            self.frame, text="Auto-Drop High-Missing Columns", padding=12)
        thresh_frame.pack(fill="x", **pad)

        thresh_row = ttk.Frame(thresh_frame)
        thresh_row.pack(fill="x")
        ttk.Label(thresh_row, text="Drop columns where missing >").pack(side="left")
        self._thresh_label = ttk.Label(thresh_row,
                                       text=f"{self._threshold_var.get()}%",
                                       foreground=theme.ACCENT)
        self._thresh_label.pack(side="left", padx=4)

        ttk.Scale(thresh_frame, from_=0, to=100,
                  variable=self._threshold_var, orient="horizontal",
                  command=self._on_threshold_move
                  ).pack(fill="x", pady=(6, 0))

        # ── Per-column table ─────────────────────────────────────────────────
        self._per_col_frame = ttk.LabelFrame(
            self.frame, text="Per-Column Configuration", padding=10)
        self._per_col_frame.pack(fill="both", expand=True, **pad)

        # Header row
        hdr = ttk.Frame(self._per_col_frame)
        hdr.pack(fill="x")
        ttk.Label(hdr, text="Column",   width=22, font=theme.FONT_BOLD).pack(side="left")
        ttk.Label(hdr, text="Strategy", width=18, font=theme.FONT_BOLD).pack(side="left")
        ttk.Label(hdr, text="Fill Value (if constant)", font=theme.FONT_BOLD).pack(side="left")
        ttk.Separator(self._per_col_frame, orient="horizontal").pack(fill="x", pady=4)

        # Scrollable container
        self._col_canvas   = tk.Canvas(self._per_col_frame, bg=theme.BG_CARD,
                                       highlightthickness=0, height=200)
        self._col_scrollbar = ttk.Scrollbar(self._per_col_frame, orient="vertical",
                                            command=self._col_canvas.yview)
        self._col_canvas.configure(yscrollcommand=self._col_scrollbar.set)
        self._col_canvas.pack(side="left", fill="both", expand=True)
        self._col_scrollbar.pack(side="right", fill="y")

        self._col_inner = ttk.Frame(self._col_canvas)
        self._col_canvas_window = self._col_canvas.create_window(
            (0, 0), window=self._col_inner, anchor="nw")
        self._col_inner.bind("<Configure>", self._on_inner_resize)

        self._no_data_lbl = ttk.Label(self._col_inner,
                                      text="Import a dataset to see column list.",
                                      style="Muted.TLabel")
        self._no_data_lbl.pack(anchor="w", padx=4, pady=4)

    def _rebuild_col_table(self):
        for w in self._col_inner.winfo_children():
            w.destroy()
        self._col_rows.clear()

        csv = self.app.csv_data
        if not csv:
            ttk.Label(self._col_inner,
                      text="Import a dataset to see column list.",
                      style="Muted.TLabel").pack(anchor="w", padx=4, pady=4)
            return

        for col in csv["headers"]:
            row_frame = ttk.Frame(self._col_inner)
            row_frame.pack(fill="x", pady=2)

            strat_var = tk.StringVar(value=STRATEGY_DROP)
            fill_var  = tk.StringVar(value="")

            ttk.Label(row_frame, text=col, width=22).pack(side="left")
            combo = ttk.Combobox(row_frame, textvariable=strat_var,
                                 values=_STRATEGIES, state="readonly", width=16)
            combo.pack(side="left", padx=4)

            fill_entry = ttk.Entry(row_frame, textvariable=fill_var, width=14)
            fill_entry.pack(side="left", padx=4)

            # Show/hide fill entry
            def _toggle_fill(var=strat_var, entry=fill_entry, *_):
                entry.configure(state="normal" if var.get() == STRATEGY_CONST else "disabled")

            strat_var.trace_add("write", _toggle_fill)
            _toggle_fill()

            self._col_rows[col] = {"strategy": strat_var, "fill": fill_var}

    def _on_global_change(self):
        mode = self._global_strategy.get()
        if mode == "apply_all":
            self._global_row.pack(anchor="w", padx=20, pady=(6, 0))
        else:
            self._global_row.pack_forget()
        if mode == "per_column":
            self._per_col_frame.pack(fill="both", expand=True, padx=14, pady=6)
        else:
            self._per_col_frame.pack_forget()

    def _on_threshold_move(self, _=None):
        self._thresh_label.config(text=f"{self._threshold_var.get()}%")

    def _on_inner_resize(self, _=None):
        self._col_canvas.configure(scrollregion=self._col_canvas.bbox("all"))
