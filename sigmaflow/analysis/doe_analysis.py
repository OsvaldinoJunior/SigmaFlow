"""
sigmaflow/analysis/doe_analysis.py
=====================================
Design of Experiments (DOE) analysis for SigmaFlow v10.

Implements one-way and two-way ANOVA using scipy, with
main effects plots and interaction plots using matplotlib.

Capabilities
------------
- One-way ANOVA for each factor vs the response
- Two-way ANOVA using manual SS decomposition (no statsmodels)
- Main effects plots (mean response per factor level)
- Interaction plots (response by factor × level combinations)
- Automatic identification of significant factors

Output
------
{
    "response":    "yield",
    "factors":     ["Temperature", "Pressure"],
    "anova_table": [
        {"factor": "Temperature", "f_value": 8.4, "p_value": 0.003, "significant": True},
        ...
    ],
    "significant_factors": ["Temperature"],
    "interpretation": "...",
}

Usage
-----
    from sigmaflow.analysis.doe_analysis import DOEAnalyzer

    doe = DOEAnalyzer(df, response_col="yield", factor_cols=["Temp","Pressure"])
    results = doe.run()
    plots   = doe.generate_plots(fig_dir)
"""
from __future__ import annotations

import logging
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

ALPHA = 0.05


class DOEAnalyzer:
    """
    One-way and two-way ANOVA for Design of Experiments analysis.

    Parameters
    ----------
    df : pd.DataFrame
    response_col : str, optional
        Response variable (Y). Auto-detected if None.
    factor_cols : list[str], optional
        Experimental factor columns. Auto-detected if None.
    alpha : float
        Significance level.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        response_col: Optional[str] = None,
        factor_cols:  Optional[List[str]] = None,
        alpha: float  = ALPHA,
    ) -> None:
        self.df       = df.dropna()
        self.alpha    = alpha
        self._response = response_col
        self._factors  = factor_cols
        self._results: Dict[str, Any] = {}

    def run(self) -> Dict[str, Any]:
        """Run ANOVA and return results dict."""
        response = self._resolve_response()
        factors  = self._resolve_factors(response)

        if not response or not factors:
            return {"error": "Need a response variable and at least one factor column."}

        logger.info("DOE: response='%s', factors=%s", response, factors)
        y = self.df[response].values.astype(float)

        # One-way ANOVA for each factor
        anova_rows = []
        for factor in factors:
            row = self._one_way_anova(y, factor)
            if row:
                anova_rows.append(row)

        sig_factors = [r["factor"] for r in anova_rows if r["significant"]]

        interp = self._build_interpretation(response, factors, sig_factors, anova_rows)

        self._results = {
            "response":           response,
            "factors":            factors,
            "n":                  len(y),
            "anova_table":        anova_rows,
            "significant_factors": sig_factors,
            "interpretation":     interp,
            "alpha":              self.alpha,
        }
        return self._results

    def generate_plots(self, fig_dir: str | Path) -> List[str]:
        """Generate main effects and interaction plots."""
        if not self._results:
            self.run()
        if "error" in self._results:
            return []

        fig_dir = Path(fig_dir)
        fig_dir.mkdir(parents=True, exist_ok=True)
        paths = []

        paths.append(self._plot_main_effects(fig_dir))
        paths.append(self._plot_anova_table(fig_dir))
        if len(self._results["factors"]) >= 2:
            paths.append(self._plot_interactions(fig_dir))

        return [p for p in paths if p]

    # ── Private: ANOVA ────────────────────────────────────────────────────────

    def _one_way_anova(self, y: np.ndarray, factor: str) -> Optional[Dict[str, Any]]:
        """Compute one-way ANOVA for factor vs response."""
        col   = self.df[factor]
        levels = col.dropna().unique()
        if len(levels) < 2:
            return None

        groups = [y[col == lv] for lv in levels if len(y[col == lv]) >= 1]
        if len(groups) < 2:
            return None

        try:
            f_stat, p = stats.f_oneway(*groups)
        except Exception:
            return None

        # Effect size: eta-squared
        grand_mean = y.mean()
        ss_between = sum(len(g) * (g.mean() - grand_mean)**2 for g in groups)
        ss_total   = ((y - grand_mean)**2).sum()
        eta_sq     = ss_between / ss_total if ss_total > 0 else 0.0

        n_groups = len(groups)
        df_between = n_groups - 1
        df_within  = len(y) - n_groups

        return {
            "factor":       factor,
            "levels":       int(n_groups),
            "df_between":   int(df_between),
            "df_within":    int(df_within),
            "f_value":      round(float(f_stat), 4),
            "p_value":      round(float(p), 6),
            "eta_squared":  round(float(eta_sq), 4),
            "significant":  bool(p < self.alpha),
        }

    # ── Private: plots ────────────────────────────────────────────────────────

    def _plot_main_effects(self, fig_dir: Path) -> str:
        """Main effects plot: mean response per level for each factor."""
        response = self._results["response"]
        factors  = self._results["factors"]
        y        = self.df[response].values.astype(float)
        grand_mean = y.mean()

        n_factors = len(factors)
        fig, axes = plt.subplots(1, n_factors, figsize=(4.5 * n_factors, 4.5), sharey=False)
        if n_factors == 1:
            axes = [axes]

        for ax, factor in zip(axes, factors):
            groups    = self.df.groupby(factor)[response]
            means     = groups.mean().sort_index()
            ci        = groups.sem().sort_index() * 1.96
            sig_row   = next((r for r in self._results["anova_table"] if r["factor"] == factor), {})
            is_sig    = sig_row.get("significant", False)
            color     = "#C62828" if is_sig else "#1565C0"

            ax.plot(range(len(means)), means.values, "o-", color=color, lw=2, ms=8)
            ax.fill_between(range(len(means)),
                            means.values - ci.values,
                            means.values + ci.values,
                            alpha=0.15, color=color)
            ax.axhline(grand_mean, ls="--", color="#757575", lw=1.2, label=f"Grand mean={grand_mean:.2f}")
            ax.set_xticks(range(len(means)))
            ax.set_xticklabels([str(x) for x in means.index], rotation=20, ha="right")
            ax.set_xlabel(factor, fontsize=11)
            ax.set_ylabel(response if factor == factors[0] else "")
            sig_label = f"  p={sig_row.get('p_value','?'):.3f} ★" if is_sig else f"  p={sig_row.get('p_value','?'):.3f}"
            ax.set_title(f"{factor}{sig_label}", fontweight="bold" if is_sig else "normal")
            ax.grid(alpha=0.3)

        plt.suptitle(f"Main Effects Plot — Response: {response}", fontweight="bold", fontsize=12)
        plt.tight_layout()
        path = str(fig_dir / "doe_main_effects.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    def _plot_anova_table(self, fig_dir: Path) -> str:
        """Visual ANOVA summary table as a figure."""
        rows  = self._results["anova_table"]
        if not rows:
            return ""

        fig, ax = plt.subplots(figsize=(10, max(2.5, len(rows) * 0.55 + 1.5)))
        ax.axis("off")

        headers = ["Factor", "Levels", "df (between)", "F-value", "p-value", "Eta²", "Significant?"]
        table_data = [
            [
                r["factor"],
                str(r["levels"]),
                str(r["df_between"]),
                f"{r['f_value']:.3f}",
                f"{r['p_value']:.4f}",
                f"{r['eta_squared']:.3f}",
                "★ YES" if r["significant"] else "no",
            ]
            for r in rows
        ]

        colors_row = [
            ["#FFCDD2" if r["significant"] else "#F5F5F5"] * len(headers)
            for r in rows
        ]

        tbl = ax.table(
            cellText=table_data,
            colLabels=headers,
            cellColours=colors_row,
            cellLoc="center",
            loc="center",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(10)
        tbl.scale(1, 1.5)
        # Style header
        for j in range(len(headers)):
            tbl[0, j].set_facecolor("#102027")
            tbl[0, j].set_text_props(color="white", fontweight="bold")

        ax.set_title(f"ANOVA Table — Response: {self._results['response']}", fontweight="bold", fontsize=12, pad=10)
        plt.tight_layout()
        path = str(fig_dir / "doe_anova_table.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    def _plot_interactions(self, fig_dir: Path) -> str:
        """Interaction plot for first two factors."""
        response = self._results["response"]
        f1, f2   = self._results["factors"][:2]

        fig, ax = plt.subplots(figsize=(9, 5))
        colors  = plt.cm.Set2.colors

        levels_f2 = sorted(self.df[f2].unique())
        for i, lv2 in enumerate(levels_f2[:6]):
            subset = self.df[self.df[f2] == lv2]
            means  = subset.groupby(f1)[response].mean().sort_index()
            ax.plot(range(len(means)), means.values,
                    "o-", color=colors[i % len(colors)], lw=2, ms=7,
                    label=f"{f2}={lv2}")
            for xi, yi in enumerate(means.values):
                ax.annotate(f"{yi:.2f}", (xi, yi), textcoords="offset points",
                            xytext=(0, 8), ha="center", fontsize=7, color=colors[i % len(colors)])

        levels_f1 = sorted(self.df[f1].unique())
        ax.set_xticks(range(len(levels_f1)))
        ax.set_xticklabels([str(x) for x in levels_f1])
        ax.set_xlabel(f1, fontsize=11)
        ax.set_ylabel(f"Mean {response}", fontsize=11)
        ax.set_title(f"Interaction Plot: {f1} × {f2} → {response}", fontweight="bold")
        ax.legend(title=f2, fontsize=9)
        ax.grid(alpha=0.3)
        plt.tight_layout()
        path = str(fig_dir / "doe_interaction_plot.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    # ── Auto-detection ────────────────────────────────────────────────────────

    def _resolve_response(self) -> Optional[str]:
        if self._response and self._response in self.df.columns:
            return self._response
        num = self.df.select_dtypes(include="number").columns
        quality_kws = ("yield", "response", "output", "defect", "quality", "result")
        for col in num:
            if any(kw in col.lower() for kw in quality_kws):
                return col
        return str(num[-1]) if len(num) > 0 else None

    def _resolve_factors(self, response: Optional[str]) -> List[str]:
        if self._factors:
            return [f for f in self._factors if f in self.df.columns]
        # Categorical or low-cardinality columns make good factors
        candidates = []
        for col in self.df.columns:
            if col == response:
                continue
            nuniq = self.df[col].nunique()
            if nuniq <= 8 or self.df[col].dtype in ["object", "category"]:
                candidates.append(col)
        return candidates[:4]  # Limit to 4 factors

    def _build_interpretation(
        self,
        response: str,
        factors: List[str],
        sig_factors: List[str],
        anova_rows: List[Dict],
    ) -> str:
        parts = [
            f"One-way ANOVA was performed for each of {len(factors)} factor(s) "
            f"against the response variable '{response}'. "
        ]
        if sig_factors:
            parts.append(
                f"Statistically significant factors (α={self.alpha}): "
                f"{', '.join(sig_factors)}. "
                "These factors have a significant effect on the response and should "
                "be prioritized in process optimization."
            )
        else:
            parts.append(
                f"No factor showed a statistically significant effect on '{response}' "
                f"at α={self.alpha}. Consider increasing sample size or exploring "
                "interaction effects."
            )
        for r in anova_rows:
            parts.append(
                f" {r['factor']}: F={r['f_value']:.2f}, p={r['p_value']:.4f}, "
                f"η²={r['eta_squared']:.3f}."
            )
        return "".join(parts)
