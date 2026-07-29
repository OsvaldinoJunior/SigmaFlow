"""
sigmaflow/core/data_profiler.py
================================
DataProfiler — Automated dataset analysis for SigmaFlow DMAIC Engine.

Examines a pandas DataFrame and returns a structured metadata dictionary
that drives all downstream analysis decisions.

Usage
-----
    from sigmaflow.core.data_profiler import DataProfiler

    profiler = DataProfiler()
    metadata = profiler.profile(df)
    print(metadata["target_candidates"])
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class DataProfiler:
    """
    Automatic dataset profiler for the DMAIC Engine.

    Analyses a DataFrame and returns structured metadata used by
    :class:`~sigmaflow.core.analysis_planner.AnalysisPlanner` to decide
    which analyses to run in each DMAIC phase.

    Parameters
    ----------
    target_hint : str, optional
        Column name to treat as the quality / response variable.
        When not provided, it is inferred automatically.
    correlation_threshold : float
        Minimum |r| to consider two numeric columns as correlated (default 0.5).
    time_col_keywords : list[str]
        Keywords used to auto-detect the time / sequence column.
    """

    _TIME_KEYWORDS = [
        "time", "timestamp", "date", "datetime", "seq",
        "sequence", "order", "index", "sample", "obs",
    ]
    _TARGET_KEYWORDS = [
        "defect", "defects", "failure", "failures", "reject",
        "rejects", "nonconform", "error", "errors", "output",
        "yield", "quality", "response", "result", "y",
    ]
    _SPEC_KEYWORDS = {"usl", "lsl", "upper_spec", "lower_spec",
                      "usl_limit", "lsl_limit", "spec_hi", "spec_lo"}

    def __init__(
        self,
        target_hint: Optional[str] = None,
        correlation_threshold: float = 0.5,
    ) -> None:
        self.target_hint           = target_hint
        self.correlation_threshold = correlation_threshold

    # ── Public API ────────────────────────────────────────────────────────────

    def profile(self, data: pd.DataFrame | str) -> Dict[str, Any]:
        """
        Profile a dataset and return metadata.

        Parameters
        ----------
        data : pd.DataFrame or str
            DataFrame or path to a CSV / Excel file.

        Returns
        -------
        dict
            Metadata dictionary with keys described in the class docstring.
        """
        df = self._load(data)
        logger.info("DataProfiler: profiling dataset (%d rows × %d cols)",
                    len(df), len(df.columns))

        numeric_cols     = self._numeric_columns(df)
        categorical_cols = self._categorical_columns(df)
        time_col         = self._detect_time_column(df, numeric_cols)
        target_candidates = self._detect_targets(df, numeric_cols, time_col)
        missing          = self._missing_summary(df)
        correlations     = self._compute_correlations(df, numeric_cols)
        spec_cols        = self._detect_spec_columns(df)
        has_groups       = len(categorical_cols) > 0
        is_time_series   = time_col is not None
        is_process_data  = len(spec_cols) > 0 or self._looks_like_process(df, numeric_cols)
        summary_stats    = self._summary_stats(df, numeric_cols)
        data_quality     = self._data_quality_score(df, numeric_cols)

        metadata: Dict[str, Any] = {
            # ── Dimensions ─────────────────────────────────────────────────
            "n_rows":              len(df),
            "n_columns":           len(df.columns),
            "columns":             list(df.columns),
            # ── Column classification ──────────────────────────────────────
            "numeric_columns":     numeric_cols,
            "categorical_columns": categorical_cols,
            "time_column":         time_col,
            "spec_columns":        spec_cols,
            # ── Target ─────────────────────────────────────────────────────
            "target_candidates":   target_candidates,
            "primary_target":      target_candidates[0] if target_candidates else None,
            # ── Data quality ───────────────────────────────────────────────
            "missing_values":      missing["has_missing"],
            "missing_summary":     missing["summary"],
            "missing_pct":         missing["total_pct"],
            "data_quality_score":  data_quality,
            # ── Structure flags ────────────────────────────────────────────
            "has_groups":          has_groups,
            "is_time_series":      is_time_series,
            "is_process_data":     is_process_data,
            "has_spec_limits":     len(spec_cols) > 0,
            # ── Statistical summary ────────────────────────────────────────
            "summary_stats":       summary_stats,
            "correlations":        correlations,
            "strong_correlations": [
                (a, b, r)
                for a, b, r in correlations
                if abs(r) >= self.correlation_threshold
            ],
        }

        logger.info(
            "DataProfiler complete: %d numeric, %d categorical, "
            "time_col=%s, targets=%s",
            len(numeric_cols), len(categorical_cols),
            time_col, target_candidates,
        )
        return metadata

    # ── Loaders ───────────────────────────────────────────────────────────────

    def _load(self, data: pd.DataFrame | str) -> pd.DataFrame:
        if isinstance(data, pd.DataFrame):
            return data.copy()
        path = str(data)
        if path.endswith(".csv"):
            return pd.read_csv(path)
        if path.endswith((".xlsx", ".xls")):
            return pd.read_excel(path)
        raise ValueError(f"Unsupported file format: {path!r}")

    # ── Column classification ─────────────────────────────────────────────────

    def _numeric_columns(self, df: pd.DataFrame) -> List[str]:
        spec = self._SPEC_KEYWORDS
        return [
            c for c in df.select_dtypes(include="number").columns
            if c.lower() not in spec
        ]

    def _categorical_columns(self, df: pd.DataFrame) -> List[str]:
        cats = list(df.select_dtypes(include=["object", "category"]).columns)
        # Also include low-cardinality integer columns (2–8 unique values)
        for col in df.select_dtypes(include="number").columns:
            if 2 <= df[col].nunique() <= 8 and col not in cats:
                cats.append(col)
        return cats

    def _detect_time_column(
        self,
        df: pd.DataFrame,
        numeric_cols: List[str],
    ) -> Optional[str]:
        # Priority 1: explicit datetime dtype
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                return col
        # Priority 2: column name contains time keyword
        for col in df.columns:
            if any(kw in col.lower() for kw in self._TIME_KEYWORDS):
                return col
        # Priority 3: monotonically increasing integer column
        for col in numeric_cols:
            vals = df[col].dropna().reset_index(drop=True)
            if len(vals) >= 6 and vals.is_monotonic_increasing and vals.dtype in (int, "int64"):
                return col
        return None

    def _detect_spec_columns(self, df: pd.DataFrame) -> List[str]:
        return [c for c in df.columns if c.lower() in self._SPEC_KEYWORDS]

    def _detect_targets(
        self,
        df: pd.DataFrame,
        numeric_cols: List[str],
        time_col: Optional[str],
    ) -> List[str]:
        if self.target_hint and self.target_hint in df.columns:
            return [self.target_hint]

        candidates = []
        # Name-based heuristic
        for col in numeric_cols:
            if any(kw in col.lower() for kw in self._TARGET_KEYWORDS):
                candidates.append(col)

        # Last numeric column often is the response (excluding time)
        non_time = [c for c in numeric_cols if c != time_col]
        if not candidates and non_time:
            candidates.append(non_time[-1])

        # If there are many numeric cols, add the one with highest variance
        if len(non_time) >= 3:
            stds = df[non_time].std()
            top_var = stds.idxmax()
            if top_var not in candidates:
                candidates.append(top_var)

        # De-duplicate while preserving order
        seen = set()
        result = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                result.append(c)
        return result

    # ── Missing values ────────────────────────────────────────────────────────

    def _missing_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        counts   = df.isnull().sum()
        has_any  = bool(counts.any())
        total    = counts.sum()
        total_pct = round(total / (len(df) * len(df.columns)) * 100, 2) if len(df) else 0
        summary  = {
            col: {"count": int(cnt), "pct": round(cnt / len(df) * 100, 1)}
            for col, cnt in counts.items()
            if cnt > 0
        }
        return {"has_missing": has_any, "summary": summary, "total_pct": total_pct}

    # ── Correlations ──────────────────────────────────────────────────────────

    def _compute_correlations(
        self,
        df: pd.DataFrame,
        numeric_cols: List[str],
    ) -> List[tuple]:
        """Return list of (col_a, col_b, pearson_r) for all column pairs."""
        if len(numeric_cols) < 2:
            return []
        try:
            corr = df[numeric_cols].corr(method="pearson")
            pairs = []
            cols  = list(corr.columns)
            for i in range(len(cols)):
                for j in range(i + 1, len(cols)):
                    r = corr.iloc[i, j]
                    if not np.isnan(r):
                        pairs.append((cols[i], cols[j], round(float(r), 4)))
            # Sort by |r| descending
            pairs.sort(key=lambda x: abs(x[2]), reverse=True)
            return pairs
        except Exception as exc:
            logger.warning("Correlation computation failed: %s", exc)
            return []

    # ── Summary statistics ────────────────────────────────────────────────────

    def _summary_stats(
        self,
        df: pd.DataFrame,
        numeric_cols: List[str],
    ) -> Dict[str, Dict[str, float]]:
        result = {}
        for col in numeric_cols:
            s = df[col].dropna()
            if len(s) == 0:
                continue
            result[col] = {
                "n":      int(len(s)),
                "mean":   round(float(s.mean()), 6),
                "std":    round(float(s.std(ddof=1)), 6) if len(s) > 1 else 0.0,
                "min":    round(float(s.min()), 6),
                "p25":    round(float(s.quantile(0.25)), 6),
                "median": round(float(s.median()), 6),
                "p75":    round(float(s.quantile(0.75)), 6),
                "max":    round(float(s.max()), 6),
                "cv":     round(float(s.std() / s.mean()), 4) if s.mean() != 0 else 0.0,
            }
        return result

    # ── Heuristics ────────────────────────────────────────────────────────────

    def _looks_like_process(
        self,
        df: pd.DataFrame,
        numeric_cols: List[str],
    ) -> bool:
        """Heuristic: looks like process data if several numeric cols and ≥ 20 rows."""
        return len(numeric_cols) >= 2 and len(df) >= 20

    def _data_quality_score(
        self,
        df: pd.DataFrame,
        numeric_cols: List[str],
    ) -> float:
        """
        Simple 0–100 data quality score.

        Penalises missing values, constant columns, and very small datasets.
        """
        score = 100.0
        # Missing values penalty (up to -30)
        missing_pct = df.isnull().mean().mean() * 100
        score -= min(missing_pct * 3, 30)
        # Constant columns penalty (up to -20)
        if numeric_cols:
            constant_ratio = sum(
                1 for c in numeric_cols if df[c].nunique() <= 1
            ) / len(numeric_cols)
            score -= constant_ratio * 20
        # Small dataset penalty (up to -20)
        if len(df) < 10:
            score -= 20
        elif len(df) < 30:
            score -= 10
        return round(max(score, 0.0), 1)
