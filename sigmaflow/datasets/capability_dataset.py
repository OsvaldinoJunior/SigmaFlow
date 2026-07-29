"""
sigmaflow/datasets/capability_dataset.py
==========================================
Analyzer for process capability datasets.

Detects when:
    - A single continuous numeric column is present (measurement), OR
    - Columns named with 'usl', 'lsl', 'spec', 'cpk', 'measurement' exist

Analysis:
    - Descriptive statistics
    - Cp / Cpk / Pp / Ppk
    - DPMO and sigma level
    - Normality test (Shapiro-Wilk)
    - Histogram + normal curve + spec limits
    - Control chart (individuals)
    - QQ-plot
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from scipy import stats as sc_stats

from sigmaflow.datasets.base_dataset import BaseDataset
from sigmaflow.analysis.transformations import (
    boxcox_transform,
    johnson_transform,
    compute_capability_nonnormal,
    compute_p_chart,
    compute_np_chart,
    compute_c_chart,
    compute_u_chart,
)

logger = logging.getLogger(__name__)


class CapabilityDataset(BaseDataset):

    name        = "capability"
    description = "Process capability: Cp, Cpk, DPMO, sigma level"
    priority    = 60

    # ── Detection ─────────────────────────────────────────────────────────────

    def detect(self, df: pd.DataFrame) -> bool:
        cols_lower = [c.lower() for c in df.columns]
        num_cols   = df.select_dtypes(include="number").columns

        # Explicit spec-limit columns
        has_spec = any(
            any(kw in c for kw in ("usl", "lsl", "spec", "cpk", "measurement", "mensura"))
            for c in cols_lower
        )
        if has_spec:
            return True

        # Single continuous numeric column, no categoricals, ≥ 30 rows
        n_num = len(num_cols)
        n_cat = len(df.select_dtypes(include=["object", "category"]).columns)
        if n_num == 1 and n_cat == 0 and len(df) >= 30:
            return True

        return False

    # ── Analysis ──────────────────────────────────────────────────────────────

    def run_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        series, usl, lsl = self._extract(df)
        self._series = series
        self._usl    = usl
        self._lsl    = lsl

        desc = series.describe().to_dict()
        result: Dict[str, Any] = {
            "n":      int(len(series)),
            "mean":   float(series.mean()),
            "std":    float(series.std()),
            "min":    float(series.min()),
            "max":    float(series.max()),
            "descriptive": desc,
        }

        # Normality test
        if len(series) >= 8:
            stat, p = sc_stats.shapiro(series[:5000])
            result["normality"] = {"test": "Shapiro-Wilk",
                                   "statistic": round(float(stat), 4),
                                   "p_value": round(float(p), 6),
                                   "normal": bool(p > 0.05)}

        # Standard capability (normal assumption)
        if usl is not None and lsl is not None:
            mu  = series.mean()
            std = series.std(ddof=1)
            cp  = (usl - lsl) / (6 * std)
            cpu = (usl - mu)  / (3 * std)
            cpl = (mu  - lsl) / (3 * std)
            cpk = min(cpu, cpl)
            n_out = int(((series < lsl) | (series > usl)).sum())
            dpmo  = n_out / len(series) * 1_000_000
            sigma = self._dpmo_to_sigma(dpmo)
            result["capability"] = {
                "Cp":  round(cp,  4), "Cpk": round(cpk, 4),
                "Cpu": round(cpu, 4), "Cpl": round(cpl, 4),
                "n_out_of_spec": n_out,
                "dpmo":          round(dpmo, 1),
                "sigma_level":   round(sigma, 2),
                "usl": usl, "lsl": lsl,
                "assumption": "normal",
            }

        # Non-normal capability (if data fails normality test)
        norm_result = result.get("normality", {})
        if not norm_result.get("normal", True) and usl is not None and lsl is not None:
            try:
                nonnorm = compute_capability_nonnormal(series, usl, lsl)
                if "error" not in nonnorm:
                    result["capability_nonnormal"] = nonnorm
            except Exception as e:
                logger.warning(f"Non-normal capability failed: {e}")

        # Attribute charts detection and analysis
        result["attribute_charts"] = self._detect_and_analyze_attribute_charts(df)

        self.results = result
        return result

    def _detect_and_analyze_attribute_charts(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Detect and analyze attribute data (p, np, c, u charts)."""
        charts = {}

        # Look for defect count columns
        defect_cols = [c for c in df.columns if any(kw in c.lower() for kw in ("defect", "reject", "nonconform", "non_conform"))]
        count_cols = [c for c in df.columns if any(kw in c.lower() for kw in ("count", "freq", "frequency", "qty", "quantity"))]
        sample_cols = [c for c in df.columns if any(kw in c.lower() for kw in ("sample", "subgroup", "lot", "batch", "n_", "size"))]

        # p-chart: defectives + sample sizes
        if defect_cols and sample_cols:
            for dcol in defect_cols[:1]:
                for scol in sample_cols[:1]:
                    try:
                        defectives = df[dcol].dropna().astype(int).values
                        sizes = df[scol].dropna().astype(int).values
                        if len(defectives) == len(sizes) and len(defectives) >= 5:
                            charts["p"] = compute_p_chart(defectives, sizes)
                    except Exception:
                        pass

        # np-chart: defectives with constant sample size
        if defect_cols and not charts.get("p"):
            for dcol in defect_cols[:1]:
                try:
                    defectives = df[dcol].dropna().astype(int).values
                    if len(defectives) >= 5:
                        # Try to infer constant sample size
                        sizes = df[sample_cols[0]].dropna().astype(int).values if sample_cols else None
                        if sizes is not None and len(set(sizes)) == 1:
                            charts["np"] = compute_np_chart(defectives, sizes[0])
                        elif len(defectives) >= 5:
                            # Assume constant n=100 if not found
                            charts["np"] = compute_np_chart(defectives, 100)
                except Exception:
                    pass

        # c-chart: defects per unit (constant area)
        if count_cols and not charts:
            for ccol in count_cols[:1]:
                try:
                    defects = df[ccol].dropna().astype(int).values
                    if len(defects) >= 5:
                        charts["c"] = compute_c_chart(defects)
                except Exception:
                    pass

        # u-chart: defects with varying area of opportunity
        if count_cols and sample_cols and not charts.get("c"):
            for ccol in count_cols[:1]:
                for scol in sample_cols[:1]:
                    try:
                        defects = df[ccol].dropna().astype(int).values
                        sizes = df[scol].dropna().astype(int).values
                        if len(defects) == len(sizes) and len(defects) >= 5:
                            charts["u"] = compute_u_chart(defects, sizes)
                    except Exception:
                        pass

        return charts

    # ── Plots ─────────────────────────────────────────────────────────────────

    def generate_plots(self, df: pd.DataFrame, output_folder: str | Path) -> List[str]:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        out = Path(output_folder)
        series, usl, lsl = self._series, self._usl, self._lsl
        saved = []

        # ── Capability histogram ──────────────────────────────────────────────
        fig, axes = plt.subplots(1, 3, figsize=(15, 4))
        fig.suptitle(f"Process Capability — {series.name}", fontsize=13, fontweight="bold")

        ax = axes[0]
        ax.hist(series, bins="auto", density=True, alpha=0.65,
                color="#1565C0", edgecolor="white", label="Data")
        mu, std = series.mean(), series.std()
        x = np.linspace(mu - 4*std, mu + 4*std, 300)
        ax.plot(x, sc_stats.norm.pdf(x, mu, std), "k-", lw=2, label="Normal fit")
        if usl: ax.axvline(usl, color="red",    ls="--", lw=2, label=f"USL={usl}")
        if lsl: ax.axvline(lsl, color="orange", ls="--", lw=2, label=f"LSL={lsl}")
        ax.axvline(mu, color="green", ls=":", lw=1.5, label=f"Mean={mu:.3f}")
        ax.set_title("Histogram + Spec Limits"); ax.legend(fontsize=7)

        ax = axes[1]
        ax.boxplot(series, vert=True, patch_artist=True,
                   boxprops=dict(facecolor="#BBDEFB"),
                   medianprops=dict(color="red", lw=2))
        ax.set_title("Boxplot"); ax.set_ylabel(str(series.name))

        ax = axes[2]
        (osm, osr), (slope, intercept, _) = sc_stats.probplot(series)
        ax.scatter(osm, osr, alpha=0.5, s=15, color="#42A5F5")
        ax.plot(osm, slope * np.array(osm) + intercept, "r-", lw=2)
        ax.set_title("QQ-Plot")

        plt.tight_layout()
        saved.append(self._save_fig(fig, out / "capability_histogram.png"))

        # ── Individuals (run) chart ───────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(12, 4))
        idx = range(len(series))
        ax.plot(idx, series, "o-", color="#1565C0", lw=1.2, ms=3)
        cl  = mu
        ucl = mu + 3*std
        lcl = mu - 3*std
        ax.axhline(cl,  color="green", ls="-",  lw=1.5, label=f"CL={cl:.3f}")
        ax.axhline(ucl, color="red",   ls="--", lw=1.5, label=f"UCL={ucl:.3f}")
        ax.axhline(lcl, color="red",   ls="--", lw=1.5, label=f"LCL={lcl:.3f}")
        ooc = [i for i, v in enumerate(series) if v > ucl or v < lcl]
        if ooc:
            ax.scatter(ooc, series.iloc[ooc], color="red", s=50, zorder=5,
                       label=f"OOC ({len(ooc)})")
        ax.set_title(f"Individuals Chart — {series.name}")
        ax.legend(fontsize=8); ax.grid(alpha=0.3)
        plt.tight_layout()
        saved.append(self._save_fig(fig, out / "control_chart.png"))

        return saved

    # ── Insights ──────────────────────────────────────────────────────────────

    def generate_insights(self, df: pd.DataFrame) -> List[str]:
        insights = []
        cap = self.results.get("capability", {})
        cpk = cap.get("Cpk")

        if cpk is not None:
            if cpk >= 1.67:
                insights.append(f"Process is EXCELLENT — Cpk={cpk:.3f} (Six Sigma capable)")
            elif cpk >= 1.33:
                insights.append(f"Process is CAPABLE — Cpk={cpk:.3f} (meets spec target)")
            elif cpk >= 1.0:
                insights.append(f"Process is MARGINAL — Cpk={cpk:.3f} (monitor closely)")
            else:
                insights.append(f"Process is INCAPABLE — Cpk={cpk:.3f} (urgent action required)")

            dpmo = cap.get("dpmo", 0)
            insights.append(f"Estimated defect rate: {dpmo:,.0f} DPMO "
                            f"({cap.get('sigma_level',0):.2f}σ)")
            if cap.get("n_out_of_spec", 0) > 0:
                insights.append(f"{cap['n_out_of_spec']} observations out of specification limits")

        norm = self.results.get("normality", {})
        if norm and not norm.get("normal", True):
            insights.append("Data does NOT follow a normal distribution — "
                            "consider non-parametric capability analysis")

        return insights

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract(self, df: pd.DataFrame):
        """Extract measurement series + USL/LSL if present."""
        cols_lower = {c.lower(): c for c in df.columns}
        usl = lsl = None

        # Named spec columns
        for kw, attr in [("usl", "usl"), ("lsl", "lsl")]:
            for cl, orig in cols_lower.items():
                if kw in cl:
                    val = df[orig].dropna().iloc[0]
                    if attr == "usl": usl = float(val)
                    else:             lsl = float(val)

        # Measurement column: prefer named, fallback to first numeric
        meas_col = None
        for cl, orig in cols_lower.items():
            if any(k in cl for k in ("measurement", "mensura", "value", "valor", "medida")):
                meas_col = orig
                break
        if meas_col is None:
            num_cols = df.select_dtypes(include="number").columns
            # Exclude spec columns
            meas_col = next(
                (c for c in num_cols if not any(k in c.lower() for k in ("usl","lsl","spec"))),
                num_cols[0]
            )

        series = df[meas_col].dropna().reset_index(drop=True)
        series.name = meas_col
        return series, usl, lsl

    @staticmethod
    def _dpmo_to_sigma(dpmo: float) -> float:
        if dpmo <= 0:   return 6.0
        if dpmo >= 1e6: return 0.0
        p = dpmo / 1_000_000
        z = -sc_stats.norm.ppf(p / 2)
        return round(z + 1.5, 2)
