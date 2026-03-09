"""
sigmaflow/dmaic/improve/phase.py
==================================
Improve Phase — SigmaFlow DMAIC Engine.

Analyses performed (depending on analysis_list):
    • doe              — Design of Experiments (factorial analysis + ANOVA)
    • optimization     — Optimal operating window for key factors
    • recommendations  — Data-driven improvement recommendations
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from sigmaflow.dmaic.base_phase import BasePhase

logger = logging.getLogger(__name__)


class ImprovePhase(BasePhase):
    """
    DMAIC Improve Phase.

    Generates data-driven improvement solutions:
    - Design of Experiments analysis to identify optimal factor settings
    - Optimization summary: factor ranges that minimise defects / maximise yield
    - Prioritised recommendations ranked by expected impact
    """

    phase_name = "improve"

    def run(
        self,
        data:          pd.DataFrame,
        analysis_list: List[str],
        metadata:      Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        logger.info("[Improve] Starting Improve phase (%d analyses)", len(analysis_list))
        m = metadata or {}

        if "doe" in analysis_list:
            self.results["doe"] = self._safe_run("doe", self._doe, data, m)

        if "optimization" in analysis_list:
            self.results["optimization"] = self._safe_run(
                "optimization", self._optimization, data, m
            )

        if "recommendations" in analysis_list:
            self.results["recommendations"] = self._safe_run(
                "recommendations", self._recommendations, data, m
            )

        self._build_insights()
        return self._phase_result()

    # ── Analyses ──────────────────────────────────────────────────────────────

    def _doe(self, df: pd.DataFrame, m: Dict[str, Any]) -> Dict[str, Any]:
        from sigmaflow.analysis.doe_analysis import DOEAnalyzer  # noqa
        cat_cols = [
            c for c in (m.get("categorical_columns") or [])
            if c in df.columns
        ]
        if not cat_cols or not self._numeric_cols(df, m):
            return {"skipped": True, "reason": "DOE requires categorical factors and numeric response."}

        doe = DOEAnalyzer(df, factor_cols=cat_cols[:3])
        return doe.run()

    def _optimization(
        self,
        df: pd.DataFrame,
        m: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Find the operating window (factor ranges) that produces the best
        outcome for the target variable.

        Strategy:
        1. Split numeric predictors into quintiles.
        2. Find the quintile of each predictor where the target mean is best.
        3. Report recommended factor levels.
        """
        target   = self._primary_numeric(df, m)
        num_cols = self._numeric_cols(df, m)
        if not target or len(num_cols) < 2:
            return {"skipped": True, "reason": "Need a numeric target and ≥ 2 predictors."}

        predictors = [c for c in num_cols if c != target]
        target_col = df[target].dropna()
        direction  = "minimize" if any(
            kw in target.lower()
            for kw in ("defect", "error", "failure", "reject", "loss")
        ) else "maximize"

        recommendations: List[Dict[str, Any]] = []
        for pred in predictors[:6]:
            try:
                combined = pd.concat([df[pred], df[target]], axis=1).dropna()
                if len(combined) < 10:
                    continue
                combined["quintile"] = pd.qcut(combined[pred], 5, duplicates="drop", labels=False)
                grouped = combined.groupby("quintile")[target].mean()
                best_q  = int(grouped.idxmin() if direction == "minimize" else grouped.idxmax())
                mask    = combined["quintile"] == best_q
                best_range = combined.loc[mask, pred]
                recommendations.append({
                    "predictor":   pred,
                    "direction":   direction,
                    "best_quintile": best_q,
                    "recommended_min": round(float(best_range.min()), 4),
                    "recommended_max": round(float(best_range.max()), 4),
                    "expected_target": round(float(grouped[best_q]), 4),
                })
            except Exception as exc:
                logger.debug("Optimization skipped for '%s': %s", pred, exc)

        return {
            "target":          target,
            "direction":       direction,
            "factor_settings": recommendations,
            "n_factors":       len(recommendations),
        }

    def _recommendations(
        self,
        df: pd.DataFrame,
        m: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build a prioritised list of improvement recommendations from
        all available metadata (profiler + previous phase results).
        """
        recs: List[Dict[str, Any]] = []
        priority = 1

        # Missing data
        if m.get("missing_pct", 0) > 5:
            recs.append({
                "priority":    priority,
                "category":    "Data Quality",
                "action":      f"Address {m['missing_pct']:.1f}% missing data — impute or collect.",
                "expected_impact": "High",
            })
            priority += 1

        # Strong correlations → potential levers
        for col_a, col_b, r in (m.get("strong_correlations") or [])[:3]:
            target = m.get("primary_target")
            if target and (col_a == target or col_b == target):
                driver = col_b if col_a == target else col_a
                recs.append({
                    "priority":    priority,
                    "category":    "Process Variable",
                    "action":      f"Control '{driver}' (r={r:+.2f} with '{target}') to improve output.",
                    "expected_impact": "High" if abs(r) >= 0.7 else "Medium",
                })
                priority += 1

        # Low capability
        cap = (m.get("_measure_capability") or {})
        cpk = cap.get("Cpk")
        if cpk is not None and cpk < 1.33:
            recs.append({
                "priority":    priority,
                "category":    "Process Capability",
                "action":      f"Improve process capability (Cpk = {cpk:.3f}). "
                               "Reduce variation or re-centre the process mean.",
                "expected_impact": "High" if cpk < 1.0 else "Medium",
            })
            priority += 1

        # Default recommendation
        if not recs:
            recs.append({
                "priority":    1,
                "category":    "Monitoring",
                "action":      "Implement ongoing SPC monitoring for key process variables.",
                "expected_impact": "Medium",
            })

        return {"recommendations": recs, "n_recommendations": len(recs)}

    # ── Insights ──────────────────────────────────────────────────────────────

    def _build_insights(self) -> None:
        doe = self.results.get("doe") or {}
        if doe.get("significant_factors"):
            factors = doe["significant_factors"]
            self.insights.append(
                f"🔬 DOE: {len(factors)} significant factor(s) identified: "
                f"{', '.join(str(f) for f in factors[:3])}."
            )

        opt = self.results.get("optimization") or {}
        settings = opt.get("factor_settings") or []
        if settings:
            self.insights.append(
                f"✅ Optimization: {len(settings)} factor(s) with recommended operating windows."
            )

        recs = (self.results.get("recommendations") or {}).get("recommendations") or []
        if recs:
            self.insights.append(
                f"📋 {len(recs)} improvement recommendation(s) generated. "
                f"Top priority: {recs[0]['action'][:80]}…"
            )
