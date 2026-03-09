"""
sigmaflow/analysis/root_cause_analysis.py
==========================================
Root cause indication through correlation analysis.

This module identifies which process variables are most strongly
associated with defects or the primary quality metric — providing
data-driven clues about potential root causes.

Methods used
------------
- Pearson correlation   : linear relationships between continuous variables
- Spearman correlation  : monotonic (non-linear) relationships / ranked data
- Variable importance   : ranked list of the most influential factors

Key concept
-----------
Correlation ≠ Causation. High correlation flags a variable as a
*candidate* for investigation, not as a confirmed cause. The ranked
list guides engineers toward the most promising hypotheses.

Interpretation thresholds (absolute correlation |r|)
-----------------------------------------------------
    |r| ≥ 0.70  → Strong association     (HIGH priority)
    |r| ≥ 0.50  → Moderate association   (MEDIUM priority)
    |r| ≥ 0.30  → Weak association       (LOW priority)
    |r| <  0.30 → Negligible association  (ignore)

Usage
-----
    from sigmaflow.analysis.root_cause_analysis import RootCauseAnalyzer

    rca = RootCauseAnalyzer(df, target_col="defects")
    results = rca.run()
    print(results["ranked_variables"])
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as sc_stats

logger = logging.getLogger(__name__)

# Correlation strength thresholds (|r|)
STRONG   = 0.70
MODERATE = 0.50
WEAK     = 0.30


class RootCauseAnalyzer:
    """
    Identify process variables most correlated with defects or variation.

    Parameters
    ----------
    df : pd.DataFrame
        The dataset to analyze. Should contain numeric columns.
    target_col : str, optional
        The column representing defects/quality output. If None, the
        analyzer uses the column with the highest variance as the target.
    exclude_cols : list[str], optional
        Columns to exclude from the analysis (e.g., timestamps, IDs).
    """

    def __init__(
        self,
        df: pd.DataFrame,
        target_col: Optional[str] = None,
        exclude_cols: Optional[List[str]] = None,
    ) -> None:
        self.df          = df.copy()
        self.exclude_cols = set(exclude_cols or [])
        self._target_col = target_col
        self._results: Dict[str, Any] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> Dict[str, Any]:
        """
        Execute the full root cause correlation analysis.

        Returns
        -------
        dict
            Keys:
            - target_col        : column used as the quality target
            - ranked_variables  : list of dicts (variable, pearson_r,
                                  spearman_r, strength, p_value)
            - strong_candidates : variables with |r| ≥ 0.70
            - heatmap_data      : full correlation matrix as dict
            - interpretation    : natural-language summary text
        """
        num_df = self._numeric_df()
        if num_df.shape[1] < 2:
            logger.warning("RootCauseAnalyzer: fewer than 2 numeric columns — skipping.")
            return {"error": "Need at least 2 numeric columns for correlation analysis."}

        target = self._resolve_target(num_df)
        logger.info("Root cause analysis — target column: '%s'", target)

        features = [c for c in num_df.columns if c != target]
        ranked   = self._rank_variables(num_df, target, features)

        strong   = [v for v in ranked if abs(v["pearson_r"]) >= STRONG]
        moderate = [v for v in ranked if MODERATE <= abs(v["pearson_r"]) < STRONG]

        heatmap_data = num_df.corr(method="pearson").round(4).to_dict()

        interpretation = self._build_interpretation(target, ranked)

        self._results = {
            "target_col":       target,
            "ranked_variables": ranked,
            "strong_candidates":  [v["variable"] for v in strong],
            "moderate_candidates":[v["variable"] for v in moderate],
            "heatmap_data":     heatmap_data,
            "interpretation":   interpretation,
            "n_analyzed":       len(features),
        }
        return self._results

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _numeric_df(self) -> pd.DataFrame:
        """Return only numeric columns, excluding explicitly excluded ones."""
        num = self.df.select_dtypes(include="number")
        excluded = {c for c in num.columns if c in self.exclude_cols}
        # Also exclude obvious index/timestamp-like columns
        excluded |= {
            c for c in num.columns
            if any(kw in c.lower() for kw in ("id", "index", "seq", "order",
                                               "timestamp", "batch", "lote"))
        }
        return num.drop(columns=list(excluded)).dropna()

    def _resolve_target(self, num_df: pd.DataFrame) -> str:
        """Determine the target (quality output) column."""
        if self._target_col and self._target_col in num_df.columns:
            return self._target_col
        # Heuristic: prefer columns with quality-related names
        quality_kws = ("defect", "failure", "reject", "yield", "quality",
                       "error", "count", "non_conform", "ncr", "cpk")
        for col in num_df.columns:
            if any(kw in col.lower() for kw in quality_kws):
                logger.info("Auto-selected target column: '%s'", col)
                return col
        # Fallback: highest-variance column
        target = str(num_df.var().idxmax())
        logger.info("No quality column found — using highest-variance column: '%s'", target)
        return target

    def _rank_variables(
        self,
        num_df: pd.DataFrame,
        target: str,
        features: List[str],
    ) -> List[Dict[str, Any]]:
        """Compute and rank correlations of each feature against the target."""
        rows = []
        target_series = num_df[target]

        for feat in features:
            feat_series = num_df[feat]

            # Skip constant columns
            if feat_series.std() == 0:
                continue

            # Pearson (linear)
            p_r, p_p = sc_stats.pearsonr(feat_series, target_series)
            # Spearman (monotonic)
            s_r, s_p = sc_stats.spearmanr(feat_series, target_series)

            abs_r = abs(p_r)
            strength = (
                "strong"   if abs_r >= STRONG   else
                "moderate" if abs_r >= MODERATE else
                "weak"     if abs_r >= WEAK     else
                "negligible"
            )

            rows.append({
                "variable":   feat,
                "pearson_r":  round(float(p_r), 4),
                "spearman_r": round(float(s_r), 4),
                "p_value":    round(float(p_p), 6),
                "strength":   strength,
                "abs_r":      round(abs_r, 4),
            })

        # Sort by absolute Pearson correlation descending
        rows.sort(key=lambda x: x["abs_r"], reverse=True)
        # Remove helper key
        for r in rows:
            r.pop("abs_r")
        return rows

    def _build_interpretation(
        self,
        target: str,
        ranked: List[Dict[str, Any]],
    ) -> str:
        """Build a natural-language interpretation of the results."""
        if not ranked:
            return "No significant correlations were found."

        top = [v for v in ranked[:3] if abs(v["pearson_r"]) >= WEAK]
        if not top:
            return (
                f"No variables showed meaningful correlation with '{target}'. "
                "The variation may be driven by factors not present in this dataset."
            )

        top_names = ", ".join(f"'{v['variable']}' (r={v['pearson_r']:+.3f})" for v in top)
        strong_count = sum(1 for v in ranked if abs(v["pearson_r"]) >= STRONG)
        mod_count    = sum(1 for v in ranked if MODERATE <= abs(v["pearson_r"]) < STRONG)

        parts = [
            f"Correlation analysis against the target variable '{target}' identified "
            f"{len(ranked)} candidate factor(s). "
        ]
        if strong_count:
            parts.append(
                f"{strong_count} variable(s) showed strong association (|r| ≥ 0.70): "
                f"{', '.join(v['variable'] for v in ranked if abs(v['pearson_r']) >= STRONG)}. "
            )
        if mod_count:
            parts.append(
                f"{mod_count} variable(s) showed moderate association (|r| ≥ 0.50). "
            )
        parts.append(
            f"The top contributors were: {top_names}. "
            "These variables should be prioritized in root cause investigation. "
            "Note: correlation indicates association, not confirmed causation."
        )
        return "".join(parts)
