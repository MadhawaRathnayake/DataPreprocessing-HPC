"""
Stage 2 — Duplicate Removal
Options: action (drop exact / drop by subset / skip), column subset, keep policy.
"""

import tkinter as tk
from tkinter import ttk
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import theme


class StageDuplicates:
    """Duplicate Removal stage."""

    LABEL = "Duplicate Removal"
    INDEX = 1

    def __init__(self, parent_frame, app):
        self.app = app
        self.frame = ttk.Frame(parent_frame)
        # Internal state
        self._action     = tk.StringVar(value="drop_exact")
        self._keep       = tk.StringVar(value="first")
        self._col_vars   = {}       # {col_name: BooleanVar}
        self._built      = False    # deferred until columns are known
        self._build_static()

    # ── public API ───────────────────────────────────────────────────────────

    def get_frame(self):
        return self.frame

    def refresh(self):
        """Rebuild column checklist when dataset changes."""
        self._rebuild_col_list()
        self._on_action_change()

    def get_config(self):
        return {
            "action":        self._action.get(),
            "keep":          self._keep.get(),
            "col_subset":    [c for c, v in self._col_vars.items() if v.get()],
        }

    def get_status(self):
        if self._action.get() == "skip":
            return "skipped"
        return "configured"

    # ── private ──────────────────────────────────────────────────────────────

    def _build_static(self):
        pad = dict(padx=14, pady=6)

        ttk.Label(self.frame, text="Duplicate Removal",
                  font=theme.FONT_TITLE, foreground=theme.HIGHLIGHT
                  ).pack(anchor="w", padx=14, pady=(12, 2))
        ttk.Label(self.frame,
                  text="Remove or mark repeated rows in the dataset.",
                  style="Muted.TLabel"
                  ).pack(anchor="w", padx=14, pady=(0, 10))
        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", padx=14, pady=(0, 14))

        # ── Action ───────────────────────────────────────────────────────────
        action_frame = ttk.LabelFrame(self.frame, text="Action", padding=12)
        action_frame.pack(fill="x", **pad)

        for text, val in [
            ("Drop exact duplicates (all columns must match)", "drop_exact"),
            ("Drop by subset of columns",                      "drop_subset"),
            ("Skip — keep all rows unchanged",                 "skip"),
        ]:
            ttk.Radiobutton(action_frame, text=text, variable=self._action,
                            value=val, command=self._on_action_change
                            ).pack(anchor="w", pady=2)

        # ── Keep policy ──────────────────────────────────────────────────────
        keep_frame = ttk.LabelFrame(self.frame, text="Keep Which Copy?", padding=12)
        keep_frame.pack(fill="x", **pad)

        for text, val in [("First occurrence", "first"),
                          ("Last occurrence",  "last"),
                          ("None — drop all copies", "none")]:
            ttk.Radiobutton(keep_frame, text=text, variable=self._keep,
                            value=val).pack(anchor="w", pady=2)

        # ── Column subset ────────────────────────────────────────────────────
        self._subset_frame = ttk.LabelFrame(
            self.frame, text="Column Subset (match duplicates on these columns only)", padding=12)
        self._subset_frame.pack(fill="x", **pad)

        self._col_check_frame = ttk.Frame(self._subset_frame)
        self._col_check_frame.pack(fill="x")

        self._no_data_label = ttk.Label(self._col_check_frame,
                                        text="Import a dataset to see column list.",
                                        style="Muted.TLabel")
        self._no_data_label.pack(anchor="w")

    def _rebuild_col_list(self):
        for w in self._col_check_frame.winfo_children():
            w.destroy()
        self._col_vars.clear()

        csv = self.app.csv_data
        if not csv:
            ttk.Label(self._col_check_frame,
                      text="Import a dataset to see column list.",
                      style="Muted.TLabel").pack(anchor="w")
            return

        # Two-column grid of checkboxes
        headers = csv["headers"]
        for idx, col in enumerate(headers):
            var = tk.BooleanVar(value=False)
            self._col_vars[col] = var
            row, col_pos = divmod(idx, 3)
            cb = ttk.Checkbutton(self._col_check_frame, text=col, variable=var)
            cb.grid(row=row, column=col_pos, sticky="w", padx=8, pady=2)

    def _on_action_change(self):
        is_subset = self._action.get() == "drop_subset"
        if is_subset:
            self._subset_frame.pack(fill="x", padx=14, pady=6)
        else:
            self._subset_frame.pack_forget()
