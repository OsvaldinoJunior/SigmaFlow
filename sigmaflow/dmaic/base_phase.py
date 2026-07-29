"""
sigmaflow/dmaic/base_phase.py
==============================
Abstract base class for all DMAIC phase implementations.

Every phase (Define, Measure, Analyze, Improve, Control) inherits from
this class, giving them a uniform interface the DMAICEngine can call.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class BasePhase(ABC):
    """
    Abstract DMAIC phase.

    Subclasses must implement:
        - ``phase_name`` class attribute
        - ``run(data, analysis_list, metadata)`` method
    """

    phase_name: str = "base"

    def __init__(self) -> None:
        self.results:  Dict[str, Any] = {}
        self.insights: List[str]      = []
        self._errors:  Dict[str, str] = {}

    # ── Public interface ──────────────────────────────────────────────────────

    @abstractmethod
    def run(
        self,
        data:          pd.DataFrame,
        analysis_list: List[str],
        metadata:      Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the phase analyses.

        Parameters
        ----------
        data : pd.DataFrame
        analysis_list : list[str]
            Tokens from the AnalysisPlanner (e.g. ["capability", "normality"]).
        metadata : dict, optional
            DataProfiler output — provides target column, column types, etc.

        Returns
        -------
        dict
            Structured results for this phase.
        """

    # ── Helpers shared across phases ─────────────────────────────────────────

    def _primary_numeric(
        self,
        df: pd.DataFrame,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Return the primary numeric column (target if available)."""
        if metadata and metadata.get("primary_target"):
            return metadata["primary_target"]
        num = list(df.select_dtypes(include="number").columns)
        return num[0] if num else None

    def _numeric_cols(
        self,
        df: pd.DataFrame,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        if metadata and metadata.get("numeric_columns"):
            return [c for c in metadata["numeric_columns"] if c in df.columns]
        return list(df.select_dtypes(include="number").columns)

    def _safe_run(self, name: str, fn, *args, **kwargs) -> Optional[Any]:
        """Execute *fn* safely, catching and recording any exception."""
        try:
            t0 = time.perf_counter()
            result = fn(*args, **kwargs)
            elapsed = round(time.perf_counter() - t0, 3)
            logger.debug("[%s] %-30s ✓  %.3fs", self.phase_name, name, elapsed)
            return result
        except Exception as exc:
            logger.error("[%s] %s failed: %s", self.phase_name, name, exc)
            self._errors[name] = str(exc)
            return None

    def _phase_result(self, **extra) -> Dict[str, Any]:
        """Wrap phase results in the standard envelope."""
        return {
            **self.results,
            "phase":    self.phase_name,
            "insights": self.insights,
            "errors":   self._errors,
            **extra,
        }
