"""
sigmaflow/visualization/correlation_heatmap.py
================================================
Correlation heatmap plot for root cause analysis.

Generates a publication-quality heatmap showing Pearson correlations
between all numeric variables, with the target column highlighted.

Also generates a ranked bar chart of variable importance (correlations
against the target) to make the top influencing factors immediately visible.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def plot_correlation_heatmap(
    df: pd.DataFrame,
    output_path: str | Path,
    target_col: Optional[str] = None,
    title: str = "Correlation Matrix",
) -> str:
    """
    Generate a full correlation heatmap for all numeric columns.

    Color scale: diverging (blue = negative, white = zero, red = positive).
    Values are annotated in each cell.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset — only numeric columns are used.
    output_path : str | Path
        Where to save the PNG.
    target_col : str, optional
        Highlighted column (border drawn around its row/column).
    title : str
        Chart title.

    Returns
    -------
    str
        Absolute path to the saved PNG.
    """
    path   = Path(output_path)
    num_df = df.select_dtypes(include="number").dropna()
    corr   = num_df.corr(method="pearson")
    n      = len(corr)

    fig_size = max(7, n * 1.1)
    fig, ax  = plt.subplots(figsize=(fig_size, fig_size * 0.85))

    cmap = plt.cm.RdBu_r
    im   = ax.imshow(corr.values, cmap=cmap, vmin=-1, vmax=1, aspect="auto")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04,
                 label="Pearson Correlation")

    # Annotate cells
    for i in range(n):
        for j in range(n):
            val   = corr.iloc[i, j]
            color = "white" if abs(val) > 0.6 else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                    fontsize=max(7, 10 - n // 3), color=color, fontweight="bold")

    # Highlight target column
    if target_col and target_col in corr.columns:
        idx = list(corr.columns).index(target_col)
        for spine_loc in ["left", "right", "top", "bottom"]:
            ax.add_patch(plt.Rectangle(
                (idx - 0.5, -0.5), 1, n,
                fill=False, edgecolor="#E65100", lw=2.5, zorder=5,
            ))

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(corr.columns, rotation=40, ha="right", fontsize=9)
    ax.set_yticklabels(corr.columns, fontsize=9)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=14)

    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=130, bbox_inches="tight")
    plt.close(fig)
    logger.debug("Saved correlation heatmap: %s", path.name)
    return str(path)


def plot_variable_importance(
    ranked_variables: List[Dict[str, Any]],
    target_col: str,
    output_path: str | Path,
    top_n: int = 15,
) -> str:
    """
    Generate a horizontal bar chart of variable importance (correlation ranking).

    Bars are colored by correlation strength:
        Red    → strong negative correlation
        Blue   → strong positive correlation
        Orange → moderate
        Gray   → weak / negligible

    Parameters
    ----------
    ranked_variables : list[dict]
        Output from RootCauseAnalyzer — list of {variable, pearson_r, strength}.
    target_col : str
        Name of the quality target column (used in title).
    output_path : str | Path
        Where to save the PNG.
    top_n : int
        Maximum number of variables to display.

    Returns
    -------
    str
        Absolute path to the saved PNG.
    """
    path = Path(output_path)
    data = ranked_variables[:top_n]
    if not data:
        logger.warning("No ranked variables to plot.")
        return str(path)

    labels = [v["variable"] for v in data]
    values = [v["pearson_r"]  for v in data]

    # Color by sign and magnitude
    def _bar_color(r: float) -> str:
        if abs(r) >= 0.70:
            return "#C62828" if r < 0 else "#1565C0"
        if abs(r) >= 0.50:
            return "#E65100" if r < 0 else "#0277BD"
        return "#757575"

    colors = [_bar_color(v) for v in values]

    fig_h = max(4, len(data) * 0.45 + 1.5)
    fig, ax = plt.subplots(figsize=(10, fig_h))

    bars = ax.barh(labels[::-1], values[::-1], color=colors[::-1],
                   edgecolor="white", height=0.65)

    # Value labels
    for bar, val in zip(bars, values[::-1]):
        x_pos = bar.get_width() + (0.02 if val >= 0 else -0.02)
        ha    = "left" if val >= 0 else "right"
        ax.text(x_pos, bar.get_y() + bar.get_height() / 2,
                f"{val:+.3f}", va="center", ha=ha, fontsize=8, fontweight="bold")

    ax.axvline(0,  color="black", lw=1.0)
    ax.axvline( 0.70, color="#C62828", ls="--", lw=1.2, alpha=0.5, label="|r| = 0.70 (strong)")
    ax.axvline(-0.70, color="#C62828", ls="--", lw=1.2, alpha=0.5)
    ax.axvline( 0.50, color="#E65100", ls=":",  lw=1.2, alpha=0.5, label="|r| = 0.50 (moderate)")
    ax.axvline(-0.50, color="#E65100", ls=":",  lw=1.2, alpha=0.5)

    ax.set_xlim(-1.15, 1.15)
    ax.set_xlabel("Pearson Correlation Coefficient (r)", fontsize=10)
    ax.set_title(
        f"Variable Importance Ranking\n(target: '{target_col}')",
        fontsize=12, fontweight="bold",
    )
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(axis="x", alpha=0.3)

    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=130, bbox_inches="tight")
    plt.close(fig)
    logger.debug("Saved variable importance chart: %s", path.name)
    return str(path)
