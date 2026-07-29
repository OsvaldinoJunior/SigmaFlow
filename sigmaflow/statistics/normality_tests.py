"""
sigmaflow/statistics/normality_tests.py
=========================================
Statistical normality testing for SigmaFlow v10.

Implements three standard normality tests used in Six Sigma:

    1. Shapiro-Wilk        — best for n < 2000 (most common in SPC)
    2. Anderson-Darling    — more sensitive to tails; preferred for process data
    3. Kolmogorov-Smirnov  — non-parametric; compares against theoretical normal

All tests return a standardized result dict compatible with the
report generator and HTML dashboard.

Result format
-------------
{
    "test":               "Shapiro-Wilk",
    "statistic":          0.9742,
    "p_value":            0.0832,
    "normal_distribution": True,
    "alpha":              0.05,
    "interpretation":     "...",
    "verdict":            "Normal"
}

Usage
-----
    from sigmaflow.statistics.normality_tests import NormalityTester

    tester = NormalityTester(df["measurement"])
    results = tester.run_all()
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# Default significance level (α)
ALPHA = 0.05


class NormalityTester:
    """
    Run a battery of normality tests on a numeric series.

    Parameters
    ----------
    data : array-like
        The sample data to test. NaN values are dropped.
    alpha : float
        Significance level (default 0.05).
    column_name : str
        Label used in result descriptions.
    """

    def __init__(
        self,
        data: Any,
        alpha: float = ALPHA,
        column_name: str = "measurement",
    ) -> None:
        series = pd.Series(data).dropna()
        self.data        = series.values.astype(float)
        self.n           = len(self.data)
        self.alpha       = alpha
        self.column_name = column_name

    # ── Public API ────────────────────────────────────────────────────────────

    def run_all(self) -> Dict[str, Any]:
        """
        Run all three normality tests and return a combined result.

        Returns
        -------
        dict
            Keys: tests (list), n, overall_normal, summary_text
        """
        if self.n < 3:
            return {"error": "Need at least 3 observations for normality tests."}

        tests = [
            self.shapiro_wilk(),
            self.anderson_darling(),
            self.kolmogorov_smirnov(),
        ]

        all_normal  = all(t.get("normal_distribution", False) for t in tests)
        any_normal  = any(t.get("normal_distribution", False) for t in tests)
        n_normal    = sum(1 for t in tests if t.get("normal_distribution", False))

        # Overall verdict
        if all_normal:
            overall = "Normal"
            summary = (
                f"All three normality tests (Shapiro-Wilk, Anderson-Darling, "
                f"Kolmogorov-Smirnov) indicate that the data follows a normal "
                f"distribution (α={self.alpha}). This supports the use of "
                f"parametric statistical methods and standard SPC techniques."
            )
        elif n_normal >= 2:
            overall = "Likely Normal"
            summary = (
                f"{n_normal}/3 normality tests support a normal distribution. "
                f"The data is likely approximately normal. Proceed with SPC analysis "
                f"but consider robust methods for borderline cases."
            )
        else:
            overall = "Non-Normal"
            summary = (
                f"The majority of normality tests indicate the data does NOT follow "
                f"a normal distribution (α={self.alpha}). Consider non-parametric "
                f"control charts (e.g., median chart) or data transformation "
                f"(Box-Cox, log) before applying standard SPC methods."
            )

        return {
            "column":        self.column_name,
            "n":             self.n,
            "tests":         tests,
            "n_tests_normal": n_normal,
            "overall_verdict": overall,
            "summary_text":  summary,
            "alpha":         self.alpha,
        }

    def shapiro_wilk(self) -> Dict[str, Any]:
        """
        Shapiro-Wilk normality test.

        Best suited for small-to-medium samples (n < 2000).
        H₀: Data comes from a normal distribution.
        H₁: Data does NOT come from a normal distribution.
        """
        # scipy limits Shapiro-Wilk to n <= 5000
        sample = self.data if self.n <= 5000 else self.data[:5000]
        try:
            stat, p = stats.shapiro(sample)
        except Exception as exc:
            return {"test": "Shapiro-Wilk", "error": str(exc)}

        is_normal = p > self.alpha
        return {
            "test":                "Shapiro-Wilk",
            "statistic":           round(float(stat), 6),
            "p_value":             round(float(p), 6),
            "normal_distribution": is_normal,
            "alpha":               self.alpha,
            "verdict":             "Normal" if is_normal else "Non-Normal",
            "interpretation":      self._interp(is_normal, "Shapiro-Wilk", p),
        }

    def anderson_darling(self) -> Dict[str, Any]:
        """
        Anderson-Darling normality test.

        More sensitive to deviations in the tails than Shapiro-Wilk.
        Uses the 5% significance level critical value.
        """
        try:
            result = stats.anderson(self.data, dist="norm")
        except Exception as exc:
            return {"test": "Anderson-Darling", "error": str(exc)}

        stat = float(result.statistic)
        # Find 5% critical value (index 2 in scipy's output)
        idx_5pct  = 2  # corresponds to 5% significance level
        cv_5pct   = float(result.critical_values[idx_5pct])
        is_normal = stat < cv_5pct

        return {
            "test":                "Anderson-Darling",
            "statistic":           round(stat, 6),
            "critical_value_5pct": round(cv_5pct, 4),
            "p_value":             None,  # AD test doesn't return p directly
            "normal_distribution": is_normal,
            "alpha":               self.alpha,
            "verdict":             "Normal" if is_normal else "Non-Normal",
            "interpretation": (
                f"Test statistic A²={stat:.4f} is "
                f"{'less than' if is_normal else 'greater than'} the critical value "
                f"{cv_5pct:.4f} at α=0.05. "
                f"{'Data appears normally distributed.' if is_normal else 'Data does NOT appear normally distributed.'}"
            ),
        }

    def kolmogorov_smirnov(self) -> Dict[str, Any]:
        """
        Kolmogorov-Smirnov test against a normal distribution.

        Compares the empirical CDF to a normal CDF fitted from the data.
        H₀: Data follows a normal distribution.
        """
        try:
            mu, sigma = self.data.mean(), self.data.std(ddof=1)
            if sigma == 0:
                return {"test": "Kolmogorov-Smirnov", "error": "Zero variance."}
            stat, p = stats.kstest(self.data, "norm", args=(mu, sigma))
        except Exception as exc:
            return {"test": "Kolmogorov-Smirnov", "error": str(exc)}

        is_normal = p > self.alpha
        return {
            "test":                "Kolmogorov-Smirnov",
            "statistic":           round(float(stat), 6),
            "p_value":             round(float(p), 6),
            "normal_distribution": is_normal,
            "alpha":               self.alpha,
            "verdict":             "Normal" if is_normal else "Non-Normal",
            "interpretation":      self._interp(is_normal, "Kolmogorov-Smirnov", p),
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _interp(self, is_normal: bool, test_name: str, p: float) -> str:
        """Generate a standardized interpretation sentence."""
        if is_normal:
            return (
                f"The {test_name} test yields p={p:.4f} > α={self.alpha}, so the null "
                f"hypothesis cannot be rejected. The data is consistent with a normal distribution."
            )
        return (
            f"The {test_name} test yields p={p:.4f} ≤ α={self.alpha}, so the null "
            f"hypothesis is rejected. The data does NOT follow a normal distribution."
        )


# ── Convenience function ──────────────────────────────────────────────────────

def run_normality_tests(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    alpha: float = ALPHA,
) -> Dict[str, Any]:
    """
    Run normality tests on all numeric columns of a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
    columns : list[str], optional — restrict to specific columns
    alpha : float — significance level

    Returns
    -------
    dict
        Key per column → NormalityTester.run_all() result.
    """
    num_cols = columns or list(df.select_dtypes(include="number").columns)
    results  = {}
    for col in num_cols:
        tester        = NormalityTester(df[col], alpha=alpha, column_name=col)
        results[col]  = tester.run_all()
        verdict       = results[col].get("overall_verdict", "?")
        logger.debug("Normality [%s]: %s", col, verdict)
    return results
