"""
sigmaflow/core/analysis_planner.py
====================================
AnalysisPlanner — Rule-based analysis plan builder for the DMAIC Engine.

Translates DataProfiler metadata into a concrete per-phase analysis plan
that the DMAICEngine uses to dispatch work to each phase.

Usage
-----
    from sigmaflow.core.analysis_planner import AnalysisPlanner

    planner = AnalysisPlanner()
    plan    = planner.build_plan(metadata)
    # plan["measure"] → ["descriptive_stats", "normality", "capability"]
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ── Analysis identifiers (tokens) ─────────────────────────────────────────────
# These strings are the contract between AnalysisPlanner and each Phase.

# DEFINE phase
DEFINE_SIPOC          = "sipoc"
DEFINE_PROBLEM_STMT   = "problem_statement"
DEFINE_CTQ            = "ctq_identification"

# MEASURE phase
MEASURE_DESCRIPTIVE   = "descriptive_stats"
MEASURE_NORMALITY     = "normality"
MEASURE_CAPABILITY    = "capability"
MEASURE_MSA           = "msa"
MEASURE_DISTRIBUTION  = "distribution_analysis"

# ANALYZE phase
ANALYZE_CORRELATION   = "correlation"
ANALYZE_REGRESSION    = "regression"
ANALYZE_ANOVA         = "anova"
ANALYZE_ROOT_CAUSE    = "root_cause"
ANALYZE_HYPOTHESIS    = "hypothesis_tests"
ANALYZE_PARETO        = "pareto"
ANALYZE_FMEA          = "fmea"
ANALYZE_NONPARAM      = "nonparametric_tests"

# IMPROVE phase
IMPROVE_DOE           = "doe"
IMPROVE_OPTIMIZATION  = "optimization"
IMPROVE_RECOMMENDATIONS = "recommendations"

# CONTROL phase
CONTROL_SPC           = "spc"
CONTROL_TIME_SERIES   = "time_series"
CONTROL_CUSUM         = "cusum"
CONTROL_EWMA          = "ewma"
CONTROL_CONTROL_PLAN  = "control_plan"


class AnalysisPlanner:
    """
    Rule-based planner: maps dataset metadata → DMAIC analysis plan.

    Each rule is a self-contained method that adds tokens to a phase list.
    Rules are evaluated independently — multiple rules can fire at once.

    Parameters
    ----------
    min_rows_regression : int
        Minimum rows required to run regression (default 20).
    min_rows_anova : int
        Minimum rows required to run ANOVA (default 10).
    min_rows_capability : int
        Minimum rows required to run capability analysis (default 25).
    """

    def __init__(
        self,
        min_rows_regression: int  = 20,
        min_rows_anova: int       = 10,
        min_rows_capability: int  = 25,
    ) -> None:
        self.min_rows_regression  = min_rows_regression
        self.min_rows_anova       = min_rows_anova
        self.min_rows_capability  = min_rows_capability

    # ── Public API ────────────────────────────────────────────────────────────

    def build_plan(self, metadata: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Build a DMAIC analysis plan from profiler metadata.

        Parameters
        ----------
        metadata : dict
            Output of :meth:`DataProfiler.profile`.

        Returns
        -------
        dict
            Keys: "define", "measure", "analyze", "improve", "control".
            Values: ordered lists of analysis token strings.
        """
        plan: Dict[str, List[str]] = {
            "define":  [],
            "measure": [],
            "analyze": [],
            "improve": [],
            "control": [],
        }

        self._plan_define(plan, metadata)
        self._plan_measure(plan, metadata)
        self._plan_analyze(plan, metadata)
        self._plan_improve(plan, metadata)
        self._plan_control(plan, metadata)

        # Deduplicate each phase list while preserving order
        for phase in plan:
            seen = set()
            plan[phase] = [x for x in plan[phase] if not (x in seen or seen.add(x))]

        self._log_plan(plan, metadata)
        return plan

    # ── Phase rule sets ───────────────────────────────────────────────────────

    def _plan_define(
        self,
        plan: Dict[str, List[str]],
        m: Dict[str, Any],
    ) -> None:
        """Define phase: always generate SIPOC summary and problem statement."""
        plan["define"].extend([
            DEFINE_SIPOC,
            DEFINE_PROBLEM_STMT,
            DEFINE_CTQ,
        ])

    def _plan_measure(
        self,
        plan: Dict[str, List[str]],
        m: Dict[str, Any],
    ) -> None:
        """
        Measure phase rules:
        - Numeric columns → descriptive stats + normality + distribution
        - Process data + spec limits → capability
        - MSA columns (part/operator/measurement) → MSA
        """
        if m["numeric_columns"]:
            plan["measure"].extend([
                MEASURE_DESCRIPTIVE,
                MEASURE_NORMALITY,
                MEASURE_DISTRIBUTION,
            ])

        # Process capability: need spec limits or clear process signal + enough rows
        if (m["is_process_data"] or m["has_spec_limits"]) and m["n_rows"] >= self.min_rows_capability:
            plan["measure"].append(MEASURE_CAPABILITY)

        # MSA: detect part + operator + measurement columns
        col_lowers = {c.lower() for c in m["columns"]}
        if all(kw in col_lowers for kw in ("part", "operator", "measurement")):
            plan["measure"].append(MEASURE_MSA)

    def _plan_analyze(
        self,
        plan: Dict[str, List[str]],
        m: Dict[str, Any],
    ) -> None:
        """
        Analyze phase rules:
        - Numeric target → correlation + regression
        - Groups + numeric → ANOVA
        - Multiple numeric columns → root cause
        - Categorical + count-like column → Pareto
        - Severity/occurrence/detection columns → FMEA
        - Non-normal or non-parametric trigger → nonparametric_tests
        """
        n_rows       = m["n_rows"]
        has_target   = m["primary_target"] is not None
        num_cols     = m["numeric_columns"]
        cat_cols     = m["categorical_columns"]
        col_lowers   = {c.lower() for c in m["columns"]}

        # Correlation analysis (≥ 2 numeric, any size)
        if len(num_cols) >= 2 and has_target:
            plan["analyze"].append(ANALYZE_CORRELATION)

        # Regression (needs target + ≥ 2 numeric + enough rows)
        if has_target and len(num_cols) >= 2 and n_rows >= self.min_rows_regression:
            plan["analyze"].append(ANALYZE_REGRESSION)

        # ANOVA (groups + numeric response)
        if cat_cols and num_cols and n_rows >= self.min_rows_anova:
            plan["analyze"].append(ANALYZE_ANOVA)

        # Root cause (many numeric columns)
        if len(num_cols) >= 3 and has_target:
            plan["analyze"].append(ANALYZE_ROOT_CAUSE)

        # Hypothesis tests (groups or target available)
        if (cat_cols or has_target) and n_rows >= 10:
            plan["analyze"].append(ANALYZE_HYPOTHESIS)

        # Pareto: categorical col + count/freq column
        count_kws = {"count", "frequency", "freq", "defects", "failures",
                     "rejects", "errors", "occurrences", "qty"}
        has_count_col = any(kw in c.lower() for c in m["columns"] for kw in count_kws)
        if cat_cols and has_count_col:
            plan["analyze"].append(ANALYZE_PARETO)

        # FMEA: severity + occurrence + detection
        if all(kw in col_lowers for kw in ("severity", "occurrence", "detection")):
            plan["analyze"].append(ANALYZE_FMEA)

        # Non-parametric: automatically added; actual trigger at runtime
        if num_cols and n_rows >= 10:
            plan["analyze"].append(ANALYZE_NONPARAM)

    def _plan_improve(
        self,
        plan: Dict[str, List[str]],
        m: Dict[str, Any],
    ) -> None:
        """
        Improve phase rules:
        - Categorical factors + numeric response → DOE
        - Always generate improvement recommendations
        """
        col_lowers = {c.lower() for c in m["columns"]}
        cat_cols   = m["categorical_columns"]

        # DOE: categorical factors + enough rows
        if cat_cols and m["numeric_columns"] and m["n_rows"] >= 4:
            plan["improve"].append(IMPROVE_DOE)

        # Optimization summary (always generated if targets exist)
        if m["primary_target"]:
            plan["improve"].append(IMPROVE_OPTIMIZATION)

        plan["improve"].append(IMPROVE_RECOMMENDATIONS)

    def _plan_control(
        self,
        plan: Dict[str, List[str]],
        m: Dict[str, Any],
    ) -> None:
        """
        Control phase rules:
        - Any numeric data → SPC (XmR)
        - Time column → time series + CUSUM + EWMA
        - Always generate control plan summary
        """
        if m["numeric_columns"]:
            plan["control"].append(CONTROL_SPC)

        if m["is_time_series"]:
            plan["control"].extend([
                CONTROL_TIME_SERIES,
                CONTROL_CUSUM,
                CONTROL_EWMA,
            ])

        plan["control"].append(CONTROL_CONTROL_PLAN)

    # ── Logging ───────────────────────────────────────────────────────────────

    def _log_plan(
        self,
        plan: Dict[str, List[str]],
        m: Dict[str, Any],
    ) -> None:
        total = sum(len(v) for v in plan.values())
        logger.info(
            "AnalysisPlanner: %d analyses planned across 5 DMAIC phases "
            "(dataset: %d rows × %d cols, target: %s)",
            total, m["n_rows"], m["n_columns"], m.get("primary_target"),
        )
        for phase, items in plan.items():
            if items:
                logger.debug("  %-8s → %s", phase, ", ".join(items))

    # ── Introspection ─────────────────────────────────────────────────────────

    def describe_plan(self, plan: Dict[str, List[str]]) -> str:
        """Return a human-readable summary of the analysis plan."""
        lines = ["DMAIC Analysis Plan", "=" * 40]
        for phase, analyses in plan.items():
            if analyses:
                lines.append(f"\n{phase.upper()}")
                for a in analyses:
                    lines.append(f"  • {a.replace('_', ' ').title()}")
            else:
                lines.append(f"\n{phase.upper()}\n  (no analyses planned)")
        return "\n".join(lines)
