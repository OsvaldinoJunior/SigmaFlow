"""
sigmaflow/datasets/spc_dataset.py
====================================
Analyzer for Statistical Process Control (SPC) datasets.

Detects when:
    - A datetime column exists, OR
    - A monotonically increasing numeric index column exists

Analysis:
    - X-bar / R chart
    - Individuals (XmR) chart
    - Trend detection (Mann-Kendall)
    - Out-of-control point detection (Western Electric Rule 1)
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


class SPCDataset(BaseDataset):

    name        = "spc"
    description = "Statistical Process Control: XmR chart, trend, OOC detection"
    priority    = 70   # SPC has a strong structural signal — check early

    # ── Detection ─────────────────────────────────────────────────────────────

    def detect(self, df: pd.DataFrame) -> bool:
        # Explicit datetime column
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                return True

        # Numeric column that is a monotonic sequence (index/order)
        num_cols = df.select_dtypes(include="number").columns
        for nc in num_cols:
            vals = df[nc].dropna().reset_index(drop=True)
            if len(vals) >= 8:
                diffs = vals.diff().dropna()
                if (diffs > 0).mean() > 0.88 and vals.max() <= len(df) + 5:
                    return True

        # Column names contain time keywords
        cols_lower = [c.lower() for c in df.columns]
        time_kws = ("timestamp", "datetime", "date", "hora", "batch",
                    "lote", "sequence", "sequencia", "order", "time")
        if any(any(kw in cl for kw in time_kws) for cl in cols_lower):
            return True

        return False

    # ── Analysis ──────────────────────────────────────────────────────────────

    def run_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        series = self._extract_series(df)
        self._series = series

        mu  = float(series.mean())
        std = float(series.std(ddof=1))
        ucl = mu + 3 * std
        lcl = mu - 3 * std

        # Moving range
        mr     = series.diff().abs().dropna()
        mr_bar = float(mr.mean())
        D4     = 3.267
        ucl_mr = D4 * mr_bar

        ooc_x  = [int(i) for i, v in enumerate(series) if v > ucl or v < lcl]
        ooc_mr = [int(i) for i, v in enumerate(mr) if v > ucl_mr]

        # Trend test (Mann-Kendall simplified via Spearman correlation)
        tau, p_trend = sc_stats.spearmanr(range(len(series)), series)
        trend = "increasing" if (tau > 0.3 and p_trend < 0.05) \
                else "decreasing" if (tau < -0.3 and p_trend < 0.05) \
                else "stable"

        result: Dict[str, Any] = {
            "n":         int(len(series)),
            "mean":      round(mu, 4),
            "std":       round(std, 4),
            "x_chart":   {"UCL": round(ucl,3), "CL": round(mu,3), "LCL": round(lcl,3),
                          "ooc_points": ooc_x, "n_ooc": len(ooc_x)},
            "mr_chart":  {"UCL": round(ucl_mr,3), "CL": round(mr_bar,3),
                          "ooc_points": ooc_mr, "n_ooc": len(ooc_mr)},
            "trend":     {"direction": trend, "tau": round(float(tau),4),
                          "p_value": round(float(p_trend),6)},
        }
        self.results = result
        return result

    # ── Plots ─────────────────────────────────────────────────────────────────

    def generate_plots(self, df: pd.DataFrame, output_folder: str | Path) -> List[str]:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        out    = Path(output_folder)
        series = self._series
        saved  = []

        xc  = self.results["x_chart"]
        mrc = self.results["mr_chart"]
        mr  = series.diff().abs().dropna()
        idx = range(len(series))

        fig, axes = plt.subplots(2, 1, figsize=(14, 8))
        fig.suptitle(f"SPC Control Charts — {series.name}", fontsize=13, fontweight="bold")

        # X (Individuals) chart
        ax = axes[0]
        ax.plot(idx, series, "o-", color="#1565C0", lw=1.3, ms=4)
        ax.axhline(xc["UCL"], color="red",   ls="--", lw=1.5, label=f"UCL={xc['UCL']}")
        ax.axhline(xc["CL"],  color="green", ls="-",  lw=1.5, label=f"CL={xc['CL']}")
        ax.axhline(xc["LCL"], color="red",   ls="--", lw=1.5, label=f"LCL={xc['LCL']}")
        if xc["ooc_points"]:
            ax.scatter(xc["ooc_points"],
                       series.iloc[xc["ooc_points"]],
                       color="red", s=60, zorder=5,
                       label=f"OOC ({xc['n_ooc']})")
        ax.set_title("X Chart (Individuals)")
        ax.legend(fontsize=8); ax.grid(alpha=0.3)

        # MR chart
        ax = axes[1]
        ax.plot(range(len(mr)), mr, "s-", color="#43A047", lw=1.3, ms=4)
        ax.axhline(mrc["UCL"], color="red",   ls="--", lw=1.5, label=f"UCL={mrc['UCL']}")
        ax.axhline(mrc["CL"],  color="green", ls="-",  lw=1.5, label=f"CL={mrc['CL']}")
        ax.axhline(0, color="gray", lw=0.8)
        ax.set_title("Moving Range (MR) Chart")
        ax.legend(fontsize=8); ax.grid(alpha=0.3)

        plt.tight_layout()
        saved.append(self._save_fig(fig, out / "spc_xmr_chart.png"))

        # Trend visualisation
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(idx, series, color="#1565C0", lw=1.5, alpha=0.8, label="Values")
        slope, intercept, *_ = sc_stats.linregress(list(idx), series.values)
        ax.plot(idx, [slope*i + intercept for i in idx],
                "r--", lw=2, label=f"Trend (τ={self.results['trend']['tau']:.3f})")
        ax.set_title(f"Trend Analysis — {self.results['trend']['direction'].upper()}")
        ax.legend(); ax.grid(alpha=0.3)
        plt.tight_layout()
        saved.append(self._save_fig(fig, out / "spc_trend.png"))

        return saved

    # ── Insights ──────────────────────────────────────────────────────────────

    def generate_insights(self, df: pd.DataFrame) -> List[str]:
        insights = []
        xc    = self.results["x_chart"]
        trend = self.results["trend"]

        if xc["n_ooc"] == 0:
            insights.append("Process is in statistical control — no out-of-control points detected")
        elif xc["n_ooc"] <= 2:
            insights.append(f"Minor instability: {xc['n_ooc']} out-of-control point(s) — investigate")
        else:
            insights.append(f"Special cause variation detected: {xc['n_ooc']} OOC points "
                            f"({xc['n_ooc']/self.results['n']*100:.1f}%) — process unstable")

        if trend["direction"] != "stable":
            insights.append(
                f"Significant {trend['direction']} trend detected "
                f"(Spearman τ={trend['tau']:.3f}, p={trend['p_value']:.4f})"
            )

        return insights

    # ── Helper ────────────────────────────────────────────────────────────────

    def _extract_series(self, df: pd.DataFrame) -> pd.Series:
        num_cols = df.select_dtypes(include="number").columns.tolist()
        # Exclude obvious index / time columns
        exclude_kws = ("time", "date", "hora", "seq", "order", "id",
                       "index", "n°", "numero", "num", "batch", "lote")
        candidates = [
            c for c in num_cols
            if not any(kw in c.lower() for kw in exclude_kws)
        ]
        col = candidates[0] if candidates else num_cols[0]
        s   = df[col].dropna().reset_index(drop=True)
        s.name = col
        return s
