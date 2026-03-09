"""
sigmaflow/dmaic/define/phase.py
================================
Define Phase — SigmaFlow DMAIC Engine.

Analyses performed:
    • sipoc             — SIPOC summary auto-generated from dataset structure
    • problem_statement — Auto-drafted problem statement from metadata
    • ctq_identification — Identify Critical-to-Quality characteristics
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from sigmaflow.dmaic.base_phase import BasePhase

logger = logging.getLogger(__name__)


class DefinePhase(BasePhase):
    """
    DMAIC Define Phase.

    Generates project framing artefacts automatically from the dataset
    and profiler metadata:

    - **SIPOC summary** — lists Suppliers, Inputs, Process steps, Outputs,
      Customers derived from column names and data types.
    - **Problem statement** — structured description of the process and
      the quality problem indicated by the data.
    - **CTQ identification** — flags the Critical-to-Quality variables
      based on target candidates and strong correlations.
    """

    phase_name = "define"

    # ── run() ─────────────────────────────────────────────────────────────────

    def run(
        self,
        data:          pd.DataFrame,
        analysis_list: List[str],
        metadata:      Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute Define phase analyses.

        Parameters
        ----------
        data : pd.DataFrame
        analysis_list : list[str]
        metadata : dict, optional

        Returns
        -------
        dict
        """
        logger.info("[Define] Starting Define phase (%d analyses)", len(analysis_list))
        m = metadata or {}

        if "sipoc" in analysis_list:
            self.results["sipoc"] = self._safe_run("sipoc", self._build_sipoc, data, m)

        if "problem_statement" in analysis_list:
            self.results["problem_statement"] = self._safe_run(
                "problem_statement", self._build_problem_statement, data, m
            )

        if "ctq_identification" in analysis_list:
            self.results["ctq"] = self._safe_run(
                "ctq_identification", self._identify_ctq, m
            )

        self._build_insights(m)
        return self._phase_result()

    # ── Analysis implementations ──────────────────────────────────────────────

    def _build_sipoc(self, df: pd.DataFrame, m: Dict[str, Any]) -> Dict[str, Any]:
        """Auto-generate SIPOC from dataset structure."""
        num_cols  = m.get("numeric_columns", list(df.select_dtypes("number").columns))
        cat_cols  = m.get("categorical_columns", [])
        time_col  = m.get("time_column")
        target    = m.get("primary_target", "Quality Output")

        # Heuristic mappings
        process_steps = ["Data Collection", "Process Execution", "Quality Inspection"]
        if time_col:
            process_steps.insert(0, "Time-sequenced Operation")

        suppliers = (
            [str(c).replace("_", " ").title() for c in cat_cols[:3]]
            or ["Process Operator", "Equipment", "Materials"]
        )
        inputs = (
            [str(c).replace("_", " ").title() for c in num_cols[:4]]
            or ["Process Variables"]
        )
        outputs  = [str(target).replace("_", " ").title()] if target else ["Process Output"]
        customers = ["Internal Quality Team", "End Customer", "Downstream Process"]

        return {
            "suppliers":     suppliers,
            "inputs":        inputs,
            "process_steps": process_steps,
            "outputs":       outputs,
            "customers":     customers,
        }

    def _build_problem_statement(
        self,
        df: pd.DataFrame,
        m: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Auto-draft a problem statement from metadata."""
        n_rows  = m.get("n_rows", len(df))
        n_cols  = m.get("n_columns", len(df.columns))
        target  = m.get("primary_target", "the primary quality characteristic")
        missing = m.get("missing_pct", 0)
        quality = m.get("data_quality_score", 100)

        issues = []
        if missing > 5:
            issues.append(f"{missing:.1f}% of data is missing")
        if quality < 70:
            issues.append("data quality score is below acceptable threshold")
        if m.get("strong_correlations"):
            a, b, r = m["strong_correlations"][0]
            issues.append(
                f"strong correlation (r={r:+.2f}) detected between "
                f"'{a}' and '{b}'"
            )

        summary = (
            f"Dataset contains {n_rows} observations across {n_cols} variables. "
            f"The primary quality characteristic is '{target}'. "
            + (
                "Issues identified: " + "; ".join(issues) + "."
                if issues
                else "No critical data quality issues detected."
            )
        )

        return {
            "dataset_summary": summary,
            "n_rows": n_rows,
            "n_columns": n_cols,
            "primary_target": target,
            "identified_issues": issues,
            "data_quality_score": quality,
        }

    def _identify_ctq(self, m: Dict[str, Any]) -> Dict[str, Any]:
        """Identify Critical-to-Quality variables from profiler metadata."""
        candidates = m.get("target_candidates", [])
        strong     = m.get("strong_correlations", [])
        spec_cols  = m.get("spec_columns", [])

        # Build CTQ list: targets + strongly correlated inputs
        ctq_variables = list(candidates)
        drivers = []
        for col_a, col_b, r in strong[:5]:
            target = m.get("primary_target")
            if target and col_a == target:
                drivers.append({"variable": col_b, "correlation": r, "role": "driver"})
            elif target and col_b == target:
                drivers.append({"variable": col_a, "correlation": r, "role": "driver"})

        return {
            "ctq_variables":    ctq_variables,
            "key_drivers":      drivers,
            "spec_limit_cols":  spec_cols,
            "n_ctq":            len(ctq_variables),
        }

    # ── Insights ──────────────────────────────────────────────────────────────

    def _build_insights(self, m: Dict[str, Any]) -> None:
        target = m.get("primary_target")
        if target:
            self.insights.append(
                f"✅ Primary quality characteristic identified: '{target}'."
            )
        if m.get("missing_values"):
            pct = m.get("missing_pct", 0)
            self.insights.append(
                f"⚠ Missing data detected ({pct:.1f}%). "
                "Address in Measure phase before analysis."
            )
        drivers = (self.results.get("ctq") or {}).get("key_drivers", [])
        if drivers:
            top = drivers[0]
            self.insights.append(
                f"📌 Top CTQ driver: '{top['variable']}' "
                f"(r = {top['correlation']:+.3f})."
            )
