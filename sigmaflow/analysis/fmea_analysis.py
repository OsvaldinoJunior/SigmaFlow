"""
sigmaflow/analysis/fmea_analysis.py
=====================================
Failure Mode and Effects Analysis (FMEA) for SigmaFlow v10.

Computes the Risk Priority Number (RPN) for each failure mode:

    RPN = Severity × Occurrence × Detection

Where each factor is rated 1–10:
    Severity   (S): Impact on customer / process (10 = catastrophic)
    Occurrence (O): Frequency of failure (10 = very high)
    Detection  (D): Ability to detect before reaching customer (10 = undetectable)

RPN ranges
----------
    RPN > 200  → Critical risk — immediate action required
    RPN 100–200 → High risk — action recommended
    RPN 50–100 → Moderate risk — monitor
    RPN < 50   → Low risk — acceptable

Expected columns
----------------
    Failure_Mode  — description of the failure
    Severity      — integer 1–10
    Occurrence    — integer 1–10
    Detection     — integer 1–10

Optional
--------
    Function        — component / function affected
    Effect          — effect on customer
    Current_Controls — existing controls
    Recommended_Action — suggested improvement

Usage
-----
    from sigmaflow.analysis.fmea_analysis import FMEAAnalyzer

    fmea = FMEAAnalyzer(df)
    results = fmea.run()
    plots   = fmea.generate_plots(fig_dir)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FMEAAnalyzer:
    """
    FMEA Risk Priority Number calculation and ranking.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain 'Severity', 'Occurrence', 'Detection'.
        'Failure_Mode' is used as the label if present.
    failure_mode_col : str
    severity_col : str
    occurrence_col : str
    detection_col : str
    """

    def __init__(
        self,
        df: pd.DataFrame,
        failure_mode_col: str = "Failure_Mode",
        severity_col:     str = "Severity",
        occurrence_col:   str = "Occurrence",
        detection_col:    str = "Detection",
    ) -> None:
        self.df              = df.copy()
        self.fm_col          = failure_mode_col
        self.sev_col         = severity_col
        self.occ_col         = occurrence_col
        self.det_col         = detection_col
        self._results: Dict[str, Any] = {}

    def run(self) -> Dict[str, Any]:
        """
        Compute RPN scores and rank failure modes.

        Returns
        -------
        dict with ranked_modes, summary stats, and interpretation.
        """
        required = [self.sev_col, self.occ_col, self.det_col]
        missing  = [c for c in required if c not in self.df.columns]
        if missing:
            return {"error": f"Missing required columns: {missing}"}

        df = self.df.copy()
        df["RPN"] = (
            df[self.sev_col].astype(float)
            * df[self.occ_col].astype(float)
            * df[self.det_col].astype(float)
        )
        df = df.sort_values("RPN", ascending=False).reset_index(drop=True)

        def _risk_level(rpn: float) -> str:
            if rpn > 200: return "Critical"
            if rpn > 100: return "High"
            if rpn >= 50: return "Moderate"
            return "Low"

        def _risk_color(rpn: float) -> str:
            if rpn > 200: return "#C62828"
            if rpn > 100: return "#E65100"
            if rpn >= 50: return "#F9A825"
            return "#2E7D32"

        # Build ranked modes
        label_col = self.fm_col if self.fm_col in df.columns else None
        modes = []
        for _, row in df.iterrows():
            rpn = row["RPN"]
            modes.append({
                "failure_mode":  str(row[label_col]) if label_col else f"Mode {_ + 1}",
                "severity":      int(row[self.sev_col]),
                "occurrence":    int(row[self.occ_col]),
                "detection":     int(row[self.det_col]),
                "rpn":           int(rpn),
                "risk_level":    _risk_level(rpn),
                "risk_color":    _risk_color(rpn),
                "recommendation": self._recommendation(rpn, int(row[self.sev_col]),
                                                        int(row[self.occ_col]),
                                                        int(row[self.det_col])),
            })

        n_critical = sum(1 for m in modes if m["risk_level"] == "Critical")
        n_high     = sum(1 for m in modes if m["risk_level"] == "High")
        avg_rpn    = float(np.mean([m["rpn"] for m in modes]))
        max_rpn    = max(m["rpn"] for m in modes) if modes else 0

        interp = self._build_interpretation(modes, n_critical, n_high, avg_rpn, max_rpn)

        self._results = {
            "n_failure_modes": len(modes),
            "ranked_modes":    modes,
            "n_critical":      n_critical,
            "n_high":          n_high,
            "avg_rpn":         round(avg_rpn, 1),
            "max_rpn":         max_rpn,
            "interpretation":  interp,
        }
        return self._results

    def generate_plots(self, fig_dir: str | Path) -> List[str]:
        """Generate RPN ranking chart and risk matrix."""
        if not self._results:
            self.run()
        if "error" in self._results:
            return []

        fig_dir = Path(fig_dir)
        fig_dir.mkdir(parents=True, exist_ok=True)
        paths = [
            self._plot_rpn_ranking(fig_dir),
            self._plot_risk_matrix(fig_dir),
        ]
        return [p for p in paths if p]

    # ── Plots ─────────────────────────────────────────────────────────────────

    def _plot_rpn_ranking(self, fig_dir: Path) -> str:
        """Horizontal bar chart of RPN values, color-coded by risk level."""
        modes  = self._results["ranked_modes"]
        top_n  = modes[:15]
        labels = [m["failure_mode"] for m in top_n]
        rpns   = [m["rpn"] for m in top_n]
        colors = [m["risk_color"] for m in top_n]

        fig_h = max(4.5, len(top_n) * 0.5 + 2)
        fig, ax = plt.subplots(figsize=(11, fig_h))

        bars = ax.barh(labels[::-1], rpns[::-1], color=colors[::-1],
                       edgecolor="white", height=0.65)

        for bar, val in zip(bars, rpns[::-1]):
            ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2,
                    f"{val}", va="center", ha="left", fontweight="bold", fontsize=9)

        # Reference lines
        for threshold, color, label in [(200, "#C62828", "Critical (>200)"),
                                         (100, "#E65100", "High (>100)"),
                                         (50,  "#F9A825", "Moderate (≥50)")]:
            ax.axvline(threshold, color=color, ls="--", lw=1.5, alpha=0.7, label=label)

        ax.set_xlabel("Risk Priority Number (RPN)", fontsize=11)
        ax.set_title("FMEA — Failure Mode Risk Ranking (RPN = S × O × D)",
                     fontweight="bold", fontsize=12)
        ax.legend(fontsize=9, loc="lower right")
        ax.set_xlim(0, max(rpns) * 1.15)
        ax.grid(axis="x", alpha=0.3)

        plt.tight_layout()
        path = str(fig_dir / "fmea_rpn_ranking.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    def _plot_risk_matrix(self, fig_dir: Path) -> str:
        """Severity × Occurrence risk matrix with RPN bubbles."""
        modes = self._results["ranked_modes"]

        fig, ax = plt.subplots(figsize=(9, 7))

        for m in modes:
            s, o, d = m["severity"], m["occurrence"], m["detection"]
            rpn     = m["rpn"]
            size    = max(30, rpn / 2)
            ax.scatter(s, o, s=size, color=m["risk_color"], alpha=0.7,
                       edgecolors="white", linewidths=1.5, zorder=5)
            ax.annotate(
                m["failure_mode"][:18],
                (s, o), textcoords="offset points", xytext=(5, 4),
                fontsize=7, color="#333333",
            )

        # Color zones
        ax.fill_between([7.5, 10.5], [7.5, 7.5], [10.5, 10.5], alpha=0.08, color="#C62828")
        ax.fill_between([4.5, 7.5], [4.5, 4.5], [10.5, 10.5], alpha=0.06, color="#E65100")

        ax.set_xlim(0.5, 10.5)
        ax.set_ylim(0.5, 10.5)
        ax.set_xticks(range(1, 11))
        ax.set_yticks(range(1, 11))
        ax.set_xlabel("Severity (S)", fontsize=11)
        ax.set_ylabel("Occurrence (O)", fontsize=11)
        ax.set_title("FMEA Risk Matrix (S × O) — Bubble size ∝ RPN", fontweight="bold")
        ax.grid(alpha=0.25)

        legend_items = [
            mpatches.Patch(color="#C62828", label="Critical (RPN>200)"),
            mpatches.Patch(color="#E65100", label="High (RPN>100)"),
            mpatches.Patch(color="#F9A825", label="Moderate (RPN≥50)"),
            mpatches.Patch(color="#2E7D32", label="Low (RPN<50)"),
        ]
        ax.legend(handles=legend_items, fontsize=9, loc="upper left")
        plt.tight_layout()
        path = str(fig_dir / "fmea_risk_matrix.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _recommendation(rpn: float, s: int, o: int, d: int) -> str:
        """Auto-generate a corrective action recommendation based on RPN drivers."""
        if rpn > 200:
            return "IMMEDIATE ACTION required. Halt production if necessary. Conduct root cause analysis."
        if rpn > 100:
            if s >= 8:
                return "Redesign to eliminate or reduce severity. Add redundancy or fail-safes."
            if o >= 7:
                return "Implement process controls or poka-yoke to reduce occurrence frequency."
            return "Improve detection controls (add inspection, sensors, or SPC monitoring)."
        if rpn >= 50:
            if d >= 7:
                return "Improve detection capability. Add end-of-line testing or inline sensors."
            return "Monitor closely. Implement preventive maintenance or process capability studies."
        return "Document and monitor. No immediate action required."

    def _build_interpretation(
        self, modes: List[Dict], n_crit: int, n_high: int, avg_rpn: float, max_rpn: int,
    ) -> str:
        parts = [
            f"FMEA analysis identified {len(modes)} failure mode(s). "
            f"Average RPN = {avg_rpn:.0f}, Maximum RPN = {max_rpn}. "
        ]
        if n_crit:
            parts.append(
                f"{n_crit} CRITICAL failure mode(s) (RPN > 200) require immediate corrective action. "
            )
        if n_high:
            parts.append(
                f"{n_high} HIGH risk failure mode(s) (RPN 100–200) are recommended for action. "
            )
        top = modes[0] if modes else {}
        if top:
            parts.append(
                f"Highest risk: '{top['failure_mode']}' (RPN={top['rpn']}, "
                f"S={top['severity']}, O={top['occurrence']}, D={top['detection']}). "
                f"{top['recommendation']}"
            )
        return "".join(parts)
