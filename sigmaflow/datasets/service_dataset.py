"""
sigmaflow/datasets/service_dataset.py
=======================================
Analyzer for service process datasets.

Detects when:
    - Highly skewed numeric column (exponential — typical wait time), OR
    - Likert scale column (1-5 satisfaction), OR
    - Column names suggest service/customer data

Analysis:
    - Service time distribution (mean, P90, P95)
    - SLA violation rate (if target known)
    - Queue / wait time variation
    - Satisfaction score breakdown
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


class ServiceDataset(BaseDataset):

    name        = "service"
    description = "Service process: wait time, SLA, queue variation, satisfaction"
    priority    = 40

    # ── Detection ─────────────────────────────────────────────────────────────

    def detect(self, df: pd.DataFrame) -> bool:
        num_cols   = self._numeric_cols(df)
        cols_lower = [c.lower() for c in df.columns]

        # Keyword match
        kws = ("wait", "espera", "service", "atendimento", "satisfaction",
               "satisfacao", "nps", "csat", "rating", "nota", "ticket",
               "sla", "queue", "fila", "customer", "cliente", "agent")
        if sum(any(k in c for k in kws) for c in cols_lower) >= 1:
            return True

        # Likert scale (satisfaction 1-5)
        for nc in num_cols:
            uq = set(df[nc].dropna().unique())
            if uq <= {1,2,3,4,5,1.0,2.0,3.0,4.0,5.0} and len(uq) >= 3:
                return True

        # Highly right-skewed column with non-negative values (wait time)
        for nc in num_cols:
            s = df[nc].dropna()
            if len(s) >= 30 and s.min() >= 0:
                try:
                    if float(s.skew()) > 1.8:
                        return True
                except Exception:
                    pass

        return False

    # ── Analysis ──────────────────────────────────────────────────────────────

    def run_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        num_cols   = self._numeric_cols(df)
        cols_lower = {c.lower(): c for c in df.columns}

        wait_col = self._find_col(cols_lower, ("wait", "espera", "queue", "fila"))
        svc_col  = self._find_col(cols_lower, ("service", "atendimento", "handle",
                                               "resolution", "resolucao", "duration"))
        sat_col  = self._find_col(cols_lower, ("satisfaction", "satisfacao", "nps",
                                               "csat", "rating", "nota", "score"))
        sla_col  = self._find_col(cols_lower, ("sla", "target", "meta", "prazo", "goal"))

        # Fallback assignment
        if wait_col is None and len(num_cols) >= 1:
            # Pick the most skewed column as wait time
            skews = {}
            for nc in num_cols:
                try:
                    skews[nc] = float(df[nc].dropna().skew())
                except Exception:
                    skews[nc] = 0
            wait_col = max(skews, key=skews.get)

        self._wait_col = wait_col
        self._svc_col  = svc_col
        self._sat_col  = sat_col
        self._sla_col  = sla_col

        result: Dict[str, Any] = {}

        for label, col in [("wait", wait_col), ("service", svc_col)]:
            if col:
                s = df[col].dropna()
                result[f"{label}_time"] = {
                    "mean": round(float(s.mean()), 3),
                    "std":  round(float(s.std()),  3),
                    "cv":   round(float(s.std() / s.mean()), 4) if s.mean() else 0,
                    "p50":  round(float(s.quantile(0.50)), 3),
                    "p90":  round(float(s.quantile(0.90)), 3),
                    "p95":  round(float(s.quantile(0.95)), 3),
                    "skew": round(float(s.skew()), 3),
                }

        if sat_col:
            s = df[sat_col].dropna()
            result["satisfaction"] = {
                "mean":        round(float(s.mean()), 3),
                "distribution": s.value_counts().sort_index().to_dict(),
            }

        if sla_col and wait_col:
            violations = (df[wait_col] > df[sla_col]).sum()
            total      = df[[wait_col, sla_col]].dropna().shape[0]
            result["sla_violation_rate"] = round(float(violations / total * 100), 1) if total else None

        self.results = result
        return result

    # ── Plots ─────────────────────────────────────────────────────────────────

    def generate_plots(self, df: pd.DataFrame, output_folder: str | Path) -> List[str]:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        out    = Path(output_folder)
        saved  = []
        cols   = [c for c in [self._wait_col, self._svc_col, self._sat_col] if c]

        if not cols:
            return saved

        n = len(cols)
        fig, axes = plt.subplots(1, n, figsize=(5 * n, 5))
        fig.suptitle("Service Process Analysis", fontsize=13, fontweight="bold")
        axes_list = [axes] if n == 1 else list(axes)
        colors    = ["#1565C0", "#43A047", "#FB8C00"]

        for i, (col, color) in enumerate(zip(cols, colors)):
            ax = axes_list[i]
            s  = df[col].dropna()

            if col == self._sat_col:
                counts = s.value_counts().sort_index()
                ax.bar(counts.index.astype(str), counts.values,
                       color=color, alpha=0.8, edgecolor="white")
                ax.set_title(f"Satisfaction — {col}")
                ax.set_xlabel("Score"); ax.set_ylabel("Count")
            else:
                ax.hist(s, bins="auto", color=color, alpha=0.75, edgecolor="white")
                label_key = "wait_time" if col == self._wait_col else "service_time"
                stats = self.results.get(label_key, {})
                if stats:
                    ax.axvline(stats["mean"], color="red",    ls="--", lw=2,
                               label=f"Mean={stats['mean']:.1f}")
                    ax.axvline(stats["p90"],  color="orange", ls=":",  lw=2,
                               label=f"P90={stats['p90']:.1f}")
                ax.set_title(f"Distribution — {col}"); ax.legend(fontsize=7)

        plt.tight_layout()
        saved.append(self._save_fig(fig, out / "service_analysis.png"))

        # Boxplot comparison
        time_cols = [c for c in [self._wait_col, self._svc_col] if c]
        if len(time_cols) >= 2:
            fig, ax = plt.subplots(figsize=(8, 5))
            data    = [df[c].dropna().values for c in time_cols]
            bp = ax.boxplot(data, patch_artist=True,
                            boxprops=dict(facecolor="#BBDEFB"),
                            medianprops=dict(color="red", lw=2))
            ax.set_xticks(range(1, len(time_cols) + 1))
            ax.set_xticklabels(time_cols)
            ax.set_title("Wait Time vs Service Time"); ax.grid(alpha=0.3)
            plt.tight_layout()
            saved.append(self._save_fig(fig, out / "service_boxplot.png"))

        return saved

    # ── Insights ──────────────────────────────────────────────────────────────

    def generate_insights(self, df: pd.DataFrame) -> List[str]:
        insights = []
        wt  = self.results.get("wait_time", {})
        svt = self.results.get("service_time", {})
        sat = self.results.get("satisfaction", {})
        sla = self.results.get("sla_violation_rate")

        if wt:
            insights.append(
                f"Service time distribution: mean={wt['mean']:.1f}, "
                f"P90={wt['p90']:.1f}, CV={wt['cv']:.2f}"
            )
            if wt["cv"] > 0.5:
                insights.append("High queue variation detected — workload balancing recommended")

        if sla is not None:
            if sla > 10:
                insights.append(f"SLA violation rate is HIGH: {sla:.1f}% — trend increasing risk")
            else:
                insights.append(f"SLA violation rate: {sla:.1f}% (within acceptable range)")

        if sat:
            mean_sat = sat.get("mean", 0)
            if mean_sat < 3:
                insights.append(f"Satisfaction score is LOW: {mean_sat:.2f}/5 — immediate review needed")
            elif mean_sat < 4:
                insights.append(f"Satisfaction score is MODERATE: {mean_sat:.2f}/5")
            else:
                insights.append(f"Satisfaction score is GOOD: {mean_sat:.2f}/5")

        return insights

    # ── Helper ────────────────────────────────────────────────────────────────

    @staticmethod
    def _find_col(cols_lower: dict, keywords) -> str | None:
        for kw in keywords:
            for cl, orig in cols_lower.items():
                if kw in cl:
                    return orig
        return None
