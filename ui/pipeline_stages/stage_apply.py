"""
Stage 7 — Apply & Preview
Executes all configured pipeline stages in order and shows before/after stats
plus a preview of the first N rows of cleaned data.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os, csv as csv_mod, collections
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import theme


class StageApply:
    """Apply & Preview stage — runs the full pipeline."""

    LABEL = "Apply & Preview"
    INDEX = 6

    def __init__(self, parent_frame, app, get_stage_configs_cb):
        """
        Parameters
        ----------
        parent_frame        : tk parent widget
        app                 : DataPreprocessingApp instance
        get_stage_configs_cb: callable() → list of config dicts (one per stage)
        """
        self.app = app
        self._get_configs = get_stage_configs_cb
        self._processed_data = None    # list-of-lists after pipeline
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

        ttk.Label(self.frame, text="Apply & Preview",
                  font=theme.FONT_TITLE, foreground=theme.HIGHLIGHT
                  ).pack(anchor="w", padx=14, pady=(12, 2))
        ttk.Label(self.frame,
                  text="Review your pipeline configuration, run it, and inspect the result.",
                  style="Muted.TLabel"
                  ).pack(anchor="w", padx=14, pady=(0, 10))
        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", padx=14, pady=(0, 14))

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

        self._run_btn = ttk.Button(btn_frame, text="▶  Run Pipeline",
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

        # ── Preview table ────────────────────────────────────────────────────
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
        lines = []
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
                status = cfg.get("_status", action)
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

        self.app.set_status("Running series processing pipeline…")
        self.app.root.update()

        try:
            configs = self._get_configs()
            headers = list(self.app.csv_data["headers"])
            data    = [list(row) for row in self.app.csv_data["data"]]

            orig_rows = len(data)
            orig_cols = len(headers)

            data, headers = self._apply_duplicates(data, headers, configs[1])
            data, headers = self._apply_missing(data, headers, configs[2])
            data, headers = self._apply_outliers(data, headers, configs[3])
            data, headers = self._apply_scaling(data, headers, configs[4])
            data, headers = self._apply_encoding(data, headers, configs[5])

            self._processed_data    = data
            self._processed_headers = headers

            # Update stats
            self._before_rows.set(f"{orig_rows} rows")
            self._before_cols.set(f"{orig_cols} columns")
            self._after_rows.set(f"{len(data)} rows")
            self._after_cols.set(f"{len(headers)} columns")

            # Update preview
            self._refresh_preview(headers, data[:20])
            self._save_btn.configure(state="normal")

            self.app.set_status(
                f"Pipeline complete — {orig_rows - len(data)} rows removed, "
                f"{len(headers)} columns remaining."
            )
        except Exception as e:
            messagebox.showerror("Pipeline Error", str(e))
            self.app.set_status("Pipeline error")
            import traceback; traceback.print_exc()

    # ── Stage processors ─────────────────────────────────────────────────────

    @staticmethod
    def _apply_duplicates(data, headers, cfg):
        action = cfg.get("action", "skip")
        if action == "skip":
            return data, headers

        keep   = cfg.get("keep", "first")
        subset = cfg.get("col_subset", [])

        if action == "drop_subset" and subset:
            indices = [headers.index(c) for c in subset if c in headers]
        else:
            indices = list(range(len(headers)))

        seen    = {}
        result  = []
        for i, row in enumerate(data):
            key = tuple(row[j] for j in indices)
            if key not in seen:
                seen[key] = i
                result.append(row)
            else:
                if keep == "last":
                    result.remove(data[seen[key]])
                    seen[key] = i
                    result.append(row)
                elif keep == "none":
                    if data[seen[key]] in result:
                        result.remove(data[seen[key]])
                    # don't append current row either

        return result, headers

    @staticmethod
    def _apply_missing(data, headers, cfg):
        mode = cfg.get("global_strategy", "skip")
        if mode == "skip":
            return data, headers

        threshold = cfg.get("drop_threshold", 80)
        total     = len(data)

        # Drop high-missing columns
        keep_idxs = []
        for j, col in enumerate(headers):
            null_c = sum(1 for row in data if j >= len(row) or not row[j] or not row[j].strip())
            pct    = (null_c / total * 100) if total else 0
            if pct <= threshold:
                keep_idxs.append(j)

        data    = [[row[j] for j in keep_idxs if j < len(row)] for row in data]
        headers = [headers[j] for j in keep_idxs]

        if mode == "apply_all":
            strategy_for = {col: cfg.get("global_common", "Drop row") for col in headers}
        else:
            col_cfg      = cfg.get("column_config", {})
            strategy_for = {col: col_cfg.get(col, {}).get("strategy", "Drop row")
                            for col in headers}

        # Collect numeric column medians/means/modes for filling
        col_stats = {}
        for j, col in enumerate(headers):
            vals = []
            for row in data:
                v = row[j] if j < len(row) else ""
                if v and v.strip():
                    try:
                        vals.append(float(v))
                    except ValueError:
                        vals.append(v)
            numeric_vals = [v for v in vals if isinstance(v, float)]
            str_vals     = [v for v in vals if isinstance(v, str)]
            col_stats[col] = {
                "mean":   sum(numeric_vals) / len(numeric_vals) if numeric_vals else 0,
                "median": sorted(numeric_vals)[len(numeric_vals) // 2] if numeric_vals else 0,
                "mode":   collections.Counter(str_vals or [str(v) for v in numeric_vals]).most_common(1)[0][0]
                          if (str_vals or numeric_vals) else "",
            }

        result = []
        for row in data:
            new_row = list(row)
            drop    = False
            for j, col in enumerate(headers):
                if j >= len(new_row):
                    continue
                val = new_row[j]
                if not val or not val.strip():
                    strat = strategy_for.get(col, "Drop row")
                    fill_val = (cfg.get("column_config", {}).get(col, {}).get("fill_val")
                                if cfg.get("global_strategy") == "per_column" else None)
                    if strat == "Drop row":
                        drop = True; break
                    elif strat == "Mean":
                        new_row[j] = str(round(col_stats[col]["mean"], 4))
                    elif strat == "Median":
                        new_row[j] = str(round(col_stats[col]["median"], 4))
                    elif strat == "Mode":
                        new_row[j] = col_stats[col]["mode"]
                    elif strat == "Fill constant":
                        new_row[j] = fill_val or "0"
                    elif strat == "Forward-fill":
                        # Use last seen value in result
                        last = next(
                            (result[-k-1][j] for k in range(len(result))
                             if j < len(result[-k-1]) and result[-k-1][j]), None)
                        new_row[j] = last or ""
            if not drop:
                result.append(new_row)
        return result, headers

    @staticmethod
    def _apply_outliers(data, headers, cfg):
        treatment = cfg.get("treatment", "skip")
        if treatment == "skip":
            return data, headers

        method  = cfg.get("method", "iqr")
        iqr_m   = cfg.get("iqr_mult", 1.5)
        z_thr   = cfg.get("zscore_thr", 3.0)
        columns = cfg.get("columns", [])

        if not columns:
            return data, headers

        col_bounds = {}
        for col in columns:
            if col not in headers:
                continue
            j = headers.index(col)
            vals = []
            for row in data:
                if j < len(row) and row[j] and row[j].strip():
                    try:
                        vals.append(float(row[j]))
                    except ValueError:
                        pass
            if not vals:
                continue
            if method == "iqr":
                sv  = sorted(vals)
                n   = len(sv)
                q1  = sv[n // 4]
                q3  = sv[3 * n // 4]
                iqr = q3 - q1
                col_bounds[col] = (q1 - iqr_m * iqr, q3 + iqr_m * iqr)
            else:  # zscore
                mean = sum(vals) / len(vals)
                var  = sum((v - mean) ** 2 for v in vals) / len(vals)
                std  = var ** 0.5 or 1
                col_bounds[col] = (mean - z_thr * std, mean + z_thr * std)

        if treatment == "flag":
            extra_headers = [f"{c}_outlier" for c in col_bounds]
            headers = list(headers) + extra_headers

        result = []
        for row in data:
            new_row = list(row)
            drop    = False
            flags   = {}
            for col, (lo, hi) in col_bounds.items():
                j = headers.index(col) if col in headers else -1
                if j == -1 or j >= len(new_row):
                    flags[col] = "0"; continue
                val_str = new_row[j]
                try:
                    val = float(val_str)
                    is_out = val < lo or val > hi
                except ValueError:
                    is_out = False

                if is_out:
                    if treatment == "remove":
                        drop = True; break
                    elif treatment == "cap":
                        new_row[j] = str(round(min(max(float(new_row[j]), lo), hi), 6))
                flags[col] = "1" if is_out else "0"

            if not drop:
                if treatment == "flag":
                    new_row += [flags.get(c, "0") for c in col_bounds]
                result.append(new_row)
        return result, headers

    @staticmethod
    def _apply_scaling(data, headers, cfg):
        method  = cfg.get("method", "skip")
        if method == "skip":
            return data, headers

        columns = cfg.get("columns", [])
        if not columns:
            return data, headers

        for col in columns:
            if col not in headers:
                continue
            j    = headers.index(col)
            vals = []
            for row in data:
                if j < len(row) and row[j] and row[j].strip():
                    try:
                        vals.append(float(row[j]))
                    except ValueError:
                        pass
            if not vals:
                continue

            if method == "minmax":
                lo, hi = min(vals), max(vals)
                rng    = (hi - lo) or 1
                for row in data:
                    if j < len(row) and row[j] and row[j].strip():
                        try:
                            row[j] = str(round((float(row[j]) - lo) / rng, 6))
                        except ValueError:
                            pass
            elif method == "zscore":
                mean = sum(vals) / len(vals)
                std  = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5 or 1
                for row in data:
                    if j < len(row) and row[j] and row[j].strip():
                        try:
                            row[j] = str(round((float(row[j]) - mean) / std, 6))
                        except ValueError:
                            pass
            elif method == "robust":
                sv  = sorted(vals)
                n   = len(sv)
                med = sv[n // 2]
                q1  = sv[n // 4]
                q3  = sv[3 * n // 4]
                iqr = (q3 - q1) or 1
                for row in data:
                    if j < len(row) and row[j] and row[j].strip():
                        try:
                            row[j] = str(round((float(row[j]) - med) / iqr, 6))
                        except ValueError:
                            pass
        return data, headers

    @staticmethod
    def _apply_encoding(data, headers, cfg):
        methods      = cfg.get("column_methods", {})
        drop_orig    = cfg.get("drop_original", True)
        if not methods:
            return data, headers

        new_headers  = list(headers)
        col_insertions = []  # (original_idx, new_cols)

        for col, method in methods.items():
            if method == "Skip" or col not in new_headers:
                continue
            j = new_headers.index(col)

            if method == "Label encode":
                unique_vals = sorted(set(row[j] for row in data if j < len(row) and row[j]))
                label_map   = {v: str(i) for i, v in enumerate(unique_vals)}
                for row in data:
                    if j < len(row):
                        row[j] = label_map.get(row[j], row[j])

            elif method == "One-hot encode":
                unique_vals = sorted(set(row[j] for row in data if j < len(row) and row[j]))
                # Build extra column names
                extra_cols  = [f"{col}_{v}" for v in unique_vals]
                col_insertions.append((j, extra_cols, unique_vals, col))

        # Apply one-hot insertions in reverse order to preserve indices
        for j, extra_cols, unique_vals, col in reversed(col_insertions):
            for row in data:
                val       = row[j] if j < len(row) else ""
                ohe_flags = ["1" if val == uv else "0" for uv in unique_vals]
                if drop_orig:
                    row[j:j+1] = ohe_flags
                else:
                    row[j+1:j+1] = ohe_flags
            if drop_orig:
                new_headers[j:j+1] = extra_cols
            else:
                new_headers[j+1:j+1] = extra_cols

        return data, new_headers

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save_csv(self):
        if not self._processed_data:
            messagebox.showinfo("Nothing to save", "Run the pipeline first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Processed Data",
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
