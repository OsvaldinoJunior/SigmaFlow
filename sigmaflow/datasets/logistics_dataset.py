"""
sigmaflow/datasets/logistics_dataset.py
=========================================
Analyzer for logistics / delivery datasets.

Detects when:
    - 2+ numeric columns with very different value ranges (distance vs. time)
    - Column names suggest distance, delivery, route, km, etc.

Analysis:
    - Lead time distribution (mean, P50, P90, P95)
    - Delay analysis (OTD rate if target column exists)
    - Throughput variation (std dev, CV)
    - Distance vs. delivery-time regression
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


class LogisticsDataset(BaseDataset):

    name        = "logistics"
    description = "Logistics: lead time, OTD rate, delay analysis"
    priority    = 45

    # ── Detection ─────────────────────────────────────────────────────────────

    def detect(self, df: pd.DataFrame) -> bool:
        # Keyword match
        kws = ("km", "distancia", "distance", "entrega", "delivery",
               "frete", "freight", "rota", "route", "transit",
               "origem", "origin", "destino", "destination", "otd")
        cols_lower = [c.lower() for c in df.columns]
        if sum(any(k in c for k in kws) for c in cols_lower) >= 1:
            return True

        # Structural: 2+ numeric cols with very different ranges
        num_cols = self._numeric_cols(df)
        if len(num_cols) >= 2 and len(df) >= 10:
            ranges = sorted(
                [df[nc].max() - df[nc].min() for nc in num_cols if df[nc].max() > 0],
                reverse=True,
            )
            if len(ranges) >= 2:
                ratio = (ranges[0] + 1) / (ranges[-1] + 1)
                if ratio > 15:
                    return True

        return False

    # ── Analysis ──────────────────────────────────────────────────────────────

    def run_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        num_cols   = self._numeric_cols(df)
        cols_lower = {c.lower(): c for c in df.columns}

        # Identify distance and time columns
        dist_col = self._find_col(cols_lower, ("km", "distancia", "distance", "miles"))
        time_col = self._find_col(cols_lower,
                                  ("delivery", "entrega", "transit", "lead", "prazo",
                                   "tempo", "time", "dias", "days", "hours"))
        sla_col  = self._find_col(cols_lower, ("sla", "target", "prazo", "meta", "goal"))

        if time_col is None and num_cols:
            # Fallback: pick the numeric column with the smallest range (likely time)
            time_col = min(num_cols, key=lambda c: df[c].max() - df[c].min())
        if dist_col is None and len(num_cols) >= 2:
            dist_col = max(
                [c for c in num_cols if c != time_col],
                key=lambda c: df[c].max() - df[c].min()
            )

        self._time_col = time_col
        self._dist_col = dist_col
        self._sla_col  = sla_col

        result: Dict[str, Any] = {}

        if time_col:
            s = df[time_col].dropna()
            result["lead_time"] = {
                "mean":   round(float(s.mean()), 3),
                "std":    round(float(s.std()),  3),
                "cv":     round(float(s.std() / s.mean()), 4) if s.mean() else 0,
                "p50":    round(float(s.quantile(0.50)), 3),
                "p90":    round(float(s.quantile(0.90)), 3),
                "p95":    round(float(s.quantile(0.95)), 3),
                "min":    round(float(s.min()), 3),
                "max":    round(float(s.max()), 3),
            }

        if sla_col and time_col:
            on_time = (df[time_col] <= df[sla_col]).sum()
            total   = df[[time_col, sla_col]].dropna().shape[0]
            result["otd_rate"] = round(float(on_time / total * 100), 1) if total else None

        if dist_col and time_col:
            x = df[dist_col].dropna()
            y = df[time_col].dropna()
            common = x.index.intersection(y.index)
            if len(common) >= 5:
                sl, ic, r, p, _ = sc_stats.linregress(x[common], y[common])
                result["regression"] = {
                    "slope":     round(float(sl), 5),
                    "intercept": round(float(ic), 4),
                    "r_squared": round(float(r**2), 4),
                    "p_value":   round(float(p), 6),
                }

        self.results = result
        return result

    # ── Plots ─────────────────────────────────────────────────────────────────

    def generate_plots(self, df: pd.DataFrame, output_folder: str | Path) -> List[str]:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        out   = Path(output_folder)
        saved = []

        n_plots = (1 if self._time_col else 0) + (1 if self._dist_col and self._time_col else 0)
        if n_plots == 0:
            return saved

        fig, axes = plt.subplots(1, max(n_plots, 1), figsize=(7 * max(n_plots, 1), 5))
        fig.suptitle("Logistics Analysis", fontsize=13, fontweight="bold")
        axes_list = [axes] if n_plots == 1 else list(axes)
        idx = 0

        if self._time_col:
            ax = axes_list[idx]; idx += 1
            s  = df[self._time_col].dropna()
            ax.hist(s, bins="auto", color="#43A047", alpha=0.75, edgecolor="white")
            lt = self.results.get("lead_time", {})
            if lt:
                ax.axvline(lt["mean"], color="red",    ls="--", lw=2,
                           label=f"Mean={lt['mean']:.1f}")
                ax.axvline(lt["p90"],  color="orange", ls=":",  lw=2,
                           label=f"P90={lt['p90']:.1f}")
            ax.set_title("Lead Time Distribution")
            ax.set_xlabel(str(self._time_col)); ax.legend(fontsize=8)

        if self._dist_col and self._time_col:
            ax = axes_list[idx]
            x  = df[self._dist_col]; y = df[self._time_col]
            ax.scatter(x, y, alpha=0.5, s=20, color="#1565C0")
            reg = self.results.get("regression", {})
            if "slope" in reg:
                xline = np.linspace(float(x.min()), float(x.max()), 100)
                ax.plot(xline, reg["slope"] * xline + reg["intercept"],
                        "r-", lw=2, label=f"R²={reg['r_squared']:.3f}")
                ax.legend(fontsize=8)
            ax.set_xlabel(str(self._dist_col)); ax.set_ylabel(str(self._time_col))
            ax.set_title("Distance vs. Delivery Time"); ax.grid(alpha=0.3)

        plt.tight_layout()
        saved.append(self._save_fig(fig, out / "logistics_analysis.png"))
        return saved

    # ── Insights ──────────────────────────────────────────────────────────────

    def generate_insights(self, df: pd.DataFrame) -> List[str]:
        insights = []
        lt  = self.results.get("lead_time", {})
        otd = self.results.get("otd_rate")
        reg = self.results.get("regression", {})

        if lt:
            insights.append(
                f"Lead time: mean={lt['mean']:.1f}, P90={lt['p90']:.1f}, "
                f"CV={lt['cv']:.2f} (variation index)"
            )
            if lt["cv"] > 0.3:
                insights.append("High throughput variation detected — investigate root causes")

        if otd is not None:
            if otd >= 95:
                insights.append(f"OTD rate is EXCELLENT: {otd:.1f}%")
            elif otd >= 85:
                insights.append(f"OTD rate acceptable but improvable: {otd:.1f}%")
            else:
                insights.append(f"SLA violation trend: OTD rate at {otd:.1f}% — below target")

        if reg:
            insights.append(
                f"Distance explains {reg['r_squared']*100:.1f}% of delivery time variance "
                f"(R²={reg['r_squared']:.3f})"
            )

        return insights

    # ── Helper ────────────────────────────────────────────────────────────────

    @staticmethod
    def _find_col(cols_lower: dict, keywords) -> str | None:
        for kw in keywords:
            for cl, orig in cols_lower.items():
                if kw in cl:
                    return orig
        return None
