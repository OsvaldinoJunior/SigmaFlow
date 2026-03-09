"""
sigmaflow/visualization/histograms.py
=======================================
Histogram and distribution plotting functions.

Provides a publication-quality histogram with:
    - Normal distribution fit curve
    - Specification limit lines (USL/LSL)
    - Process mean line
    - QQ-plot panel for normality assessment
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats as sc_stats

logger = logging.getLogger(__name__)

BLUE   = "#1565C0"
GREEN  = "#2E7D32"
RED    = "#C62828"
ORANGE = "#E65100"


def plot_distribution(
    series: pd.Series,
    output_path: str | Path,
    usl: Optional[float] = None,
    lsl: Optional[float] = None,
    title: Optional[str] = None,
) -> str:
    """
    Plot a 3-panel distribution figure:
        1. Histogram with normal fit and spec limits
        2. Boxplot
        3. QQ-plot

    Parameters
    ----------
    series : pd.Series
        Measurement data.
    output_path : str | Path
        Where to save the PNG.
    usl : float, optional
        Upper specification limit.
    lsl : float, optional
        Lower specification limit.
    title : str, optional
        Chart title (defaults to series.name).

    Returns
    -------
    str
        Absolute path to the saved PNG.
    """
    path   = Path(output_path)
    values = series.dropna()
    mu     = float(values.mean())
    std    = float(values.std())
    name   = str(series.name or "Measurement")
    title  = title or f"Distribution Analysis — {name}"

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(title, fontsize=13, fontweight="bold", y=1.01)

    # ── Panel 1: Histogram + normal fit ──────────────────────────────────────
    ax = axes[0]
    ax.hist(values, bins="auto", density=True, alpha=0.65,
            color=BLUE, edgecolor="white", label="Data")
    x = np.linspace(mu - 4 * std, mu + 4 * std, 300)
    ax.plot(x, sc_stats.norm.pdf(x, mu, std), "k-", lw=2, label="Normal fit")

    if usl is not None:
        ax.axvline(usl, color=RED,    ls="--", lw=2, label=f"USL = {usl}")
    if lsl is not None:
        ax.axvline(lsl, color=ORANGE, ls="--", lw=2, label=f"LSL = {lsl}")
    ax.axvline(mu, color=GREEN, ls=":", lw=1.8, label=f"Mean = {mu:.4f}")

    ax.set_title("Histogram + Normal Fit")
    ax.set_xlabel(name)
    ax.set_ylabel("Density")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    # ── Panel 2: Boxplot ──────────────────────────────────────────────────────
    ax = axes[1]
    bp = ax.boxplot(
        values, vert=True, patch_artist=True,
        boxprops=dict(facecolor="#BBDEFB", color=BLUE),
        medianprops=dict(color=RED, lw=2.5),
        whiskerprops=dict(color=BLUE),
        capprops=dict(color=BLUE),
        flierprops=dict(marker="o", color=RED, alpha=0.5, ms=4),
    )
    if usl is not None:
        ax.axhline(usl, color=RED,    ls="--", lw=1.5, label=f"USL={usl}")
    if lsl is not None:
        ax.axhline(lsl, color=ORANGE, ls="--", lw=1.5, label=f"LSL={lsl}")
    ax.set_title("Boxplot")
    ax.set_ylabel(name)
    ax.set_xticks([])
    if usl or lsl:
        ax.legend(fontsize=7)
    ax.grid(alpha=0.3, axis="y")

    # ── Panel 3: QQ-plot ──────────────────────────────────────────────────────
    ax = axes[2]
    (osm, osr), (slope, intercept, _) = sc_stats.probplot(values)
    ax.scatter(osm, osr, alpha=0.5, s=15, color="#42A5F5")
    ax.plot(osm, slope * np.array(osm) + intercept, color=RED, lw=2, label="Reference line")
    ax.set_title("QQ-Plot (Normality Check)")
    ax.set_xlabel("Theoretical Quantiles")
    ax.set_ylabel("Sample Quantiles")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    plt.tight_layout()

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=130, bbox_inches="tight")
    plt.close(fig)
    logger.debug("Saved distribution chart: %s", path.name)
    return str(path)
