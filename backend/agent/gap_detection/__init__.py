"""Gap Detection pipeline package.

This package implements a LangGraph-based pipeline for detecting research gaps
from a set of analyzed papers.

Usage:
    from backend.agent.gap_detection.schemas import GapReport, GapDetectionState
"""

from backend.agent.gap_detection.schemas import (
    ExtractedPaperData,
    GapDetectionState,
    GapItem,
    GapOrigin,
    GapReport,
    GapStatus,
    GapType,
    PaperRef,
)

__all__ = [
    "GapType",
    "GapOrigin",
    "GapStatus",
    "PaperRef",
    "ExtractedPaperData",
    "GapItem",
    "GapReport",
    "GapDetectionState",
]
