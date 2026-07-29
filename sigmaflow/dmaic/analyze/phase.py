"""
sigmaflow/dmaic/analyze/phase.py
==================================
Analyze Phase — SigmaFlow DMAIC Engine.

Analyses performed (depending on analysis_list):
    • correlation         — Pearson / Spearman correlation matrix
    • regression          — Multiple linear regression, R², significant vars
    • anova               — One-way ANOVA for each categorical group
    • root_cause          — Ranked variable importance vs. target
    • hypothesis_tests    — t-tests, F-tests, Levene's test
    • pareto              — Pareto chart data (vital few / useful many)
    • fmea                — FMEA RPN analysis
    • nonparametric_tests — Mann-Whitney, Kruskal-Wallis, Chi-square
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from sigmaflow.dmaic.base_phase import BasePhase

logger = logging.getLogger(__name__)


class AnalyzePhase(BasePhase):
    """
    DMAIC Analyze Phase.

    Identifies root causes and significant variables through:
    - Correlation and regression analysis
    - Statistical hypothesis testing
    - ANOVA for grouped data
    - Pareto prioritisation
    - FMEA risk quantification
    - Non-parametric fallbacks when normality fails
    """

    phase_name = "analyze"

    def run(
        self,
        data:          pd.DataFrame,
        analysis_list: List[str],
        metadata:      Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        logger.info("[Analyze] Starting Analyze phase (%d analyses)", len(analysis_list))
        m = metadata or {}

        dispatch = {
            "correlation":        self._correlation,
            "regression":         self._regression,
            "anova":              self._anova,
            "root_cause":         self._root_cause,
            "hypothesis_tests":   self._hypothesis_tests,
            "pareto":             self._pareto,
            "fmea":               self._fmea,
            "nonparametric_tests":self._nonparametric,
        }

        for key, fn in dispatch.items():
            if key in analysis_list:
                self.results[key] = self._safe_run(key, fn, data, m)

        self._build_insights(m)
        return self._phase_result()

    # ── Analyses ──────────────────────────────────────────────────────────────

    def _correlation(self, df: pd.DataFrame, m: Dict[str, Any]) -> Dict[str, Any]:
        num_cols = self._numeric_cols(df, m)
        if len(num_cols) < 2:
            return {"skipped": True, "reason": "Need ≥ 2 numeric columns."}

        pearson  = df[num_cols].corr(method="pearson")
        spearman = df[num_cols].corr(method="spearman")

        # Extract strongest pairs
        strong = []
        cols = list(pearson.columns)
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                r = pearson.iloc[i, j]
                if not np.isnan(r) and abs(r) >= 0.3:
                    strong.append({
                        "var_a":     cols[i],
                        "var_b":     cols[j],
                        "pearson_r": round(float(r), 4),
                        "strength":  "strong" if abs(r) >= 0.7 else
                                     "moderate" if abs(r) >= 0.5 else "weak",
                    })
        strong.sort(key=lambda x: abs(x["pearson_r"]), reverse=True)

        return {
            "pearson_matrix":  pearson.round(4).to_dict(),
            "spearman_matrix": spearman.round(4).to_dict(),
            "strong_pairs":    strong[:10],
            "n_strong":        sum(1 for x in strong if x["strength"] == "strong"),
        }

    def _regression(self, df: pd.DataFrame, m: Dict[str, Any]) -> Dict[str, Any]:
        from sigmaflow.analysis.regression_analysis import RegressionAnalyzer  # noqa
        target = self._primary_numeric(df, m)
        if not target:
            return {"skipped": True, "reason": "No target column found."}
        ra = RegressionAnalyzer(df, response_col=target)
        return ra.run()

    def _anova(self, df: pd.DataFrame, m: Dict[str, Any]) -> Dict[str, Any]:
        from scipy import stats as sc  # noqa
        cat_cols  = [c for c in (m.get("categorical_columns") or []) if c in df.columns]
        num_cols  = self._numeric_cols(df, m)
        target    = self._primary_numeric(df, m)

        if not cat_cols or not target:
            return {"skipped": True, "reason": "Need categorical column and numeric target."}

        results = {}
        for cat in cat_cols[:3]:
            groups = [g[target].dropna().values for _, g in df.groupby(cat) if len(g) >= 2]
            if len(groups) < 2:
                continue
            try:
                f_stat, p_val = sc.f_oneway(*groups)
                results[cat] = {
                    "factor":      cat,
                    "target":      target,
                    "f_statistic": round(float(f_stat), 4),
                    "p_value":     round(float(p_val), 6),
                    "significant": bool(p_val < 0.05),
                    "n_groups":    len(groups),
                }
            except Exception as exc:
                results[cat] = {"error": str(exc)}

        return {"anova_tests": results, "alpha": 0.05}

    def _root_cause(self, df: pd.DataFrame, m: Dict[str, Any]) -> Dict[str, Any]:
        from sigmaflow.analysis.root_cause_analysis import RootCauseAnalyzer  # noqa
        return RootCauseAnalyzer(df).run()

    def _hypothesis_tests(self, df: pd.DataFrame, m: Dict[str, Any]) -> Dict[str, Any]:
        from sigmaflow.statistics.hypothesis_tests import HypothesisTester  # noqa
        return HypothesisTester(df).run_all()

    def _pareto(self, df: pd.DataFrame, m: Dict[str, Any]) -> Dict[str, Any]:
        from sigmaflow.analysis.pareto_analysis import compute_pareto  # noqa
        # Detect categorical + count columns
        cat_col = next(
            (c for c in df.columns if df[c].dtype == object
             or df[c].nunique() <= 15),
            None
        )
        count_kws = {"count", "freq", "frequency", "defects", "failures",
                     "rejects", "errors", "qty", "occurrences"}
        count_col = next(
            (c for c in df.select_dtypes("number").columns
             if c.lower() in count_kws),
            None
        )
        if not cat_col or not count_col:
            return {"skipped": True, "reason": "Pareto requires a category and count column."}
        return compute_pareto(df, category_col=cat_col, count_col=count_col)

    def _fmea(self, df: pd.DataFrame, m: Dict[str, Any]) -> Dict[str, Any]:
        from sigmaflow.analysis.fmea_analysis import FMEAAnalyzer  # noqa
        sev_col = next((c for c in df.columns if c.lower() == "severity"), None)
        occ_col = next((c for c in df.columns if c.lower() == "occurrence"), None)
        det_col = next((c for c in df.columns if c.lower() == "detection"), None)
        fm_col  = next((c for c in df.columns if "failure" in c.lower()), sev_col)
        if not all([sev_col, occ_col, det_col]):
            return {"skipped": True, "reason": "FMEA requires Severity, Occurrence, Detection columns."}
        return FMEAAnalyzer(df, fm_col, sev_col, occ_col, det_col).run()

    def _nonparametric(self, df: pd.DataFrame, m: Dict[str, Any]) -> Dict[str, Any]:
        # Check if normality failed in measure phase (passed via metadata)
        normality = m.get("_measure_normality") or {}
        non_normal = any(
            isinstance(v, dict) and v.get("normal_distribution") is False
            for v in normality.values()
        )
        if not non_normal and normality:
            return {"skipped": True, "reason": "Data is normal — parametric tests used."}

        from scipy import stats as sc  # noqa
        num_cols = self._numeric_cols(df, m)
        cat_cols = [c for c in (m.get("categorical_columns") or []) if c in df.columns]
        target   = self._primary_numeric(df, m)
        results  = {}

        # Mann-Whitney U (two groups)
        if cat_cols and target:
            groups = df.groupby(cat_cols[0])[target].apply(lambda x: x.dropna().values)
            group_list = [(name, vals) for name, vals in groups.items() if len(vals) >= 2]
            if len(group_list) >= 2:
                g1n, g1v = group_list[0]
                g2n, g2v = group_list[1]
                try:
                    stat, p = sc.mannwhitneyu(g1v, g2v, alternative="two-sided")
                    results["mann_whitney"] = {
                        "group_1": str(g1n), "group_2": str(g2n),
                        "statistic": round(float(stat), 4),
                        "p_value":   round(float(p), 6),
                        "significant": bool(p < 0.05),
                    }
                except Exception as exc:
                    results["mann_whitney"] = {"error": str(exc)}

            # Kruskal-Wallis (all groups)
            if len(group_list) >= 2:
                try:
                    stat, p = sc.kruskal(*[v for _, v in group_list])
                    results["kruskal_wallis"] = {
                        "n_groups":  len(group_list),
                        "H_stat":    round(float(stat), 4),
                        "p_value":   round(float(p), 6),
                        "significant": bool(p < 0.05),
                    }
                except Exception as exc:
                    results["kruskal_wallis"] = {"error": str(exc)}

        return results

    # ── Insights ──────────────────────────────────────────────────────────────

    def _build_insights(self, m: Dict[str, Any]) -> None:
        # Regression
        reg = self.results.get("regression") or {}
        r2  = reg.get("r2")
        if r2 is not None:
            sig_vars = reg.get("significant_vars", [])
            if r2 >= 0.75:
                self.insights.append(
                    f"✅ Regression model explains {r2:.1%} of variance (R² = {r2:.3f}). "
                    f"Key predictors: {', '.join(str(v) for v in sig_vars[:3])}."
                )
            else:
                self.insights.append(
                    f"⚠ Regression model explains only {r2:.1%} of variance (R² = {r2:.3f}). "
                    "Consider additional variables."
                )

        # ANOVA
        anova = self.results.get("anova") or {}
        for factor, res in (anova.get("anova_tests") or {}).items():
            if isinstance(res, dict) and res.get("significant"):
                p = res.get("p_value", 0)
                self.insights.append(
                    f"🔴 ANOVA significant: factor '{factor}' affects the response "
                    f"(p = {p:.4f})."
                )

        # Root cause
        rca = self.results.get("root_cause") or {}
        ranked = rca.get("ranked_variables", [])
        if ranked:
            top = ranked[0]
            self.insights.append(
                f"📌 Top root cause candidate: '{top.get('variable', '?')}' "
                f"(Pearson r = {top.get('pearson_r', 0):+.3f})."
            )
