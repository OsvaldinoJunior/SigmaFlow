"""
sigmaflow/datasets/root_cause_dataset.py
==========================================
Analyzer for defect / root-cause datasets.

Detects when:
    - 1 categorical column (defect type) + 1 numeric column (count/frequency)
    - Few rows (typical Pareto table)

Analysis:
    - Pareto chart (80/20 rule)
    - Defect frequency ranking
    - Category distribution
    - Vital-few identification
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from sigmaflow.datasets.base_dataset import BaseDataset

logger = logging.getLogger(__name__)


class RootCauseDataset(BaseDataset):

    name        = "root_cause"
    description = "Defect / Pareto analysis: frequency ranking, 80/20 rule"
    priority    = 50

    # ── Detection ─────────────────────────────────────────────────────────────

    def detect(self, df: pd.DataFrame) -> bool:
        cat_cols = self._cat_cols(df)
        num_cols = self._numeric_cols(df)
        n_rows   = len(df)

        # Classic Pareto table: 1+ categorical + 1-3 numeric + few rows
        if len(cat_cols) >= 1 and 1 <= len(num_cols) <= 4 and n_rows <= 200:
            vals = df[num_cols[0]].dropna()
            # Values are non-negative counts/frequencies
            if vals.min() >= 0:
                try:
                    if (vals == vals.round()).all():
                        return True
                except Exception:
                    pass

        # Column names hint at defect/category data
        kws = ("defect", "defeito", "causa", "cause", "categoria", "category",
               "tipo", "type", "mode", "modo", "falha", "failure",
               "count", "contagem", "freq", "occurrence")
        cols_lower = [c.lower() for c in df.columns]
        if sum(any(k in c for k in kws) for c in cols_lower) >= 2:
            return True

        return False

    # ── Analysis ──────────────────────────────────────────────────────────────

    def run_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        cat_cols = self._cat_cols(df)
        num_cols = self._numeric_cols(df)

        cat_col   = cat_cols[0]  if cat_cols else None
        count_col = num_cols[0]  if num_cols else None

        if cat_col and count_col:
            pareto = df.groupby(cat_col)[count_col].sum().sort_values(ascending=False)
        elif cat_col:
            pareto = df[cat_col].value_counts()
            count_col = "count"
        else:
            pareto = df[count_col].value_counts() if count_col else pd.Series(dtype=float)

        total     = float(pareto.sum())
        cum_pct   = pareto.cumsum() / total * 100
        vital_80  = pareto[cum_pct <= 80].index.tolist()
        useful_80 = float(pareto[cum_pct <= 80].sum() / total * 100)

        result: Dict[str, Any] = {
            "total":          total,
            "n_categories":   int(len(pareto)),
            "pareto":         {str(k): float(v) for k, v in pareto.items()},
            "cumulative_pct": {str(k): round(float(v), 2) for k, v in cum_pct.items()},
            "vital_few":      [str(v) for v in vital_80],
            "vital_few_pct":  round(useful_80, 1),
        }
        self._pareto     = pareto
        self._cum_pct    = cum_pct
        self._cat_col    = cat_col
        self._count_col  = count_col
        self.results     = result
        return result

    # ── Plots ─────────────────────────────────────────────────────────────────

    def generate_plots(self, df: pd.DataFrame, output_folder: str | Path) -> List[str]:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        out    = Path(output_folder)
        pareto = self._pareto
        cum    = self._cum_pct
        saved  = []

        n = len(pareto)
        fig, ax1 = plt.subplots(figsize=(max(10, n * 1.1), 6))
        fig.suptitle(f"Pareto Chart — {self.name.title()}", fontsize=13, fontweight="bold")

        vital = self.results["vital_few"]
        colors = ["#E53935" if str(k) in vital else "#1565C0" for k in pareto.index]
        x = range(n)
        ax1.bar(x, pareto.values, color=colors, alpha=0.85, edgecolor="white")
        ax1.set_xticks(list(x))
        ax1.set_xticklabels([str(l) for l in pareto.index],
                             rotation=35, ha="right", fontsize=9)
        ax1.set_ylabel(str(self._count_col)); ax1.set_xlabel(str(self._cat_col))

        ax2 = ax1.twinx()
        ax2.plot(list(x), cum.values, "o-", color="#FB8C00", lw=2, ms=6)
        ax2.axhline(80, color="orange", ls="--", lw=1.5, label="80%")
        ax2.set_ylim(0, 105); ax2.set_ylabel("Cumulative %", color="#FB8C00")
        ax2.legend(fontsize=9)

        # Vertical line at 80% threshold
        if vital:
            ax1.axvline(len(vital) - 0.5, color="orange", ls="--", lw=1.5)

        plt.tight_layout()
        saved.append(self._save_fig(fig, out / "pareto_chart.png"))

        # Pie chart of top categories
        top_n = min(8, n)
        fig, ax = plt.subplots(figsize=(8, 6))
        top = pareto.head(top_n)
        rest = pareto.iloc[top_n:].sum()
        labels = [str(l) for l in top.index]
        values = list(top.values)
        if rest > 0:
            labels.append("Others")
            values.append(rest)
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90,
               colors=plt.cm.Set3(np.linspace(0, 1, len(values))))
        ax.set_title("Defect Distribution")
        plt.tight_layout()
        saved.append(self._save_fig(fig, out / "defect_distribution.png"))

        return saved

    # ── Insights ──────────────────────────────────────────────────────────────

    def generate_insights(self, df: pd.DataFrame) -> List[str]:
        vital = self.results["vital_few"]
        pct   = self.results["vital_few_pct"]
        n_cat = self.results["n_categories"]
        total = self.results["total"]

        insights = []
        if vital:
            insights.append(
                f"Dominant defect category identified: '{vital[0]}' accounts for the most occurrences"
            )
            insights.append(
                f"Vital few: {len(vital)} out of {n_cat} categories account for "
                f"{pct:.1f}% of total defects ({total:,.0f})"
            )
            insights.append(
                f"Focus corrective actions on: {', '.join(vital[:3])}"
            )
        return insights
