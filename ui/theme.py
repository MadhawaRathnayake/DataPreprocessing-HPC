"""
theme.py - Light & Minimal Theme for the HPC Data Preprocessing Application

To switch themes in the future, simply replace this file with another
theme file that exports the same constants and the apply() function.
"""

import tkinter as tk
from tkinter import ttk

# ── Colour Palette (Light / Clean) ───────────────────────────────────────────
BG_ROOT   = "#f0f2f5"   # app-level background (window chrome area)
BG_FRAME  = "#f8f9fb"   # general frame / tab body
BG_CARD   = "#ffffff"   # LabelFrame card / panel backgrounds
BG_INPUT  = "#ffffff"   # input fields, Treeview, ScrolledText

ACCENT    = "#2563eb"   # primary accent — clean blue
ACCENT_DK = "#1d4ed8"   # hover / pressed state
ACCENT_LT = "#dbeafe"   # light accent tint (selected row highlight)
HIGHLIGHT = "#1e40af"   # heading labels — deeper blue
TEXT      = "#1e293b"   # primary text — near-black slate
TEXT_MUTED = "#64748b"  # secondary / placeholder text — medium slate
SUCCESS   = "#16a34a"   # success green
WARNING   = "#d97706"   # warning amber
BORDER    = "#e2e8f0"   # subtle borders — very light slate

# ── Typography ────────────────────────────────────────────────────────────────
FONT       = ("Segoe UI", 10)
FONT_BOLD  = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 11, "bold")
FONT_LARGE = ("Segoe UI", 14, "bold")
FONT_SMALL = ("Segoe UI",  9)
FONT_MONO  = ("Consolas",  10)

# ── Direct config for tk.Text / ScrolledText ─────────────────────────────────
TEXT_WIDGET_CFG = {
    "bg":               BG_INPUT,
    "fg":               TEXT,
    "insertbackground": ACCENT,
    "selectbackground": ACCENT_LT,
    "selectforeground": TEXT,
    "font":             FONT_MONO,
    "relief":           "flat",
    "borderwidth":      0,
    "padx":             10,
    "pady":             8,
}


def apply(root: tk.Tk) -> ttk.Style:
    """Apply the light minimal theme.  Call BEFORE creating any widgets."""
    root.configure(bg=BG_ROOT)

    style = ttk.Style(root)
    style.theme_use("clam")

    # ── Global defaults ───────────────────────────────────────────────────────
    style.configure(".",
        background=BG_FRAME,
        foreground=TEXT,
        fieldbackground=BG_INPUT,
        troughcolor=BORDER,
        selectbackground=ACCENT_LT,
        selectforeground=TEXT,
        relief="flat",
        font=FONT,
        borderwidth=0,
        highlightthickness=0,
    )

    # ── TFrame ────────────────────────────────────────────────────────────────
    style.configure("TFrame", background=BG_FRAME)

    # ── TLabel ────────────────────────────────────────────────────────────────
    style.configure("TLabel",
        background=BG_FRAME, foreground=TEXT, font=FONT)
    style.configure("Muted.TLabel",
        background=BG_FRAME, foreground=TEXT_MUTED, font=FONT_SMALL)

    # ── TLabelFrame ───────────────────────────────────────────────────────────
    style.configure("TLabelframe",
        background=BG_CARD,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        relief="groove",
        borderwidth=1,
    )
    style.configure("TLabelframe.Label",
        background=BG_CARD,
        foreground=HIGHLIGHT,
        font=FONT_BOLD,
    )

    # ── TButton ───────────────────────────────────────────────────────────────
    style.configure("TButton",
        background=ACCENT,
        foreground="#ffffff",
        font=FONT_BOLD,
        padding=(14, 7),
        relief="flat",
        borderwidth=0,
        anchor="center",
    )
    style.map("TButton",
        background=[
            ("active",   ACCENT_DK),
            ("pressed",  ACCENT_DK),
            ("disabled", BORDER),
        ],
        foreground=[("disabled", TEXT_MUTED)],
        relief=[("pressed", "flat")],
    )

    # ── TEntry ────────────────────────────────────────────────────────────────
    style.configure("TEntry",
        fieldbackground=BG_INPUT,
        foreground=TEXT,
        insertcolor=TEXT,
        selectbackground=ACCENT_LT,
        selectforeground=TEXT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=(6, 5),
        relief="flat",
        borderwidth=1,
    )
    style.map("TEntry",
        bordercolor=[("focus", ACCENT)],
        lightcolor=[("focus", ACCENT)],
        darkcolor=[("focus", ACCENT)],
    )

    # ── TCombobox ─────────────────────────────────────────────────────────────
    style.configure("TCombobox",
        fieldbackground=BG_INPUT,
        background=BG_INPUT,
        foreground=TEXT,
        selectbackground=ACCENT_LT,
        selectforeground=TEXT,
        arrowcolor=ACCENT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=(6, 5),
        relief="flat",
    )
    style.map("TCombobox",
        fieldbackground=[("readonly", BG_INPUT), ("focus", BG_INPUT)],
        foreground=[("readonly", TEXT)],
        background=[("readonly", BG_INPUT), ("active", BG_INPUT)],
        bordercolor=[("focus", ACCENT)],
        lightcolor=[("focus", ACCENT)],
        arrowcolor=[("disabled", TEXT_MUTED)],
    )
    root.option_add("*TCombobox*Listbox.background", BG_INPUT)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_LT)
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT)
    root.option_add("*TCombobox*Listbox.font", FONT)

    # ── TSpinbox ──────────────────────────────────────────────────────────────
    style.configure("TSpinbox",
        fieldbackground=BG_INPUT,
        foreground=TEXT,
        background=BG_INPUT,
        arrowcolor=ACCENT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=(6, 5),
        insertcolor=TEXT,
        relief="flat",
    )
    style.map("TSpinbox",
        bordercolor=[("focus", ACCENT)],
        lightcolor=[("focus", ACCENT)],
    )

    # ── TNotebook ─────────────────────────────────────────────────────────────
    style.configure("TNotebook",
        background=BG_ROOT,
        borderwidth=0,
        tabmargins=[2, 4, 2, 0],
    )
    style.configure("TNotebook.Tab",
        background=BG_FRAME,
        foreground=TEXT_MUTED,
        font=FONT_BOLD,
        padding=(16, 8),
        borderwidth=0,
    )
    style.map("TNotebook.Tab",
        background=[("selected", BG_CARD), ("active", "#e8edf5")],
        foreground=[("selected", ACCENT), ("active", TEXT)],
        expand=[("selected", [0, 0, 0, 2])],
    )

    # ── Treeview ──────────────────────────────────────────────────────────────
    style.configure("Treeview",
        background=BG_INPUT,
        foreground=TEXT,
        fieldbackground=BG_INPUT,
        rowheight=28,
        font=FONT,
        borderwidth=0,
        relief="flat",
    )
    style.configure("Treeview.Heading",
        background=BG_ROOT,
        foreground=HIGHLIGHT,
        font=FONT_BOLD,
        relief="flat",
        borderwidth=0,
        padding=(8, 7),
    )
    style.map("Treeview",
        background=[("selected", ACCENT_LT)],
        foreground=[("selected", TEXT)],
    )
    style.map("Treeview.Heading",
        background=[("active", BORDER)],
        relief=[("active", "flat")],
    )

    # ── TScrollbar ────────────────────────────────────────────────────────────
    style.configure("TScrollbar",
        background=BORDER,
        troughcolor=BG_FRAME,
        arrowcolor=TEXT_MUTED,
        borderwidth=0,
        relief="flat",
        width=8,
        arrowsize=8,
    )
    style.map("TScrollbar",
        background=[("active", ACCENT), ("pressed", ACCENT_DK)],
        arrowcolor=[("active", ACCENT)],
    )

    # ── TSeparator ────────────────────────────────────────────────────────────
    style.configure("TSeparator", background=BORDER)

    return style
