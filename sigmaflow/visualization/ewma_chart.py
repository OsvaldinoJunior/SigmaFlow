"""
sigmaflow/visualization/ewma_chart.py
========================================
EWMA (Exponentially Weighted Moving Average) control chart for SigmaFlow v10.

The EWMA chart gives exponentially decreasing weights to past observations,
making it more sensitive to small process shifts (0.5–2σ) than the Shewhart
XmR chart, while being less sensitive to non-normality.

The smoothing parameter λ controls the weighting:
    λ = 0.05–0.25 → sensitive to small shifts
    λ = 0.40–1.00 → approaches Shewhart chart behavior (λ=1 = XmR)

Control limits:
    UCL/LCL = μ ± L·σ · sqrt(λ/(2-λ) · [1-(1-λ)^(2i)])

Usage
-----
    from sigmaflow.visualization.ewma_chart import plot_ewma_chart
    path = plot_ewma_chart(df["thickness"], output_path="output/figures/ewma.png")
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


def plot_ewma_chart(
    data: Any,
    output_path: Union[str, Path],
    target: Optional[float] = None,
    lam: float = 0.20,
    L: float   = 3.0,
    title: str = "EWMA Control Chart",
    col_name: str = "Value",
) -> str:
    """
    Generate an EWMA control chart.

    Parameters
    ----------
    data        : Series or array of numeric values
    output_path : Where to save the PNG
    target      : Process target mean (default: sample mean)
    lam         : EWMA smoothing parameter λ, 0 < λ ≤ 1 (default 0.20)
    L           : Control limit multiplier (default 3.0 → 3σ)
    title       : Chart title
    col_name    : Variable name for labels

    Returns
    -------
    str — path to saved PNG
    """
    path   = Path(output_path)
    series = pd.Series(data).dropna().values.astype(float)
    n      = len(series)

    if n < 4:
        logger.warning("EWMA: need at least 4 observations.")
        return str(path)

    mu    = target if target is not None else float(series.mean())
    sigma = float(series.std(ddof=1))
    if sigma == 0:
        sigma = 1.0

    # Compute EWMA
    ewma = np.zeros(n)
    ewma[0] = mu
    for i in range(1, n):
        ewma[i] = lam * series[i] + (1 - lam) * ewma[i-1]

    # Variable-width control limits
    idx    = np.arange(1, n + 1)
    factor = np.sqrt(lam / (2 - lam) * (1 - (1 - lam) ** (2 * idx)))
    ucl    = mu + L * sigma * factor
    lcl    = mu - L * sigma * factor

    ooc    = np.where((ewma > ucl) | (ewma < lcl))[0]
    n_ooc  = len(ooc)

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # Top: raw observations
    axes[0].plot(series, color="#546E7A", lw=1.0, alpha=0.8, label=col_name)
    axes[0].axhline(mu,         color="#455A64", ls="--", lw=1.2, label=f"μ={mu:.3f}")
    axes[0].axhline(mu+3*sigma, color="#C62828", ls=":",  lw=1.2, alpha=0.7, label="+3σ")
    axes[0].axhline(mu-3*sigma, color="#C62828", ls=":",  lw=1.2, alpha=0.7, label="-3σ")
    axes[0].set_ylabel(col_name, fontsize=10)
    axes[0].set_title(f"Individual Values  (μ={mu:.3f}, σ={sigma:.3f})", fontsize=10)
    axes[0].legend(fontsize=8, loc="upper right")
    axes[0].grid(alpha=0.3)

    # Bottom: EWMA
    axes[1].plot(ewma, color="#1565C0", lw=2.0, label=f"EWMA (λ={lam})", zorder=5)
    axes[1].plot(ucl,  color="#C62828", lw=1.5, ls="--", label=f"UCL/LCL (L={L}σ)")
    axes[1].plot(lcl,  color="#C62828", lw=1.5, ls="--")
    axes[1].axhline(mu, color="#455A64", ls=":", lw=1.0)
    axes[1].fill_between(range(n), lcl, ucl, alpha=0.08, color="#1565C0")

    # OOC markers
    for i in ooc:
        axes[1].scatter(i, ewma[i], color="#C62828", s=60, zorder=10)

    axes[1].set_xlabel("Observation", fontsize=10)
    axes[1].set_ylabel("EWMA statistic", fontsize=10)
    axes[1].set_title(
        f"EWMA Chart  (λ={lam}, L={L})  —  "
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
    logger.debug("Saved EWMA chart: %s", path.name)
    return str(path)
