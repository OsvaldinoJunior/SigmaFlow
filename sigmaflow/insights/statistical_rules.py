"""
sigmaflow/insights/statistical_rules.py
=========================================
Concrete implementations of statistical rule sets.

Western Electric Rules
----------------------
Originally published by Western Electric Co. (1956) as the Statistical
Quality Control Handbook. These rules detect non-random patterns in
time-ordered data, indicating a process may be out of statistical control.

Rule 1: Any single point outside 3σ limits
Rule 2: Nine consecutive points on the same side of the center line
Rule 3: Six consecutive points trending upward or downward
Rule 4: Fourteen consecutive points alternating up and down

Capability Rules
----------------
Evaluate Cp and Cpk indices against Six Sigma thresholds.

Trend Rules
-----------
Interpret Spearman/Mann-Kendall trend test results.

Each rule class exposes a single method:
    evaluate(data, ...) -> List[Insight]
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Import Insight here to avoid circular imports ────────────────────────────
def _insight(**kwargs):
    """Deferred import of Insight to avoid circular dependency."""
    from sigmaflow.insights.rules_engine import Insight
    return Insight(**kwargs)


# ─── Western Electric Rules ───────────────────────────────────────────────────

class WesternElectricRules:
    """
    Applies the four standard Western Electric (WECO) rules to a numeric series.

    Each rule checks a specific non-random pattern in process data.
    All rules require control limits (UCL/LCL) computed from the series.
    """

    def evaluate(
        self,
        series: "pd.Series",
        analysis: Dict[str, Any],
    ) -> List[Any]:
        """
        Apply all four WECO rules and return a list of Insight objects.

        Parameters
        ----------
        series : pd.Series
            The primary measurement series (time-ordered).
        analysis : dict
            Analysis dict from the dataset analyzer (may contain UCL/LCL).
        """
        insights = []
        values = np.array(series.dropna())

        if len(values) < 9:
            return insights  # Not enough data for meaningful rule checks

        # Compute control limits from data if not already in analysis
        x_chart = analysis.get("x_chart", {})
        mu  = x_chart.get("CL",  float(np.mean(values)))
        ucl = x_chart.get("UCL", mu + 3 * float(np.std(values, ddof=1)))
        lcl = x_chart.get("LCL", mu - 3 * float(np.std(values, ddof=1)))
        sigma = (ucl - mu) / 3

        # Apply each rule
        r1 = self._rule_1(values, mu, ucl, lcl)
        r2 = self._rule_2(values, mu)
        r3 = self._rule_3(values)
        r4 = self._rule_4(values)

        if r1:
            insights.append(_insight(
                rule="western_electric_rule_1",
                description=f"Rule 1: {len(r1)} point(s) outside the 3σ control limits (at indices {r1[:5]}).",
                meaning=(
                    "A data point beyond ±3σ from the mean is statistically rare (~0.27% chance "
                    "under normality). Its presence strongly suggests a special-cause event — "
                    "something changed in the process at that moment."
                ),
                recommendation=(
                    "Identify and investigate the specific points flagged. Check for equipment "
                    "malfunction, operator changes, raw material variation, or measurement errors. "
                    "Remove confirmed special causes before computing capability indices."
                ),
                severity="critical",
                data={"ooc_indices": r1, "ucl": round(ucl, 4), "lcl": round(lcl, 4)},
            ))

        if r2:
            insights.append(_insight(
                rule="western_electric_rule_2",
                description=f"Rule 2: {len(r2)} run(s) of 9+ consecutive points on the same side of the mean.",
                meaning=(
                    "A run of nine or more points on one side of the center line has only a "
                    "~0.4% probability under a stable process. This pattern typically indicates "
                    "a sustained shift in the process mean — the average has quietly changed."
                ),
                recommendation=(
                    "Investigate recent process changes: new supplier batches, equipment "
                    "recalibration, environmental conditions, or procedural changes. "
                    "Recalculate control limits if the shift is intentional and sustained."
                ),
                severity="warning",
                data={"run_start_indices": r2},
            ))

        if r3:
            insights.append(_insight(
                rule="western_electric_rule_3",
                description=f"Rule 3: {len(r3)} run(s) of 6+ consecutive points trending in the same direction.",
                meaning=(
                    "Six consecutive increasing or decreasing points suggest a systematic "
                    "drift in the process — tool wear, gradual machine degradation, "
                    "or a slowly changing environmental factor."
                ),
                recommendation=(
                    "Perform preventive maintenance checks. Review process parameters for "
                    "drift (temperature, pressure, tooling). Consider implementing automatic "
                    "process adjustments if the drift is predictable."
                ),
                severity="warning",
                data={"trend_start_indices": r3},
            ))

        if r4:
            insights.append(_insight(
                rule="western_electric_rule_4",
                description=f"Rule 4: {len(r4)} run(s) of 14+ consecutive points alternating up and down.",
                meaning=(
                    "Systematic alternation (zigzag) is less random than a natural process. "
                    "It often indicates over-adjustment (tampering) — operators making frequent "
                    "small corrections that amplify variation — or a two-stream process "
                    "(e.g., two machines alternating)."
                ),
                recommendation=(
                    "Stop unnecessary process adjustments. Investigate whether measurements "
                    "come from multiple streams (machines, operators, shifts). "
                    "Apply the funnel experiment concept to understand tampering effects."
                ),
                severity="warning",
                data={"alternation_start_indices": r4},
            ))

        if not insights:
            insights.append(_insight(
                rule="western_electric_all_pass",
                description="All four Western Electric rules passed — no special-cause patterns detected.",
                meaning=(
                    "The process exhibits only common-cause (random) variation. "
                    "The process appears to be in statistical control."
                ),
                recommendation=(
                    "Maintain current process conditions. Focus improvement efforts on "
                    "reducing inherent (common-cause) variation through process redesign."
                ),
                severity="info",
                data={},
            ))

        return insights

    # ── Rule implementations ──────────────────────────────────────────────────

    @staticmethod
    def _rule_1(values: np.ndarray, mu: float, ucl: float, lcl: float) -> List[int]:
        """Rule 1: Points outside 3σ."""
        return [int(i) for i, v in enumerate(values) if v > ucl or v < lcl]

    @staticmethod
    def _rule_2(values: np.ndarray, mu: float) -> List[int]:
        """Rule 2: 9+ consecutive points on same side of center line."""
        sides = np.where(values >= mu, 1, -1)
        starts = []
        run = 1
        for i in range(1, len(sides)):
            if sides[i] == sides[i - 1]:
                run += 1
                if run == 9:
                    starts.append(int(i - 8))
            else:
                run = 1
        return starts

    @staticmethod
    def _rule_3(values: np.ndarray) -> List[int]:
        """Rule 3: 6+ consecutive points trending in one direction."""
        diffs = np.diff(values)
        starts = []
        run = 1
        for i in range(1, len(diffs)):
            if (diffs[i] > 0 and diffs[i - 1] > 0) or (diffs[i] < 0 and diffs[i - 1] < 0):
                run += 1
                if run == 6:
                    starts.append(int(i - 5))
            else:
                run = 1
        return starts

    @staticmethod
    def _rule_4(values: np.ndarray) -> List[int]:
        """Rule 4: 14+ consecutive points alternating direction."""
        diffs = np.sign(np.diff(values))
        starts = []
        run = 1
        for i in range(1, len(diffs)):
            if diffs[i] != 0 and diffs[i] == -diffs[i - 1]:
                run += 1
                if run == 14:
                    starts.append(int(i - 13))
            else:
                run = 1
        return starts


# ─── Capability Rules ─────────────────────────────────────────────────────────

class CapabilityRules:
    """
    Evaluates process capability indices (Cp, Cpk) against Six Sigma thresholds.

    Standard thresholds:
        Cpk ≥ 1.67  → Six Sigma capable (world class)
        Cpk ≥ 1.33  → Capable (industry standard for new processes)
        Cpk ≥ 1.00  → Marginally capable (monitor closely)
        Cpk < 1.00  → Incapable (immediate corrective action required)
    """

    _THRESHOLDS = [
        (1.67, "critical", "Six Sigma capable (world class)"),
        (1.33, "capable",  "Capable — meets standard industry requirement"),
        (1.00, "marginal", "Marginally capable — monitor closely"),
        (0.00, "incapable","Incapable — exceeds acceptable defect levels"),
    ]

    def evaluate(self, capability: Dict[str, Any]) -> List[Any]:
        """
        Evaluate Cpk and return capability insights.

        Parameters
        ----------
        capability : dict
            The "capability" sub-dict from the analysis results.
        """
        insights = []
        cpk = capability.get("Cpk")
        cp  = capability.get("Cp")

        if cpk is None:
            return insights

        # Determine capability level
        if cpk >= 1.67:
            level, sev = "Six Sigma capable (world class)", "info"
            meaning = (
                f"Cpk = {cpk:.3f} indicates the process is well within specification limits. "
                f"The estimated defect rate is below 3.4 DPMO (6σ quality level). "
                f"This is the target for world-class manufacturing processes."
            )
            rec = (
                "Maintain current process conditions. Consider reducing inspection frequency. "
                "Document process parameters as a baseline for future comparison."
            )
        elif cpk >= 1.33:
            level, sev = "Capable", "info"
            meaning = (
                f"Cpk = {cpk:.3f} meets the industry standard for new processes. "
                f"The process consistently produces within specification limits."
            )
            rec = (
                "Continue monitoring with control charts. Investigate opportunities "
                "to further reduce variation toward Cpk ≥ 1.67."
            )
        elif cpk >= 1.00:
            level, sev = "Marginally Capable", "warning"
            meaning = (
                f"Cpk = {cpk:.3f} is marginally acceptable. The process is meeting "
                f"specifications but with insufficient margin. Small shifts in the "
                f"process mean or spread could lead to out-of-spec production."
            )
            rec = (
                "Increase measurement frequency and control chart monitoring. "
                "Identify and reduce sources of variation. Target Cpk ≥ 1.33."
            )
        else:
            level, sev = "Incapable", "critical"
            meaning = (
                f"Cpk = {cpk:.3f} indicates the process cannot consistently meet "
                f"specification requirements. A significant proportion of output "
                f"is expected to be out of specification."
            )
            rec = (
                "Immediately investigate and address root causes of variation. "
                "Consider 100% inspection until capability is improved. "
                "Engage process improvement team for DMAIC project."
            )

        dpmo = capability.get("dpmo", 0)
        sigma_level = capability.get("sigma_level", 0)

        insights.append(_insight(
            rule="capability_cpk",
            description=f"Process Capability: {level} (Cpk = {cpk:.3f}).",
            meaning=meaning,
            recommendation=rec,
            severity=sev,
            data={
                "Cp": cp,
                "Cpk": cpk,
                "dpmo": dpmo,
                "sigma_level": sigma_level,
            },
        ))

        # Check centering: Cp >> Cpk suggests off-center process
        if cp is not None and cpk is not None and cp > 0:
            centering_ratio = cpk / cp
            if centering_ratio < 0.80:
                insights.append(_insight(
                    rule="capability_centering",
                    description=f"Process is off-center: Cp={cp:.3f} vs Cpk={cpk:.3f} (ratio={centering_ratio:.2f}).",
                    meaning=(
                        "A large gap between Cp and Cpk means the process has sufficient "
                        "inherent capability but is not centered within the specification range. "
                        "The process mean is shifted toward one of the specification limits."
                    ),
                    recommendation=(
                        "Adjust the process target (mean) to center within the specification window. "
                        "Check for systematic biases in raw materials, tooling offsets, or "
                        "measurement system calibration."
                    ),
                    severity="warning",
                    data={"Cp": cp, "Cpk": cpk, "centering_ratio": round(centering_ratio, 3)},
                ))

        return insights


# ─── Trend Rules ──────────────────────────────────────────────────────────────

class TrendRules:
    """
    Interprets Spearman/Mann-Kendall trend test results.

    A statistically significant trend in process data indicates that
    the process mean is drifting over time — a form of special-cause variation.
    """

    def evaluate(self, trend: Dict[str, Any]) -> List[Any]:
        """
        Evaluate trend analysis results and return insight objects.

        Parameters
        ----------
        trend : dict
            The "trend" sub-dict from the analysis results, containing:
            "direction", "tau" (Spearman correlation), "p_value".
        """
        insights = []
        direction = trend.get("direction", "stable")
        tau       = trend.get("tau", 0.0)
        p_value   = trend.get("p_value", 1.0)

        if direction == "stable":
            insights.append(_insight(
                rule="trend_stable",
                description="No statistically significant trend detected in the process data.",
                meaning=(
                    f"The Spearman correlation coefficient (τ = {tau:.3f}) and p-value "
                    f"(p = {p_value:.4f}) indicate no systematic drift in the process over time."
                ),
                recommendation=(
                    "Continue routine monitoring. The process is temporally stable."
                ),
                severity="info",
                data={"tau": tau, "p_value": p_value},
            ))
        else:
            severity = "critical" if abs(tau) > 0.6 else "warning"
            insights.append(_insight(
                rule=f"trend_{direction}",
                description=(
                    f"Significant {direction.upper()} trend detected "
                    f"(τ = {tau:.3f}, p = {p_value:.4f})."
                ),
                meaning=(
                    f"The process shows a statistically significant {direction} drift over time. "
                    f"The Spearman correlation (τ = {tau:.3f}) with p-value {p_value:.4f} "
                    f"confirms this is unlikely due to random chance. "
                    f"This represents a special cause of variation requiring investigation."
                ),
                recommendation=(
                    "Investigate time-dependent factors: tool wear, temperature drift, "
                    "operator fatigue, gradual raw material changes, or machine degradation. "
                    "If the trend is expected (e.g., predictable tool wear), consider "
                    "implementing an automatic process adjustment strategy."
                ),
                severity=severity,
                data={"direction": direction, "tau": tau, "p_value": p_value},
            ))

        return insights
