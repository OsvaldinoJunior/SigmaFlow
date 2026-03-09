"""
sigmaflow/visualization/capability_plots.py
=============================================
Process capability visualization — Cp, Cpk capability plots.

Generates the standard Six Sigma capability plot showing:
    - Process distribution curve
    - Specification limits
    - Cp and Cpk index values annotated on the chart
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


def plot_capability(
    series: pd.Series,
    capability: Dict[str, Any],
    output_path: str | Path,
) -> str:
    """
    Generate a Six Sigma capability plot.

    Shows the process distribution against specification limits,
    with Cp and Cpk values annotated. Color coding:
        Green  → Cpk ≥ 1.33 (capable)
        Orange → 1.00 ≤ Cpk < 1.33 (marginal)
        Red    → Cpk < 1.00 (incapable)

    Parameters
    ----------
    series : pd.Series
        Measurement data.
    capability : dict
        Output from ``compute_capability()``.
    output_path : str | Path
        Where to save the PNG.

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

    usl = capability.get("usl")
    lsl = capability.get("lsl")
    cpk = capability.get("Cpk")
    cp  = capability.get("Cp")
    sigma_level = capability.get("sigma_level")
    dpmo        = capability.get("dpmo")

    # Color by capability level
    if cpk is None:
        curve_color = "#1565C0"
    elif cpk >= 1.33:
        curve_color = "#2E7D32"
    elif cpk >= 1.00:
        curve_color = "#E65100"
    else:
        curve_color = "#C62828"

    fig, ax = plt.subplots(figsize=(12, 5))

    # ── Distribution curve ────────────────────────────────────────────────────
    x_min = mu - 4.5 * std
    x_max = mu + 4.5 * std
    x     = np.linspace(x_min, x_max, 400)
    y     = sc_stats.norm.pdf(x, mu, std)

    ax.plot(x, y, color=curve_color, lw=2.5, label="Process distribution")
    ax.fill_between(x, y, alpha=0.15, color=curve_color)

    # Shade out-of-spec regions
    if lsl is not None:
        x_low = x[x < lsl]
        ax.fill_between(x_low, sc_stats.norm.pdf(x_low, mu, std),
                        alpha=0.4, color="#C62828", label="Out of spec (below LSL)")
        ax.axvline(lsl, color="#E65100", ls="--", lw=2.5, label=f"LSL = {lsl}")

    if usl is not None:
        x_high = x[x > usl]
        ax.fill_between(x_high, sc_stats.norm.pdf(x_high, mu, std),
                        alpha=0.4, color="#C62828", label="Out of spec (above USL)")
        ax.axvline(usl, color="#E65100", ls="--", lw=2.5, label=f"USL = {usl}")

    ax.axvline(mu, color="#1565C0", ls=":", lw=2, label=f"Mean = {mu:.4f}")

    # ── Annotation box ────────────────────────────────────────────────────────
    stats_text_lines = [f"n = {len(values)}", f"μ = {mu:.4f}", f"σ = {std:.4f}"]
    if cp  is not None: stats_text_lines.append(f"Cp  = {cp:.3f}")
    if cpk is not None: stats_text_lines.append(f"Cpk = {cpk:.3f}")
    if sigma_level:     stats_text_lines.append(f"Sigma = {sigma_level:.2f}σ")
    if dpmo is not None: stats_text_lines.append(f"DPMO = {dpmo:,.0f}")

    stats_text = "\n".join(stats_text_lines)
    ax.text(
        0.02, 0.97, stats_text,
        transform=ax.transAxes, fontsize=9,
        verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="lightyellow",
                  alpha=0.85, edgecolor="gray"),
        fontfamily="monospace",
    )

    ax.set_title(f"Process Capability Analysis — {name}", fontsize=13, fontweight="bold")
    ax.set_xlabel(name)
    ax.set_ylabel("Probability Density")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(alpha=0.3)

    plt.tight_layout()

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=130, bbox_inches="tight")
    plt.close(fig)
    logger.debug("Saved capability plot: %s", path.name)
    return str(path)
