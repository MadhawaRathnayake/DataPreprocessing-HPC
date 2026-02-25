"""
UI Package for Data Preprocessing Application

This package contains modular UI components organized by tabs.
Each tab is implemented as a separate module inheriting from BaseTab.
"""

from .base_tab import BaseTab
from .import_tab import ImportTab
from .series_processing_tab import SeriesProcessingTab
from .openmp_analyzer_tab import OpenMPAnalyzerTab
from .mpi_analyzer_tab import MPIAnalyzerTab
from .export_tab import ExportTab

__all__ = [
    'BaseTab',
    'ImportTab',
    'SeriesProcessingTab',
    'OpenMPAnalyzerTab',
    'MPIAnalyzerTab',
    'ExportTab'
]

__version__ = '1.0.0'
