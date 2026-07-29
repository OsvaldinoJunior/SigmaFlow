"""
sigmaflow/dmaic/measure/phase.py
==================================
Measure Phase — SigmaFlow DMAIC Engine.

Analyses performed (depending on analysis_list):
    • descriptive_stats  — mean, std, quartiles, skewness, kurtosis
    • normality          — Shapiro-Wilk / Anderson-Darling tests
    • distribution_analysis — histogram + best-fit distribution
    • capability         — Cp, Cpk, Pp, Ppk, DPMO, sigma level
    • msa                — Gauge R&R measurement system analysis
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from sigmaflow.dmaic.base_phase import BasePhase

logger = logging.getLogger(__name__)


class MeasurePhase(BasePhase):
    """
    DMAIC Measure Phase.

    Quantifies the current process baseline:
    - Descriptive statistics for all numeric variables
    - Normality assessment (required for downstream test selection)
    - Process capability if spec limits are detectable
    - Measurement System Analysis (Gauge R&R) if part/operator columns exist
    """

    phase_name = "measure"

    def run(
        self,
        data:          pd.DataFrame,
        analysis_list: List[str],
        metadata:      Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        logger.info("[Measure] Starting Measure phase (%d analyses)", len(analysis_list))
        m = metadata or {}

        if "descriptive_stats" in analysis_list:
            self.results["descriptive_stats"] = self._safe_run(
                "descriptive_stats", self._descriptive_stats, data, m
            )

        if "normality" in analysis_list:
            self.results["normality"] = self._safe_run(
                "normality", self._normality, data, m
            )

        if "distribution_analysis" in analysis_list:
            self.results["distribution_analysis"] = self._safe_run(
                "distribution_analysis", self._distribution_analysis, data, m
            )

        if "capability" in analysis_list:
            self.results["capability"] = self._safe_run(
                "capability", self._capability, data, m
            )

        if "msa" in analysis_list:
            self.results["msa"] = self._safe_run(
                "msa", self._msa, data, m
            )

        self._build_insights()
        return self._phase_result()

    # ── Descriptive statistics ────────────────────────────────────────────────

    def _descriptive_stats(
        self,
        df: pd.DataFrame,
        m: Dict[str, Any],
    ) -> Dict[str, Any]:
        num_cols = self._numeric_cols(df, m)
        if not num_cols:
            return {}

        stats = {}
        for col in num_cols:
            s = df[col].dropna()
            if len(s) == 0:
                continue
            stats[col] = {
                "n":        int(len(s)),
                "mean":     round(float(s.mean()), 6),
                "std":      round(float(s.std(ddof=1)), 6) if len(s) > 1 else 0.0,
                "variance": round(float(s.var(ddof=1)), 6) if len(s) > 1 else 0.0,
                "min":      round(float(s.min()), 6),
                "p25":      round(float(s.quantile(0.25)), 6),
                "median":   round(float(s.median()), 6),
                "p75":      round(float(s.quantile(0.75)), 6),
                "max":      round(float(s.max()), 6),
                "iqr":      round(float(s.quantile(0.75) - s.quantile(0.25)), 6),
                "skewness": round(float(s.skew()), 4),
                "kurtosis": round(float(s.kurtosis()), 4),
                "cv":       round(float(s.std() / s.mean()), 4) if s.mean() != 0 else None,
            }
        return {"columns": stats, "n_columns_analysed": len(stats)}

    # ── Normality ─────────────────────────────────────────────────────────────

    def _normality(
        self,
        df: pd.DataFrame,
        m: Dict[str, Any],
    ) -> Dict[str, Any]:
        from sigmaflow.statistics.normality_tests import run_normality_tests  # noqa
        num_cols = self._numeric_cols(df, m)[:6]   # cap for performance
        return run_normality_tests(df, columns=num_cols)

    # ── Distribution analysis ─────────────────────────────────────────────────

    def _distribution_analysis(
        self,
        df: pd.DataFrame,
        m: Dict[str, Any],
    ) -> Dict[str, Any]:
        from scipy import stats as sc  # noqa
        num_cols = self._numeric_cols(df, m)
        result   = {}
        CANDIDATES = [
            ("normal",      sc.norm),
            ("lognormal",   sc.lognorm),
            ("exponential", sc.expon),
            ("weibull_min", sc.weibull_min),
        ]
        for col in num_cols[:4]:
            s = df[col].dropna().values
            if len(s) < 8:
                continue
            best_dist, best_sse = None, float("inf")
            for dist_name, dist_obj in CANDIDATES:
                try:
                    params = dist_obj.fit(s)
                    fitted = dist_obj.pdf(s, *params)
                    # KDE approximation for comparison
                    from scipy.stats import gaussian_kde  # noqa
                    kde  = gaussian_kde(s)
                    actual = kde(s)
                    sse  = float(np.sum((fitted - actual) ** 2))
                    if sse < best_sse:
                        best_sse  = sse
                        best_dist = dist_name
                except Exception:
                    pass
            result[col] = {
                "best_fit_distribution": best_dist,
                "n":                     int(len(s)),
                "mean":                  round(float(np.mean(s)), 6),
                "std":                   round(float(np.std(s, ddof=1)), 6),
            }
        return result

    # ── Capability ────────────────────────────────────────────────────────────

    def _capability(
        self,
        df: pd.DataFrame,
        m: Dict[str, Any],
    ) -> Dict[str, Any]:
        from sigmaflow.analysis.capability_analysis import compute_capability  # noqa

        target   = self._primary_numeric(df, m)
        if not target:
            return {"skipped": True, "reason": "No numeric target column found."}

        # Auto-detect spec limits
        usl = lsl = None
        for col in df.columns:
            lo = col.lower()
            if lo in ("usl", "upper_spec", "usl_limit"):
                try:
                    usl = float(df[col].dropna().iloc[0])
                except Exception:
                    pass
            if lo in ("lsl", "lower_spec", "lsl_limit"):
                try:
                    lsl = float(df[col].dropna().iloc[0])
                except Exception:
                    pass

        # Fallback: use ±3σ as surrogate spec limits
        if usl is None and lsl is None:
            series = df[target].dropna()
            mu, sigma = float(series.mean()), float(series.std(ddof=1))
            usl = mu + 3 * sigma
            lsl = mu - 3 * sigma

        series = df[target].dropna()
        result = compute_capability(series, usl=usl, lsl=lsl)
        result["target_column"] = target
        result["usl_used"]      = round(usl, 6) if usl else None
        result["lsl_used"]      = round(lsl, 6) if lsl else None
        return result

    # ── MSA (Gauge R&R) ───────────────────────────────────────────────────────

    def _msa(
        self,
        df: pd.DataFrame,
        m: Dict[str, Any],
    ) -> Dict[str, Any]:
        from sigmaflow.analysis.msa_analysis import MSAAnalyzer  # noqa

        # Detect standard MSA column names
        part_col = next((c for c in df.columns if c.lower() == "part"), None)
        op_col   = next((c for c in df.columns if c.lower() == "operator"), None)
        ms_col   = next((c for c in df.columns if c.lower() == "measurement"), None)

        if not all([part_col, op_col, ms_col]):
            return {"skipped": True, "reason": "MSA requires 'Part', 'Operator', 'Measurement' columns."}

        msa    = MSAAnalyzer(df, part_col, op_col, ms_col)
        return msa.run()

    # ── Insights ──────────────────────────────────────────────────────────────

    def _build_insights(self) -> None:
        # Capability insight
        cap = self.results.get("capability") or {}
        cpk = cap.get("Cpk")
        if cpk is not None:
            if cpk >= 1.33:
                self.insights.append(
                    f"✅ Process is CAPABLE: Cpk = {cpk:.3f} ≥ 1.33."
                )
            elif cpk >= 1.0:
                self.insights.append(
                    f"⚠ Process is MARGINAL: Cpk = {cpk:.3f} (target ≥ 1.33)."
                )
            else:
                self.insights.append(
                    f"🔴 Process is NOT CAPABLE: Cpk = {cpk:.3f} < 1.00 — "
                    "immediate action required."
                )

        # Normality insight
        norm = self.results.get("normality") or {}
        non_normal = [
            col for col, res in norm.items()
            if isinstance(res, dict) and res.get("normal_distribution") is False
        ]
        if non_normal:
            self.insights.append(
                f"⚠ Non-normal distributions detected in: {', '.join(non_normal[:3])}. "
                "Use non-parametric tests in Analyze phase."
            )

        # MSA insight
        msa = self.results.get("msa") or {}
        grr = msa.get("grr_pct")
        if grr is not None:
            if grr <= 10:
                self.insights.append(f"✅ Measurement system is ADEQUATE: GRR% = {grr:.1f}%.")
            elif grr <= 30:
                self.insights.append(f"⚠ Measurement system is MARGINAL: GRR% = {grr:.1f}%.")
            else:
                self.insights.append(f"🔴 Measurement system is INADEQUATE: GRR% = {grr:.1f}%.")
