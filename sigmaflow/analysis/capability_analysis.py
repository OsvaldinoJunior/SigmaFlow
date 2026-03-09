"""
sigmaflow/analysis/capability_analysis.py
==========================================
Process capability analysis functions.

Computes Cp, Cpk, Pp, Ppk, DPMO, and sigma level from a measurement
series and specification limits.

Functions
---------
    compute_capability(series, usl, lsl)   → dict with all indices
    compute_normality(series)              → dict with test results
    dpmo_to_sigma(dpmo)                    → float sigma level
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as sc_stats


def compute_capability(
    series: pd.Series,
    usl: Optional[float],
    lsl: Optional[float],
) -> Dict[str, Any]:
    """
    Compute process capability indices from a measurement series.

    Cp / Cpk use the within-subgroup (short-term) standard deviation.
    Pp / Ppk use the overall (long-term) standard deviation.

    For individual data (no subgroups), both use the sample std dev.

    Parameters
    ----------
    series : pd.Series
        Measurement data (clean, numeric).
    usl : float or None
        Upper specification limit.
    lsl : float or None
        Lower specification limit.

    Returns
    -------
    dict
        Cp, Cpk, Cpu, Cpl, Pp, Ppk, DPMO, sigma_level, n_out_of_spec.
    """
    values = series.dropna()
    mu     = float(values.mean())
    std    = float(values.std(ddof=1))   # sample std dev

    result: Dict[str, Any] = {"usl": usl, "lsl": lsl}

    # ── Bilateral capability (both limits present) ────────────────────────────
    if usl is not None and lsl is not None:
        spec_range = usl - lsl
        cp  = spec_range / (6 * std)
        cpu = (usl - mu) / (3 * std)
        cpl = (mu - lsl) / (3 * std)
        cpk = min(cpu, cpl)
        pp  = spec_range / (6 * std)   # same formula for individual data
        ppk = cpk                       # same for individual data

        n_out = int(((values < lsl) | (values > usl)).sum())
        dpmo  = (n_out / len(values)) * 1_000_000 if len(values) > 0 else 0.0
        sigma = dpmo_to_sigma(dpmo)

        result.update({
            "Cp":              round(cp,  4),
            "Cpk":             round(cpk, 4),
            "Cpu":             round(cpu, 4),
            "Cpl":             round(cpl, 4),
            "Pp":              round(pp,  4),
            "Ppk":             round(ppk, 4),
            "n_out_of_spec":   n_out,
            "dpmo":            round(dpmo, 1),
            "sigma_level":     round(sigma, 2),
        })

    # ── One-sided capability ──────────────────────────────────────────────────
    elif usl is not None:
        cpu = (usl - mu) / (3 * std)
        result.update({"Cpu": round(cpu, 4)})
    elif lsl is not None:
        cpl = (mu - lsl) / (3 * std)
        result.update({"Cpl": round(cpl, 4)})

    return result


def compute_normality(series: pd.Series) -> Dict[str, Any]:
    """
    Test whether a series follows a normal distribution (Shapiro-Wilk).

    Shapiro-Wilk is the preferred test for n < 5000. For larger datasets
    the Anderson-Darling test is used as a fallback.

    Parameters
    ----------
    series : pd.Series

    Returns
    -------
    dict
        Keys: test, statistic, p_value, normal (bool), interpretation.
    """
    values = series.dropna()
    n      = len(values)

    if n < 3:
        return {"test": "insufficient_data", "normal": True}

    if n <= 5000:
        stat, p = sc_stats.shapiro(values[:5000])
        test_name = "Shapiro-Wilk"
    else:
        result   = sc_stats.anderson(values, dist="norm")
        # Map critical value at 5% significance
        stat = float(result.statistic)
        p    = 0.01 if stat > result.critical_values[2] else 0.10
        test_name = "Anderson-Darling"

    normal = bool(p > 0.05)
    interpretation = (
        "Data appears normally distributed (p > 0.05). "
        "Standard capability indices (Cp, Cpk) are appropriate."
        if normal else
        "Data does NOT appear normally distributed (p ≤ 0.05). "
        "Consider non-parametric capability analysis or data transformation."
    )

    return {
        "test":            test_name,
        "statistic":       round(float(stat), 4),
        "p_value":         round(float(p), 6),
        "normal":          normal,
        "interpretation":  interpretation,
    }


def dpmo_to_sigma(dpmo: float) -> float:
    """
    Convert DPMO (Defects Per Million Opportunities) to sigma level.

    Uses the standard Six Sigma conversion with a 1.5σ shift assumption.

    Parameters
    ----------
    dpmo : float
        Defect rate in parts per million.

    Returns
    -------
    float
        Sigma level (0–6).
    """
    if dpmo <= 0:
        return 6.0
    if dpmo >= 1_000_000:
        return 0.0
    p = dpmo / 1_000_000
    z = -sc_stats.norm.ppf(p / 2)
    return round(z + 1.5, 2)
