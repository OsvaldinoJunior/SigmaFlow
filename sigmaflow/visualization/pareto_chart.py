"""
sigmaflow/visualization/pareto_chart.py
=========================================
Pareto chart plotting function.

The classic Pareto chart shows bars (frequency, descending) plus a
cumulative percentage line. The 80% reference line highlights the
"vital few" categories responsible for most of the defects.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


def plot_pareto_chart(
    pareto: Dict[str, Any],
    title: str,
    output_path: str | Path,
) -> str:
    """
    Plot a Pareto chart from pre-computed pareto analysis results.

    Parameters
    ----------
    pareto : dict
        Output from ``compute_pareto()``, containing:
        "categories", "counts", "cumulative_pct", "vital_few".
    title : str
        Chart title string.
    output_path : str | Path
        File path (PNG) to save the chart.

    Returns
    -------
    str
        Absolute path to the saved PNG file.
    """
    path       = Path(output_path)
    categories = pareto["categories"]
    counts     = pareto["counts"]
    cumulative = pareto["cumulative_pct"]
    vital_few  = set(pareto.get("vital_few", []))
    n          = len(categories)

    colors = ["#1565C0" if c in vital_few else "#90CAF9" for c in categories]

    fig, ax1 = plt.subplots(figsize=(max(10, n * 1.2), 6))
    ax2 = ax1.twinx()

    # Bars
    x = np.arange(n)
    bars = ax1.bar(x, counts, color=colors, edgecolor="white", width=0.7)

    # Cumulative line
    ax2.plot(x, cumulative, "o-", color="#C62828", lw=2.5, ms=6, label="Cumulative %")
    ax2.axhline(80, color="#E65100", ls="--", lw=1.8, label="80% threshold")
    ax2.set_ylim(0, 110)
    ax2.set_ylabel("Cumulative Percentage (%)", fontsize=11)
    ax2.legend(loc="center right", fontsize=9)

    # Formatting
    ax1.set_xticks(x)
    ax1.set_xticklabels(categories, rotation=30, ha="right", fontsize=9)
    ax1.set_ylabel("Frequency / Count", fontsize=11)
    ax1.set_title(title, fontsize=13, fontweight="bold", pad=12)

    # Add count labels above bars
    for bar, count in zip(bars, counts):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(counts) * 0.01,
            str(count), ha="center", va="bottom", fontsize=8, fontweight="bold",
        )

    # Legend for bar colors
    vital_patch   = plt.Rectangle((0, 0), 1, 1, fc="#1565C0", label="Vital Few (≤80%)")
    trivial_patch = plt.Rectangle((0, 0), 1, 1, fc="#90CAF9", label="Useful Many (>80%)")
    ax1.legend(handles=[vital_patch, trivial_patch], loc="upper right", fontsize=9)

    plt.tight_layout()

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=130, bbox_inches="tight")
    plt.close(fig)
    logger.debug("Saved pareto chart: %s", path.name)
    return str(path)
