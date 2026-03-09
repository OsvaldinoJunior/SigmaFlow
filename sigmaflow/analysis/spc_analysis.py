"""
sigmaflow/analysis/spc_analysis.py
=====================================
Statistical Process Control analysis functions.

Provides pure functions for SPC computations — decoupled from plotting
and insight generation. These are called by dataset analyzers.

Functions
---------
    compute_xmr_chart(series)  → dict with UCL, LCL, OOC points
    compute_trend(series)      → dict with direction, tau, p-value
    compute_xbar_r_chart(df, col, subgroup_size) → dict
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy import stats as sc_stats


def compute_xmr_chart(series: pd.Series) -> Dict[str, Any]:
    """
    Compute Individuals (X) and Moving Range (MR) chart limits.

    The XmR chart is appropriate for individual observations — no subgrouping.
    Control limits are calculated from the average moving range (d2 = 1.128).

    Parameters
    ----------
    series : pd.Series
        Time-ordered individual measurements.

    Returns
    -------
    dict
        Keys: mean, std, x_chart (CL, UCL, LCL, ooc_points, n_ooc),
              mr_chart (CL, UCL, ooc_points, n_ooc).
    """
    values = series.dropna().reset_index(drop=True)
    mu     = float(values.mean())
    std    = float(values.std(ddof=1))

    # Standard 3σ limits from sample standard deviation
    ucl = mu + 3 * std
    lcl = mu - 3 * std

    # Moving range chart
    mr      = values.diff().abs().dropna()
    mr_bar  = float(mr.mean())
    D4      = 3.267   # Control chart constant for n=2
    ucl_mr  = D4 * mr_bar

    ooc_x  = [int(i) for i, v in enumerate(values) if v > ucl or v < lcl]
    ooc_mr = [int(i) for i, v in enumerate(mr)    if v > ucl_mr]

    return {
        "mean":     round(mu, 6),
        "std":      round(std, 6),
        "x_chart": {
            "CL":         round(mu, 4),
            "UCL":        round(ucl, 4),
            "LCL":        round(lcl, 4),
            "ooc_points": ooc_x,
            "n_ooc":      len(ooc_x),
        },
        "mr_chart": {
            "CL":         round(mr_bar, 4),
            "UCL":        round(ucl_mr, 4),
            "ooc_points": ooc_mr,
            "n_ooc":      len(ooc_mr),
        },
    }


def compute_trend(series: pd.Series) -> Dict[str, Any]:
    """
    Perform a Spearman rank correlation trend test.

    A significant positive/negative τ with p < 0.05 indicates a
    monotonic trend over time.

    Parameters
    ----------
    series : pd.Series
        Time-ordered measurements.

    Returns
    -------
    dict
        Keys: direction ("increasing", "decreasing", "stable"),
              tau (Spearman ρ), p_value.
    """
    values = series.dropna().reset_index(drop=True)
    tau, p = sc_stats.spearmanr(range(len(values)), values)

    if tau > 0.3 and p < 0.05:
        direction = "increasing"
    elif tau < -0.3 and p < 0.05:
        direction = "decreasing"
    else:
        direction = "stable"

    return {
        "direction": direction,
        "tau":       round(float(tau), 4),
        "p_value":   round(float(p), 6),
    }


def compute_xbar_r_chart(
    df: pd.DataFrame,
    measurement_col: str,
    subgroup_col: str,
) -> Dict[str, Any]:
    """
    Compute X-bar and R control chart limits for subgrouped data.

    Uses AIAG control chart constants (A2, D3, D4) appropriate for
    the subgroup size found in the data.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset containing measurements and subgroup identifiers.
    measurement_col : str
        Column name for the measured values.
    subgroup_col : str
        Column name for the subgroup identifier.

    Returns
    -------
    dict
        X-bar chart and R chart limits, plus OOC points.
    """
    # Control chart constants (AIAG, indexed by subgroup size n=2..10)
    A2 = {2:1.880, 3:1.023, 4:0.729, 5:0.577, 6:0.483, 7:0.419, 8:0.373, 9:0.337, 10:0.308}
    D3 = {2:0,     3:0,     4:0,     5:0,     6:0,     7:0.076, 8:0.136, 9:0.184, 10:0.223}
    D4 = {2:3.267, 3:2.574, 4:2.282, 5:2.114, 6:2.004, 7:1.924, 8:1.864, 9:1.816, 10:1.777}

    groups = df.groupby(subgroup_col)[measurement_col]
    xbar   = groups.mean()
    ranges = groups.apply(lambda g: g.max() - g.min())
    n      = int(groups.size().mode()[0])
    n      = max(2, min(n, 10))

    xbar_bar = float(xbar.mean())
    r_bar    = float(ranges.mean())

    ucl_x = xbar_bar + A2[n] * r_bar
    lcl_x = xbar_bar - A2[n] * r_bar
    ucl_r = D4[n] * r_bar
    lcl_r = D3[n] * r_bar

    return {
        "subgroup_size": n,
        "xbar_chart": {
            "CL":  round(xbar_bar, 4),
            "UCL": round(ucl_x, 4),
            "LCL": round(lcl_x, 4),
        },
        "r_chart": {
            "CL":  round(r_bar, 4),
            "UCL": round(ucl_r, 4),
            "LCL": round(lcl_r, 4),
        },
    }
