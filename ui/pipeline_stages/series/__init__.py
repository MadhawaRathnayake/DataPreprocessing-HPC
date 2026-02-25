"""
pipeline_stages.series — Series (serial / single-threaded) processing stages.
Backend: modules/series_processing/ (libserialanalyzer.so via ctypes).
Orchestrated by ui/series_processing_tab.py.
"""
from .stage_overview   import StageOverview
from .stage_duplicates import StageDuplicates
from .stage_missing    import StageMissing
from .stage_outliers   import StageOutliers
from .stage_scaling    import StageScaling
from .stage_encoding   import StageEncoding
from .stage_apply      import StageApply

__all__ = [
    "StageOverview",
    "StageDuplicates",
    "StageMissing",
    "StageOutliers",
    "StageScaling",
    "StageEncoding",
    "StageApply",
]
