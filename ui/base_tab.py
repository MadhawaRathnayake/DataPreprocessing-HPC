"""
Base Tab Class
All tab implementations should inherit from this class
"""

import tkinter as tk
from tkinter import ttk

class BaseTab:
    """Base class for all application tabs"""
    
    def __init__(self, parent, app_context):
        """
        Initialize the tab
        
        Args:
            parent: The parent notebook widget
            app_context: Reference to main application context (for shared data)
        """
        self.parent = parent
        self.app = app_context
        self.frame = ttk.Frame(parent)
        
    def get_frame(self):
        """Return the tab's frame"""
        return self.frame
        
    def build_ui(self):
        """Build the tab's UI - must be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement build_ui()")
        
    def on_tab_selected(self):
        """Called when this tab is selected - can be overridden"""
        pass
        
    def on_tab_deselected(self):
        """Called when this tab is deselected - can be overridden"""
        pass
