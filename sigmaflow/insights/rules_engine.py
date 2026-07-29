"""
sigmaflow/insights/rules_engine.py
====================================
Central insight engine that evaluates statistical rules against analysis
results and returns structured, machine-readable Insight objects.

Each Insight contains:
    - rule        : rule identifier (e.g. "western_electric_rule_1")
    - description : what was detected
    - meaning     : statistical interpretation
    - recommendation : recommended action
    - severity    : "info" | "warning" | "critical"

Usage
-----
    from sigmaflow.insights.rules_engine import RulesEngine

    engine = RulesEngine()
    insights = engine.evaluate(df, analysis_results, dataset_type="spc")
    for ins in insights:
        print(ins.description)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from sigmaflow.insights.statistical_rules import (
    WesternElectricRules,
    CapabilityRules,
    TrendRules,
)

logger = logging.getLogger(__name__)


@dataclass
class Insight:
    """
    A single structured insight produced by the rules engine.

    Attributes
    ----------
    rule : str
        Unique identifier for the rule that fired.
    description : str
        Short human-readable description of what was detected.
    meaning : str
        Statistical meaning / interpretation of the finding.
    recommendation : str
        Suggested corrective or investigative action.
    severity : str
        "info", "warning", or "critical".
    data : dict
        Optional supporting numeric data (indices, values, etc.).
    """
    rule: str
    description: str
    meaning: str
    recommendation: str
    severity: str = "info"
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dictionary (JSON-safe)."""
        return {
            "rule": self.rule,
            "description": self.description,
            "meaning": self.meaning,
            "recommendation": self.recommendation,
            "severity": self.severity,
            "data": self.data,
        }


class RulesEngine:
    """
    Applies statistical rules to analysis results and produces
    a list of structured Insight objects.

    The engine delegates rule logic to specialized rule modules:
        - WesternElectricRules  (SPC / out-of-control patterns)
        - CapabilityRules       (Cp, Cpk thresholds)
        - TrendRules            (monotonic trends, runs)

    Parameters
    ----------
    apply_western_electric : bool
        Whether to run Western Electric rules (default: True).
    apply_capability : bool
        Whether to run capability rules (default: True).
    apply_trend : bool
        Whether to run trend rules (default: True).
    """

    def __init__(
        self,
        apply_western_electric: bool = True,
        apply_capability: bool = True,
        apply_trend: bool = True,
    ) -> None:
        self.apply_western_electric = apply_western_electric
        self.apply_capability = apply_capability
        self.apply_trend = apply_trend

    def evaluate(
        self,
        df: pd.DataFrame,
        analysis: Dict[str, Any],
        dataset_type: str = "",
    ) -> List[Insight]:
        """
        Run all applicable rules and return structured insights.

        Parameters
        ----------
        df : pd.DataFrame
            The original dataset (used for series-level rule checks).
        analysis : dict
            Output from the dataset analyzer's run_analysis().
        dataset_type : str
            Hint about the dataset type ("spc", "capability", etc.).

        Returns
        -------
        list[Insight]
        """
        insights: List[Insight] = []
        series = self._extract_primary_series(df, analysis)

        # Western Electric Rules (require a numeric series)
        if self.apply_western_electric and series is not None:
            we_rules = WesternElectricRules()
            insights.extend(we_rules.evaluate(series, analysis))

        # Capability rules
        if self.apply_capability and "capability" in analysis:
            cap_rules = CapabilityRules()
            insights.extend(cap_rules.evaluate(analysis["capability"]))

        # Trend rules
        if self.apply_trend and "trend" in analysis:
            trend_rules = TrendRules()
            insights.extend(trend_rules.evaluate(analysis["trend"]))

        logger.debug("RulesEngine produced %d insight(s) for '%s'", len(insights), dataset_type)
        return insights

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_primary_series(
        self,
        df: pd.DataFrame,
        analysis: Dict[str, Any],
    ) -> "pd.Series | None":
        """
        Extract the primary numeric measurement series from the dataframe.
        Returns None if no suitable series is found.
        """
        exclude_kws = ("time", "date", "hora", "seq", "order", "id",
                       "index", "num", "batch", "lote", "usl", "lsl", "spec")
        num_cols = df.select_dtypes(include="number").columns.tolist()
        candidates = [
            c for c in num_cols
            if not any(kw in c.lower() for kw in exclude_kws)
        ]
        if candidates:
            return df[candidates[0]].dropna().reset_index(drop=True)
        if num_cols:
            return df[num_cols[0]].dropna().reset_index(drop=True)
        return None
