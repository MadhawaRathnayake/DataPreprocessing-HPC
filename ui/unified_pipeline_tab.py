"""
Unified Pipeline Tab — Consolidated 7-stage pipeline with method selection.

Users can select which processing method to use:
  • Serial (single-threaded)
  • OpenMP (shared-memory parallel)
  • MPI (distributed-memory parallel)
  • CUDA (GPU acceleration)
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from base_tab import BaseTab
import theme

# Pipeline stage modules - imported dynamically based on method selection
# These imports are done dynamically in _load_stages()


_STATUS_COLORS = {
    "pending":    (theme.TEXT_MUTED, "○"),
    "configured": (theme.SUCCESS,    "✓"),
    "skipped":    (theme.WARNING,    "—"),
}

_CIRCLED = ["①", "②", "③", "④", "⑤", "⑥", "⑦"]

# Mapping of method names to their pipeline_stages subpackages
_METHOD_MODULES = {
    "Serial":  "pipeline_stages.series",
    "OpenMP":  "pipeline_stages.openmp",
    "MPI":     "pipeline_stages.mpi",
    "CUDA":    "pipeline_stages.cuda",
}


class UnifiedPipelineTab(BaseTab):
    """Unified Pipeline tab with method selection."""

    def __init__(self, parent, app_context):
        super().__init__(parent, app_context)
        self._current_stage = 0
        self._stages = []
        self._rail_btns = []
        self._current_method = tk.StringVar(value="Serial")
        self._method_selector = None
        self._method_info_label = None
        self._pipeline_container = None
        self._saved_configs = []  # Store configs when switching methods
        
        self.build_ui()

    # ── BaseTab API ──────────────────────────────────────────────────────────

    def build_ui(self):
        """Build the unified pipeline UI with method selector."""
        # Top bar: Method selector
        self._build_method_selector()
        
        # Pipeline container (will hold rail + right panel)
        self._pipeline_container = ttk.Frame(self.frame)
        self._pipeline_container.pack(fill='both', expand=True)
        self._pipeline_container.columnconfigure(1, weight=1)
        self._pipeline_container.rowconfigure(0, weight=1)
        
        # Build initial pipeline with default method
        self._load_pipeline()

    def _build_method_selector(self):
        """Build the top method selector bar."""
        selector_frame = ttk.Frame(self.frame)
        selector_frame.pack(fill='x', padx=14, pady=10)
        
        ttk.Label(selector_frame, text="Processing Method:").pack(side='left', padx=(0, 8))
        
        # Method dropdown
        self._method_selector = ttk.Combobox(
            selector_frame,
            textvariable=self._current_method,
            values=list(_METHOD_MODULES.keys()),
            state='readonly',
            width=12
        )
        self._method_selector.pack(side='left', padx=5)
        
        # Bind both events to ensure the callback is triggered
        self._method_selector.bind('<<ComboboxSelected>>', self._on_method_changed)
        
        # Also trace the StringVar for fallback
        self._current_method.trace_add('write', self._on_method_var_changed)
        
        # Info label
        self._method_info_label = ttk.Label(
            selector_frame,
            text="",
            foreground='gray',
            font=('TkDefaultFont', 9)
        )
        self._method_info_label.pack(side='left', padx=20)
        
        ttk.Separator(self.frame, orient='horizontal').pack(fill='x')
        
        self._update_method_info()

    def _update_method_info(self):
        """Update the info label based on selected method."""
        method = self._current_method.get()
        info_map = {
            "Serial": "Single-threaded processing",
            "OpenMP": "Shared-memory parallel (multi-core)",
            "MPI": "Distributed-memory parallel (multi-node)",
            "CUDA": "GPU acceleration",
        }
        self._method_info_label.config(text=info_map.get(method, ""))

    def _on_method_var_changed(self, *args):
        """Trace callback for StringVar changes (fallback for variable tracking)."""
        pass

    def _on_method_changed(self, event=None):
        """Called when user changes the processing method.
        
        NOTE: Configurations are preserved across method changes, allowing
        the same pipeline to be applied with different processing backends.
        """
        # Save current configurations before switching methods
        self._saved_configs = self._collect_configs() if self._stages else []
        
        # Load pipeline with new method
        self._load_pipeline()
        
        # Apply saved configurations
        self._apply_saved_configs()
        
        # Select and display the first stage
        self._select_stage(0)
        
        self._update_method_info()

    def _load_pipeline(self):
        """Load the pipeline stages for the selected method."""
        # Clear existing pipeline
        if self._pipeline_container.winfo_exists():
            for widget in self._pipeline_container.winfo_children():
                widget.destroy()
        
        self._stages = []
        self._rail_btns = []
        self._current_stage = 0
        
        # Rebuild pipeline container
        self._pipeline_container.columnconfigure(1, weight=1)
        self._pipeline_container.rowconfigure(0, weight=1)
        
        self._build_left_rail()
        self._build_right_panel()
        self._build_stages()
        
        # DO NOT call _select_stage here - it will be called after configs are applied
        # Just set first stage as active without triggering refresh
        self._current_stage = 0

    # ── Left rail ────────────────────────────────────────────────────────────

    def _build_left_rail(self):
        """Vertical stage navigation rail."""
        rail_outer = tk.Frame(self._pipeline_container, bg=theme.BG_ROOT, width=220)
        rail_outer.grid(row=0, column=0, sticky="nsew")
        rail_outer.grid_propagate(False)

        method = self._current_method.get()
        tk.Label(rail_outer, text=f"Pipeline Stages [{method}]",
                 bg=theme.BG_ROOT, fg=theme.TEXT_MUTED,
                 font=theme.FONT_SMALL
                 ).pack(anchor="w", padx=14, pady=(14, 6))

        tk.Frame(rail_outer, bg=theme.BORDER, height=1).pack(fill="x", padx=10)

        self._rail_container = tk.Frame(rail_outer, bg=theme.BG_ROOT)
        self._rail_container.pack(fill="both", expand=True, pady=6)

    def _build_right_panel(self):
        """Right config + navigation panel."""
        right = ttk.Frame(self._pipeline_container)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self._content = ttk.Frame(right)
        self._content.grid(row=0, column=0, sticky="nsew")
        self._content.rowconfigure(0, weight=1)
        self._content.columnconfigure(0, weight=1)

        nav = ttk.Frame(right)
        nav.grid(row=1, column=0, sticky="ew", padx=14, pady=10)

        self._back_btn = ttk.Button(nav, text="← Back", command=self._go_back)
        self._back_btn.pack(side="left", padx=(0, 8))

        self._next_btn = ttk.Button(nav, text="Next →", command=self._go_next)
        self._next_btn.pack(side="left")

        self._stage_label = ttk.Label(nav, text="", style="Muted.TLabel")
        self._stage_label.pack(side="right", padx=8)

    # ── Stage construction ────────────────────────────────────────────────────

    def _build_stages(self):
        """Load and build stage objects for the selected method."""
        method = self._current_method.get()
        module_name = _METHOD_MODULES[method]
        
        # Dynamically import stage modules
        try:
            stage_overview = __import__(f"{module_name}.stage_overview", fromlist=["StageOverview"]).StageOverview
            stage_duplicates = __import__(f"{module_name}.stage_duplicates", fromlist=["StageDuplicates"]).StageDuplicates
            stage_missing = __import__(f"{module_name}.stage_missing", fromlist=["StageMissing"]).StageMissing
            stage_outliers = __import__(f"{module_name}.stage_outliers", fromlist=["StageOutliers"]).StageOutliers
            stage_scaling = __import__(f"{module_name}.stage_scaling", fromlist=["StageScaling"]).StageScaling
            stage_encoding = __import__(f"{module_name}.stage_encoding", fromlist=["StageEncoding"]).StageEncoding
            stage_apply = __import__(f"{module_name}.stage_apply", fromlist=["StageApply"]).StageApply
        except ImportError as e:
            messagebox.showerror("Error", f"Failed to load {method} pipeline stages: {str(e)}")
            return

        stage_classes = [
            stage_overview,
            stage_duplicates,
            stage_missing,
            stage_outliers,
            stage_scaling,
            stage_encoding,
        ]

        for idx, cls in enumerate(stage_classes):
            obj = cls(self._content, self.app)
            self._stages.append(obj)

        apply_stage = stage_apply(self._content, self.app, self._collect_configs)
        self._stages.append(apply_stage)

        for stage in self._stages:
            stage.get_frame().grid(row=0, column=0, sticky="nsew")

        for idx, stage in enumerate(self._stages):
            self._build_rail_btn(idx, stage.LABEL)
    
    # ── Configuration application after loading ──────────────────────────────
    
    def _apply_saved_configs(self):
        """Apply saved configurations to newly created stages.
        
        Store configs on the stage objects so they can be applied
        AFTER refresh() populates the stage's data structures.
        """
        if not self._saved_configs:
            return
        
        # Store configs on stage objects for later application
        for idx, stage in enumerate(self._stages[:-1]):  # Exclude Apply stage
            if idx < len(self._saved_configs):
                config = self._saved_configs[idx]
                if config:
                    stage._saved_config_to_apply = config
        
        # Clear the saved configs list  
        self._saved_configs = []
    
    def _apply_config_to_stage(self, stage, config):
        """Directly apply configuration dictionary to a stage.
        
        This sets the internal tk variables directly without using getters.
        Used AFTER refresh() has been called.
        """
        if not config:
            return
        
        try:
            # Map config keys directly to internal variables
            if 'action' in config and hasattr(stage, '_action'):
                stage._action.set(config['action'])
            
            if 'keep' in config and hasattr(stage, '_keep'):
                stage._keep.set(config['keep'])
            
            if 'missing_action' in config and hasattr(stage, '_missing_action'):
                stage._missing_action.set(config['missing_action'])
            
            if 'missing_threshold' in config and hasattr(stage, '_missing_threshold'):
                stage._missing_threshold.set(config['missing_threshold'])
            
            if 'outlier_action' in config and hasattr(stage, '_outlier_action'):
                stage._outlier_action.set(config['outlier_action'])
            
            if 'outlier_threshold' in config and hasattr(stage, '_outlier_threshold'):
                stage._outlier_threshold.set(config['outlier_threshold'])
            
            if 'scaling_method' in config and hasattr(stage, '_scaling_method'):
                stage._scaling_method.set(config['scaling_method'])
            
            if 'encoding_method' in config and hasattr(stage, '_encoding_method'):
                stage._encoding_method.set(config['encoding_method'])
            
            # Handle column subset (list of column names to keep checked)
            if 'col_subset' in config and hasattr(stage, '_col_vars'):
                col_subset = config['col_subset']
                col_vars = stage._col_vars
                
                # Uncheck all first
                for col_name, var in col_vars.items():
                    try:
                        var.set(False)
                    except Exception:
                        pass
                
                # Check the saved ones
                for col_name in col_subset:
                    if col_name in col_vars:
                        try:
                            col_vars[col_name].set(True)
                        except Exception:
                            pass
            
            # Trigger action change to update UI after restoration
            if hasattr(stage, '_on_action_change'):
                try:
                    stage._on_action_change()
                except Exception:
                    pass
        
        except Exception:
            pass
    
    def _apply_config_to_stage_after_refresh(self, stage, config):
        """Apply saved configuration to a stage AFTER refresh() has been called.
        
        At this point, all the stage's internal data structures are populated,
        so we can safely restore the full configuration.
        """
        if not config:
            return
        
        try:
            # Try to use a set_config() method if the stage has one
            if hasattr(stage, 'set_config') and callable(stage.set_config):
                try:
                    stage.set_config(config)
                    return
                except Exception:
                    pass
            
            # Fallback: manually set all variables/attributes from config
            for config_key, config_value in config.items():
                var_name = f'_{config_key}'
                
                if hasattr(stage, var_name):
                    attr = getattr(stage, var_name)
                    
                    try:
                        # Case 1: tk variable
                        if hasattr(attr, 'set'):
                            attr.set(config_value)
                        # Case 2: plain Python attribute (list, dict, etc.)
                        else:
                            setattr(stage, var_name, config_value)
                    except Exception:
                        pass
            
            # Trigger UI updates if stage has a refresh method for callbacks
            if hasattr(stage, '_on_action_change') and callable(stage._on_action_change):
                try:
                    stage._on_action_change()
                except Exception:
                    pass
            
        except Exception:
            pass

    def _apply_config_to_stage_direct(self, stage, config):
        """Apply config to stage BEFORE refresh() is called.
        
        This sets the tk variables so that when refresh() creates the UI,
        the values are already correct. This is crucial for persistence!
        
        Handles BOTH simple tk variables and complex config values (lists, dicts).
        """
        if not config:
            return
        
        try:
            # Strategy 1: Try to use a set_config() method if the stage has one
            if hasattr(stage, 'set_config') and callable(stage.set_config):
                try:
                    stage.set_config(config)
                    return
                except Exception:
                    pass
            
            # Strategy 2: Dynamically apply any matching variables or attributes
            for config_key, config_value in config.items():
                var_name = f'_{config_key}'
                
                # Try to find and set the variable/attribute
                if hasattr(stage, var_name):
                    attr = getattr(stage, var_name)
                    
                    # Case 1: It's a tk variable (has .set() method)
                    if hasattr(attr, 'set'):
                        try:
                            attr.set(config_value)
                        except Exception:
                            pass
                    
                    # Case 2: It's a plain Python list or dict (for complex config)
                    elif isinstance(config_value, (list, dict)):
                        try:
                            setattr(stage, var_name, config_value)
                        except Exception:
                            pass
                    
                    # Case 3: Unknown type, try to set it anyway
                    else:
                        try:
                            setattr(stage, var_name, config_value)
                        except Exception:
                            pass
            
        except Exception:
            pass

    def _build_rail_btn(self, idx, label):
        """Build a single stage rail button."""
        btn_frame = tk.Frame(self._rail_container, bg=theme.BG_ROOT, cursor="hand2")
        btn_frame.pack(fill="x", padx=6, pady=2)
        btn_frame.bind("<Button-1>", lambda _e, i=idx: self._select_stage(i))

        badge = tk.Label(btn_frame, text=_CIRCLED[idx],
                         bg=theme.BG_ROOT, fg=theme.ACCENT,
                         font=(theme.FONT[0], 12, "bold"), width=3)
        badge.pack(side="left")
        badge.bind("<Button-1>", lambda _e, i=idx: self._select_stage(i))

        name_lbl = tk.Label(btn_frame, text=label,
                            bg=theme.BG_ROOT, fg=theme.TEXT,
                            font=theme.FONT, anchor="w")
        name_lbl.pack(side="left", fill="x", expand=True)
        name_lbl.bind("<Button-1>", lambda _e, i=idx: self._select_stage(i))

        self._rail_btns.append((btn_frame, badge, name_lbl))

    # ── Stage navigation ─────────────────────────────────────────────────────

    def _select_stage(self, idx, skip_refresh=False):
        """Select stage by index.
        
        Parameters
        ----------
        idx : int
            Stage index to select
        skip_refresh : bool
            If True, skip calling refresh() on the stage.
            NORMALLY THIS SHOULD BE FALSE to ensure stage data is current.
        """
        if not (0 <= idx < len(self._stages)):
            return

        old_idx = self._current_stage
        self._current_stage = idx

        # Update rail buttons
        self._refresh_rail()

        # Update content
        stage = self._stages[idx]
        stage.get_frame().tkraise()

        # Update nav buttons and label
        self._back_btn.config(state='normal' if idx > 0 else 'disabled')
        self._next_btn.config(state='normal' if idx < len(self._stages) - 1 else 'disabled')
        
        label = f"{_CIRCLED[idx]} {stage.LABEL}"
        self._stage_label.config(text=label)

        # ALWAYS refresh the visible stage to ensure data is current
        if not skip_refresh:
            if hasattr(stage, "refresh"):
                stage.refresh()
                
                # AFTER refresh, apply any saved config
                if hasattr(stage, '_saved_config_to_apply'):
                    config = stage._saved_config_to_apply
                    self._apply_config_to_stage_after_refresh(stage, config)
                    delattr(stage, '_saved_config_to_apply')

    def _refresh_rail(self):
        """Update rail button states based on stage configuration."""
        for idx, (btn_frame, badge, name_lbl) in enumerate(self._rail_btns):
            stage = self._stages[idx]
            status = getattr(stage, "get_status", lambda: "pending")()
            
            if status in _STATUS_COLORS:
                color, symbol = _STATUS_COLORS[status]
                badge.config(text=symbol, fg=color)

            if idx == self._current_stage:
                btn_frame.config(bg=theme.BG_CARD)
                name_lbl.config(fg=theme.ACCENT)
            else:
                btn_frame.config(bg=theme.BG_ROOT)
                name_lbl.config(fg=theme.TEXT)

    def _go_back(self):
        """Navigate to previous stage."""
        if self._current_stage > 0:
            self._select_stage(self._current_stage - 1)

    def _go_next(self):
        """Navigate to next stage."""
        if self._current_stage < len(self._stages) - 1:
            self._select_stage(self._current_stage + 1)

    # ── Stage configuration restoration ──────────────────────────────────────

    def _restore_stage_config(self, stage, config):
        """Restore configuration to a stage object.
        
        Attempts to restore internal variables and state based on saved config.
        This works because all method variants (serial/openmp/mpi/cuda) use
        the same internal variable names and structure.
        """
        if not config or not hasattr(stage, '__dict__'):
            return
        
        try:
            # Restore simple variables first
            simple_mappings = {
                'action': '_action',
                'keep': '_keep',
                'missing_action': '_missing_action',
                'missing_threshold': '_missing_threshold',
                'outlier_action': '_outlier_action',
                'outlier_threshold': '_outlier_threshold',
                'scaling_method': '_scaling_method',
                'encoding_method': '_encoding_method',
            }
            
            for config_key, var_name in simple_mappings.items():
                if config_key not in config:
                    continue
                if not hasattr(stage, var_name):
                    continue
                
                stage_var = getattr(stage, var_name)
                config_value = config[config_key]
                
                if hasattr(stage_var, 'set'):
                    try:
                        stage_var.set(config_value)
                    except Exception:
                        pass
            
            # Restore column selections after simple vars are set
            if 'col_subset' in config and hasattr(stage, '_col_vars'):
                col_subset = config['col_subset']
                col_vars = stage._col_vars
                
                # Uncheck all first
                for col_name, var in col_vars.items():
                    if hasattr(var, 'set'):
                        try:
                            var.set(False)
                        except Exception:
                            pass
                
                # Check selected ones
                for col_name in col_subset:
                    if col_name in col_vars and hasattr(col_vars[col_name], 'set'):
                        try:
                            col_vars[col_name].set(True)
                        except Exception:
                            pass
        
        except Exception:
            pass
    
    # ── Configuration collection ─────────────────────────────────────────────

    def _collect_configs(self):
        """Collect all stage configurations as a list.
        
        Returns a list where index corresponds to stage number:
        [0]=Overview, [1]=Duplicates, [2]=Missing, [3]=Outliers, [4]=Scaling, [5]=Encoding
        
        Compatible with preprocess.py which expects configs[1], configs[3], etc.
        """
        configs = []
        for stage in self._stages[:-1]:  # Exclude Apply stage
            if hasattr(stage, "get_config"):
                configs.append(stage.get_config())
            else:
                configs.append({})
        return configs

    # ── BaseTab lifecycle ────────────────────────────────────────────────────

    def on_tab_selected(self):
        """Called every time the tab becomes active."""
        if self.app.csv_data:
            method = self._current_method.get()
            self.app.set_status(f"{method} Processing — configure stages, then Run Pipeline")
            if self._stages and self._current_stage < len(self._stages):
                stage = self._stages[self._current_stage]
                if hasattr(stage, "refresh"):
                    stage.refresh()
                self._refresh_rail()
        else:
            self.app.set_status("Pipeline — import a dataset first")
