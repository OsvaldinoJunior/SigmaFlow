"""
sigmaflow/visualization/control_charts.py
==========================================
Centralized control chart plotting functions.

All functions accept a series + analysis dict and save charts to the
specified output path. They return the saved file path as a string.

Functions
---------
    plot_xmr_chart(series, analysis, output_path) → str
    plot_trend_chart(series, analysis, output_path) → str
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
from scipy import stats as sc_stats

logger = logging.getLogger(__name__)

# ── Style constants ───────────────────────────────────────────────────────────
BLUE   = "#1565C0"
GREEN  = "#2E7D32"
RED    = "#C62828"
ORANGE = "#E65100"
GRAY   = "#757575"


def _save(fig: plt.Figure, path: Path) -> str:
    """Save figure and close it. Returns string path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=130, bbox_inches="tight")
    plt.close(fig)
    logger.debug("Saved chart: %s", path.name)
    return str(path)


def plot_xmr_chart(
    series: pd.Series,
    analysis: Dict[str, Any],
    output_path: str | Path,
) -> str:
    """
    Plot an XmR (Individuals and Moving Range) control chart.

    The chart consists of two panels:
        Top: X (Individuals) chart with UCL, CL, LCL and OOC points marked
        Bottom: MR (Moving Range) chart with UCL and CL

    Parameters
    ----------
    series : pd.Series
        Time-ordered measurement values.
    analysis : dict
        Must contain "x_chart" and "mr_chart" sub-dicts from spc_analysis.
    output_path : str | Path
        File path (PNG) to save the chart.

    Returns
    -------
    str
        Absolute path to the saved PNG file.
    """
    path   = Path(output_path)
    values = series.dropna().reset_index(drop=True)
    mr     = values.diff().abs().dropna()
    idx    = range(len(values))

    xc  = analysis.get("x_chart", {})
    mrc = analysis.get("mr_chart", {})

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=False)
    fig.suptitle(
        f"XmR Control Chart — {series.name}",
        fontsize=14, fontweight="bold", y=0.98,
    )

    # ── X chart ───────────────────────────────────────────────────────────────
    ax = axes[0]
    ax.plot(idx, values, "o-", color=BLUE, lw=1.3, ms=4, alpha=0.85, label="Observations")
    ax.axhline(xc.get("UCL", 0), color=RED,   ls="--", lw=1.8, label=f"UCL = {xc.get('UCL','')}")
    ax.axhline(xc.get("CL",  0), color=GREEN, ls="-",  lw=2.0, label=f"CL  = {xc.get('CL','')}")
    ax.axhline(xc.get("LCL", 0), color=RED,   ls="--", lw=1.8, label=f"LCL = {xc.get('LCL','')}")

    # Shade sigma zones (1σ, 2σ)
    mu  = xc.get("CL", values.mean())
    ucl = xc.get("UCL", mu)
    lcl = xc.get("LCL", mu)
    sigma = (ucl - mu) / 3 if ucl != mu else 1
    ax.fill_between(idx, mu - sigma, mu + sigma, alpha=0.06, color=GREEN, label="±1σ zone")
    ax.fill_between(idx, mu - 2*sigma, mu + 2*sigma, alpha=0.04, color=ORANGE)

    # Mark OOC points
    ooc = xc.get("ooc_points", [])
    if ooc:
        ax.scatter(
            ooc, values.iloc[ooc],
            color=RED, s=70, zorder=5,
            label=f"Out-of-Control ({len(ooc)} pts)",
        )

    ax.set_title("X Chart (Individuals)", fontsize=11)
    ax.set_ylabel(str(series.name))
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(alpha=0.3)

    # ── MR chart ──────────────────────────────────────────────────────────────
    ax = axes[1]
    ax.plot(range(len(mr)), mr, "s-", color="#43A047", lw=1.3, ms=4, alpha=0.85)
    ax.axhline(mrc.get("UCL", 0), color=RED,   ls="--", lw=1.8, label=f"UCL = {mrc.get('UCL','')}")
    ax.axhline(mrc.get("CL",  0), color=GREEN, ls="-",  lw=2.0, label=f"CL  = {mrc.get('CL','')}")
    ax.axhline(0, color=GRAY, lw=0.8)

    mr_ooc = mrc.get("ooc_points", [])
    if mr_ooc:
        ax.scatter(mr_ooc, mr.iloc[mr_ooc], color=RED, s=60, zorder=5)

    ax.set_title("Moving Range (MR) Chart", fontsize=11)
    ax.set_ylabel("Moving Range")
    ax.set_xlabel("Observation")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    return _save(fig, path)


def plot_trend_chart(
    series: pd.Series,
    analysis: Dict[str, Any],
    output_path: str | Path,
) -> str:
    """
    Plot the process trend with a linear regression overlay.

    Parameters
    ----------
    series : pd.Series
        Time-ordered measurement values.
    analysis : dict
        Must contain a "trend" sub-dict with "direction" and "tau".
    output_path : str | Path
        File path (PNG) to save the chart.

    Returns
    -------
    str
        Absolute path to the saved PNG file.
    """
    path   = Path(output_path)
    values = series.dropna().reset_index(drop=True)
    idx    = range(len(values))

    trend = analysis.get("trend", {})
    direction = trend.get("direction", "stable").upper()
    tau       = trend.get("tau", 0.0)

    slope, intercept, *_ = sc_stats.linregress(list(idx), values.values)
    trend_line = [slope * i + intercept for i in idx]

    fig, ax = plt.subplots(figsize=(13, 4))
    ax.plot(idx, values, color=BLUE, lw=1.5, alpha=0.8, label="Observations")
    ax.fill_between(idx, values, alpha=0.08, color=BLUE)
    ax.plot(idx, trend_line, color=RED, ls="--", lw=2.5,
            label=f"Trend — {direction}  (τ={tau:.3f})")

    ax.set_title(f"Process Trend Analysis — {series.name}", fontsize=12, fontweight="bold")
    ax.set_xlabel("Observation")
    ax.set_ylabel(str(series.name))
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    return _save(fig, path)
