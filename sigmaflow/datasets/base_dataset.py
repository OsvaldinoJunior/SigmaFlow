"""
sigmaflow/datasets/base_dataset.py
===================================
Abstract base class that every dataset analyzer must inherit from.

To add a new analyzer:
    1. Create a new file in sigmaflow/datasets/
    2. Inherit from BaseDataset
    3. Set a unique class attribute: name = "my_type"
    4. Implement all four abstract methods
    5. Done — the registry discovers it automatically.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class BaseDataset(ABC):
    """
    Abstract base for all SigmaFlow dataset analyzers.

    Every concrete subclass **must** define:
        - ``name``          unique string identifier (e.g. "capability")
        - ``detect()``      returns True if this analyzer matches the dataframe
        - ``run_analysis()``
        - ``generate_plots()``
        - ``generate_insights()``
    """

    # ── Class-level metadata (override in subclass) ──────────────────────────
    name: str = "base"
    description: str = "Base dataset analyzer"
    priority: int = 0   # Higher = checked first during auto-detection

    def __init__(self) -> None:
        self.results: Dict[str, Any] = {}
        self.insights_list: List[str] = []
        self._plots: List[str] = []

    # ── Abstract interface ───────────────────────────────────────────────────

    @abstractmethod
    def detect(self, df: pd.DataFrame) -> bool:
        """
        Return True if this analyzer is appropriate for *df*.

        The registry calls detect() on every registered analyzer and selects
        the one with the highest priority that returns True.

        Parameters
        ----------
        df : pd.DataFrame
            The dataset to evaluate.

        Returns
        -------
        bool
        """

    @abstractmethod
    def run_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Perform statistical analysis on *df*.

        Returns
        -------
        dict
            Key/value results that will be passed to the report generator.
        """

    @abstractmethod
    def generate_plots(self, df: pd.DataFrame, output_folder: str | Path) -> List[str]:
        """
        Generate all relevant charts and save them to *output_folder*.

        Returns
        -------
        list[str]
            Absolute paths of every generated image file.
        """

    @abstractmethod
    def generate_insights(self, df: pd.DataFrame) -> List[str]:
        """
        Return a list of human-readable insight strings discovered during
        the analysis.

        Returns
        -------
        list[str]
        """

    # ── Shared helpers available to all subclasses ──────────────────────────

    def _numeric_cols(self, df: pd.DataFrame,
                      exclude: Optional[List[str]] = None) -> List[str]:
        """Return numeric column names, optionally excluding some."""
        exc = set(exclude or [])
        return [c for c in df.select_dtypes(include="number").columns if c not in exc]

    def _cat_cols(self, df: pd.DataFrame) -> List[str]:
        """Return categorical / object column names."""
        return df.select_dtypes(include=["object", "category"]).columns.tolist()

    def _save_fig(self, fig, path: Path) -> str:
        """Save a matplotlib figure and register it."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(path), dpi=130, bbox_inches="tight")
        plt.close(fig)
        self._plots.append(str(path))
        logger.debug("Plot saved: %s", path.name)
        return str(path)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name='{self.name}'>"
