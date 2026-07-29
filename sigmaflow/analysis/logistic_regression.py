"""
sigmaflow/analysis/logistic_regression.py
==========================================
Logistic Regression Analysis for SigmaFlow.

Implements:
- Binary Logistic Regression (logit link)
- Ordinal Logistic Regression (proportional odds model)
- Model evaluation: AUC, accuracy, confusion matrix, classification report

Based on maximum likelihood estimation using scipy.optimize.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Literal

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from scipy.special import expit, logsumexp
from sklearn.metrics import (
    roc_auc_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
    roc_curve,
    precision_recall_curve,
)

logger = logging.getLogger(__name__)

ALPHA = 0.05


# ─── Binary Logistic Regression ────────────────────────────────────────────────


class BinaryLogisticRegression:
    """
    Binary Logistic Regression via Maximum Likelihood Estimation.

    Model: logit(p) = ln(p/(1-p)) = X @ beta
    p = 1 / (1 + exp(-X @ beta))  = expit(X @ beta)

    Estimation: MLE via scipy.optimize.minimize (BFGS/L-BFGS-B)
    Standard errors: sqrt(diag(inv(Hessian)))
    """

    def __init__(
        self,
        df: pd.DataFrame,
        response_col: str,
        predictor_cols: Optional[List[str]] = None,
        alpha: float = ALPHA,
        add_intercept: bool = True,
    ) -> None:
        # Filter numeric columns and drop NA
        self.df = df.select_dtypes(include="number").dropna()
        self.response_col = response_col
        self.predictor_cols = predictor_cols
        self.alpha = alpha
        self.add_intercept = add_intercept

        self._results: Dict[str, Any] = {}

    def _prepare_data(self) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Prepare X and y matrices."""
        if self.response_col not in self.df.columns:
            raise ValueError(f"Response column '{self.response_col}' not found")

        y = self.df[self.response_col].values
        # Ensure binary 0/1
        unique_vals = np.unique(y)
        if not set(unique_vals).issubset({0, 1}):
            # Try to map to 0/1
            mapping = {unique_vals[0]: 0, unique_vals[1]: 1} if len(unique_vals) == 2 else None
            if mapping:
                y = np.array([mapping[v] for v in y])
            else:
                raise ValueError(f"Response must be binary (0/1), got values: {unique_vals}")

        if self.predictor_cols:
            predictors = [c for c in self.predictor_cols if c in self.df.columns]
        else:
            predictors = [c for c in self.df.select_dtypes(include="number").columns if c != self.response_col]

        if not predictors:
            raise ValueError("No predictor columns available")

        X = self.df[predictors].values.astype(float)
        return X, y, predictors

    def _add_intercept(self, X: np.ndarray) -> np.ndarray:
        """Add intercept column to X."""
        return np.column_stack([np.ones(len(X)), X])

    def _log_likelihood(self, beta: np.ndarray, X: np.ndarray, y: np.ndarray) -> float:
        """Negative log-likelihood for logistic regression."""
        eta = X @ beta
        p = expit(eta)  # 1 / (1 + exp(-eta))
        # Clip for numerical stability
        p = np.clip(p, 1e-15, 1 - 1e-15)
        ll = np.sum(y * np.log(p) + (1 - y) * np.log(1 - p))
        return -ll  # Negative log-likelihood for minimization

    def _gradient(self, beta: np.ndarray, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Gradient of negative log-likelihood."""
        eta = X @ beta
        p = expit(eta)
        grad = X.T @ (p - y)
        return grad

    def _hessian(self, beta: np.ndarray, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Hessian matrix for logistic regression."""
        eta = X @ beta
        p = expit(eta)
        w = p * (1 - p)
        # X.T @ diag(w) @ X
        return X.T @ (w[:, np.newaxis] * X)

    def fit(self) -> Dict[str, Any]:
        """Fit the logistic regression model."""
        X_raw, y, predictors = self._prepare_data()
        X = self._add_intercept(X_raw) if self.add_intercept else X_raw
        n, k = X.shape

        # Initial coefficients (zeros)
        beta0 = np.zeros(k)

        # Fit using BFGS (faster for logistic regression)
        result = minimize(
            fun=self._log_likelihood,
            x0=beta0,
            args=(X, y),
            method="BFGS",
            jac=self._gradient,
            options={"gtol": 1e-6, "maxiter": 1000, "disp": False},
        )

        if not result.success:
            logger.warning(f"Optimization may not have converged: {result.message}")

        beta = result.x
        nll = result.fun

        # Hessian for standard errors
        try:
            hess = self._hessian(beta, X, y)
            cov = np.linalg.inv(hess)
            se = np.sqrt(np.diag(cov))
        except np.linalg.LinAlgError:
            se = np.full(k, np.nan)

        # Wald tests
        z_stats = beta / np.where(se > 0, se, np.nan)
        p_vals = 2 * (1 - stats.norm.cdf(np.abs(z_stats)))

        # Predicted probabilities
        eta = X @ beta
        probs = expit(eta)
        y_pred = (probs >= 0.5).astype(int)

        # Model metrics
        accuracy = accuracy_score(y, y_pred)
        precision = precision_score(y, y_pred, zero_division=0)
        recall = recall_score(y, y_pred, zero_division=0)
        f1 = f1_score(y, y_pred, zero_division=0)
        auc = roc_auc_score(y, probs)

        # Log-likelihood of null model (intercept only)
        p_null = np.mean(y)
        ll_null = np.sum(y * np.log(p_null) + (1 - y) * np.log(1 - p_null))
        ll_model = -nll

        # Pseudo R² (McFadden)
        mcfadden_r2 = 1 - (ll_model / ll_null) if ll_null != 0 else 0

        # Likelihood ratio test
        lr_stat = -2 * (ll_null - ll_model)
        lr_p = 1 - stats.chi2.cdf(lr_stat, df=k - 1) if k > 1 else np.nan

        # Coefficient table
        coeff_table = []
        names = ["intercept"] + list(self.predictor_cols) if self.add_intercept else list(self.predictor_cols)
        if self.add_intercept:
            names = ["intercept"] + list(self.predictor_cols)
        else:
            names = list(self.predictor_cols)

        for i, (name, c, se_i, z, p) in enumerate(zip(names, beta, se, z_stats, p_vals)):
            sig = bool(p < ALPHA) if not np.isnan(p) else False
            coeff_table.append({
                "variable": name,
                "coefficient": round(float(c), 6),
                "std_error": round(float(se_i), 6) if not np.isnan(se_i) else None,
                "z_statistic": round(float(z), 4) if not np.isnan(z) else None,
                "p_value": round(float(p), 6) if not np.isnan(p) else None,
                "significant": sig,
                "odds_ratio": round(float(np.exp(c)), 4),
                "odds_ratio_ci_lower": round(float(np.exp(c - 1.96 * se_i)), 4) if not np.isnan(se_i) else None,
                "odds_ratio_ci_upper": round(float(np.exp(c + 1.96 * se_i)), 4) if not np.isnan(se_i) else None,
            })

        sig_vars = [c["variable"] for c in coeff_table if c["significant"] and c["variable"] != "intercept"]

        # Confusion matrix
        cm = confusion_matrix(y, y_pred)

        self._results = {
            "model_type": "binary_logistic",
            "response": self.response_col,
            "predictors": predictors,
            "n": len(y),
            "coefficients": coeff_table,
            "significant_vars": sig_vars,
            "n_iterations": result.nit if hasattr(result, "nit") else None,
            "converged": result.success,
            "log_likelihood": round(float(ll_model), 4),
            "null_log_likelihood": round(float(ll_null), 4),
            "mcfadden_r2": round(float(mcfadden_r2), 4),
            "lr_statistic": round(float(lr_stat), 4),
            "lr_p_value": round(float(lr_p), 6) if not np.isnan(lr_p) else None,
            "accuracy": round(float(accuracy), 4),
            "precision": round(float(precision), 4),
            "recall": round(float(recall), 4),
            "f1": round(float(f1), 4),
            "auc": round(float(auc), 4),
            "confusion_matrix": cm.tolist(),
            "predicted_probs": probs.tolist(),
            "y_pred": y_pred.tolist(),
            "y_true": y.tolist(),
        }
        return self._results

    def generate_plots(self, fig_dir: str | Path) -> List[str]:
        """Generate diagnostic plots."""
        if not self._results:
            self.fit()

        fig_dir = Path(fig_dir)
        fig_dir.mkdir(parents=True, exist_ok=True)
        paths = []

        # 1. ROC Curve
        y_true = np.array(self._results["y_true"])
        y_prob = np.array(self._results["predicted_probs"])
        fpr, tpr, _ = roc_curve(y_true, y_prob)
        auc = self._results["auc"]

        fig, ax = plt.subplots(figsize=(7, 6))
        ax.plot(fpr, tpr, color="#1565C0", lw=2, label=f"ROC Curve (AUC = {auc:.3f})")
        ax.plot([0, 1], [0, 1], "k--", lw=1, label="Random")
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
        ax.set_title("ROC Curve — Binary Logistic Regression")
        ax.legend(loc="lower right")
        ax.grid(alpha=0.3)
        plt.tight_layout()
        path = str(fig_dir / "logistic_roc_curve.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        paths.append(path)

        # 2. Precision-Recall Curve
        precision, recall, _ = precision_recall_curve(self._results["y_true"], self._results["predicted_probs"])
        fig, ax = plt.subplots(figsize=(7, 6))
        ax.plot(recall, precision, color="#C62828", lw=2)
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_title("Precision-Recall Curve")
        ax.grid(alpha=0.3)
        plt.tight_layout()
        path = str(fig_dir / "logistic_pr_curve.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        paths.append(path)

        # 3. Coefficient plot
        coeffs = [c for c in self._results["coefficients"] if c["variable"] != "intercept"]
        if coeffs:
            labels = [c["variable"] for c in coeffs]
            values = [c["coefficient"] for c in coeffs]
            colors = ["#C62828" if v < 0 else "#1565C0" for v in values]
            sig = [c["significant"] for c in coeffs]

            fig, ax = plt.subplots(figsize=(9, max(3, len(labels) * 0.5 + 1.5)))
            bars = ax.barh(labels[::-1], values[::-1], color=colors[::-1], edgecolor="white", height=0.6)
            for bar, s in zip(bars, sig[::-1]):
                if not s:
                    bar.set_hatch("//")
                    bar.set_alpha(0.5)
            for bar, val in zip(bars, values[::-1]):
                x_pos = bar.get_width() + (0.001 if val >= 0 else -0.001)
                ha = "left" if val >= 0 else "right"
                ax.text(x_pos, bar.get_y() + bar.get_height() / 2, f"{val:+.4f}",
                        va="center", ha=ha, fontsize=8)
            ax.axvline(0, color="black", lw=1.0)
            ax.set_xlabel("Log-odds coefficient (β)")
            ax.set_title("Logistic Regression Coefficients (excl. intercept)")
            ax.text(0.97, 0.02, "Hatched = not significant (α=0.05)",
                    transform=ax.transAxes, fontsize=8, ha="right", color="#757575")
            ax.grid(axis="x", alpha=0.3)
            plt.tight_layout()
            path = str(fig_dir / "logistic_coefficients.png")
            fig.savefig(path, dpi=130, bbox_inches="tight")
            plt.close(fig)
            paths.append(path)

        return paths


# ─── Ordinal Logistic Regression (Proportional Odds Model) ─────────────────────


class OrdinalLogisticRegression:
    """
    Ordinal Logistic Regression (Proportional Odds Model).

    Model: logit(P(Y <= j)) = α_j - X @ β   for j = 1, ..., J-1
    where J = number of ordered categories.

    This is the proportional odds model (McCullagh, 1980).
    """

    def __init__(
        self,
        df: pd.DataFrame,
        response_col: str,
        predictor_cols: Optional[List[str]] = None,
        alpha: float = ALPHA,
    ) -> None:
        self.df = df.select_dtypes(include="number").dropna()
        self.response_col = response_col
        self.predictor_cols = predictor_cols
        self.alpha = alpha
        self._results: Dict[str, Any] = {}

    def _prepare_data(self) -> Tuple[np.ndarray, np.ndarray, List[str], np.ndarray]:
        if self.response_col not in self.df.columns:
            raise ValueError(f"Response column '{self.response_col}' not found")

        y = self.df[self.response_col].values
        unique_y = np.unique(y)
        self.classes_ = np.sort(unique_y)
        self.n_classes_ = len(self.classes_)

        if self.n_classes_ < 3:
            raise ValueError("Ordinal logistic requires at least 3 ordered categories")

        # Encode y as 0, 1, 2, ..., J-1
        y_encoded = np.searchsorted(self.classes_, y)

        if self.predictor_cols:
            predictors = [c for c in self.predictor_cols if c in self.df.columns]
        else:
            predictors = [c for c in self.df.select_dtypes(include="number").columns if c != self.response_col]

        if not predictors:
            raise ValueError("No predictor columns available")

        X = self.df[predictors].values.astype(float)
        return X, y_encoded, predictors, self.classes_

    def _log_likelihood(self, params: np.ndarray, X: np.ndarray, y: np.ndarray, n_classes: int) -> float:
        """Negative log-likelihood for ordinal logistic (proportional odds)."""
        k = X.shape[1]
        # First k params are beta, next (n_classes - 1) are intercepts (thresholds)
        beta = params[:k]
        thresholds = params[k:]
        n = len(y)

        eta = X @ beta
        ll = 0.0

        for i in range(n):
            yi = y[i]
            eta_i = eta[i]

            # P(Y <= j) = expit(threshold_j - eta)
            # For category j: P(Y = j) = P(Y <= j) - P(Y <= j-1)
            probs = []
            prev = 0.0
            for j in range(n_classes - 1):
                prob = expit(thresholds[j] - eta[i])
                probs.append(prob - prev)
                prev = prob
            probs.append(1 - prev)

            probs = np.clip(probs, 1e-15, 1 - 1e-15)
            ll += np.log(probs[yi])

        return -ll

    def _gradient(self, params: np.ndarray, X: np.ndarray, y: np.ndarray, n_classes: int) -> np.ndarray:
            """Analytical gradient for ordinal logistic regression (proportional odds model).

            Returns gradient of NEGATIVE log-likelihood (for minimization).
            """
            k = X.shape[1]
            beta = params[:k]
            thresholds = params[k:]
            n = len(y)

            eta = X @ beta
            grad = np.zeros(k + n_classes - 1)

            # Gradient of POSITIVE log-likelihood
            grad_beta_pos = np.zeros(k)
            grad_thresholds_pos = np.zeros(n_classes - 1)

            for i in range(n):
                yi = y[i]
                eta_i = eta[i]

                # Compute cumulative probabilities and their derivatives
                cum_probs = np.array([expit(thresholds[j] - eta_i) for j in range(n_classes - 1)])
                f_vals = cum_probs * (1 - cum_probs)  # derivatives of expit

                # Compute probabilities P(Y = j)
                probs = np.zeros(n_classes)
                probs[0] = cum_probs[0]
                for j in range(1, n_classes - 1):
                    probs[j] = cum_probs[j] - cum_probs[j - 1]
                probs[-1] = 1 - cum_probs[-1]

                # Clip
                probs = np.clip(probs, 1e-15, 1 - 1e-15)

                # Gradient for beta (positive log-likelihood)
                # d log P(Y=j) / d beta = -X_i * [f(theta_j - eta_i) - f(theta_{j-1} - eta_i)] / P(Y=j)
                for j in range(n_classes):
                    if yi == j:
                        f_j = f_vals[j] if j < n_classes - 1 else 0
                        f_jm1 = f_vals[j - 1] if j > 0 else 0
                        grad_beta_pos -= X[i] * (f_j - f_jm1) / probs[j]

                # Gradient for thresholds (positive log-likelihood)
                # d LL / d theta_k = I(y=k) * f_k / P(Y=k) - I(y=k+1) * f_k / P(Y=k+1)
                for k_idx in range(n_classes - 1):
                    if yi == k_idx:
                        grad_thresholds_pos[k_idx] += f_vals[k_idx] / probs[k_idx]
                    if yi == k_idx + 1:
                        grad_thresholds_pos[k_idx] -= f_vals[k_idx] / probs[k_idx + 1]

            # Return gradient of NEGATIVE log-likelihood
            grad[:k] = -grad_beta_pos
            grad[k:] = -grad_thresholds_pos
            return grad

    def fit(self) -> Dict[str, Any]:
        X, y, predictors, classes = self._prepare_data()
        n, k = X.shape
        n_classes = len(classes)

        # Add intercept to X
        X_with_intercept = np.column_stack([np.ones(n), X])
        k_full = X_with_intercept.shape[1]

        # Initial params: beta (k_full) + thresholds (n_classes - 1)
        # Thresholds should be ordered: theta_1 < theta_2 < ... < theta_{J-1}
        init_beta = np.zeros(k_full)
        init_thresholds = np.linspace(-2, 2, n_classes - 1)
        init_params = np.concatenate([init_beta, init_thresholds])

        result = minimize(
            fun=self._log_likelihood,
            x0=init_params,
            args=(X_with_intercept, y, n_classes),
            method="L-BFGS-B",
            jac=self._gradient,
            options={"maxiter": 2000, "ftol": 1e-8},
        )

        if not result.success:
            logger.warning(f"Ordinal logistic may not have converged: {result.message}")

        params = result.x
        beta = params[:k_full]
        thresholds = params[k_full:]

        # Hessian for standard errors (numerical, using the NEGATIVE log-likelihood function)
        try:
            hess = np.zeros((len(params), len(params)))
            eps = 1e-5
            for i in range(len(params)):
                for j in range(len(params)):
                    # Central difference of negative log-likelihood
                    params_pp = params.copy()
                    params_pp[i] += eps
                    params_pp[j] += eps
                    params_pm = params.copy()
                    params_pm[i] += eps
                    params_pm[j] -= eps
                    params_mp = params.copy()
                    params_mp[i] -= eps
                    params_mp[j] += eps
                    params_mm = params.copy()
                    params_mm[i] -= eps
                    params_mm[j] -= eps
                    
                    f_pp = self._log_likelihood(params_pp, X_with_intercept, y, n_classes)
                    f_pm = self._log_likelihood(params_pm, X_with_intercept, y, n_classes)
                    f_mp = self._log_likelihood(params_mp, X_with_intercept, y, n_classes)
                    f_mm = self._log_likelihood(params_mm, X_with_intercept, y, n_classes)
                    
                    hess[i, j] = (f_pp - f_pm - f_mp + f_mm) / (4 * eps * eps)
            
            # Regularize to ensure positive definiteness
            hess = (hess + hess.T) / 2  # symmetrize
            min_eig = np.min(np.linalg.eigvalsh(hess))
            if min_eig < 1e-8:
                hess += np.eye(len(params)) * (1e-8 - min_eig + 1e-10)
            
            cov = np.linalg.inv(hess)
            se = np.sqrt(np.diag(cov))
        except Exception:
            se = np.full(len(params), np.nan)

        # Coefficients (excluding intercept)
        beta_coeffs = beta[1:]  # exclude first intercept
        beta_se = se[1:] if len(se) > 1 else np.array([])

        # Predictions
        probs = self._predict_proba(X_with_intercept, beta, thresholds)
        y_pred = np.argmax(probs, axis=1)

        # Metrics
        accuracy = accuracy_score(y, y_pred)
        precision = precision_score(y, y_pred, average="weighted", zero_division=0)
        recall = recall_score(y, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y, y_pred, average="weighted", zero_division=0)

        # Coefficient table
        coeff_table = []
        pred_names = ["intercept"] + [c for c in self.predictor_cols if c != self.response_col]
        for i, (name, c) in enumerate(zip(pred_names, beta)):
            se_i = se[i] if i < len(se) else np.nan
            z = c / se_i if se_i > 0 else np.nan
            p = 2 * (1 - stats.norm.cdf(abs(z))) if not np.isnan(z) else np.nan
            sig = bool(p < ALPHA) if not np.isnan(p) else False
            coeff_table.append({
                "variable": name,
                "coefficient": round(float(c), 6),
                "std_error": round(float(se_i), 6) if not np.isnan(se_i) else None,
                "z_statistic": round(float(z), 4) if not np.isnan(z) else None,
                "p_value": round(float(p), 6) if not np.isnan(p) else None,
                "significant": sig,
            })

        sig_vars = [c["variable"] for c in coeff_table if c["significant"] and c["variable"] != "intercept"]

        # Confusion matrix
        cm = confusion_matrix(y, y_pred)

        self._results = {
            "model_type": "ordinal_logistic",
            "response": self.response_col,
            "predictors": list(self.predictor_cols) if self.predictor_cols else [],
            "classes": classes.tolist(),
            "n": len(y),
            "coefficients": coeff_table,
            "thresholds": [round(float(t), 4) for t in thresholds],
            "significant_vars": sig_vars,
            "converged": result.success,
            "n_iterations": result.nit if hasattr(result, "nit") else None,
            "accuracy": round(float(accuracy), 4),
            "precision": round(float(precision), 4),
            "recall": round(float(recall), 4),
            "f1": round(float(f1), 4),
            "confusion_matrix": cm.tolist(),
            "log_likelihood": round(float(-result.fun), 4),
        }
        return self._results

    def _predict_proba(self, X: np.ndarray, beta: np.ndarray, thresholds: np.ndarray) -> np.ndarray:
        """Predict class probabilities."""
        n = X.shape[0]
        n_classes = len(thresholds) + 1
        eta = X @ beta
        probs = np.zeros((n, len(thresholds) + 1))

        prev = np.zeros(X.shape[0])
        for j, theta in enumerate(thresholds):
            prob = expit(theta - eta)
            probs[:, j] = prob - prev
            prev = prob
        probs[:, -1] = 1 - prev
        return probs


# ─── Factory Function ───────────────────────────────────────────────────────────


def run_logistic_regression(
    df: pd.DataFrame,
    response_col: str,
    predictor_cols: Optional[List[str]] = None,
    model_type: Literal["binary", "ordinal"] = "binary",
    **kwargs,
) -> Dict[str, Any]:
    """
    Factory function to run logistic regression.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    response_col : str
        Name of the response variable column.
    predictor_cols : list[str], optional
        Predictor column names.
    model_type : "binary" | "ordinal"
        Type of logistic regression.
    **kwargs
        Additional arguments passed to the model constructor.

    Returns
    -------
    dict
        Model results dictionary.
    """
    if model_type == "binary":
        model = BinaryLogisticRegression(df, response_col, predictor_cols, **kwargs)
    elif model_type == "ordinal":
        model = OrdinalLogisticRegression(df, response_col, predictor_cols, **kwargs)
    else:
        raise ValueError(f"Unknown model_type: {model_type}. Use 'binary' or 'ordinal'.")

    return model.fit()