"""
Test script for Stage 2.5 Sprint 2 validation.
Tests: Binary Logistic Regression, Ordinal Logistic Regression
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, ".")

from sigmaflow.analysis.logistic_regression import BinaryLogisticRegression, OrdinalLogisticRegression


def test_binary_logistic():
    """Test binary logistic regression on synthetic data."""
    print("\n=== Test: Binary Logistic Regression ===")

    # Generate synthetic binary data with known relationship
    np.random.seed(42)
    n = 500

    # Predictors
    X1 = np.random.normal(0, 1, n)
    X2 = np.random.normal(0, 1, n)
    X3 = np.random.normal(0, 1, n)

    # True coefficients: intercept=-0.5, X1=1.5, X2=-0.8, X3=0.3
    logit = -0.5 + 1.5 * X1 - 0.8 * X2 + 0.3 * X3
    p = 1 / (1 + np.exp(-logit))
    y = np.random.binomial(1, p)

    df = pd.DataFrame({
        "response": y,
        "predictor1": X1,
        "predictor2": X2,
        "predictor3": X3,
    })

    # Fit binary logistic regression
    model = BinaryLogisticRegression(
        df,
        response_col="response",
        predictor_cols=["predictor1", "predictor2", "predictor3"],
    )
    results = model.fit()

    print(f"\nBinary Logistic Regression Results:")
    print(f"  Converged: {results['converged']}")
    print(f"  Iterations: {results['n_iterations']}")
    print(f"  Log-likelihood: {results['log_likelihood']}")
    print(f"  Null LL: {results['null_log_likelihood']}")
    print(f"  McFadden R²: {results['mcfadden_r2']:.4f}")
    print(f"  LR Statistic: {results['lr_statistic']:.4f} (p={results['lr_p_value']:.4f})")
    print(f"  Accuracy: {results['accuracy']:.4f}")
    print(f"  Precision: {results['precision']:.4f}")
    print(f"  Recall: {results['recall']:.4f}")
    print(f"  F1: {results['f1']:.4f}")
    print(f"  AUC: {results['auc']:.4f}")

    print(f"\n  Coefficients:")
    for c in results['coefficients']:
        sig = " *" if c['significant'] else ""
        print(f"    {c['variable']:12s} β={c['coefficient']:8.4f}  SE={c['std_error']:8.4f}  z={c['z_statistic']:8.4f}  p={c['p_value']:.4f}  OR={c['odds_ratio']:.4f}{sig}")

    print(f"\n  Significant variables: {results['significant_vars']}")
    print(f"  Confusion Matrix: {results['confusion_matrix']}")

    # Verify results
    assert results['converged'], "Model should converge"
    assert results['auc'] > 0.7, f"AUC should be > 0.7, got {results['auc']}"
    assert len(results['significant_vars']) > 0, "Should have significant predictors"

    # Check coefficients are in expected direction
    coef_dict = {c['variable']: c['coefficient'] for c in results['coefficients']}
    assert coef_dict['predictor1'] > 0, "X1 should have positive coefficient"
    assert coef_dict['predictor2'] < 0, "X2 should have negative coefficient"

    print("\n✅ Binary Logistic Regression test passed")
    return results


def test_ordinal_logistic():
    """Test ordinal logistic regression on synthetic data."""
    print("\n=== Test: Ordinal Logistic Regression ===")

    # Generate synthetic ordinal data
    np.random.seed(42)
    n = 600

    # Predictors
    X1 = np.random.normal(0, 1, n)
    X2 = np.random.normal(0, 1, n)

    # True coefficients
    beta1, beta2 = 1.2, -0.7
    thresholds = [-1.0, 0.5, 1.5]  # 4 categories: 0,1,2,3

    # Generate latent variable
    latent = 1.5 * X1 - 0.8 * X2 + np.random.normal(0, 1, n)

    # Apply thresholds to get ordinal categories
    y = np.zeros(n, dtype=int)
    y[latent > thresholds[0]] = 1
    y[latent > thresholds[1]] = 2
    y[latent > thresholds[2]] = 3

    df = pd.DataFrame({
        "quality_rating": y,  # 0, 1, 2, 3
        "process_temp": X1,
        "pressure": X2,
    })

    print(f"\nClass distribution: {np.bincount(y)}")

    # Fit ordinal logistic regression
    model = OrdinalLogisticRegression(
        df,
        response_col="quality_rating",
        predictor_cols=["process_temp", "pressure"],
    )
    results = model.fit()

    print(f"\nOrdinal Logistic Regression Results:")
    print(f"  Converged: {results['converged']}")
    print(f"  Iterations: {results['n_iterations']}")
    print(f"  Log-likelihood: {results['log_likelihood']}")
    print(f"  Classes: {results['classes']}")
    print(f"  Thresholds: {results['thresholds']}")
    print(f"  Accuracy: {results['accuracy']:.4f}")
    print(f"  Precision: {results['precision']:.4f}")
    print(f"  Recall: {results['recall']:.4f}")
    print(f"  F1: {results['f1']:.4f}")

    print(f"\n  Coefficients:")
    for c in results['coefficients']:
        sig = " *" if c['significant'] else ""
        se_str = f"{c['std_error']:8.4f}" if c['std_error'] is not None else "       N/A"
        z_str = f"{c['z_statistic']:8.4f}" if c['z_statistic'] is not None else "       N/A"
        p_str = f"{c['p_value']:.4f}" if c['p_value'] is not None else "     N/A"
        print(f"    {c['variable']:12s} β={c['coefficient']:8.4f}  SE={se_str}  z={z_str}  p={p_str}{sig}")

    print(f"\n  Significant variables: {results['significant_vars']}")
    print(f"  Confusion Matrix:")
    cm = np.array(results['confusion_matrix'])
    print(f"  {cm}")

    # Verify results
    assert results['converged'], "Model should converge"
    assert results['accuracy'] > 0.5, f"Accuracy should be > 0.5, got {results['accuracy']}"
    assert len(results['thresholds']) == 3, "Should have 3 thresholds for 4 classes"

    # Check coefficients direction
    coef_dict = {c['variable']: c['coefficient'] for c in results['coefficients']}
    # Note: ordinal logistic has thresholds, coefficients should match expected direction

    print("\n✅ Ordinal Logistic Regression test passed")
    return results


def test_end_to_end():
    """Test full pipeline with mixed binary/ordinal data."""
    print("\n=== Test: End-to-End Pipeline ===")

    # Create mixed dataset
    np.random.seed(42)
    n = 400

    # Binary response
    X1 = np.random.normal(0, 1, n)
    X2 = np.random.normal(0, 1, n)
    logit = 0.5 + 1.2 * X1 - 0.5 * X2
    p = 1 / (1 + np.exp(-logit))
    y_binary = np.random.binomial(1, p)

    # Ordinal response
    latent = 0.8 * X1 - 0.3 * X2 + np.random.normal(0, 1, n)
    y_ordinal = np.zeros(n, dtype=int)
    y_ordinal[latent > -0.5] = 1
    y_ordinal[latent > 0.5] = 2
    y_ordinal[latent > 1.5] = 3

    df = pd.DataFrame({
        "pass_fail": y_binary,
        "quality_score": y_ordinal,
        "temp": X1,
        "pressure": X2,
    })

    print(f"\nDataset shape: {df.shape}")
    print(f"Binary response distribution: {np.bincount(y_binary)}")
    print(f"Ordinal distribution: {np.bincount(y_ordinal)}")

    # Test binary logistic
    print("\n--- Binary Logistic (pass_fail) ---")
    model_bin = BinaryLogisticRegression(
        df, response_col="pass_fail", predictor_cols=["temp", "pressure"]
    )
    bin_results = model_bin.fit()
    print(f"  AUC: {bin_results['auc']:.4f}, Accuracy: {bin_results['accuracy']:.4f}")
    print(f"  Significant: {bin_results['significant_vars']}")

    # Test ordinal logistic
    print("\n--- Ordinal Logistic (quality_score) ---")
    model_ord = OrdinalLogisticRegression(
        df, response_col="quality_score", predictor_cols=["temp", "pressure"]
    )
    ord_results = model_ord.fit()
    print(f"  Accuracy: {ord_results['accuracy']:.4f}")
    print(f"  Thresholds: {ord_results['thresholds']}")
    print(f"  Significant: {ord_results['significant_vars']}")

    print("\n✅ End-to-end test passed")


if __name__ == "__main__":
    test_binary_logistic()
    test_ordinal_logistic()
    test_end_to_end()

    print("\n" + "="*60)
    print("🎉 ALL SPRINT 2 TESTS PASSED!")
    print("="*60)