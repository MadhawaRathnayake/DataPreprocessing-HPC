"""
Stage 1 — Data Overview & Profile
Read-only snapshot of the imported dataset: row/col counts and per-column info.
"""

import tkinter as tk
from tkinter import ttk
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import theme


class StageOverview:
    """Data Overview & Profile — always runs first, read-only."""

    LABEL = "Overview & Profile"
    INDEX = 0

    def __init__(self, parent_frame, app):
        self.app = app
        self.frame = ttk.Frame(parent_frame)
        self._build()

    # ── public API ───────────────────────────────────────────────────────────

    def get_frame(self):
        return self.frame

    def refresh(self):
        """Populate the stats grid from app.csv_data."""
        csv = self.app.csv_data
        if not csv:
            self._show_placeholder()
            return

        self._stats_vars["rows"].set(str(csv["num_rows"]))
        self._stats_vars["cols"].set(str(csv["num_cols"]))

        # Detect numeric / categorical counts
        num_numeric = num_categorical = 0
        col_info_rows = []
        for i, col in enumerate(csv["headers"]):
            col_data = [row[i] for row in csv["data"] if i < len(row)]
            total = len(col_data)
            null_count = sum(1 for v in col_data if not v or v.strip() == "")
            null_pct = (null_count / total * 100) if total else 0

            numeric_count = 0
            for v in col_data:
                if v and v.strip():
                    try:
                        float(v)
                        numeric_count += 1
                    except ValueError:
                        pass

            if total and numeric_count / total > 0.5:
                col_type = "Numeric"
                num_numeric += 1
            else:
                col_type = "Categorical"
                num_categorical += 1

            col_info_rows.append((col, col_type, null_count, f"{null_pct:.1f}%"))

        self._stats_vars["numeric"].set(str(num_numeric))
        self._stats_vars["categorical"].set(str(num_categorical))

        # Duplicate detection (pure Python)
        seen = set()
        dup_count = 0
        for row in csv["data"]:
            key = tuple(row)
            if key in seen:
                dup_count += 1
            else:
                seen.add(key)
        dup_text = f"{dup_count}"
        dup_color = theme.WARNING if dup_count > 0 else theme.SUCCESS
        self._dup_label.config(text=dup_text, foreground=dup_color)

        # Populate per-column treeview
        for item in self._col_tree.get_children():
            self._col_tree.delete(item)
        for col_name, col_type, null_c, null_p in col_info_rows:
            self._col_tree.insert("", "end", values=(col_name, col_type, null_c, null_p))

    # ── private ──────────────────────────────────────────────────────────────

    def _build(self):
        pad = dict(padx=14, pady=6)

        # Title
        ttk.Label(self.frame, text="Data Overview & Profile",
                  font=theme.FONT_TITLE, foreground=theme.HIGHLIGHT
                  ).pack(anchor="w", padx=14, pady=(12, 2))
        ttk.Label(self.frame,
                  text="Auto-populated when the tab becomes active — no configuration needed.",
                  style="Muted.TLabel"
                  ).pack(anchor="w", padx=14, pady=(0, 10))

        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", padx=14, pady=(0, 14))

        # ── Stats grid ──────────────────────────────────────────────────────
        grid_frame = ttk.LabelFrame(self.frame, text="Dataset Summary", padding=12)
        grid_frame.pack(fill="x", **pad)

        self._stats_vars = {
            "rows":        tk.StringVar(value="—"),
            "cols":        tk.StringVar(value="—"),
            "numeric":     tk.StringVar(value="—"),
            "categorical": tk.StringVar(value="—"),
        }
        labels = [
            ("Total Rows",    "rows"),
            ("Total Columns", "cols"),
            ("Numeric Cols",  "numeric"),
            ("Categorical Cols", "categorical"),
        ]
        for col_idx, (label_text, key) in enumerate(labels):
            cell = ttk.Frame(grid_frame)
            cell.grid(row=0, column=col_idx, padx=16, pady=4, sticky="w")
            ttk.Label(cell, text=label_text, style="Muted.TLabel").pack(anchor="w")
            ttk.Label(cell, textvariable=self._stats_vars[key],
                      font=theme.FONT_LARGE, foreground=theme.ACCENT).pack(anchor="w")

        # Duplicate count
        dup_cell = ttk.Frame(grid_frame)
        dup_cell.grid(row=0, column=4, padx=16, pady=4, sticky="w")
        ttk.Label(dup_cell, text="Duplicate Rows", style="Muted.TLabel").pack(anchor="w")
        self._dup_label = tk.Label(dup_cell, text="—",
                                   bg=theme.BG_CARD,
                                   font=theme.FONT_LARGE)
        self._dup_label.pack(anchor="w")

        # ── Per-column table ─────────────────────────────────────────────────
        col_frame = ttk.LabelFrame(self.frame, text="Column Details", padding=10)
        col_frame.pack(fill="both", expand=True, **pad)

        columns = ("Column", "Type", "Missing #", "Missing %")
        self._col_tree = ttk.Treeview(col_frame, columns=columns,
                                      show="headings", height=10)
        for c in columns:
            self._col_tree.heading(c, text=c)
            width = 200 if c == "Column" else 120
            self._col_tree.column(c, width=width, anchor="w")

        vsb = ttk.Scrollbar(col_frame, orient="vertical",
                            command=self._col_tree.yview)
        self._col_tree.configure(yscrollcommand=vsb.set)
        self._col_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._show_placeholder()

    def _show_placeholder(self):
        for item in self._col_tree.get_children():
            self._col_tree.delete(item)
        for k in self._stats_vars.values():
            k.set("—")
        self._dup_label.config(text="—", foreground=theme.TEXT_MUTED)

    def get_config(self):
        """Stage 1 has no user config — return empty dict."""
        return {}

    def get_status(self):
        """Return one of: pending, configured, skipped."""
        return "configured" if self.app.csv_data else "pending"
