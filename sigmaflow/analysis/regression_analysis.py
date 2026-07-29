"""
sigmaflow/analysis/regression_analysis.py
==========================================
Linear and multiple regression analysis for SigmaFlow v10.

Implements regression using numpy (lstsq) and scipy, providing
results equivalent to statsmodels without requiring that dependency.

Capabilities
------------
- Simple linear regression (1 predictor)
- Multiple linear regression (n predictors)
- Coefficient significance testing (t-tests)
- R², Adjusted R², RMSE, F-statistic
- Automatic selection of response and predictor variables
- Regression coefficient bar chart (PNG)

Output format
-------------
{
    "response":       "defects",
    "predictors":     ["temperature", "pressure"],
    "r2":             0.847,
    "adj_r2":         0.831,
    "rmse":           2.14,
    "f_statistic":    49.3,
    "f_p_value":      0.0001,
    "coefficients":   [{"variable": "temperature", "coeff": 0.31, "p_value": 0.002, ...}],
    "significant_vars": ["temperature", "pressure"],
    "interpretation": "...",
}

Usage
-----
    from sigmaflow.analysis.regression_analysis import RegressionAnalyzer

    ra = RegressionAnalyzer(df, response_col="defects")
    results = ra.run()
    plots   = ra.generate_plots(fig_dir)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

ALPHA = 0.05


class RegressionAnalyzer:
    """
    Run linear / multiple regression on a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
    response_col : str, optional
        Name of the response (Y) variable. Auto-detected if None.
    predictor_cols : list[str], optional
        Names of predictor (X) variables. All numeric non-response
        columns used if None.
    alpha : float
        Significance level for coefficient t-tests.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        response_col: Optional[str] = None,
        predictor_cols: Optional[List[str]] = None,
        alpha: float = ALPHA,
    ) -> None:
        self.df      = df.select_dtypes(include="number").dropna()
        self.alpha   = alpha
        self._response   = response_col
        self._predictors = predictor_cols
        self._results: Dict[str, Any] = {}

    def run(self) -> Dict[str, Any]:
        """
        Run the regression analysis.

        Returns
        -------
        dict  — see module docstring for format.
        """
        response   = self._resolve_response()
        predictors = self._resolve_predictors(response)

        if not response or not predictors:
            return {"error": "Need at least 1 response and 1 predictor variable."}

        logger.info("Regression: response='%s', predictors=%s", response, predictors)

        y = self.df[response].values.astype(float)
        X_raw = self.df[predictors].values.astype(float)

        # Add intercept
        X = np.column_stack([np.ones(len(y)), X_raw])
        n, k = X.shape   # k includes intercept

        # OLS via numpy lstsq
        coeffs, residuals_ss, rank, sv = np.linalg.lstsq(X, y, rcond=None)
        y_hat = X @ coeffs
        resid = y - y_hat

        # Sums of squares
        ss_res = float(np.sum(resid**2))
        ss_tot = float(np.sum((y - y.mean())**2))
        ss_reg = ss_tot - ss_res

        r2      = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        adj_r2  = 1 - (1 - r2) * (n - 1) / max(n - k, 1)
        rmse    = float(np.sqrt(ss_res / max(n - k, 1)))

        # Standard errors and t-statistics for coefficients
        mse     = ss_res / max(n - k, 1)
        try:
            XtX_inv = np.linalg.inv(X.T @ X)
            se      = np.sqrt(np.diag(XtX_inv) * mse)
        except np.linalg.LinAlgError:
            se      = np.full(k, np.nan)

        t_stats = coeffs / np.where(se > 0, se, np.nan)
        p_vals  = [2 * (1 - stats.t.cdf(abs(t), df=n - k)) for t in t_stats]

        # F-statistic
        df_reg = k - 1
        df_res = n - k
        f_stat = (ss_reg / df_reg) / (ss_res / df_res) if df_reg > 0 and df_res > 0 else np.nan
        f_p    = 1 - stats.f.cdf(f_stat, df_reg, df_res) if not np.isnan(f_stat) else np.nan

        # Coefficient table
        coeff_table = []
        names = ["intercept"] + predictors
        for i, (name, c, se_i, t, p) in enumerate(zip(names, coeffs, se, t_stats, p_vals)):
            sig = bool(p < self.alpha) if not np.isnan(p) else False
            coeff_table.append({
                "variable": name,
                "coefficient": round(float(c), 6),
                "std_error":   round(float(se_i), 6) if not np.isnan(se_i) else None,
                "t_statistic": round(float(t), 4)    if not np.isnan(t)    else None,
                "p_value":     round(float(p), 6)    if not np.isnan(p)    else None,
                "significant": sig,
            })

        sig_vars = [c["variable"] for c in coeff_table if c["significant"] and c["variable"] != "intercept"]

        # Calculate VIF
        vif_results = self._calculate_vif(X_raw, predictors)

        # Calculate diagnostics
        diagnostics = self._calculate_diagnostics(X_raw, y, y_hat, resid, predictors)

        # Interpretation
        interp = self._build_interpretation(
            response, predictors, sig_vars, r2, adj_r2, f_stat, f_p,
        )

        self._results = {
            "response":        response,
            "predictors":      predictors,
            "n":               n,
            "r2":              round(r2, 4),
            "adj_r2":          round(adj_r2, 4),
            "rmse":            round(rmse, 4),
            "f_statistic":     round(float(f_stat), 4) if not np.isnan(f_stat) else None,
            "f_p_value":       round(float(f_p), 6)    if not np.isnan(f_p)    else None,
            "coefficients":    coeff_table,
            "significant_vars": sig_vars,
            "vif":             vif_results,
            "diagnostics":     diagnostics,
            "y_hat":           y_hat.tolist(),
            "residuals":       resid.tolist(),
            "interpretation":  interp,
        }
        return self._results

    def generate_plots(self, fig_dir: str | Path) -> List[str]:
        """
        Generate regression plots and save them.

        Returns
        -------
        list[str]  Paths to saved PNG files.
        """
        if not self._results:
            self.run()
        if "error" in self._results:
            return []

        fig_dir = Path(fig_dir)
        fig_dir.mkdir(parents=True, exist_ok=True)
        paths   = []

        paths.append(self._plot_coefficients(fig_dir))
        paths.append(self._plot_actual_vs_predicted(fig_dir))
        paths.append(self._plot_residuals(fig_dir))

        return [p for p in paths if p]

    # ── Private: plots ────────────────────────────────────────────────────────

    def _plot_coefficients(self, fig_dir: Path) -> str:
        """Horizontal bar chart of regression coefficients (excl. intercept)."""
        coeffs = [c for c in self._results["coefficients"] if c["variable"] != "intercept"]
        if not coeffs:
            return ""

        labels = [c["variable"] for c in coeffs]
        values = [c["coefficient"] for c in coeffs]
        colors = ["#C62828" if v < 0 else "#1565C0" for v in values]
        sig    = [c["significant"] for c in coeffs]

        fig, ax = plt.subplots(figsize=(9, max(3, len(labels) * 0.5 + 1.5)))
        bars = ax.barh(labels[::-1], values[::-1], color=colors[::-1],
                       edgecolor="white", height=0.6)

        # Hatch non-significant bars
        for bar, s in zip(bars, sig[::-1]):
            if not s:
                bar.set_hatch("//")
                bar.set_alpha(0.5)

        for bar, val in zip(bars, values[::-1]):
            x_pos = bar.get_width() + (0.001 if val >= 0 else -0.001)
            ha    = "left" if val >= 0 else "right"
            ax.text(x_pos, bar.get_y() + bar.get_height() / 2,
                    f"{val:+.4f}", va="center", ha=ha, fontsize=8)

        ax.axvline(0, color="black", lw=1.0)
        ax.set_title(
            f"Regression Coefficients — Response: '{self._results['response']}'\n"
            f"R²={self._results['r2']:.3f}  Adj.R²={self._results['adj_r2']:.3f}",
            fontsize=11, fontweight="bold",
        )
        ax.set_xlabel("Coefficient value")
        ax.text(0.97, 0.02, "Hatched = not significant (α=0.05)",
                transform=ax.transAxes, fontsize=8, ha="right", color="#757575")
        ax.grid(axis="x", alpha=0.3)
        plt.tight_layout()
        path = str(fig_dir / "regression_coefficients.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        logger.debug("Saved: %s", path)
        return path

    def _plot_actual_vs_predicted(self, fig_dir: Path) -> str:
        """Scatter plot of actual vs predicted values."""
        y_hat = np.array(self._results["y_hat"])
        y_act = y_hat + np.array(self._results["residuals"])
        r2    = self._results["r2"]

        fig, ax = plt.subplots(figsize=(7, 6))
        ax.scatter(y_hat, y_act, alpha=0.6, color="#1565C0", s=25, edgecolors="white", lw=0.5)
        mn, mx = min(y_hat.min(), y_act.min()), max(y_hat.max(), y_act.max())
        ax.plot([mn, mx], [mn, mx], "r--", lw=1.5, label="Perfect fit")
        ax.set_xlabel("Predicted values (Ŷ)")
        ax.set_ylabel("Actual values (Y)")
        ax.set_title(f"Actual vs. Predicted  (R²={r2:.3f})", fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3)
        plt.tight_layout()
        path = str(fig_dir / "regression_actual_vs_predicted.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    def _plot_residuals(self, fig_dir: Path) -> str:
        """Residuals vs. fitted values diagnostic plot."""
        y_hat = np.array(self._results["y_hat"])
        resid = np.array(self._results["residuals"])

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # Residuals vs. Fitted
        axes[0].scatter(y_hat, resid, alpha=0.6, color="#1565C0", s=25)
        axes[0].axhline(0, color="red", lw=1.5, ls="--")
        axes[0].set_xlabel("Fitted values")
        axes[0].set_ylabel("Residuals")
        axes[0].set_title("Residuals vs. Fitted")
        axes[0].grid(alpha=0.3)

        # QQ plot of residuals
        stats.probplot(resid, dist="norm", plot=axes[1])
        axes[1].set_title("Normal Q-Q Plot of Residuals")
        axes[1].grid(alpha=0.3)

        plt.suptitle("Regression Diagnostics", fontweight="bold", fontsize=12)
        plt.tight_layout()
        path = str(fig_dir / "regression_diagnostics.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    # ── Private: helpers ──────────────────────────────────────────────────────

    def _resolve_response(self) -> Optional[str]:
        if self._response and self._response in self.df.columns:
            return self._response
        quality_kws = ("defect", "yield", "quality", "error", "count", "output", "response")
        for col in self.df.columns:
            if any(kw in col.lower() for kw in quality_kws):
                return col
        # Fallback: highest-variance column
        if len(self.df.columns) > 0:
            return str(self.df.var().idxmax())
        return None

    def _resolve_predictors(self, response: Optional[str]) -> List[str]:
        if self._predictors:
            return [c for c in self._predictors if c in self.df.columns and c != response]
        return [c for c in self.df.columns if c != response]

    def _build_interpretation(
        self,
        response: str,
        predictors: List[str],
        sig_vars: List[str],
        r2: float,
        adj_r2: float,
        f_stat: float,
        f_p: float,
    ) -> str:
        parts = [
            f"Multiple regression analysis of '{response}' against "
            f"{len(predictors)} predictor(s): {', '.join(predictors)}. "
        ]
        if r2 >= 0.80:
            parts.append(f"The model explains a HIGH proportion of variance (R²={r2:.3f}). ")
        elif r2 >= 0.50:
            parts.append(f"The model explains a MODERATE proportion of variance (R²={r2:.3f}). ")
        else:
            parts.append(f"The model explains a LOW proportion of variance (R²={r2:.3f}). ")

        if not np.isnan(f_p):
            if f_p < 0.05:
                parts.append(f"The overall regression model is statistically significant (F={f_stat:.2f}, p={f_p:.4f}). ")
            else:
                parts.append(f"The overall regression model is NOT statistically significant (F={f_stat:.2f}, p={f_p:.4f}). ")

        if sig_vars:
            parts.append(
                f"Statistically significant predictors (α=0.05): {', '.join(sig_vars)}. "
                "These variables should be prioritized in process control efforts."
            )
        else:
            parts.append(
                "No individual predictor showed statistical significance at α=0.05. "
                "Consider collecting more data or investigating interactions."
            )
        return "".join(parts)

    # ─── Sprint 3: VIF, Stepwise Selection, Enhanced Diagnostics ────────────────

    def _calculate_vif(self, X: np.ndarray, predictors: List[str]) -> List[Dict[str, Any]]:
        """Calculate Variance Inflation Factor for each predictor.
        
        VIF = 1 / (1 - R²_j) where R²_j is from regressing predictor j on all others.
        VIF > 5 indicates moderate multicollinearity, VIF > 10 indicates severe multicollinearity.
        """
        n, k = X.shape
        vif_results = []
        
        for j in range(k):
            # Regress predictor j on all other predictors
            X_j = X[:, j]
            X_others = np.delete(X, j, axis=1)
            
            if X_others.shape[1] == 0:
                vif = 1.0
            else:
                try:
                    # Add intercept for the auxiliary regression
                    X_aux = np.column_stack([np.ones(n), X_others])
                    coeffs_aux, _, _, _ = np.linalg.lstsq(X_aux, X_j, rcond=None)
                    y_hat_aux = X_aux @ coeffs_aux
                    ss_res_aux = np.sum((X_j - y_hat_aux) ** 2)
                    ss_tot_aux = np.sum((X_j - X_j.mean()) ** 2)
                    r2_aux = 1 - ss_res_aux / ss_tot_aux if ss_tot_aux > 0 else 0
                    vif = 1 / (1 - r2_aux) if r2_aux < 1 else np.inf
                except np.linalg.LinAlgError:
                    vif = np.inf
            
            vif_results.append({
                "variable": predictors[j],
                "vif": round(float(vif), 2) if np.isfinite(vif) else None,
                "multicollinearity": "High" if vif > 10 else ("Moderate" if vif > 5 else "Low")
            })
        
        return vif_results

    def _stepwise_selection(
        self,
        X: np.ndarray,
        y: np.ndarray,
        predictors: List[str],
        method: Literal["forward", "backward", "both"] = "both",
        criterion: Literal["aic", "bic"] = "aic",
    ) -> Dict[str, Any]:
        """Perform stepwise variable selection.
        
        Parameters
        ----------
        method : "forward" | "backward" | "both"
            Selection direction.
        criterion : "aic" | "bic"
            Information criterion to optimize.
        """
        n = len(y)
        k_full = X.shape[1]
        
        def fit_model(X_subset, pred_names):
            """Fit OLS and return AIC/BIC."""
            if X_subset.shape[1] == 0:
                return {"aic": np.inf, "bic": np.inf, "coeffs": [], "preds": []}
            
            X_with_int = np.column_stack([np.ones(n), X_subset])
            try:
                coeffs, _, _, _ = np.linalg.lstsq(X_with_int, y, rcond=None)
                y_hat = X_with_int @ coeffs
                rss = np.sum((y - y_hat) ** 2)
                k = len(coeffs)
                
                # AIC = n * ln(RSS/n) + 2k
                aic = n * np.log(rss / n) + 2 * k
                # BIC = n * ln(RSS/n) + k * ln(n)
                bic = n * np.log(rss / n) + k * np.log(n)
                
                return {"aic": aic, "bic": bic, "coeffs": coeffs, "preds": pred_names}
            except np.linalg.LinAlgError:
                return {"aic": np.inf, "bic": np.inf, "coeffs": [], "preds": []}
        
        current_preds = list(predictors)
        current_X = X.copy()
        
        if method == "backward":
            current_X = X
            current_preds = list(predictors)
        elif method == "forward":
            current_X = np.empty((n, 0))
            current_preds = []
        
        def get_best_next_step(X_current, preds_current, remaining_preds, direction):
            """Evaluate adding/removing each variable."""
            best_criterion = np.inf
            best_idx = -1
            best_result = None
            
            for idx, pred in enumerate(remaining_preds):
                if direction == "add":
                    X_new = np.column_stack([X_current, X[:, preds_current.index(pred)]]) if X_current.size else X[:, [preds_current.index(pred)]]
                    new_preds = preds_current + [pred]
                elif direction == "remove":
                    keep_idx = [i for i, p in enumerate(preds_current) if p != pred]
                    X_new = X_current[:, keep_idx]
                    new_preds = [p for p in preds_current if p != pred]
                else:
                    continue
                
                result = fit_model(X_new, new_preds)
                crit = result["aic"] if criterion == "aic" else result["bic"]
                
                if crit < best_criterion:
                    best_criterion = crit
                    best_idx = idx
                    best_result = result
            
            return best_idx, best_result
        
        if method == "forward" or method == "both":
            # Start with no predictors or intercept only
            remaining = [p for p in predictors if p not in current_preds]
            
            while remaining:
                best_idx, best_result = get_best_next_step(
                    current_X, current_preds, remaining, "add"
                )
                
                current_result = fit_model(current_X, current_preds)
                current_crit = current_result["aic"] if criterion == "aic" else current_result["bic"]
                
                if best_result and best_result[criterion] < current_crit:
                    pred_to_add = remaining[best_idx]
                    current_preds.append(pred_to_add)
                    remaining.remove(pred_to_add)
                    current_X = X[:, [predictors.index(p) for p in current_preds]]
                else:
                    break
        
        if method == "backward" or method == "both":
            # Start with all predictors
            current_X = X
            current_preds = list(predictors)
            removed_any = True
            
            while removed_any and len(current_preds) > 1:
                removed_any = False
                remaining = list(current_preds)
                
                best_idx, best_result = get_best_next_step(
                    current_X, current_preds, remaining, "remove"
                )
                
                current_result = fit_model(current_X, current_preds)
                current_crit = current_result["aic"] if criterion == "aic" else current_result["bic"]
                
                if best_result and best_result[criterion] < current_crit:
                    pred_to_remove = remaining[best_idx]
                    current_preds.remove(pred_to_remove)
                    current_X = X[:, [predictors.index(p) for p in current_preds]]
                    removed_any = True
                else:
                    break
        
        # Final model
        final_result = fit_model(current_X, current_preds)
        
        return {
            "selected_variables": current_preds,
            "final_aic": round(final_result["aic"], 2) if np.isfinite(final_result["aic"]) else None,
            "final_bic": round(final_result["bic"], 2) if np.isfinite(final_result["bic"]) else None,
            "criterion_used": criterion,
            "method_used": method,
        }

    def _calculate_diagnostics(
        self,
        X: np.ndarray,
        y: np.ndarray,
        y_hat: np.ndarray,
        residuals: np.ndarray,
        predictors: List[str],
    ) -> Dict[str, Any]:
        """Calculate regression diagnostics: Cook's distance, leverage, outliers."""
        n, k = X.shape
        X_with_int = np.column_stack([np.ones(n), X])
        
        # Hat matrix H = X(X'X)^{-1}X'
        try:
            XtX_inv = np.linalg.inv(X_with_int.T @ X_with_int)
            H = X_with_int @ XtX_inv @ X_with_int.T
            leverage = np.diag(H)
        except np.linalg.LinAlgError:
            leverage = np.full(n, np.nan)
        
        # Standardized residuals
        mse = np.sum(residuals**2) / max(n - k - 1, 1)
        try:
            std_residuals = residuals / np.sqrt(mse * (1 - leverage))
        except (ValueError, ZeroDivisionError):
            std_residuals = np.full(n, np.nan)
        
        # Cook's distance
        try:
            cooks_d = np.zeros(n)
            for i in range(n):
                if leverage[i] < 1:
                    cooks_d[i] = (std_residuals[i]**2 / (k + 1)) * (leverage[i] / (1 - leverage[i]))
        except (ValueError, ZeroDivisionError):
            cooks_d = np.full(n, np.nan)
        
        # Outliers: standardized residual > 3 or < -3
        outlier_mask = np.abs(std_residuals) > 3
        
        # High leverage: leverage > 2*(k+1)/n or > 3*(k+1)/n
        leverage_threshold = 2 * (k + 1) / n
        high_leverage_mask = leverage > leverage_threshold
        
        # Influential points: Cook's D > 4/n
        influential_mask = cooks_d > (4 / n)
        
        return {
            "cooks_distance_max": round(float(np.nanmax(cooks_d)), 4),
            "cooks_distance_mean": round(float(np.nanmean(cooks_d)), 4),
            "high_leverage_count": int(np.sum(high_leverage_mask)),
            "high_leverage_threshold": round(float(leverage_threshold), 4),
            "outlier_count": int(np.sum(outlier_mask)),
            "influential_count": int(np.sum(influential_mask)),
            "leverage_values": [round(float(l), 4) for l in leverage],
            "cooks_distance_values": [round(float(c), 4) for c in cooks_d],
            "standardized_residuals": [round(float(r), 4) for r in std_residuals],
        }

    def stepwise_selection(
        self,
        method: Literal["forward", "backward", "both"] = "both",
        criterion: Literal["aic", "bic"] = "aic",
    ) -> Dict[str, Any]:
        """Public method for stepwise selection."""
        if not self._results:
            self.run()
        
        if "error" in self._results:
            return {"error": self._results["error"]}
        
        response = self._results["response"]
        predictors = self._results["predictors"]
        
        y = self.df[response].values.astype(float)
        X = self.df[predictors].values.astype(float)
        
        return self._stepwise_selection(X, y, predictors, method, criterion)
