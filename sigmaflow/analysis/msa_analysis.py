"""
sigmaflow/analysis/msa_analysis.py
=====================================
Measurement System Analysis (MSA) — Gauge R&R for SigmaFlow v10.

Implements the AIAG Gauge R&R (Gage Repeatability & Reproducibility)
method using an Analysis of Variance (ANOVA) approach (GRR Study).

Expected dataset columns
------------------------
    Part        — part identifier (categorical/numeric)
    Operator    — operator identifier (categorical)
    Measurement — numeric measured value

Computed quantities
-------------------
    EV   (Equipment Variation / Repeatability)
    AV   (Appraiser Variation / Reproducibility)
    GRR  (Total Gauge R&R = sqrt(EV² + AV²))
    PV   (Part-to-Part Variation)
    TV   (Total Variation = sqrt(GRR² + PV²))
    %GRR (GRR / TV × 100)
    ndc  (Number of Distinct Categories)

Acceptance criteria (AIAG MSA Manual)
--------------------------------------
    %GRR < 10%   → Excellent — system is acceptable
    10% ≤ %GRR < 30% → Acceptable — may be OK based on application
    %GRR ≥ 30%   → Unacceptable — requires improvement

Usage
-----
    from sigmaflow.analysis.msa_analysis import MSAAnalyzer

    msa = MSAAnalyzer(df, part_col="Part", operator_col="Operator",
                      measurement_col="Measurement")
    results = msa.run()
    plots   = msa.generate_plots(fig_dir)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class MSAAnalyzer:
    """
    Gauge R&R (MSA) analysis using ANOVA method.

    Parameters
    ----------
    df : pd.DataFrame
    part_col : str         Column identifying parts (default: 'Part')
    operator_col : str     Column identifying operators (default: 'Operator')
    measurement_col : str  Numeric measurement column (default: 'Measurement')
    k_sigma : float        Number of sigma for study variation (default: 5.15 = 99% of normal)
    """

    def __init__(
        self,
        df: pd.DataFrame,
        part_col: str         = "Part",
        operator_col: str     = "Operator",
        measurement_col: str  = "Measurement",
        k_sigma: float        = 5.15,
    ) -> None:
        self.df      = df.dropna(subset=[c for c in [part_col, operator_col, measurement_col] if c in df.columns])
        self.part_col    = part_col
        self.operator_col = operator_col
        self.meas_col    = measurement_col
        self.k           = k_sigma
        self._results: Dict[str, Any] = {}

    def run(self) -> Dict[str, Any]:
        """
        Compute full Gauge R&R study.

        Returns
        -------
        dict with variance components, %contributions, and interpretation.
        """
        # Validate columns
        missing = [c for c in [self.part_col, self.operator_col, self.meas_col]
                   if c not in self.df.columns]
        if missing:
            return {"error": f"Missing columns: {missing}"}

        y       = self.df[self.meas_col].values.astype(float)
        parts   = self.df[self.part_col]
        ops     = self.df[self.operator_col]

        n_parts = parts.nunique()
        n_ops   = ops.nunique()
        n_rep   = len(y) / (n_parts * n_ops) if n_parts * n_ops > 0 else 1

        logger.info("MSA: %d parts × %d operators × %.1f replicates", n_parts, n_ops, n_rep)

        # ── ANOVA-based variance components ───────────────────────────────────
        # Total mean
        grand_mean = y.mean()

        # SS for parts
        part_means = self.df.groupby(self.part_col)[self.meas_col].mean()
        ss_parts   = n_ops * n_rep * ((part_means - grand_mean)**2).sum()
        df_parts   = n_parts - 1

        # SS for operators
        op_means   = self.df.groupby(self.operator_col)[self.meas_col].mean()
        ss_ops     = n_parts * n_rep * ((op_means - grand_mean)**2).sum()
        df_ops     = n_ops - 1

        # SS total
        ss_total   = ((y - grand_mean)**2).sum()
        df_total   = len(y) - 1

        # SS error (repeatability)
        ss_error   = ss_total - ss_parts - ss_ops
        df_error   = df_total - df_parts - df_ops
        df_error   = max(df_error, 1)  # safety

        # Mean squares
        ms_parts   = ss_parts / max(df_parts, 1)
        ms_ops     = ss_ops   / max(df_ops, 1)
        ms_error   = ss_error / df_error

        # Variance components
        var_repeat = max(ms_error, 0)
        var_reprod = max((ms_ops - ms_error) / (n_parts * n_rep), 0)
        var_part   = max((ms_parts - ms_error) / (n_ops * n_rep), 0)
        var_grr    = var_repeat + var_reprod
        var_total  = var_grr + var_part

        # Study variation (5.15σ spans 99% of normal distribution)
        ev   = self.k * float(np.sqrt(var_repeat))
        av   = self.k * float(np.sqrt(var_reprod))
        grr  = self.k * float(np.sqrt(var_grr))
        pv   = self.k * float(np.sqrt(var_part))
        tv   = self.k * float(np.sqrt(var_total)) if var_total > 0 else 0.0

        pct_grr   = (grr  / tv * 100) if tv > 0 else 0.0
        pct_ev    = (ev   / tv * 100) if tv > 0 else 0.0
        pct_av    = (av   / tv * 100) if tv > 0 else 0.0
        pct_pv    = (pv   / tv * 100) if tv > 0 else 0.0

        # Number of distinct categories (AIAG criterion: ndc ≥ 5)
        ndc = int(1.41 * pv / grr) if grr > 0 else 0

        # F-statistics
        f_parts = ms_parts / ms_error if ms_error > 0 else 0
        f_ops   = ms_ops   / ms_error if ms_error > 0 else 0
        p_parts = 1 - stats.f.cdf(f_parts, df_parts, df_error)
        p_ops   = 1 - stats.f.cdf(f_ops,   df_ops,   df_error)

        verdict, interpretation = self._interpret(pct_grr, ndc, ev, av, grr, tv)

        self._results = {
            "part_col":       self.part_col,
            "operator_col":   self.operator_col,
            "measurement_col": self.meas_col,
            "n_parts":        int(n_parts),
            "n_operators":    int(n_ops),
            "n_replicates":   round(n_rep, 1),
            "k_sigma":        self.k,
            "anova_table": [
                {"source": "Parts",     "ss": round(ss_parts,4), "df": int(df_parts), "ms": round(ms_parts,4), "f": round(f_parts,3), "p": round(p_parts,4)},
                {"source": "Operators", "ss": round(ss_ops,4),   "df": int(df_ops),   "ms": round(ms_ops,4),   "f": round(f_ops,3),   "p": round(p_ops,4)},
                {"source": "Repeatability (Error)", "ss": round(ss_error,4), "df": int(df_error), "ms": round(ms_error,4), "f": None, "p": None},
                {"source": "Total",     "ss": round(ss_total,4), "df": int(df_total), "ms": None, "f": None, "p": None},
            ],
            "components": {
                "EV_repeatability":   round(ev, 4),
                "AV_reproducibility": round(av, 4),
                "GRR_total":          round(grr, 4),
                "PV_part_variation":  round(pv, 4),
                "TV_total":           round(tv, 4),
            },
            "percent_contribution": {
                "pct_EV":  round(pct_ev, 2),
                "pct_AV":  round(pct_av, 2),
                "pct_GRR": round(pct_grr, 2),
                "pct_PV":  round(pct_pv, 2),
            },
            "ndc":           ndc,
            "verdict":       verdict,
            "interpretation": interpretation,
        }
        return self._results

    def generate_plots(self, fig_dir: str | Path) -> List[str]:
        """Generate GRR variance and component charts."""
        if not self._results:
            self.run()
        if "error" in self._results:
            return []

        fig_dir = Path(fig_dir)
        fig_dir.mkdir(parents=True, exist_ok=True)
        paths = [
            self._plot_components(fig_dir),
            self._plot_by_operator(fig_dir),
            self._plot_by_part(fig_dir),
        ]
        return [p for p in paths if p]

    # ── Plots ─────────────────────────────────────────────────────────────────

    def _plot_components(self, fig_dir: Path) -> str:
        """Pie + bar chart of variance components."""
        pct = self._results["percent_contribution"]
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # Left: stacked bar
        cats    = ["EV (Repeat.)", "AV (Reprod.)", "PV (Part-to-Part)"]
        pct_vals = [pct["pct_EV"], pct["pct_AV"], pct["pct_PV"]]
        colors   = ["#C62828", "#E65100", "#1565C0"]
        bars = axes[0].bar(cats, pct_vals, color=colors, edgecolor="white", width=0.5)
        for bar, val in zip(bars, pct_vals):
            axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                         f"{val:.1f}%", ha="center", va="bottom", fontweight="bold")
        axes[0].axhline(30, color="red", ls="--", lw=1.5, label="30% threshold")
        axes[0].axhline(10, color="green", ls="--", lw=1.5, label="10% threshold")
        axes[0].set_ylabel("% of Total Variation")
        axes[0].set_title("Variance Component %Contribution", fontweight="bold")
        axes[0].set_ylim(0, max(pct_vals + [35]) * 1.15)
        axes[0].legend(fontsize=9)
        axes[0].grid(axis="y", alpha=0.3)

        # Right: GRR verdict
        grr_pct = pct["pct_GRR"]
        color   = "#2E7D32" if grr_pct < 10 else ("#E65100" if grr_pct < 30 else "#C62828")
        verdict = self._results["verdict"]
        bg_color = "#E8F5E9" if grr_pct < 10 else ("#FFF3E0" if grr_pct < 30 else "#FFEBEE")
        axes[1].set_facecolor(bg_color)
        axes[1].text(0.5, 0.60, f"{grr_pct:.1f}%", transform=axes[1].transAxes,
                     fontsize=52, ha="center", va="center", color=color, fontweight="bold")
        axes[1].text(0.5, 0.30, f"Total %GRR", transform=axes[1].transAxes,
                     fontsize=14, ha="center", va="center", color="#546E7A")
        axes[1].text(0.5, 0.15, verdict, transform=axes[1].transAxes,
                     fontsize=16, ha="center", va="center", color=color, fontweight="bold")
        axes[1].text(0.5, 0.05, f"ndc = {self._results['ndc']} distinct categories",
                     transform=axes[1].transAxes, fontsize=10, ha="center", color="#757575")
        axes[1].axis("off")
        axes[1].set_title("Gauge R&R Verdict", fontweight="bold")

        plt.suptitle(
            f"Measurement System Analysis (Gauge R&R)\n"
            f"Parts: {self._results['n_parts']}  |  Operators: {self._results['n_operators']}  |  "
            f"Replicates: {self._results['n_replicates']}  |  k={self._results['k_sigma']}σ",
            fontweight="bold", fontsize=11,
        )
        plt.tight_layout()
        path = str(fig_dir / "msa_grr_components.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    def _plot_by_operator(self, fig_dir: Path) -> str:
        """Box plots of measurements by operator."""
        fig, ax = plt.subplots(figsize=(8, 5))
        ops     = sorted(self.df[self.operator_col].unique())
        data    = [self.df.loc[self.df[self.operator_col]==op, self.meas_col].dropna().values for op in ops]
        bp      = ax.boxplot(data, labels=[str(o) for o in ops], patch_artist=True)
        colors  = plt.cm.Set2.colors
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        ax.set_xlabel(self.operator_col)
        ax.set_ylabel(self.meas_col)
        ax.set_title(f"Measurements by {self.operator_col} (Reproducibility check)", fontweight="bold")
        ax.grid(axis="y", alpha=0.3)
        plt.tight_layout()
        path = str(fig_dir / "msa_by_operator.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    def _plot_by_part(self, fig_dir: Path) -> str:
        """Scatter / range plot by part number."""
        fig, ax = plt.subplots(figsize=(10, 5))
        parts   = sorted(self.df[self.part_col].unique())
        colors  = plt.cm.Set2.colors
        for i, op in enumerate(sorted(self.df[self.operator_col].unique())):
            sub = self.df[self.df[self.operator_col] == op]
            means = [sub.loc[sub[self.part_col]==p, self.meas_col].mean() for p in parts]
            ax.plot(range(len(parts)), means, "o-",
                    color=colors[i % len(colors)], label=str(op), lw=1.5, ms=6)
        ax.set_xticks(range(len(parts)))
        ax.set_xticklabels([str(p) for p in parts])
        ax.set_xlabel(self.part_col)
        ax.set_ylabel(f"Mean {self.meas_col}")
        ax.set_title(f"Mean Measurements by {self.part_col} per {self.operator_col}", fontweight="bold")
        ax.legend(title=self.operator_col, fontsize=9)
        ax.grid(alpha=0.3)
        plt.tight_layout()
        path = str(fig_dir / "msa_by_part.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    # ── Interpretation ────────────────────────────────────────────────────────

    def _interpret(
        self, pct_grr: float, ndc: int, ev: float, av: float, grr: float, tv: float,
    ):
        if pct_grr < 10:
            verdict = "Excellent — Measurement System Acceptable"
            interp  = (
                f"The measurement system variation represents {pct_grr:.1f}% of total variation. "
                f"This is EXCELLENT (< 10%). The gauge is acceptable for production use."
            )
        elif pct_grr < 30:
            verdict = "Acceptable — May Be OK Depending on Application"
            interp  = (
                f"The measurement system variation represents {pct_grr:.1f}% of total variation. "
                f"This is ACCEPTABLE but borderline (10–30%). Review criticality of the characteristic. "
                "Consider improving the measurement procedure or gauge calibration."
            )
        else:
            verdict = "Unacceptable — Measurement System Requires Improvement"
            interp  = (
                f"The measurement system variation represents {pct_grr:.1f}% of total variation. "
                f"This is UNACCEPTABLE (≥ 30%). The gauge must be improved before use in production. "
                "Investigate sources of operator variability (AV) and equipment repeatability (EV)."
            )

        dom = "repeatability (EV)" if ev > av else "reproducibility (AV)"
        interp += (
            f" The dominant source of variation is {dom}. "
            f"Number of distinct categories (ndc) = {ndc}. "
            + ("ndc ≥ 5 is acceptable for production monitoring."
               if ndc >= 5 else
               f"ndc < 5 indicates the gauge cannot adequately distinguish between parts "
               "(minimum 5 categories required for process control).")
        )
        return verdict, interp
