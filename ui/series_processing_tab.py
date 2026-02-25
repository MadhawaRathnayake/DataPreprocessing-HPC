"""
Series Processing Tab — 7-stage milstone pipeline (serial / single-threaded).

Layout:
  ┌──────────────┬──────────────────────────────────────────┐
  │  STAGE RAIL  │  CONFIGURATION PANEL                     │
  │  (left ~28%) │  (right ~72%)                            │
  │              │                                          │
  │  ① Overview  │  [ Stage title & widgets ]               │
  │  ② Dupes     │                                          │
  │  ③ Missing   │                                          │
  │  ④ Outliers  │  ┌─────────────┐  ┌────────────────┐     │
  │  ⑤ Scale     │  │  ← Back     │  │   Next →       │     │
  │  ⑥ Encode    │  └─────────────┘  └────────────────┘     │
  │  ⑦ Apply     │                                          │
  └──────────────┴──────────────────────────────────────────┘
"""

import tkinter as tk
from tkinter import ttk
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from base_tab import BaseTab
import theme

# Pipeline stage modules (Series / serial processing sub-package)
from pipeline_stages.series.stage_overview   import StageOverview
from pipeline_stages.series.stage_duplicates import StageDuplicates
from pipeline_stages.series.stage_missing    import StageMissing
from pipeline_stages.series.stage_outliers   import StageOutliers
from pipeline_stages.series.stage_scaling    import StageScaling
from pipeline_stages.series.stage_encoding   import StageEncoding
from pipeline_stages.series.stage_apply      import StageApply


# Status badge colours
_STATUS_COLORS = {
    "pending":    (theme.TEXT_MUTED, "○"),
    "configured": (theme.SUCCESS,    "✓"),
    "skipped":    (theme.WARNING,    "—"),
}

_CIRCLED = ["①", "②", "③", "④", "⑤", "⑥", "⑦"]


class SeriesProcessingTab(BaseTab):
    """Series Processing tab — stepper/milestone pipeline UI."""

    def __init__(self, parent, app_context):
        super().__init__(parent, app_context)
        self._current_stage = 0
        self._stages        = []       # list of stage objects in order
        self._rail_btns     = []       # list of stage rail button frames
        self.build_ui()

    # ── BaseTab API ──────────────────────────────────────────────────────────

    def build_ui(self):
        self.frame.columnconfigure(1, weight=1)
        self.frame.rowconfigure(0, weight=1)

        self._build_left_rail()
        self._build_right_panel()
        self._build_stages()
        self._select_stage(0)

    def on_tab_selected(self):
        """Called every time the tab becomes active."""
        if self.app.csv_data:
            self.app.set_status("Series Processing — configure stages, then Run Pipeline")
            # Refresh active stage with fresh column lists
            stage = self._stages[self._current_stage]
            if hasattr(stage, "refresh"):
                stage.refresh()
            self._refresh_rail()
        else:
            self.app.set_status("Series Processing — import a dataset first")

    # ── Left rail ────────────────────────────────────────────────────────────

    def _build_left_rail(self):
        """Vertical stage navigation rail."""
        rail_outer = tk.Frame(self.frame, bg=theme.BG_ROOT, width=220)
        rail_outer.grid(row=0, column=0, sticky="nsew")
        rail_outer.grid_propagate(False)

        # Title strip
        tk.Label(rail_outer, text="Pipeline Stages",
                 bg=theme.BG_ROOT, fg=theme.TEXT_MUTED,
                 font=theme.FONT_SMALL
                 ).pack(anchor="w", padx=14, pady=(14, 6))

        tk.Frame(rail_outer, bg=theme.BORDER, height=1).pack(fill="x", padx=10)

        self._rail_container = tk.Frame(rail_outer, bg=theme.BG_ROOT)
        self._rail_container.pack(fill="both", expand=True, pady=6)

    def _build_right_panel(self):
        """Right config + navigation panel."""
        right = ttk.Frame(self.frame)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        # Content area — stages stack here
        self._content = ttk.Frame(right)
        self._content.grid(row=0, column=0, sticky="nsew")
        self._content.rowconfigure(0, weight=1)
        self._content.columnconfigure(0, weight=1)

        # Navigation buttons
        nav = ttk.Frame(right)
        nav.grid(row=1, column=0, sticky="ew", padx=14, pady=10)

        self._back_btn = ttk.Button(nav, text="← Back",  command=self._go_back)
        self._back_btn.pack(side="left", padx=(0, 8))

        self._next_btn = ttk.Button(nav, text="Next →",  command=self._go_next)
        self._next_btn.pack(side="left")

        self._stage_label = ttk.Label(nav, text="", style="Muted.TLabel")
        self._stage_label.pack(side="right", padx=8)

    # ── Stage construction ────────────────────────────────────────────────────

    def _build_stages(self):
        """Instantiate all 7 stages and build their rail buttons."""
        stage_classes = [
            StageOverview,
            StageDuplicates,
            StageMissing,
            StageOutliers,
            StageScaling,
            StageEncoding,
        ]

        for cls in stage_classes:
            obj = cls(self._content, self.app)
            self._stages.append(obj)

        # Stage 7 (Apply) needs a callback to collect configs from stages 1-6
        apply_stage = StageApply(self._content, self.app, self._collect_configs)
        self._stages.append(apply_stage)

        # Grid all stage frames in the same cell; only one visible at a time
        for stage in self._stages:
            stage.get_frame().grid(row=0, column=0, sticky="nsew")

        # Build rail buttons
        for idx, stage in enumerate(self._stages):
            self._build_rail_btn(idx, stage.LABEL)

    def _build_rail_btn(self, idx, label):
        """One clickable stage item in the rail."""
        btn_frame = tk.Frame(self._rail_container, bg=theme.BG_ROOT,
                             cursor="hand2")
        btn_frame.pack(fill="x", padx=6, pady=2)
        btn_frame.bind("<Button-1>", lambda _e, i=idx: self._select_stage(i))

        # Number badge
        badge = tk.Label(btn_frame, text=_CIRCLED[idx],
                         bg=theme.BG_ROOT, fg=theme.ACCENT,
                         font=(theme.FONT[0], 12, "bold"),
                         width=3)
        badge.pack(side="left")
        badge.bind("<Button-1>", lambda _e, i=idx: self._select_stage(i))

        # Stage name
        name_lbl = tk.Label(btn_frame, text=label,
                            bg=theme.BG_ROOT, fg=theme.TEXT,
                            font=theme.FONT, anchor="w")
        name_lbl.pack(side="left", fill="x", expand=True)
        name_lbl.bind("<Button-1>", lambda _e, i=idx: self._select_stage(i))

        # Status icon
        status_lbl = tk.Label(btn_frame, text="○",
                              bg=theme.BG_ROOT, fg=theme.TEXT_MUTED,
                              font=theme.FONT, width=2)
        status_lbl.pack(side="right", padx=4)
        status_lbl.bind("<Button-1>", lambda _e, i=idx: self._select_stage(i))

        self._rail_btns.append({
            "frame":  btn_frame,
            "badge":  badge,
            "name":   name_lbl,
            "status": status_lbl,
        })

    # ── Stage navigation ──────────────────────────────────────────────────────

    def _select_stage(self, idx):
        """Switch to the specified stage."""
        if idx < 0 or idx >= len(self._stages):
            return

        # Highlight new, de-highlight old
        self._set_rail_active(self._current_stage, active=False)
        self._current_stage = idx
        self._set_rail_active(idx, active=True)

        # Raise the correct frame to the top
        self._stages[idx].get_frame().tkraise()

        # Refresh stage content from current data
        stage = self._stages[idx]
        if hasattr(stage, "refresh"):
            stage.refresh()

        # Update nav buttons
        self._back_btn.configure(state="normal" if idx > 0            else "disabled")
        self._next_btn.configure(state="normal" if idx < len(self._stages) - 1 else "disabled")
        self._stage_label.configure(
            text=f"Stage {idx + 1} of {len(self._stages)}")

        self._refresh_rail()

    def _go_back(self):
        self._select_stage(self._current_stage - 1)

    def _go_next(self):
        self._select_stage(self._current_stage + 1)

    def _set_rail_active(self, idx, active):
        btn = self._rail_btns[idx]
        bg  = theme.ACCENT_LT if active else theme.BG_ROOT
        fg  = theme.ACCENT     if active else theme.TEXT
        btn["frame"].configure(bg=bg)
        btn["badge"].configure(bg=bg, fg=theme.ACCENT)
        btn["name"].configure(bg=bg, fg=fg,
                              font=(theme.FONT[0], theme.FONT[1],
                                    "bold" if active else "normal"))
        btn["status"].configure(bg=bg)

    def _refresh_rail(self):
        """Update status icons for all stages."""
        for idx, stage in enumerate(self._stages):
            status = stage.get_status() if hasattr(stage, "get_status") else "pending"
            color, icon = _STATUS_COLORS.get(status, _STATUS_COLORS["pending"])
            self._rail_btns[idx]["status"].configure(text=icon, fg=color)

    # ── Config collection (for Apply stage) ──────────────────────────────────

    def _collect_configs(self):
        """Return list of config dicts for stages 0-5 (stage 7 itself excluded)."""
        return [s.get_config() for s in self._stages[:-1]]
