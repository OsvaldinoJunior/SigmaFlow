"""
sigmaflow/visualization/cusum_chart.py
========================================
CUSUM (Cumulative Sum) control chart for SigmaFlow v10.

The CUSUM chart accumulates deviations from a target value,
making it highly sensitive to small sustained shifts (±0.5–2σ)
that the Shewhart XmR chart may miss.

Parameters
----------
k : float   Reference value = allowable slack (default 0.5σ)
h : float   Decision interval = control limit (default 4σ-equivalent)

Usage
-----
    from sigmaflow.visualization.cusum_chart import plot_cusum_chart
    path = plot_cusum_chart(df["thickness"], output_path="output/figures/cusum.png")
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, Union

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def plot_cusum_chart(
    data: Any,
    output_path: Union[str, Path],
    target: Optional[float] = None,
    k_ref: float = 0.5,
    h_limit: float = 4.0,
    title: str = "CUSUM Control Chart",
    col_name: str = "Value",
) -> str:
    """
    Generate a CUSUM control chart.

    The chart plots cumulative upper (C⁺) and lower (C⁻) sums.
    A signal occurs when either exceeds ±h·σ.

    Parameters
    ----------
    data        : Series or array of numeric values
    output_path : Where to save the PNG
    target      : Target mean (default: sample mean)
    k_ref       : Reference value as fraction of σ (default 0.5)
    h_limit     : Decision interval as multiple of σ (default 4.0)
    title       : Chart title
    col_name    : Label for the y-axis

    Returns
    -------
    str — path to saved PNG
    """
    path   = Path(output_path)
    series = pd.Series(data).dropna().values.astype(float)
    n      = len(series)

    if n < 4:
        logger.warning("CUSUM: need at least 4 observations.")
        return str(path)

    mu    = target if target is not None else float(series.mean())
    sigma = float(series.std(ddof=1))
    if sigma == 0:
        sigma = 1.0

    k_val = k_ref * sigma
    h_val = h_limit * sigma

    # Compute CUSUM
    c_plus  = np.zeros(n)
    c_minus = np.zeros(n)
    for i in range(1, n):
        c_plus[i]  = max(0.0, c_plus[i-1]  + (series[i] - mu) - k_val)
        c_minus[i] = max(0.0, c_minus[i-1] - (series[i] - mu) - k_val)

    ooc_plus  = np.where(c_plus  > h_val)[0]
    ooc_minus = np.where(c_minus > h_val)[0]
    n_ooc     = len(ooc_plus) + len(ooc_minus)

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # Top: raw data
    axes[0].plot(series, color="#1565C0", lw=1.2, alpha=0.8, label=col_name)
    axes[0].axhline(mu, color="#455A64", ls="--", lw=1.2, label=f"Target μ={mu:.3f}")
    axes[0].axhline(mu + 3*sigma, color="#C62828", ls=":", lw=1.2, alpha=0.7, label="+3σ")
    axes[0].axhline(mu - 3*sigma, color="#C62828", ls=":", lw=1.2, alpha=0.7, label="-3σ")
    axes[0].set_ylabel(col_name, fontsize=10)
    axes[0].set_title(f"Individual Values  (μ={mu:.3f}, σ={sigma:.3f})", fontsize=10)
    axes[0].legend(fontsize=8, loc="upper right")
    axes[0].grid(alpha=0.3)

    # Bottom: CUSUM
    axes[1].plot(c_plus,  color="#1565C0", lw=1.5, label="C⁺ (upper CUSUM)")
    axes[1].plot(-c_minus, color="#E65100", lw=1.5, label="C⁻ (lower CUSUM, neg.)")
    axes[1].axhline( h_val, color="#C62828", ls="--", lw=1.5, label=f"+H={h_val:.2f}")
    axes[1].axhline(-h_val, color="#C62828", ls="--", lw=1.5, label=f"-H={h_val:.2f}")
    axes[1].axhline(0, color="black", lw=0.8, alpha=0.5)

    # Highlight OOC points
    for i in ooc_plus:
        axes[1].axvline(i, color="#C62828", alpha=0.25, lw=2)
    for i in ooc_minus:
        axes[1].axvline(i, color="#E65100", alpha=0.25, lw=2)

    axes[1].set_xlabel("Observation", fontsize=10)
    axes[1].set_ylabel("CUSUM statistic", fontsize=10)
    axes[1].set_title(
        f"CUSUM  (k={k_ref}σ, H={h_limit}σ)  —  "
        f"{'🔴 ' + str(n_ooc) + ' signal(s) detected' if n_ooc else '✓ No signals'}",
        fontsize=10,
    )
    axes[1].legend(fontsize=8, loc="upper right")
    axes[1].grid(alpha=0.3)

    plt.suptitle(title, fontsize=13, fontweight="bold")
    plt.tight_layout()

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=130, bbox_inches="tight")
    plt.close(fig)
    logger.debug("Saved CUSUM chart: %s", path.name)
    return str(path)
