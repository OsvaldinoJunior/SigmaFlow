"""
sigmaflow/core/problem_detector.py
====================================
ProblemDetector — Automatic statistical problem identification.

Analyses DataProfiler metadata and classifies the dataset into one or more
statistical problem types. Each problem type maps to a specific family of
analytical techniques in the DMAIC pipeline.

Problem taxonomy
----------------
spc          : Statistical Process Control (time-series / sequential data)
capability   : Process Capability (spec limits or clear process signal)
regression   : Regression / correlation (many numeric predictors)
anova        : ANOVA / group comparison (categorical + numeric)
pareto       : Pareto / defect classification (categorical + count)
msa          : Measurement System Analysis (part/operator/measurement)
fmea         : Failure Mode & Effects Analysis (severity/occurrence/detection)
doe          : Design of Experiments (categorical factors + numeric response)
exploratory  : Exploratory data analysis (fallback for unclassified datasets)

Usage
-----
    from sigmaflow.core.data_profiler  import DataProfiler
    from sigmaflow.core.problem_detector import ProblemDetector

    profiler = DataProfiler()
    metadata = profiler.profile(df)

    detector = ProblemDetector()
    result   = detector.detect(metadata)

    print(result.problems)          # ['spc', 'capability', 'regression']
    print(result.primary_problem)   # 'spc'
    print(result.response_variable) # 'thickness'
    print(result.feature_variables) # ['temperature', 'pressure', 'speed']
    print(result.summary())         # human-readable log
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Keywords ──────────────────────────────────────────────────────────────────

_RESPONSE_KEYWORDS = [
    "defect", "defects", "failure", "failures", "reject", "rejects",
    "nonconform", "error", "errors", "output", "yield", "quality",
    "response", "result", "target", "y", "outcome", "measure", "kpi",
    "cycle_time", "lead_time", "throughput", "scrap", "waste",
]

_COUNT_KEYWORDS = [
    "count", "frequency", "freq", "defects", "failures", "rejects",
    "errors", "occurrences", "qty", "quantity", "total",
]

_MSA_REQUIRED   = {"part", "operator", "measurement"}
_FMEA_REQUIRED  = {"severity", "occurrence", "detection"}


# ── Detection result dataclass ────────────────────────────────────────────────

@dataclass
class DetectionResult:
    """
    Result of automatic problem detection.

    Attributes
    ----------
    problems : list[str]
        Ordered list of detected problem types (most specific first).
    primary_problem : str
        The single most representative problem type.
    response_variable : str | None
        Auto-detected response / quality variable.
    feature_variables : list[str]
        Candidate predictor / input variables.
    confidence : dict[str, float]
        Confidence score (0–1) per detected problem.
    rationale : dict[str, list[str]]
        Human-readable rules that fired for each problem.
    metadata_snapshot : dict
        Key profiler metrics used during detection.
    """
    problems:          List[str]       = field(default_factory=list)
    primary_problem:   str             = "exploratory"
    response_variable: Optional[str]   = None
    feature_variables: List[str]       = field(default_factory=list)
    confidence:        Dict[str, float] = field(default_factory=dict)
    rationale:         Dict[str, List[str]] = field(default_factory=dict)
    metadata_snapshot: Dict[str, Any]  = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "  SigmaFlow — Problem Detection Summary",
            "=" * 60,
            f"  Problems detected  : {', '.join(self.problems)}",
            f"  Primary problem    : {self.primary_problem.upper()}",
            f"  Response variable  : {self.response_variable or '(not detected)'}",
            f"  Feature variables  : {', '.join(self.feature_variables[:6]) or '(none)'}",
            "",
            "  Rationale:",
        ]
        for prob, reasons in self.rationale.items():
            lines.append(f"    [{prob.upper()}]")
            for r in reasons:
                lines.append(f"      • {r}")
        lines.append("=" * 60)
        return "\n".join(lines)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "problems":          self.problems,
            "primary_problem":   self.primary_problem,
            "response_variable": self.response_variable,
            "feature_variables": self.feature_variables,
            "confidence":        self.confidence,
            "rationale":         self.rationale,
        }


# ── Main detector ─────────────────────────────────────────────────────────────

class ProblemDetector:
    """
    Automatic statistical problem type detector.

    Evaluates a set of detection rules against DataProfiler metadata and
    returns a :class:`DetectionResult` with ordered problems, confidence
    scores, and rationale.

    Parameters
    ----------
    min_rows_spc : int
        Minimum observations to trigger SPC detection (default 15).
    min_rows_regression : int
        Minimum observations for regression (default 20).
    min_rows_capability : int
        Minimum observations for capability (default 25).
    min_rows_anova : int
        Minimum observations for ANOVA (default 10).
    """

    # Priority order for primary_problem selection
    _PRIORITY = [
        "msa", "fmea", "capability", "spc", "doe",
        "regression", "anova", "pareto", "exploratory",
    ]

    def __init__(
        self,
        min_rows_spc:        int = 15,
        min_rows_regression: int = 20,
        min_rows_capability: int = 25,
        min_rows_anova:      int = 10,
    ) -> None:
        self.min_rows_spc        = min_rows_spc
        self.min_rows_regression = min_rows_regression
        self.min_rows_capability = min_rows_capability
        self.min_rows_anova      = min_rows_anova

    # ── Public API ────────────────────────────────────────────────────────────

    def detect(self, metadata: Dict[str, Any]) -> DetectionResult:
        """
        Run all detection rules against DataProfiler metadata.

        Parameters
        ----------
        metadata : dict
            Output of :meth:`~sigmaflow.core.data_profiler.DataProfiler.profile`.

        Returns
        -------
        DetectionResult
        """
        n_rows   = metadata.get("n_rows", 0)
        n_num    = len(metadata.get("numeric_columns", []))
        n_cat    = len(metadata.get("categorical_columns", []))
        has_time = metadata.get("is_time_series", False)
        has_spec = metadata.get("has_spec_limits", False)
        col_set  = {c.lower() for c in metadata.get("columns", [])}

        problems:   Dict[str, List[str]] = {}
        confidence: Dict[str, float]     = {}

        # ── Rule: MSA ────────────────────────────────────────────────────────
        if _MSA_REQUIRED.issubset(col_set):
            reasons = [
                "Columns 'part', 'operator', 'measurement' all present",
                "Gauge R&R / MSA analysis applicable",
            ]
            problems["msa"]   = reasons
            confidence["msa"] = 1.0

        # ── Rule: FMEA ───────────────────────────────────────────────────────
        if _FMEA_REQUIRED.issubset(col_set):
            reasons = [
                "Columns 'severity', 'occurrence', 'detection' all present",
                "FMEA / RPN analysis applicable",
            ]
            problems["fmea"]   = reasons
            confidence["fmea"] = 1.0

        # ── Rule: Process Capability ─────────────────────────────────────────
        cap_reasons = []
        cap_conf    = 0.0
        if has_spec:
            cap_reasons.append("Specification limit columns (USL/LSL) detected")
            cap_conf += 0.6
        if metadata.get("is_process_data", False) and n_rows >= self.min_rows_capability:
            cap_reasons.append(f"Process data detected with {n_rows} observations (>= {self.min_rows_capability})")
            cap_conf = min(cap_conf + 0.4, 1.0)
        if cap_reasons:
            problems["capability"]   = cap_reasons
            confidence["capability"] = round(cap_conf, 2)

        # ── Rule: SPC ────────────────────────────────────────────────────────
        spc_reasons = []
        spc_conf    = 0.0
        if has_time:
            spc_reasons.append("Time / sequence column detected — time-series structure")
            spc_conf += 0.5
        if n_num >= 1 and n_rows >= self.min_rows_spc:
            spc_reasons.append(f"{n_num} numeric column(s) with {n_rows} rows — SPC charts viable")
            spc_conf += 0.3
        if metadata.get("is_process_data", False):
            spc_reasons.append("Dataset heuristically classified as process data")
            spc_conf += 0.2
        if spc_reasons:
            problems["spc"]   = spc_reasons
            confidence["spc"] = round(min(spc_conf, 1.0), 2)

        # ── Rule: Regression ─────────────────────────────────────────────────
        reg_reasons = []
        reg_conf    = 0.0
        if n_num >= 3 and n_rows >= self.min_rows_regression:
            reg_reasons.append(f"{n_num} numeric columns with {n_rows} rows — regression feasible")
            reg_conf += 0.5
        strong_corrs = metadata.get("strong_correlations", [])
        if strong_corrs:
            reg_reasons.append(f"{len(strong_corrs)} strong correlation(s) detected (|r| >= 0.5)")
            reg_conf += 0.4
        if reg_reasons:
            problems["regression"]   = reg_reasons
            confidence["regression"] = round(min(reg_conf, 1.0), 2)

        # ── Rule: ANOVA ───────────────────────────────────────────────────────
        if n_cat >= 1 and n_num >= 1 and n_rows >= self.min_rows_anova:
            reasons = [
                f"{n_cat} categorical + {n_num} numeric column(s) — group comparison viable",
                f"{n_rows} observations (>= {self.min_rows_anova})",
            ]
            problems["anova"]   = reasons
            confidence["anova"] = round(min(0.4 + n_cat * 0.1 + n_num * 0.05, 1.0), 2)

        # ── Rule: Pareto ──────────────────────────────────────────────────────
        has_count = any(kw in c for c in col_set for kw in _COUNT_KEYWORDS)
        if n_cat >= 1 and has_count:
            reasons = [
                f"{n_cat} categorical column(s) present",
                "Count / frequency column detected — Pareto analysis applicable",
            ]
            problems["pareto"]   = reasons
            confidence["pareto"] = 0.8

        # ── Rule: DOE ────────────────────────────────────────────────────────
        if n_cat >= 1 and n_num >= 1 and n_rows >= 4:
            reasons = [
                f"{n_cat} categorical factor(s) + {n_num} numeric response(s)",
                "Factorial experimental structure possible",
            ]
            problems["doe"]   = reasons
            confidence["doe"] = round(min(0.3 + n_cat * 0.15, 0.85), 2)

        # ── Fallback ──────────────────────────────────────────────────────────
        if not problems:
            problems["exploratory"] = [
                "No specific problem type detected",
                "Running exploratory analysis (descriptive statistics + normality)",
            ]
            confidence["exploratory"] = 0.5

        # ── Order & select primary problem ────────────────────────────────────
        ordered = [p for p in self._PRIORITY if p in problems]

        # Response variable detection
        response, features = self.detect_response_variable(
            metadata.get("columns", []),
            metadata.get("numeric_columns", []),
            metadata.get("primary_target"),
            metadata.get("strong_correlations", []),
        )

        result = DetectionResult(
            problems          = ordered,
            primary_problem   = ordered[0] if ordered else "exploratory",
            response_variable = response,
            feature_variables = features,
            confidence        = {p: confidence[p] for p in ordered},
            rationale         = {p: problems[p] for p in ordered},
            metadata_snapshot = {
                "n_rows":  n_rows,
                "n_num":   n_num,
                "n_cat":   n_cat,
                "has_time": has_time,
                "has_spec": has_spec,
            },
        )

        self._log(result)
        return result

    # ── Response variable detection ───────────────────────────────────────────

    def detect_response_variable(
        self,
        all_columns:   List[str],
        numeric_cols:  List[str],
        primary_hint:  Optional[str] = None,
        correlations:  Optional[List] = None,
    ) -> tuple[Optional[str], List[str]]:
        """
        Identify the response (Y) variable and feature (X) variables.

        Detection priority
        ------------------
        1. primary_hint from DataProfiler (if provided)
        2. Column name matching _RESPONSE_KEYWORDS
        3. Column with highest variance (from correlations)
        4. Last numeric column (convention fallback)

        Returns
        -------
        (response_variable, feature_variables)
        """
        response = None

        # Priority 1: DataProfiler hint
        if primary_hint and primary_hint in all_columns:
            response = primary_hint
            logger.debug("Response variable from DataProfiler hint: '%s'", response)

        # Priority 2: keyword match in column names
        if response is None:
            for col in numeric_cols:
                if any(kw in col.lower() for kw in _RESPONSE_KEYWORDS):
                    response = col
                    logger.debug("Response variable by keyword: '%s'", response)
                    break

        # Priority 3: column most correlated with others (hub in correlation network)
        if response is None and correlations:
            from collections import Counter
            hub_counts: Counter = Counter()
            for a, b, r in correlations:
                if abs(r) >= 0.5:
                    hub_counts[a] += 1
                    hub_counts[b] += 1
            if hub_counts:
                response = hub_counts.most_common(1)[0][0]
                logger.debug("Response variable by correlation hub: '%s'", response)

        # Priority 4: last numeric column
        if response is None and numeric_cols:
            response = numeric_cols[-1]
            logger.debug("Response variable fallback (last numeric): '%s'", response)

        features = [c for c in numeric_cols if c != response]

        return response, features

    # ── Logging ───────────────────────────────────────────────────────────────

    def _log(self, result: DetectionResult) -> None:
        logger.info(
            "ProblemDetector: detected %d problem(s) — %s | "
            "primary=%s | response='%s' | features=%s",
            len(result.problems),
            result.problems,
            result.primary_problem,
            result.response_variable,
            result.feature_variables[:4],
        )
        print(f"\n  🔍 Detected problems   : {', '.join(p.upper() for p in result.problems)}")
        print(f"  🎯 Primary problem     : {result.primary_problem.upper()}")
        print(f"  📊 Response variable   : {result.response_variable or '(auto)'}")
        if result.feature_variables:
            feats = result.feature_variables[:5]
            more  = len(result.feature_variables) - len(feats)
            extra = f" (+{more} more)" if more > 0 else ""
            print(f"  📐 Feature variables   : {', '.join(feats)}{extra}")
