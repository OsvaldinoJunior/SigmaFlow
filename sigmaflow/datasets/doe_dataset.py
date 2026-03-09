"""
sigmaflow/datasets/doe_dataset.py
====================================
Analyzer for Design of Experiments (DOE) datasets.

Detects when:
    - 2+ columns have exactly 2 distinct values (-1/+1 or low/high)
    - Column names contain 'factor', 'fator', 'run', 'level', etc.

Analysis:
    - Main effects (regression coefficients)
    - ANOVA-style significance testing
    - Interaction plot (first two factors)
    - R² of fitted model
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from scipy import stats as sc_stats

from sigmaflow.datasets.base_dataset import BaseDataset

logger = logging.getLogger(__name__)


class DOEDataset(BaseDataset):

    name        = "doe"
    description = "Design of Experiments: main effects, interactions, ANOVA"
    priority    = 80   # Strong structural signal (-1/+1 columns)

    # ── Detection ─────────────────────────────────────────────────────────────

    def detect(self, df: pd.DataFrame) -> bool:
        num_cols = self._numeric_cols(df)

        # Count columns with exactly -1/+1 values (classic full-factorial)
        pm1_count = sum(
            1 for nc in num_cols
            if set(df[nc].dropna().unique()) <= {-1, 1, -1.0, 1.0}
        )
        if pm1_count >= 2:
            return True

        # Count columns with exactly 2 distinct numeric values
        two_level = sum(
            1 for nc in num_cols
            if df[nc].dropna().nunique() == 2
        )
        if two_level >= 2:
            return True

        # Column name keywords
        kws = ("factor", "fator", "level", "nivel", "run", "ensaio",
               "replicate", "block", "bloco", "treatment")
        cols_lower = [c.lower() for c in df.columns]
        if sum(any(k in c for k in kws) for c in cols_lower) >= 2:
            return True

        return False

    # ── Analysis ──────────────────────────────────────────────────────────────

    def run_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        num_cols  = self._numeric_cols(df)
        # Last numeric column is the response
        response_col = num_cols[-1]
        factor_cols  = [c for c in num_cols if c != response_col][:8]

        self._response = response_col
        self._factors  = factor_cols

        y = df[response_col].dropna().values

        # Main effects via linear regression
        effects: Dict[str, Any] = {}
        for fc in factor_cols:
            x = df[fc].dropna().values
            common = min(len(x), len(y))
            slope, intercept, r, p, se = sc_stats.linregress(x[:common], y[:common])
            effects[fc] = {
                "effect":    round(float(slope), 4),
                "r":         round(float(r), 4),
                "p_value":   round(float(p), 6),
                "significant": bool(p < 0.05),
            }

        # Multi-factor R² via numpy OLS
        r2 = None
        if len(factor_cols) >= 1:
            try:
                X = np.column_stack([np.ones(len(y))] +
                                    [df[fc].values[:len(y)] for fc in factor_cols])
                beta = np.linalg.lstsq(X, y, rcond=None)[0]
                y_pred = X @ beta
                ss_res = ((y - y_pred) ** 2).sum()
                ss_tot = ((y - y.mean()) ** 2).sum()
                r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
            except Exception:
                pass

        sig_factors = [f for f, v in effects.items() if v["significant"]]

        result: Dict[str, Any] = {
            "response_col":     response_col,
            "factor_cols":      factor_cols,
            "effects":          effects,
            "r_squared":        round(r2, 4) if r2 is not None else None,
            "significant_factors": sig_factors,
        }
        self.results = result
        return result

    # ── Plots ─────────────────────────────────────────────────────────────────

    def generate_plots(self, df: pd.DataFrame, output_folder: str | Path) -> List[str]:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        out    = Path(output_folder)
        factors = self._factors
        saved   = []

        n_f = min(len(factors), 4)
        if n_f == 0:
            return saved

        # Main effects plots
        cols = min(n_f, 2)
        rows = (n_f + 1) // 2
        fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 4 * rows))
        fig.suptitle(f"Main Effects — {self._response}", fontsize=13, fontweight="bold")
        axes_flat = np.array(axes).flatten() if n_f > 1 else [axes]

        y = df[self._response].dropna()
        for i, factor in enumerate(factors[:n_f]):
            ax = axes_flat[i]
            x  = df[factor]
            ax.scatter(x, y, alpha=0.4, s=20, color="#42A5F5")
            try:
                sl, ic, *_ = sc_stats.linregress(x.dropna(), y[x.dropna().index])
                xline = np.linspace(float(x.min()), float(x.max()), 100)
                ax.plot(xline, sl * xline + ic, "r-", lw=2)
            except Exception:
                pass
            eff = self.results["effects"].get(factor, {})
            sig_marker = " *" if eff.get("significant") else ""
            ax.set_title(f"{factor}{sig_marker}  (r={eff.get('r',0):.3f})")
            ax.set_xlabel(factor); ax.set_ylabel(self._response)
            ax.grid(alpha=0.3)

        for j in range(i + 1, len(axes_flat)):
            axes_flat[j].set_visible(False)

        plt.tight_layout()
        saved.append(self._save_fig(fig, out / "doe_main_effects.png"))

        # Interaction plot (first 2 factors)
        if len(factors) >= 2:
            saved.extend(self._interaction_plot(df, factors[0], factors[1], out))

        return saved

    def _interaction_plot(self, df, f1, f2, out) -> List[str]:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 5))
        q33, q67 = df[f2].quantile([0.33, 0.67])
        low  = df[df[f2] <= q33]
        high = df[df[f2] >= q67]

        for subset, label, color in [
            (low,  f"{f2} LOW",  "#1565C0"),
            (high, f"{f2} HIGH", "#E53935"),
        ]:
            if len(subset) < 3:
                continue
            x = subset[f1]; y = subset[self._response]
            ax.scatter(x, y, color=color, alpha=0.35, s=20)
            try:
                sl, ic, *_ = sc_stats.linregress(x, y)
                xline = np.linspace(float(x.min()), float(x.max()), 100)
                ax.plot(xline, sl * xline + ic, color=color, lw=2, label=label)
            except Exception:
                ax.plot([], [], color=color, lw=2, label=label)

        ax.set_title(f"Interaction: {f1} × {f2}")
        ax.set_xlabel(f1); ax.set_ylabel(self._response)
        ax.legend(); ax.grid(alpha=0.3)
        plt.tight_layout()
        return [self._save_fig(fig, out / f"doe_interaction_{f1}_{f2}.png")]

    # ── Insights ──────────────────────────────────────────────────────────────

    def generate_insights(self, df: pd.DataFrame) -> List[str]:
        sig  = self.results["significant_factors"]
        r2   = self.results["r_squared"]
        effects = self.results["effects"]

        insights = []
        if sig:
            top = sorted(sig, key=lambda f: -abs(effects[f]["r"]))[:3]
            insights.append(f"Significant factors identified: {', '.join(top)}")
        else:
            insights.append("No statistically significant factors detected (p < 0.05)")

        if r2 is not None:
            qual = "high" if r2 > 0.7 else "moderate" if r2 > 0.4 else "low"
            insights.append(f"Model R² = {r2:.3f} — {qual} explanatory power")

        if sig:
            insights.append("Validate model with confirmation runs before process change")

        return insights
