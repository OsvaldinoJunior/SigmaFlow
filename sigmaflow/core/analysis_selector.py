"""
sigmaflow/core/analysis_selector.py
=====================================
AnalysisSelector — Maps detected statistical problems to concrete analyses.

Takes the output of :class:`~sigmaflow.core.problem_detector.ProblemDetector`
and returns an ordered list of analysis tokens that the Engine and DMAIC phases
should execute.

This is the bridge between *what kind of problem* was detected and *which
specific tools* should be applied in each DMAIC phase.

Usage
-----
    from sigmaflow.core.problem_detector  import ProblemDetector
    from sigmaflow.core.analysis_selector import AnalysisSelector

    detection = ProblemDetector().detect(metadata)
    selector  = AnalysisSelector()
    plan      = selector.select(detection)

    # plan["measure"]  → ["descriptive_stats", "normality", "capability"]
    # plan["analyze"]  → ["spc_analysis", "regression", "correlation"]
    # plan["control"]  → ["control_charts", "cusum_chart", "ewma_chart"]

    print(selector.describe(plan))
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Analysis token catalogue ──────────────────────────────────────────────────
# These strings are the stable contract between AnalysisSelector and
# each DMAIC phase / Engine dispatch method.

# MEASURE
DESCRIPTIVE_STATS   = "descriptive_stats"
NORMALITY_TESTS     = "normality"
CAPABILITY          = "capability"
DISTRIBUTION        = "distribution_analysis"
MSA                 = "msa"

# ANALYZE
CORRELATION         = "correlation"
REGRESSION          = "regression"
ANOVA               = "anova"
ROOT_CAUSE          = "root_cause"
HYPOTHESIS_TESTS    = "hypothesis_tests"
PARETO              = "pareto"
FMEA                = "fmea"
NONPARAMETRIC       = "nonparametric_tests"

# IMPROVE
DOE                 = "doe"
OPTIMIZATION        = "optimization"
RECOMMENDATIONS     = "recommendations"

# CONTROL
SPC                 = "spc"
CONTROL_CHARTS      = "control_charts"
CUSUM               = "cusum_chart"
EWMA                = "ewma_chart"
XBAR_R              = "xbar_r_chart"
TIME_SERIES         = "time_series"
CONTROL_PLAN        = "control_plan"


# ── Core mapping: problem → {phase: [analyses]} ───────────────────────────────

_PROBLEM_MAP: Dict[str, Dict[str, List[str]]] = {

    "spc": {
        "measure": [DESCRIPTIVE_STATS, NORMALITY_TESTS, DISTRIBUTION],
        "analyze": [CORRELATION, HYPOTHESIS_TESTS],
        "control": [SPC, CONTROL_CHARTS, CUSUM, EWMA, TIME_SERIES, CONTROL_PLAN],
    },

    "capability": {
        "measure": [DESCRIPTIVE_STATS, NORMALITY_TESTS, CAPABILITY, DISTRIBUTION],
        "analyze": [HYPOTHESIS_TESTS, NONPARAMETRIC],
        "control": [SPC, CONTROL_CHARTS, CONTROL_PLAN],
    },

    "regression": {
        "measure": [DESCRIPTIVE_STATS, NORMALITY_TESTS, DISTRIBUTION],
        "analyze": [CORRELATION, REGRESSION, ROOT_CAUSE, HYPOTHESIS_TESTS],
        "improve": [OPTIMIZATION, RECOMMENDATIONS],
        "control": [SPC, CONTROL_PLAN],
    },

    "anova": {
        "measure": [DESCRIPTIVE_STATS, NORMALITY_TESTS],
        "analyze": [ANOVA, HYPOTHESIS_TESTS, NONPARAMETRIC, CORRELATION],
        "improve": [DOE, RECOMMENDATIONS],
        "control": [CONTROL_PLAN],
    },

    "pareto": {
        "measure": [DESCRIPTIVE_STATS],
        "analyze": [PARETO, ROOT_CAUSE, HYPOTHESIS_TESTS],
        "improve": [RECOMMENDATIONS],
        "control": [CONTROL_PLAN],
    },

    "msa": {
        "measure": [DESCRIPTIVE_STATS, NORMALITY_TESTS, MSA],
        "analyze": [HYPOTHESIS_TESTS, CORRELATION],
        "control": [CONTROL_PLAN],
    },

    "fmea": {
        "measure": [DESCRIPTIVE_STATS],
        "analyze": [FMEA, PARETO, ROOT_CAUSE],
        "improve": [RECOMMENDATIONS],
        "control": [CONTROL_PLAN],
    },

    "doe": {
        "measure": [DESCRIPTIVE_STATS, NORMALITY_TESTS],
        "analyze": [ANOVA, CORRELATION, REGRESSION, HYPOTHESIS_TESTS],
        "improve": [DOE, OPTIMIZATION, RECOMMENDATIONS],
        "control": [SPC, CONTROL_PLAN],
    },

    "exploratory": {
        "measure": [DESCRIPTIVE_STATS, NORMALITY_TESTS, DISTRIBUTION],
        "analyze": [CORRELATION, HYPOTHESIS_TESTS, NONPARAMETRIC],
        "improve": [RECOMMENDATIONS],
        "control": [CONTROL_PLAN],
    },
}

# Always included in every plan
_ALWAYS_DEFINE  = ["sipoc", "problem_statement", "ctq_identification"]
_ALWAYS_IMPROVE = [RECOMMENDATIONS]
_ALWAYS_CONTROL = [CONTROL_PLAN]


# ── Selector class ────────────────────────────────────────────────────────────

class AnalysisSelector:
    """
    Maps a :class:`~sigmaflow.core.problem_detector.DetectionResult`
    (or a plain list of problem strings) to a DMAIC-phase analysis plan.

    The plan is a dict with phase keys mapping to ordered, de-duplicated
    lists of analysis token strings.

    Parameters
    ----------
    add_xbar_r_threshold : int
        Minimum rows to automatically add X-bar/R chart (default 25).
    """

    def __init__(self, add_xbar_r_threshold: int = 25) -> None:
        self.add_xbar_r_threshold = add_xbar_r_threshold

    # ── Public API ────────────────────────────────────────────────────────────

    def select(
        self,
        detection_or_problems,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[str]]:
        """
        Build a DMAIC analysis plan from detected problems.

        Parameters
        ----------
        detection_or_problems : DetectionResult | list[str]
            Either a :class:`DetectionResult` or a plain list of problem
            type strings (e.g. ``["spc", "capability"]``).
        metadata : dict, optional
            DataProfiler metadata for context-sensitive refinements.

        Returns
        -------
        dict
            Keys: "define", "measure", "analyze", "improve", "control".
            Values: ordered, de-duplicated analysis token lists.
        """
        # Accept either DetectionResult or plain list
        if hasattr(detection_or_problems, "problems"):
            problems  = detection_or_problems.problems
            n_rows    = detection_or_problems.metadata_snapshot.get("n_rows", 0)
            has_time  = detection_or_problems.metadata_snapshot.get("has_time", False)
        else:
            problems = list(detection_or_problems)
            n_rows   = (metadata or {}).get("n_rows", 0)
            has_time = (metadata or {}).get("is_time_series", False)

        plan: Dict[str, List[str]] = {
            "define":  list(_ALWAYS_DEFINE),
            "measure": [],
            "analyze": [],
            "improve": [],
            "control": [],
        }

        # Merge per-problem mappings
        for problem in problems:
            mapping = _PROBLEM_MAP.get(problem, {})
            for phase, tokens in mapping.items():
                plan[phase].extend(tokens)

        # Context-sensitive additions
        if has_time and "spc" in problems:
            if n_rows >= self.add_xbar_r_threshold:
                plan["control"].append(XBAR_R)

        # Always ensure improve/control have the base items
        plan["improve"].extend(_ALWAYS_IMPROVE)
        plan["control"].extend(_ALWAYS_CONTROL)

        # De-duplicate each phase while preserving order
        for phase in plan:
            seen: set = set()
            plan[phase] = [
                x for x in plan[phase]
                if not (x in seen or seen.add(x))  # type: ignore[func-returns-value]
            ]

        self._log(plan, problems)
        return plan

    def select_flat(self, detection_or_problems, **kwargs) -> List[str]:
        """
        Return a flat, de-duplicated list of all selected analyses
        (ignoring DMAIC phases).
        """
        plan = self.select(detection_or_problems, **kwargs)
        all_tokens = []
        seen: set = set()
        for tokens in plan.values():
            for t in tokens:
                if t not in seen:
                    seen.add(t)
                    all_tokens.append(t)
        return all_tokens

    def describe(self, plan: Dict[str, List[str]]) -> str:
        """Return a human-readable plan summary."""
        lines = ["  Selected Analyses (DMAIC):"]
        for phase, tokens in plan.items():
            if tokens:
                labels = ", ".join(t.replace("_", " ").title() for t in tokens)
                lines.append(f"    {phase.upper():<10} → {labels}")
        return "\n".join(lines)

    # ── Logging ───────────────────────────────────────────────────────────────

    def _log(
        self,
        plan:     Dict[str, List[str]],
        problems: List[str],
    ) -> None:
        total = sum(len(v) for v in plan.values())
        logger.info(
            "AnalysisSelector: %d analyses selected for problems=%s",
            total, problems,
        )
        for phase, tokens in plan.items():
            if tokens:
                logger.debug("  %-8s → %s", phase, ", ".join(tokens))

        flat = [t for tokens in plan.values() for t in tokens]
        print(f"  📋 Analyses selected   : {len(flat)} total across 5 DMAIC phases")
