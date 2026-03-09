"""
sigmaflow/visualization/xbar_r_chart.py
========================================
X-bar and R (Range) control chart for SigmaFlow v10.

Used when data is collected in rational subgroups (e.g., 3–10
measurements per sample). The X-bar chart monitors the process mean;
the R chart monitors within-subgroup variation.

Control limits
--------------
    X-bar:  CL = X̄̄   UCL/LCL = X̄̄ ± A₂ × R̄
    R chart: CL = R̄   UCL = D₄ × R̄   LCL = D₃ × R̄

A₂, D₃, D₄ are standard Shewhart control chart constants
depending on subgroup size n.

Usage
-----
    from sigmaflow.visualization.xbar_r_chart import plot_xbar_r_chart

    # If data is in a 2D array (rows = subgroups, cols = measurements):
    plot_xbar_r_chart(data, output_path="output/figures/xbar_r.png", n=5)

    # If data is in a long-format DataFrame:
    plot_xbar_r_chart(df, output_path="...", subgroup_col="batch", value_col="measurement")
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

# AIAG control chart constants for subgroup sizes n=2..10
_CONSTANTS = {
    2:  {"A2": 1.880, "D3": 0.000, "D4": 3.267, "d2": 1.128},
    3:  {"A2": 1.023, "D3": 0.000, "D4": 2.575, "d2": 1.693},
    4:  {"A2": 0.729, "D3": 0.000, "D4": 2.282, "d2": 2.059},
    5:  {"A2": 0.577, "D3": 0.000, "D4": 2.115, "d2": 2.326},
    6:  {"A2": 0.483, "D3": 0.000, "D4": 2.004, "d2": 2.534},
    7:  {"A2": 0.419, "D3": 0.076, "D4": 1.924, "d2": 2.704},
    8:  {"A2": 0.373, "D3": 0.136, "D4": 1.864, "d2": 2.847},
    9:  {"A2": 0.337, "D3": 0.184, "D4": 1.816, "d2": 2.970},
    10: {"A2": 0.308, "D3": 0.223, "D4": 1.777, "d2": 3.078},
}


def plot_xbar_r_chart(
    data: Any,
    output_path: Union[str, Path],
    n: int = 5,
    subgroup_col: Optional[str] = None,
    value_col: Optional[str]    = None,
    title: str = "X-bar and R Control Chart",
) -> str:
    """
    Generate X-bar and R control chart.

    Parameters
    ----------
    data         : 2D array, DataFrame (long or wide format), or Series
    output_path  : Where to save PNG
    n            : Subgroup size (used if data is a 1D series)
    subgroup_col : Column identifying subgroups (long-format DataFrame)
    value_col    : Column with measurement values (long-format DataFrame)
    title        : Chart title

    Returns
    -------
    str — path to saved PNG
    """
    path = Path(output_path)

    # ── Build subgroup array ──────────────────────────────────────────────────
    if isinstance(data, pd.DataFrame) and subgroup_col and value_col:
        groups      = data.groupby(subgroup_col)[value_col].apply(list)
        max_n       = max(len(g) for g in groups)
        subgroup_n  = min(max_n, 10)
        arr         = np.array([g[:subgroup_n] for g in groups if len(g) >= 2], dtype=float)
    elif isinstance(data, pd.DataFrame):
        arr = data.select_dtypes(include="number").dropna().values
    elif isinstance(data, (pd.Series, list, np.ndarray)):
        values = pd.Series(data).dropna().values.astype(float)
        n      = max(2, min(n, 10))
        # Split into subgroups of size n
        n_groups = len(values) // n
        if n_groups < 2:
            logger.warning("X-bar/R: insufficient data for subgroups of size %d", n)
            return str(path)
        arr = values[:n_groups * n].reshape(n_groups, n)
        subgroup_n = n
    else:
        logger.warning("X-bar/R: unsupported data type.")
        return str(path)

    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)

    subgroup_n = arr.shape[1]
    if subgroup_n < 2 or subgroup_n > 10:
        subgroup_n = max(2, min(subgroup_n, 10))

    consts = _CONSTANTS.get(subgroup_n, _CONSTANTS[5])
    A2, D3, D4 = consts["A2"], consts["D3"], consts["D4"]

    # Compute X-bar and R for each subgroup
    x_bars  = arr.mean(axis=1)
    ranges  = arr.max(axis=1) - arr.min(axis=1)
    n_subs  = len(x_bars)

    x_bar_bar = float(x_bars.mean())
    r_bar     = float(ranges.mean())

    ucl_x = x_bar_bar + A2 * r_bar
    lcl_x = x_bar_bar - A2 * r_bar
    ucl_r = D4 * r_bar
    lcl_r = D3 * r_bar  # = 0 for n ≤ 6

    ooc_x = np.where((x_bars > ucl_x) | (x_bars < lcl_x))[0]
    ooc_r = np.where(ranges > ucl_r)[0]

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    idx       = np.arange(1, n_subs + 1)

    def _draw_chart(ax, values, cl, ucl, lcl, ooc, y_label, sub_title, color):
        ax.plot(idx, values, "o-", color=color, lw=1.5, ms=6, zorder=5)
        ax.axhline(cl,  color="#455A64", lw=1.5, ls="--", label=f"CL={cl:.3f}")
        ax.axhline(ucl, color="#C62828", lw=1.5, ls=":",  label=f"UCL={ucl:.3f}")
        if lcl > 0:
            ax.axhline(lcl, color="#C62828", lw=1.5, ls=":", label=f"LCL={lcl:.3f}")
        ax.fill_between(idx, lcl, ucl, alpha=0.07, color=color)
        for i in ooc:
            ax.scatter(i + 1, values[i], color="#C62828", s=70, zorder=10)
            ax.annotate("OOC", (i + 1, values[i]), textcoords="offset points",
                        xytext=(3, 5), fontsize=7, color="#C62828")
        ax.set_ylabel(y_label, fontsize=10)
        ax.set_title(
            f"{sub_title}  —  "
            f"{'⚠ ' + str(len(ooc)) + ' OOC' if ooc.size else '✓ In control'}",
            fontsize=10,
        )
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(alpha=0.3)

    _draw_chart(axes[0], x_bars, x_bar_bar, ucl_x, lcl_x, ooc_x,
                "Subgroup Mean (X̄)", "X-bar Chart", "#1565C0")
    _draw_chart(axes[1], ranges, r_bar, ucl_r, lcl_r, ooc_r,
                "Subgroup Range (R)", "R Chart", "#2E7D32")

    axes[1].set_xlabel("Subgroup", fontsize=10)
    plt.suptitle(
        f"{title}  (n={subgroup_n}, A₂={A2}, D₃={D3}, D₄={D4})",
        fontsize=12, fontweight="bold",
    )
    plt.tight_layout()

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=130, bbox_inches="tight")
    plt.close(fig)
    logger.debug("Saved X-bar/R chart: %s", path.name)
    return str(path)
