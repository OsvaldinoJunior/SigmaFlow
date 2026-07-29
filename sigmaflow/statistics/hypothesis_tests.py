"""
sigmaflow/statistics/hypothesis_tests.py
==========================================
Statistical hypothesis testing for SigmaFlow v10.

Implements the most common hypothesis tests used in Six Sigma DMAIC:

    1. One-sample t-test     — compare sample mean to a target value
    2. Two-sample t-test     — compare two independent group means
    3. Chi-square test       — test association between categorical variables

All tests follow the same standardized output format and include
automatic plain-language interpretation of results.

Output format
-------------
{
    "test":          "One-Sample t-Test",
    "statistic":     2.41,
    "p_value":       0.032,
    "significant":   True,
    "alpha":         0.05,
    "interpretation": "The p-value (0.032) is less than α=0.05, so..."
}

Usage
-----
    from sigmaflow.statistics.hypothesis_tests import HypothesisTester

    ht = HypothesisTester(df, alpha=0.05)
    results = ht.run_all()
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

ALPHA = 0.05


class HypothesisTester:
    """
    Run a battery of hypothesis tests appropriate for the dataset structure.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataset. Tests are selected based on column structure.
    alpha : float
        Significance level (default 0.05).
    target_col : str, optional
        Primary numeric column to test. Auto-detected if None.
    group_col : str, optional
        Column defining groups for two-sample test. Auto-detected if None.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        alpha: float = ALPHA,
        target_col: Optional[str] = None,
        group_col: Optional[str] = None,
    ) -> None:
        self.df         = df.copy()
        self.alpha      = alpha
        self._target    = target_col
        self._group     = group_col

    # ── Public API ────────────────────────────────────────────────────────────

    def run_all(self) -> Dict[str, Any]:
        """
        Run all applicable hypothesis tests.

        Returns
        -------
        dict with keys: tests (list), summary_text
        """
        tests   = []
        target  = self._resolve_target()
        group   = self._resolve_group(target)

        if target:
            # One-sample t-test: compare to process mean
            pop_mean = float(self.df[target].mean())
            t1 = self.one_sample_ttest(self.df[target], mu=pop_mean)
            tests.append(t1)

            # Two-sample t-test if a group column exists
            if group:
                t2 = self.two_sample_ttest(self.df, target, group)
                if t2:
                    tests.append(t2)

        # Chi-square test on categorical columns
        cat_cols = list(self.df.select_dtypes(include=["object", "category"]).columns)
        if len(cat_cols) >= 2:
            chi = self.chi_square_test(self.df, cat_cols[0], cat_cols[1])
            if chi:
                tests.append(chi)

        n_sig = sum(1 for t in tests if t.get("significant"))
        summary = (
            f"A total of {len(tests)} hypothesis test(s) were performed. "
            f"{n_sig} test(s) yielded statistically significant results (α={self.alpha}). "
            + (
                "Significant findings indicate the presence of meaningful differences "
                "or associations in the process data that warrant engineering investigation."
                if n_sig else
                "No statistically significant differences were detected at the current "
                "significance level. Collect more data or review the measurement system "
                "if practical differences are expected."
            )
        )

        return {"tests": tests, "alpha": self.alpha, "summary_text": summary}

    # ── Tests ─────────────────────────────────────────────────────────────────

    def one_sample_ttest(
        self,
        data: Any,
        mu: float = 0.0,
        alternative: str = "two-sided",
    ) -> Dict[str, Any]:
        """
        One-sample t-test: H₀: μ = mu

        Tests whether the sample mean differs significantly from a
        reference value (e.g., a specification target or historical mean).
        """
        series = pd.Series(data).dropna().values.astype(float)
        if len(series) < 2:
            return {"test": "One-Sample t-Test", "error": "Insufficient data."}

        try:
            stat, p = stats.ttest_1samp(series, popmean=mu, alternative=alternative)
        except Exception as exc:
            return {"test": "One-Sample t-Test", "error": str(exc)}

        n       = len(series)
        df_val  = n - 1
        sig     = p < self.alpha
        ci      = stats.t.interval(1 - self.alpha, df_val, loc=series.mean(), scale=stats.sem(series))

        return {
            "test":             "One-Sample t-Test",
            "statistic":        round(float(stat), 4),
            "p_value":          round(float(p), 6),
            "df":               df_val,
            "n":                n,
            "sample_mean":      round(float(series.mean()), 4),
            "reference_mu":     round(mu, 4),
            "ci_95_lower":      round(float(ci[0]), 4),
            "ci_95_upper":      round(float(ci[1]), 4),
            "significant":      sig,
            "alpha":            self.alpha,
            "interpretation":   self._ttest_interp(sig, p, self.alpha, "sample mean", f"μ₀={mu:.4f}"),
        }

    def two_sample_ttest(
        self,
        df: pd.DataFrame,
        value_col: str,
        group_col: str,
        equal_var: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Two-sample (Welch's) t-test: H₀: μ₁ = μ₂

        Compares the means of two independent groups.
        Uses Welch's t-test by default (does not assume equal variance).
        """
        groups = df[group_col].dropna().unique()
        if len(groups) < 2:
            return None

        g1 = df.loc[df[group_col] == groups[0], value_col].dropna().values.astype(float)
        g2 = df.loc[df[group_col] == groups[1], value_col].dropna().values.astype(float)

        if len(g1) < 2 or len(g2) < 2:
            return None

        try:
            stat, p = stats.ttest_ind(g1, g2, equal_var=equal_var)
        except Exception as exc:
            return {"test": "Two-Sample t-Test", "error": str(exc)}

        sig      = p < self.alpha
        effect_d = (g1.mean() - g2.mean()) / np.sqrt((g1.std(ddof=1)**2 + g2.std(ddof=1)**2) / 2)

        return {
            "test":             "Two-Sample t-Test (Welch)",
            "statistic":        round(float(stat), 4),
            "p_value":          round(float(p), 6),
            "group_col":        group_col,
            "group_1":          str(groups[0]),
            "group_2":          str(groups[1]),
            "mean_1":           round(float(g1.mean()), 4),
            "mean_2":           round(float(g2.mean()), 4),
            "n_1":              len(g1),
            "n_2":              len(g2),
            "cohen_d":          round(float(effect_d), 4),
            "significant":      sig,
            "alpha":            self.alpha,
            "interpretation":   self._ttest_interp(
                sig, p, self.alpha,
                f"group '{groups[0]}'", f"group '{groups[1]}'"
            ),
        }

    def chi_square_test(
        self,
        df: pd.DataFrame,
        col1: str,
        col2: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Chi-square test of independence: H₀: col1 and col2 are independent.

        Tests whether two categorical variables are associated.
        Useful for detecting relationships between defect types and
        process conditions (shift, operator, machine).
        """
        try:
            ct   = pd.crosstab(df[col1].dropna(), df[col2].dropna())
            if ct.shape[0] < 2 or ct.shape[1] < 2:
                return None
            stat, p, dof, expected = stats.chi2_contingency(ct)
        except Exception as exc:
            return {"test": "Chi-Square Test", "error": str(exc)}

        sig     = p < self.alpha
        # Cramér's V (effect size for chi-square)
        n       = ct.values.sum()
        cramers = float(np.sqrt(stat / (n * (min(ct.shape) - 1))))

        return {
            "test":         "Chi-Square Test of Independence",
            "statistic":    round(float(stat), 4),
            "p_value":      round(float(p), 6),
            "dof":          int(dof),
            "col1":         col1,
            "col2":         col2,
            "cramers_v":    round(cramers, 4),
            "significant":  sig,
            "alpha":        self.alpha,
            "interpretation": (
                f"Chi-square statistic={stat:.4f}, p={p:.4f}, dof={dof}. "
                f"Cramér's V={cramers:.3f} (effect size). "
                + (
                    f"There IS a statistically significant association between '{col1}' and '{col2}' (p<{self.alpha})."
                    if sig else
                    f"No significant association between '{col1}' and '{col2}' was detected (p≥{self.alpha})."
                )
            ),
        }

    # ── Auto-detection ────────────────────────────────────────────────────────

    def _resolve_target(self) -> Optional[str]:
        if self._target and self._target in self.df.columns:
            return self._target
        num = self.df.select_dtypes(include="number").columns
        quality_kws = ("defect", "yield", "measurement", "quality", "error", "count")
        for col in num:
            if any(kw in col.lower() for kw in quality_kws):
                return col
        return str(num[0]) if len(num) > 0 else None

    def _resolve_group(self, target: Optional[str]) -> Optional[str]:
        if self._group and self._group in self.df.columns:
            return self._group
        cat_cols = self.df.select_dtypes(include=["object", "category"]).columns
        for col in cat_cols:
            if self.df[col].nunique() == 2:
                return col
        return None

    def _ttest_interp(self, sig: bool, p: float, alpha: float, a: str, b: str) -> str:
        if sig:
            return (
                f"The p-value ({p:.4f}) is less than the significance level α={alpha}. "
                f"The null hypothesis is rejected. There is a statistically significant "
                f"difference between {a} and {b}. "
                f"Engineering investigation of this difference is warranted."
            )
        return (
            f"The p-value ({p:.4f}) is greater than α={alpha}. "
            f"The null hypothesis cannot be rejected at the 0.05 significance level. "
            f"No statistically significant difference was detected between {a} and {b}."
        )
