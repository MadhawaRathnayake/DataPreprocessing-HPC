import os
import re

backends = ['series', 'openmp', 'mpi', 'cuda']
stages = ['duplicates', 'missing', 'outliers', 'scaling', 'encoding']

def update_duplicates(content):
    # set_config
    if 'def set_config' not in content:
        content = content.replace(
            'def refresh(self):',
            'def refresh(self):\n        self._rebuild_col_list()\n        self._on_action_change()\n\n    def set_config(self, config):\n        if not config:\n            return\n        if "action" in config:\n            self._action.set(config["action"])\n        if "keep" in config:\n            self._keep.set(config["keep"])\n        if "col_subset" in config:\n            self._selected_columns_to_restore = config["col_subset"]\n            for col in config["col_subset"]:\n                if col in self._col_vars:\n                    self._col_vars[col].set(True)\n            for col, var in self._col_vars.items():\n                if col not in config["col_subset"]:\n                    var.set(False)'
        )
        # Remove duplicate refresh
        content = content.replace(
            'def refresh(self):\n        """Rebuild column checklist when dataset changes."""\n        self._rebuild_col_list()\n        self._on_action_change()',
            ''
        )
        # Cleanup extra newlines if needed
        content = re.sub(r'\n\s+def refresh\(self\):\n\s+self\._rebuild_col_list\(\)\n\s+self\._on_action_change\(\)\n+', '\n    def refresh(self):\n        self._rebuild_col_list()\n        self._on_action_change()\n\n', content)

    # _rebuild_col_list
    new_rebuild = """    def _rebuild_col_list(self):
        # Save old selections
        old_selections = {col: var.get() for col, var in self._col_vars.items()}
        
        # Check for restore list from set_config
        restore_list = None
        if hasattr(self, "_selected_columns_to_restore"):
            restore_list = self._selected_columns_to_restore
            delattr(self, "_selected_columns_to_restore")

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
            if restore_list is not None:
                val = (col in restore_list)
            else:
                val = old_selections.get(col, False)
            
            var = tk.BooleanVar(value=val)
            self._col_vars[col] = var
            row, col_pos = divmod(idx, 3)
            cb = ttk.Checkbutton(self._col_check_frame, text=col, variable=var)
            cb.grid(row=row, column=col_pos, sticky="w", padx=8, pady=2)"""
    
    content = re.sub(r'    def _rebuild_col_list\(self\):.*?cb\.grid\(row=row, column=col_pos, sticky="w", padx=8, pady=2\)', new_rebuild, content, flags=re.DOTALL)
    return content

def update_missing(content):
    # set_config
    if 'def set_config' not in content:
        content = content.replace(
            'def refresh(self):',
            'def refresh(self):\n        self._rebuild_col_table()\n        self._on_global_change()\n\n    def set_config(self, config):\n        if not config:\n            return\n        if "global_strategy" in config:\n            self._global_strategy.set(config["global_strategy"])\n        if "global_common" in config:\n            self._global_common.set(config["global_common"])\n        if "drop_threshold" in config:\n            self._threshold_var.set(config["drop_threshold"])\n            self._on_threshold_move()\n        if "column_config" in config:\n            self._selected_columns_to_restore = config["column_config"]\n            for col, cfg in config["column_config"].items():\n                if col in self._col_rows:\n                    self._col_rows[col]["strategy"].set(cfg.get("strategy", STRATEGY_DROP))\n                    self._col_rows[col]["fill"].set(cfg.get("fill_val", ""))'
        )
        content = content.replace(
            'def refresh(self):\n        self._rebuild_col_table()\n        self._on_global_change()',
            ''
        )
        content = re.sub(r'\n\s+def refresh\(self\):\n\s+self\._rebuild_col_table\(\)\n\s+self\._on_global_change\(\)\n+', '\n    def refresh(self):\n        self._rebuild_col_table()\n        self._on_global_change()\n\n', content)

    # _rebuild_col_table
    new_rebuild = """    def _rebuild_col_table(self):
        # Save old selections
        old_selections = {}
        for col, widgets in self._col_rows.items():
            old_selections[col] = {
                "strategy": widgets["strategy"].get(),
                "fill": widgets["fill"].get()
            }
        
        # Check for restore list from set_config
        restore_map = None
        if hasattr(self, "_selected_columns_to_restore"):
            restore_map = self._selected_columns_to_restore
            delattr(self, "_selected_columns_to_restore")

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

            if restore_map is not None and col in restore_map:
                s_val = restore_map[col].get("strategy", STRATEGY_DROP)
                f_val = restore_map[col].get("fill_val", "")
            elif col in old_selections:
                s_val = old_selections[col]["strategy"]
                f_val = old_selections[col]["fill"]
            else:
                s_val = STRATEGY_DROP
                f_val = ""

            strat_var = tk.StringVar(value=s_val)
            fill_var  = tk.StringVar(value=f_val)

            ttk.Label(row_frame, text=col, width=22).pack(side="left")
            combo = ttk.Combobox(row_frame, textvariable=strat_var,
                                 values=_STRATEGIES, state="readonly", width=16)
            combo.pack(side="left", padx=4)

            fill_entry = ttk.Entry(row_frame, textvariable=fill_var, width=14)
            fill_entry.pack(side="left", padx=4)

            # Show/hide fill entry
            def make_toggle(v, e):
                def _toggle(*_):
                    e.configure(state="normal" if v.get() == STRATEGY_CONST else "disabled")
                return _toggle

            toggle_func = make_toggle(strat_var, fill_entry)
            strat_var.trace_add("write", toggle_func)
            toggle_func()

            self._col_rows[col] = {"strategy": strat_var, "fill": fill_var}"""

    content = re.sub(r'    def _rebuild_col_table\(self\):.*?self\._col_rows\[col\] = \{"strategy": strat_var, "fill": fill_var\}', new_rebuild, content, flags=re.DOTALL)
    return content

def update_outliers(content):
    # set_config
    if 'def set_config' not in content:
        content = content.replace(
            'def refresh(self):',
            'def refresh(self):\n        self._rebuild_col_list()\n        self._on_method_change()\n\n    def set_config(self, config):\n        if not config:\n            return\n        if "method" in config:\n            self._method.set(config["method"])\n        if "zscore_thr" in config:\n            self._zscore_thr.set(config["zscore_thr"])\n        if "iqr_mult" in config:\n            self._iqr_mult.set(config["iqr_mult"])\n        if "treatment" in config:\n            self._treatment.set(config["treatment"])\n        if "columns" in config:\n            self._selected_columns_to_restore = config["columns"]\n            for col in config["columns"]:\n                if col in self._col_vars:\n                    self._col_vars[col].set(True)\n            for col, var in self._col_vars.items():\n                if col not in config["columns"]:\n                    var.set(False)'
        )
        content = content.replace(
            'def refresh(self):\n        self._rebuild_col_list()\n        self._on_method_change()',
            ''
        )
        content = re.sub(r'\n\s+def refresh\(self\):\n\s+self\._rebuild_col_list\(\)\n\s+self\._on_method_change\(\)\n+', '\n    def refresh(self):\n        self._rebuild_col_list()\n        self._on_method_change()\n\n', content)

    # _rebuild_col_list
    new_rebuild = """    def _rebuild_col_list(self):
        # Save old selections
        old_selections = {col: var.get() for col, var in self._col_vars.items()}
        
        # Check for restore list from set_config
        restore_list = None
        if hasattr(self, "_selected_columns_to_restore"):
            restore_list = self._selected_columns_to_restore
            delattr(self, "_selected_columns_to_restore")

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
            if restore_list is not None:
                val = (col in restore_list)
            else:
                val = old_selections.get(col, True)
            
            var = tk.BooleanVar(value=val)
            self._col_vars[col] = var
            r, c = divmod(idx, 3)
            ttk.Checkbutton(self._col_inner, text=col, variable=var
                            ).grid(row=r, column=c, sticky="w", padx=8, pady=2)"""
    
    content = re.sub(r'    def _rebuild_col_list\(self\):.*?ttk\.Checkbutton\(self\._col_inner, text=col, variable=var\n\s+\)\.grid\(row=r, column=c, sticky="w", padx=8, pady=2\)', new_rebuild, content, flags=re.DOTALL)
    return content

def update_scaling(content):
    # set_config
    if 'def set_config' not in content:
        content = content.replace(
            'def refresh(self):',
            'def refresh(self):\n        self._rebuild_col_list()\n\n    def set_config(self, config):\n        if not config:\n            return\n        if "method" in config:\n            self._method.set(config["method"])\n        if "columns" in config:\n            self._selected_columns_to_restore = config["columns"]\n            for col in config["columns"]:\n                if col in self._col_vars:\n                    self._col_vars[col].set(True)\n            for col, var in self._col_vars.items():\n                if col not in config["columns"]:\n                    var.set(False)'
        )
        content = content.replace(
            'def refresh(self):\n        self._rebuild_col_list()',
            ''
        )
        content = re.sub(r'\n\s+def refresh\(self\):\n\s+self\._rebuild_col_list\(\)\n+', '\n    def refresh(self):\n        self._rebuild_col_list()\n\n', content)
    else:
        # Update existing set_config to match pattern if needed
        pass

    # _rebuild_col_list
    new_rebuild = """    def _rebuild_col_list(self):
        # Save old selections
        old_selections = {col: var.get() for col, var in self._col_vars.items()}
        
        # Check for restore list from set_config
        restore_list = None
        if hasattr(self, "_selected_columns_to_restore"):
            restore_list = self._selected_columns_to_restore
            delattr(self, "_selected_columns_to_restore")

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
            if restore_list is not None:
                val = (col in restore_list)
            else:
                val = old_selections.get(col, True)
            
            var = tk.BooleanVar(value=val)
            self._col_vars[col] = var
            r, c = divmod(idx, 3)
            ttk.Checkbutton(self._col_inner, text=col, variable=var
                            ).grid(row=r, column=c, sticky="w", padx=8, pady=2)"""

    content = re.sub(r'    def _rebuild_col_list\(self\):.*?ttk\.Checkbutton\(self\._col_inner, text=col, variable=var\n\s+\)\.grid\(row=r, column=c, sticky="w", padx=8, pady=2\)', new_rebuild, content, flags=re.DOTALL)
    # Also handle the slightly different version in series/stage_scaling.py
    content = re.sub(r'    def _rebuild_col_list\(self\):.*?ttk\.Checkbutton\(self\._col_inner, text=col, variable=var\s+\)\.grid\(row=r, column=c, sticky="w", padx=8, pady=2\)', new_rebuild, content, flags=re.DOTALL)
    
    return content

def update_encoding(content):
    # set_config
    if 'def set_config' not in content:
        content = content.replace(
            'def refresh(self):',
            'def refresh(self):\n        self._rebuild_col_table()\n\n    def set_config(self, config):\n        if not config:\n            return\n        if "drop_original" in config:\n            self._drop_original.set(config["drop_original"])\n        if "column_methods" in config:\n            self._selected_columns_to_restore = config["column_methods"]\n            for col, method in config["column_methods"].items():\n                if col in self._col_rows:\n                    self._col_rows[col].set(method)'
        )
        content = content.replace(
            'def refresh(self):\n        self._rebuild_col_table()',
            ''
        )
        content = re.sub(r'\n\s+def refresh\(self\):\n\s+self\._rebuild_col_table\(\)\n+', '\n    def refresh(self):\n        self._rebuild_col_table()\n\n', content)

    # _rebuild_col_table
    new_rebuild = """    def _rebuild_col_table(self):
        # Save old selections
        old_selections = {col: var.get() for col, var in self._col_rows.items()}
        
        # Check for restore list from set_config
        restore_map = None
        if hasattr(self, "_selected_columns_to_restore"):
            restore_map = self._selected_columns_to_restore
            delattr(self, "_selected_columns_to_restore")

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

            if restore_map is not None and col in restore_map:
                val = restore_map[col]
            else:
                val = old_selections.get(col, "Label encode")
            
            method_var = tk.StringVar(value=val)
            self._col_rows[col] = method_var

            ttk.Label(row_frame, text=col, width=24).pack(side="left")
            ttk.Combobox(row_frame, textvariable=method_var,
                         values=_METHODS, state="readonly", width=16
                         ).pack(side="left", padx=4)
            ttk.Label(row_frame, text=f"{unique_count} unique",
                      style="Muted.TLabel").pack(side="left", padx=8)"""

    content = re.sub(r'    def _rebuild_col_table\(self\):.*?ttk\.Label\(row_frame, text=f"\{unique_count\} unique",\n\s+style="Muted.TLabel"\)\.pack\(side="left", padx=8\)', new_rebuild, content, flags=re.DOTALL)
    return content

update_map = {
    'duplicates': update_duplicates,
    'missing': update_missing,
    'outliers': update_outliers,
    'scaling': update_scaling,
    'encoding': update_encoding
}

for b in backends:
    for s in stages:
        path = f'ui/pipeline_stages/{b}/stage_{s}.py'
        if os.path.exists(path):
            print(f'Updating {path}...')
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content = update_map[s](content)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
