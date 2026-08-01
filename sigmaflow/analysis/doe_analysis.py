"""
sigmaflow/analysis/doe_analysis.py
=====================================
Design of Experiments (DOE) analysis for SigmaFlow v10.

Implements one-way and two-way ANOVA using scipy, with
main effects plots and interaction plots using matplotlib.

Capabilities
------------
- One-way ANOVA for each factor vs the response
- Two-way ANOVA using manual SS decomposition (no statsmodels)
- Main effects plots (mean response per factor level)
- Interaction plots (response by factor × level combinations)
- Automatic identification of significant factors

Output
------
{
    "response":    "yield",
    "factors":     ["Temperature", "Pressure"],
    "anova_table": [
        {"factor": "Temperature", "f_value": 8.4, "p_value": 0.003, "significant": True},
        ...
    ],
    "significant_factors": ["Temperature"],
    "interpretation": "...",
}

Usage
-----
    from sigmaflow.analysis.doe_analysis import DOEAnalyzer

    doe = DOEAnalyzer(df, response_col="yield", factor_cols=["Temp","Pressure"])
    results = doe.run()
    plots   = doe.generate_plots(fig_dir)
"""
from __future__ import annotations

import logging
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize

logger = logging.getLogger(__name__)

ALPHA = 0.05


class DOEAnalyzer:
    """
    One-way and two-way ANOVA for Design of Experiments analysis.
    
    Parameters
    ----------
    df : pd.DataFrame
    response_col : str, optional
        Response variable (Y). Auto-detected if None.
    factor_cols : list[str], optional
        Experimental factor columns. Auto-detected if None.
    alpha : float
        Significance level.
    method : str, optional
        Analysis method: "anova" (default), "fractional", or "rsm".
        "fractional" uses 2^(k-p) fractional factorial design.
        "rsm" uses Central Composite Design + quadratic response surface.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        response_col: Optional[str] = None,
        factor_cols:  Optional[List[str]] = None,
        alpha: float  = ALPHA,
        method: str = "anova",
    ) -> None:
        self.df       = df.dropna()
        self.alpha    = alpha
        self._response = response_col
        self._factors  = factor_cols
        self._method   = method
        self._results: Dict[str, Any] = {}

    def run(self) -> Dict[str, Any]:
        """Run DOE analysis and return results dict."""
        response = self._resolve_response()
        factors  = self._resolve_factors(response)

        if not response or not factors:
            return {"error": "Need a response variable and at least one factor column."}

        logger.info("DOE: response='%s', factors=%s, method='%s'", response, factors, self._method)

        # ── Method dispatch ─────────────────────────────────────────────────────
        if self._method == "fractional":
            return self._run_fractional(response, factors)
        elif self._method == "rsm":
            return self._run_rsm(response)
        else:
            # Default: standard ANOVA
            result = self._run_anova(response, factors)
            
            # Auto-suggest if dataset looks like a designed experiment
            suggestion = self._suggest_method(factors)
            if suggestion:
                result["method_suggestion"] = suggestion
            
            return result

    # ── Private: ANOVA (default method) ────────────────────────────────────────

    def _run_anova(self, response: str, factors: List[str]) -> Dict[str, Any]:
        """Run standard one-way and two-way ANOVA."""
        y = self.df[response].values.astype(float)

        # One-way ANOVA for each factor
        anova_rows = []
        for factor in factors:
            row = self._one_way_anova(y, factor)
            if row:
                anova_rows.append(row)

        sig_factors = [r["factor"] for r in anova_rows if r["significant"]]

        interp = self._build_interpretation(response, factors, sig_factors, anova_rows)

        self._results = {
            "response":           response,
            "factors":            factors,
            "n":                  len(y),
            "anova_table":        anova_rows,
            "significant_factors": sig_factors,
            "interpretation":     interp,
            "alpha":              self.alpha,
        }
        return self._results

    # ── Private: Fractional Factorial Design ───────────────────────────────────

    def _run_fractional(self, response: str, factors: List[str]) -> Dict[str, Any]:
        """Run fractional factorial analysis (2^(k-p) design)."""
        y = self.df[response].values.astype(float)
        k = len(factors)
        
        # For fractional factorial, we need at least 3 factors
        if k < 3:
            return {"error": "Fractional factorial requires at least 3 factors."}
        
        # Use p=1 (half-fraction) by default
        p = 1
        if len(self.df) < 2 ** (k - p):
            return {"error": f"Insufficient runs for 2^({k}-{p}) design. Need at least {2 ** (k - p)} runs."}
        
        design, generators = self.fractional_factorial_2k_p(k, p)
        
        # Run standard ANOVA on the factors
        y_vals = self.df[response].values.astype(float)
        anova_rows = []
        for factor in factors:
            row = self._one_way_anova(y_vals, factor)
            if row:
                anova_rows.append(row)
        
        sig_factors = [r["factor"] for r in anova_rows if r["significant"]]
        interp = self._build_interpretation(response, factors, sig_factors, anova_rows)
        
        self._results = {
            "response":           response,
            "factors":            factors,
            "n":                  len(y_vals),
            "anova_table":        anova_rows,
            "significant_factors": sig_factors,
            "interpretation":     interp,
            "alpha":              self.alpha,
            "method":             "fractional",
            "design":             design.tolist(),
            "generators":         generators,
            "fraction":           f"2^({k}-{p})",
        }
        return self._results

    # ── Private: Response Surface Methodology (RSM) ────────────────────────────

    def _run_rsm(self, response: str) -> Dict[str, Any]:
        """Run Response Surface Methodology with Central Composite Design."""
        # Check if we already have RSM results
        if not hasattr(self, '_rsm_results') or self._rsm_results is None:
            self._rsm_results = self.fit_rsm()
        
        if "error" in self._rsm_results:
            return self._rsm_results
        
        # Generate RSM plots
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = self.generate_rsm_plots(tmpdir)
            self._rsm_results["plots"] = paths
        
        self._results = {
            **self._rsm_results,
            "method": "rsm",
        }
        return self._results

    # ── Private: Method Suggestion ────────────────────────────────────────────────

    def _suggest_method(self, factors: List[str]) -> Optional[str]:
        """
        Analyze factor columns to suggest if this looks like a designed experiment.
        
        Checks for:
        - Factor values in {-1, 0, 1} (CCD) or {-1, 1} (full/fractional factorial)
        - Number of runs consistent with 2^k, 2^(k-p), or CCD patterns
        
        Returns suggestion string or None.
        """
        if len(self.df) < 4:
            return None
        
        # Check factor value patterns
        factor_cols = [f for f in factors if f in self.df.columns]
        if not factor_cols:
            return None
        
        n_factors = len(factor_cols)
        n_runs = len(self.df)
        
        # Check if all factor values are in {-1, 1} or {-1, 0, 1}
        all_binary = True
        all_ternary = True
        for col in factor_cols:
            unique_vals = set(self.df[col].dropna().unique())
            if not unique_vals.issubset({-1, 1, -1.0, 1.0}):
                all_binary = False
            if not unique_vals.issubset({-1, 0, 1, -1.0, 0.0, 1.0}):
                all_ternary = False
        
        # Full factorial: 2^k runs, all binary
        if all_binary and n_runs == 2 ** n_factors:
            return "This dataset has structure consistent with a full 2^{} factorial design — consider method='fractional' for explicit fractional factorial analysis.".format(len(factor_cols))
        
        # Fractional factorial: 2^(k-p) runs, all binary
        if all_binary and n_runs < 2 ** n_factors:
            # Find p such that 2^(k-p) ≈ n_runs
            for p in range(1, n_factors):
                expected = 2 ** (n_factors - p)
                if expected == n_runs:
                    return "This dataset has structure consistent with a 2^({}-{}) fractional factorial design ({} runs) — consider method='fractional' for explicit analysis.".format(n_factors, p, n_runs)
        
        # CCD: 2^k + 2*k + center_points runs, values include -alpha, -1, 0, 1, alpha
        # Check if values are approximately in the CCD pattern
        ccd_pattern = True
        for col in factor_cols:
            unique_vals = set(round(v, 4) for v in self.df[col].dropna().unique())
            # Allow values approximately -alpha, -1, 0, 1, alpha where alpha = sqrt(k)
            alpha = np.sqrt(n_factors)
            expected_vals = {-alpha, -1, 0, 1, alpha}
            # Check if all values are close to expected
            for v in unique_vals:
                if not any(abs(v - ev) < 0.001 for ev in expected_vals):
                    ccd_pattern = False
                    break
            if not ccd_pattern:
                break
        
        if ccd_pattern:
            for center_pts in range(1, 6):
                expected_ccd = 2 ** n_factors + 2 * n_factors + center_pts
                if expected_ccd == n_runs:
                    return "This dataset has structure consistent with a Central Composite Design (CCD) with {} center points ({} runs, {} factors) — consider method='rsm' for Response Surface Methodology.".format(center_pts, n_runs, n_factors)
        
        return None

    def generate_plots(self, fig_dir: str | Path) -> List[str]:
        """Generate main effects and interaction plots."""
        if not self._results:
            self.run()
        if "error" in self._results:
            return []

        fig_dir = Path(fig_dir)
        fig_dir.mkdir(parents=True, exist_ok=True)
        paths = []

        paths.append(self._plot_main_effects(fig_dir))
        paths.append(self._plot_anova_table(fig_dir))
        if len(self._results["factors"]) >= 2:
            paths.append(self._plot_interactions(fig_dir))

        return [p for p in paths if p]

    # ── Private: ANOVA ────────────────────────────────────────────────────────

    def _one_way_anova(self, y: np.ndarray, factor: str) -> Optional[Dict[str, Any]]:
        """Compute one-way ANOVA for factor vs response."""
        col   = self.df[factor]
        levels = col.dropna().unique()
        if len(levels) < 2:
            return None

        groups = [y[col == lv] for lv in levels if len(y[col == lv]) >= 1]
        if len(groups) < 2:
            return None

        try:
            f_stat, p = stats.f_oneway(*groups)
        except Exception:
            return None

        # Effect size: eta-squared
        grand_mean = y.mean()
        ss_between = sum(len(g) * (g.mean() - grand_mean)**2 for g in groups)
        ss_total   = ((y - grand_mean)**2).sum()
        eta_sq     = ss_between / ss_total if ss_total > 0 else 0.0

        n_groups = len(groups)
        df_between = n_groups - 1
        df_within  = len(y) - n_groups

        return {
            "factor":       factor,
            "levels":       int(n_groups),
            "df_between":   int(df_between),
            "df_within":    int(df_within),
            "f_value":      round(float(f_stat), 4),
            "p_value":      round(float(p), 6),
            "eta_squared":  round(float(eta_sq), 4),
            "significant":  bool(p < self.alpha),
        }

    # ── Private: plots ────────────────────────────────────────────────────────

    def _plot_main_effects(self, fig_dir: Path) -> str:
        """Main effects plot: mean response per level for each factor."""
        response = self._results["response"]
        factors  = self._results["factors"]
        y        = self.df[response].values.astype(float)
        grand_mean = y.mean()

        n_factors = len(factors)
        fig, axes = plt.subplots(1, n_factors, figsize=(4.5 * n_factors, 4.5), sharey=False)
        if n_factors == 1:
            axes = [axes]

        for ax, factor in zip(axes, factors):
            groups    = self.df.groupby(factor)[response]
            means     = groups.mean().sort_index()
            ci        = groups.sem().sort_index() * 1.96
            sig_row   = next((r for r in self._results["anova_table"] if r["factor"] == factor), {})
            is_sig    = sig_row.get("significant", False)
            color     = "#C62828" if is_sig else "#1565C0"

            ax.plot(range(len(means)), means.values, "o-", color=color, lw=2, ms=8)
            ax.fill_between(range(len(means)),
                            means.values - ci.values,
                            means.values + ci.values,
                            alpha=0.15, color=color)
            ax.axhline(grand_mean, ls="--", color="#757575", lw=1.2, label=f"Grand mean={grand_mean:.2f}")
            ax.set_xticks(range(len(means)))
            ax.set_xticklabels([str(x) for x in means.index], rotation=20, ha="right")
            ax.set_xlabel(factor, fontsize=11)
            ax.set_ylabel(response if factor == factors[0] else "")
            sig_label = f"  p={sig_row.get('p_value','?'):.3f} ★" if is_sig else f"  p={sig_row.get('p_value','?'):.3f}"
            ax.set_title(f"{factor}{sig_label}", fontweight="bold" if is_sig else "normal")
            ax.grid(alpha=0.3)

        plt.suptitle(f"Main Effects Plot — Response: {response}", fontweight="bold", fontsize=12)
        plt.tight_layout()
        path = str(fig_dir / "doe_main_effects.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    def _plot_anova_table(self, fig_dir: Path) -> str:
        """Visual ANOVA summary table as a figure."""
        rows  = self._results["anova_table"]
        if not rows:
            return ""

        fig, ax = plt.subplots(figsize=(10, max(2.5, len(rows) * 0.55 + 1.5)))
        ax.axis("off")

        headers = ["Factor", "Levels", "df (between)", "F-value", "p-value", "Eta²", "Significant?"]
        table_data = [
            [
                r["factor"],
                str(r["levels"]),
                str(r["df_between"]),
                f"{r['f_value']:.3f}",
                f"{r['p_value']:.4f}",
                f"{r['eta_squared']:.3f}",
                "★ YES" if r["significant"] else "no",
            ]
            for r in rows
        ]

        colors_row = [
            ["#FFCDD2" if r["significant"] else "#F5F5F5"] * len(headers)
            for r in rows
        ]

        tbl = ax.table(
            cellText=table_data,
            colLabels=headers,
            cellColours=colors_row,
            cellLoc="center",
            loc="center",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(10)
        tbl.scale(1, 1.5)
        # Style header
        for j in range(len(headers)):
            tbl[0, j].set_facecolor("#102027")
            tbl[0, j].set_text_props(color="white", fontweight="bold")

        ax.set_title(f"ANOVA Table — Response: {self._results['response']}", fontweight="bold", fontsize=12, pad=10)
        plt.tight_layout()
        path = str(fig_dir / "doe_anova_table.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    def _plot_interactions(self, fig_dir: Path) -> str:
        """Interaction plot for first two factors."""
        response = self._results["response"]
        f1, f2   = self._results["factors"][:2]

        fig, ax = plt.subplots(figsize=(9, 5))
        colors  = plt.cm.Set2.colors

        levels_f2 = sorted(self.df[f2].unique())
        for i, lv2 in enumerate(levels_f2[:6]):
            subset = self.df[self.df[f2] == lv2]
            means  = subset.groupby(f1)[response].mean().sort_index()
            ax.plot(range(len(means)), means.values,
                    "o-", color=colors[i % len(colors)], lw=2, ms=7,
                    label=f"{f2}={lv2}")
            for xi, yi in enumerate(means.values):
                ax.annotate(f"{yi:.2f}", (xi, yi), textcoords="offset points",
                            xytext=(0, 8), ha="center", fontsize=7, color=colors[i % len(colors)])

        levels_f1 = sorted(self.df[f1].unique())
        ax.set_xticks(range(len(levels_f1)))
        ax.set_xticklabels([str(x) for x in levels_f1])
        ax.set_xlabel(f1, fontsize=11)
        ax.set_ylabel(f"Mean {response}", fontsize=11)
        ax.set_title(f"Interaction Plot: {f1} × {f2} → {response}", fontweight="bold")
        ax.legend(title=f2, fontsize=9)
        ax.grid(alpha=0.3)
        plt.tight_layout()
        path = str(fig_dir / "doe_interaction_plot.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    # ── Auto-detection ────────────────────────────────────────────────────────

    def _resolve_response(self) -> Optional[str]:
        if self._response and self._response in self.df.columns:
            return self._response
        num = self.df.select_dtypes(include="number").columns
        quality_kws = ("yield", "response", "output", "defect", "quality", "result")
        for col in num:
            if any(kw in col.lower() for kw in quality_kws):
                return col
        return str(num[-1]) if len(num) > 0 else None

    def _resolve_factors(self, response: Optional[str]) -> List[str]:
        if self._factors:
            return [f for f in self._factors if f in self.df.columns]
        # Categorical or low-cardinality columns make good factors
        candidates = []
        for col in self.df.columns:
            if col == response:
                continue
            nuniq = self.df[col].nunique()
            if nuniq <= 8 or self.df[col].dtype in ["object", "category"]:
                candidates.append(col)
        return candidates[:4]  # Limit to 4 factors

    def _build_interpretation(
        self,
        response: str,
        factors: List[str],
        sig_factors: List[str],
        anova_rows: List[Dict],
    ) -> str:
        parts = [
            f"One-way ANOVA was performed for each of {len(factors)} factor(s) "
            f"against the response variable '{response}'. "
        ]
        if sig_factors:
            parts.append(
                f"Statistically significant factors (α={self.alpha}): "
                f"{', '.join(sig_factors)}. "
                "These factors have a significant effect on the response and should "
                "be prioritized in process optimization."
            )
        else:
            parts.append(
                f"No factor showed a statistically significant effect on '{response}' "
                f"at α={self.alpha}. Consider increasing sample size or exploring "
                "interaction effects."
            )
        for r in anova_rows:
            parts.append(
                f" {r['factor']}: F={r['f_value']:.2f}, p={r['p_value']:.4f}, "
                f"η²={r['eta_squared']:.3f}."
            )
        return "".join(parts)

    # ─── Sprint 4: Fractional Factorial Design + RSM ────────────────────────────

    @staticmethod
    def fractional_factorial_2k_p(k: int, p: int) -> Tuple[np.ndarray, List[str]]:
        """
        Generate a 2^(k-p) fractional factorial design.

        Parameters
        ----------
        k : int
            Number of factors.
        p : int
            Fraction (2^(-p)). e.g., k=5, p=1 gives 2^4 = 16 runs.

        Returns
        -------
        design : np.ndarray
            Design matrix with -1/+1 coding.
        generators : list[str]
            Defining relation generators.
        """
        if p >= k:
            raise ValueError("p must be less than k")

        n_base = 2 ** (k - p)
        # Create full factorial for first (k-p) factors
        base_factors = k - p
        design = np.zeros((n_base, k), dtype=int)

        # Generate full factorial for base factors
        for i in range(n_base):
            for j in range(base_factors):
                design[i, j] = -1 if (i // (2 ** (base_factors - 1 - j))) % 2 == 0 else 1

        # Add p factors using generators
        # Standard generators for resolution V designs
        # For k=5, p=1: E = ABCD
        # For k=6, p=1: F = ABCD
        # For k=6, p=2: E = ABCD, F = ABD
        generators = []

        if k == 5 and p == 1:
            # 2^(5-1) Resolution V: E = ABCD
            design[:, 4] = design[:, 0] * design[:, 1] * design[:, 2] * design[:, 3]
            generators.append("E = ABCD")
        elif k == 6 and p == 1:
            # 2^(6-1) Resolution V: F = ABCD
            design[:, 5] = design[:, 0] * design[:, 1] * design[:, 2] * design[:, 3]
            generators.append("F = ABCD")
        elif k == 6 and p == 2:
            # 2^(6-2) Resolution IV: E = ABCD, F = ABD
            design[:, 4] = design[:, 0] * design[:, 1] * design[:, 2] * design[:, 3]
            design[:, 5] = design[:, 0] * design[:, 1] * design[:, 3]
            generators.append("E = ABCD")
            generators.append("F = ABD")
        elif k == 7 and p == 1:
            # 2^(7-1) Resolution IV: G = ABCDEF
            design[:, 6] = design[:, 0] * design[:, 1] * design[:, 2] * design[:, 3] * design[:, 4] * design[:, 5]
            generators.append("G = ABCDEF")
        else:
            # Default: use highest-order interactions for remaining factors
            for i in range(p):
                factor_idx = base_factors + i
                # Use product of first base_factors as generator
                gen = np.prod(design[:, :base_factors], axis=1)
                design[:, factor_idx] = gen
                factor_name = chr(65 + factor_idx)
                base_names = [chr(65 + j) for j in range(base_factors)]
                generators.append(f"{factor_name} = {' * '.join(base_names)}")

        factor_names = [chr(65 + i) for i in range(k)]
        return design, generators

    @staticmethod
    def central_composite_design(k: int, center_points: int = 3, alpha: Optional[float] = None) -> np.ndarray:
        """
        Generate a Central Composite Design (CCD) for RSM.

        Parameters
        ----------
        k : int
            Number of factors.
        center_points : int
            Number of center points (default 3).
        alpha : float, optional
            Axial distance. If None, uses sqrt(k) for rotatability.

        Returns
        -------
        design : np.ndarray
            Design matrix with coded levels.
        """
        if alpha is None:
            alpha = np.sqrt(k)

        # Factorial portion (2^k)
        fact_size = 2 ** k
        factorial = np.zeros((fact_size, k), dtype=float)
        for i in range(fact_size):
            for j in range(k):
                factorial[i, j] = -1 if (i // (2 ** (k - 1 - j))) % 2 == 0 else 1

        # Center points
        center = np.zeros((center_points, k), dtype=float)

        # Star points (2k)
        star = np.zeros((2 * k, k), dtype=float)
        for i in range(k):
            star[2 * i, i] = -alpha
            star[2 * i + 1, i] = alpha

        design = np.vstack([factorial, center, star])
        return design

    def fit_rsm(self, factors: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Fit a quadratic response surface model.

        Model: y = β0 + Σβi*xi + Σβii*xi² + ΣΣβij*xi*xj

        Parameters
        ----------
        factors : list[str], optional
            Factors to include. If None, uses all numeric factors.

        Returns
        -------
        dict with:
            - coefficients: dict of model coefficients
            - r2, adj_r2: model fit statistics
            - optimum: stationary point coordinates
            - nature: "maximum", "minimum", or "saddle"
            - predicted_optimum: predicted response at optimum
        """
        # Run standard ANOVA first to get factors/response
        if not self._results:
            self._run_anova(self._resolve_response(), self._resolve_factors(self._resolve_response()))

        if "error" in self._results:
            return {"error": self._results["error"]}

        response = self._results["response"]
        all_factors = self._results["factors"]

        if factors is None:
            factors = [f for f in all_factors if self.df[f].dtype in ['float64', 'int64', 'float32', 'int32']]
        factors = [f for f in factors if f in self.df.columns]

        if len(factors) < 1:
            return {"error": "Need at least 1 numeric factor for RSM"}

        y = self.df[response].values.astype(float)
        X_data = self.df[factors].values.astype(float)
        n = len(y)
        k = len(factors)

        # Build quadratic model matrix
        # Columns: intercept, linear (k), quadratic (k), interactions (k choose 2)
        n_terms = 1 + k + k + k * (k - 1) // 2
        X_model = np.ones((n, n_terms))

        col_names = ["intercept"]

        # Linear terms
        for i in range(k):
            X_model[:, 1 + i] = X_data[:, i]
            col_names.append(factors[i])

        # Quadratic terms
        quad_start = 1 + k
        for i in range(k):
            X_model[:, quad_start + i] = X_data[:, i] ** 2
            col_names.append(f"{factors[i]}^2")

        # Interaction terms
        inter_start = 1 + k + k
        inter_idx = 0
        for i in range(k):
            for j in range(i + 1, k):
                X_model[:, inter_start + inter_idx] = X_data[:, i] * X_data[:, j]
                col_names.append(f"{factors[i]}:{factors[j]}")
                inter_idx += 1

        # Fit OLS
        try:
            coeffs, _, _, _ = np.linalg.lstsq(X_model, y, rcond=None)
        except np.linalg.LinAlgError:
            return {"error": "Singular matrix in RSM fit"}

        y_hat = X_model @ coeffs
        ss_res = np.sum((y - y_hat) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        adj_r2 = 1 - (1 - r2) * (n - 1) / (n - n_terms)

        # Coefficient table
        coeff_dict = {}
        for name, val in zip(col_names, coeffs):
            coeff_dict[name] = round(float(val), 6)

        # Find stationary point (optimum)
        # For quadratic model: ∇y = b + 2B x = 0  =>  x* = -0.5 * B^(-1) * b
        # where b = linear coefficients, B = quadratic coefficient matrix
        b = coeffs[1:1 + k]
        B = np.zeros((k, k))
        for i in range(k):
            B[i, i] = coeffs[quad_start + i]  # quadratic terms
        for i in range(k):
            for j in range(i + 1, k):
                inter_name = f"{factors[i]}:{factors[j]}"
                if inter_name in coeff_dict:
                    B[i, j] = coeff_dict[inter_name]
                    B[j, i] = coeff_dict[inter_name]

        try:
            x_opt = -0.5 * np.linalg.inv(B) @ b
        except np.linalg.LinAlgError:
            x_opt = np.full(k, np.nan)

        # Determine nature from eigenvalues of B
        try:
            eigvals = np.linalg.eigvals(B)
            if np.all(eigvals < 0):
                nature = "maximum"
            elif np.all(eigvals > 0):
                nature = "minimum"
            else:
                nature = "saddle"
        except np.linalg.LinAlgError:
            nature = "unknown"

        # Predicted response at optimum
        X_opt_model = np.ones((1, n_terms))
        X_opt_model[0, 1:1 + k] = x_opt
        for i in range(k):
            X_opt_model[0, quad_start + i] = x_opt[i] ** 2
        inter_idx = 0
        for i in range(k):
            for j in range(i + 1, k):
                X_opt_model[0, inter_start + inter_idx] = x_opt[i] * x_opt[j]
                inter_idx += 1

        predicted_opt = X_opt_model @ coeffs

        return {
            "model_type": "quadratic_rsm",
            "response": response,
            "factors": factors,
            "n": n,
            "n_terms": n_terms,
            "coefficients": coeff_dict,
            "r2": round(float(r2), 4),
            "adj_r2": round(float(adj_r2), 4),
            "rmse": round(float(np.sqrt(ss_res / max(n - n_terms, 1))), 4),
            "optimum": [round(float(x), 4) for x in x_opt],
            "optimum_factors": {f: round(float(x), 4) for f, x in zip(factors, x_opt)},
            "nature": nature,
            "eigenvalues": [round(float(v), 4) for v in np.linalg.eigvals(B)] if k > 0 else [],
            "predicted_optimum": round(float(predicted_opt[0]), 4),
        }

    def generate_rsm_plots(self, fig_dir: str | Path, factors: Optional[List[str]] = None) -> List[str]:
        """Generate RSM contour and surface plots."""
        if not hasattr(self, '_rsm_results') or self._rsm_results is None:
            self._rsm_results = self.fit_rsm(factors)

        if "error" in self._rsm_results:
            return []

        fig_dir = Path(fig_dir)
        fig_dir.mkdir(parents=True, exist_ok=True)
        paths = []

        response = self._rsm_results["response"]
        factors = self._rsm_results["factors"]
        k = len(factors)

        if k == 2:
            # 2D contour plot
            f1, f2 = factors
            X_data = self.df[factors].values

            x1_range = np.linspace(X_data[:, 0].min(), X_data[:, 0].max(), 50)
            x2_range = np.linspace(X_data[:, 1].min(), X_data[:, 1].max(), 50)
            X1, X2 = np.meshgrid(x1_range, x2_range)

            # Build model matrix for grid
            n_terms = self._rsm_results["n_terms"]
            coeffs = np.array([self._rsm_results["coefficients"].get(n, 0) for n in [
                "intercept", f1, f2, f1 + "^2", f2 + "^2", f1 + ":" + f2
            ]])

            # Handle missing interaction term
            if len(coeffs) < 6:
                coeffs = np.pad(coeffs, (0, 6 - len(coeffs)))

            Z = (coeffs[0] + coeffs[1] * X1 + coeffs[2] * X2 +
                 coeffs[3] * X1**2 + coeffs[4] * X2**2 +
                 coeffs[5] * X1 * X2)

            fig, ax = plt.subplots(figsize=(8, 6))
            contour = ax.contourf(X1, X2, Z, levels=20, cmap="RdYlBu_r", alpha=0.8)
            ax.contour(X1, X2, Z, levels=10, colors="black", alpha=0.4, linewidths=0.5)
            plt.colorbar(contour, ax=ax, label=f"Predicted {response}")

            # Plot actual data points
            y_data = self.df[response].values
            scatter = ax.scatter(X_data[:, 0], X_data[:, 1], c=y_data,
                                cmap="RdYlBu_r", s=60, edgecolors="white", linewidths=1)

            # Mark optimum
            opt = self._rsm_results["optimum"]
            ax.plot(opt[0], opt[1], 'r*', ms=20, label=f"Optimum ({opt[0]:.2f}, {opt[1]:.2f})")

            ax.set_xlabel(f1)
            ax.set_ylabel(f2)
            ax.set_title(f"RSM Contour Plot — {response}", fontweight="bold")
            ax.legend()
            ax.grid(alpha=0.3)
            plt.tight_layout()

            path = str(fig_dir / "rsm_contour.png")
            fig.savefig(path, dpi=130, bbox_inches="tight")
            plt.close(fig)
            paths.append(path)

        return paths
