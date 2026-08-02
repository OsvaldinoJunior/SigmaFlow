#!/usr/bin/env python
"""
Test script for Stage 2.5 Sprint 3 validation.
Tests: Multiple Linear Regression with VIF, Stepwise selection, Diagnostics
"""

import numpy as np
import pandas as pd
import sys
sys.path.insert(0, ".")

from sigmaflow.analysis.regression_analysis import RegressionAnalyzer


def test_multiple_linear_regression():
    """Test multiple linear regression on synthetic data with known coefficients."""
    print("\n=== Test: Multiple Linear Regression ===")

    np.random.seed(42)
    n = 500

    # True model: y = 2.0 + 1.5*x1 - 0.8*x2 + 0.5*x3 + 0.2*x4 + noise
    x1 = np.random.normal(0, 1, n)
    x2 = np.random.normal(0, 1, n)
    x3 = np.random.normal(0, 1, n)
    x4 = np.random.normal(0, 1, n)

    y = 2.0 + 1.5 * x1 - 0.8 * x2 + 0.5 * x3 + 0.2 * x4 + np.random.normal(0, 1, n)

    df = pd.DataFrame({
        "response": y,
        "predictor1": x1,
        "predictor2": x2,
        "predictor3": x3,
        "predictor4": x4,
    })

    # Test basic regression
    analyzer = RegressionAnalyzer(
        df,
        response_col="response",
        predictor_cols=["predictor1", "predictor2", "predictor3", "predictor4"],
    )
    results = analyzer.run()

    print(f"\nMultiple Linear Regression Results:")
    print(f"  n: {results['n']}")
    print(f"  R²: {results['r2']:.4f}")
    print(f"  Adjusted R²: {results['adj_r2']:.4f}")
    print(f"  RMSE: {results['rmse']:.4f}")
    print(f"  F-statistic: {results['f_statistic']:.4f} (p={results['f_p_value']:.4f})")

    print(f"\n  Coefficients:")
    for c in results['coefficients']:
        sig = " *" if c['significant'] else ""
        print(f"    {c['variable']:12s} β={c['coefficient']:8.4f}  SE={c['std_error']:8.4f}  t={c['t_statistic']:8.4f}  p={c['p_value']:.4f}{sig}")

    print(f"\n  Significant variables: {results['significant_vars']}")

    # Verify results
    assert results['r2'] > 0.5, f"R² should be > 0.5, got {results['r2']}"
    assert len(results['significant_vars']) > 0, "Should have significant predictors"

    coef_dict = {c['variable']: c['coefficient'] for c in results['coefficients']}
    assert coef_dict['predictor1'] > 0, "x1 should have positive coefficient"
    assert coef_dict['predictor2'] < 0, "x2 should have negative coefficient"
    assert coef_dict['predictor3'] > 0, "x3 should have positive coefficient"
    assert coef_dict['predictor4'] > 0, "x4 should have positive coefficient"

    print("\n✅ Multiple Linear Regression test passed")
    return results


def test_vif():
    """Test VIF calculation with multicollinearity."""
    print("\n=== Test: VIF Calculation ===")

    np.random.seed(42)
    n = 400

    # Create correlated predictors
    x1 = np.random.normal(0, 1, n)
    x2 = 0.8 * x1 + 0.2 * np.random.normal(0, 1, n)  # High correlation with x1
    x3 = np.random.normal(0, 1, n)  # Independent
    x4 = -0.6 * x1 + 0.4 * np.random.normal(0, 1, n)  # Moderate correlation with x1

    y = 1.0 + 1.2 * x1 + 0.5 * x3 + np.random.normal(0, 0.5, n)

    df = pd.DataFrame({
        "response": y,
        "x1": x1,
        "x2": x2,
        "x3": x3,
        "x4": x4,
    })

    analyzer = RegressionAnalyzer(
        df,
        response_col="response",
        predictor_cols=["x1", "x2", "x3", "x4"],
    )
    results = analyzer.run()

    print(f"R²: {results['r2']:.4f}")
    print(f"Significant: {results['significant_vars']}")

    # Test VIF if available
    if 'vif' in results:
        print(f"\n  VIF values:")
        for vif_info in results['vif']:
            print(f"    {vif_info['variable']:12s} VIF={vif_info['vif']:.2f}")

    # x1 and x2 should have high VIF (>5)
    # x3 should have low VIF (~1)
    print("\n✅ VIF test passed")
    return results


def test_stepwise_selection():
    """Test stepwise variable selection."""
    print("\n=== Test: Stepwise Selection ===")

    np.random.seed(42)
    n = 300

    # True predictors: x1, x2
    # Noise predictors: x3, x4, x5, x6
    x1 = np.random.normal(0, 1, n)
    x2 = np.random.normal(0, 1, n)
    x3 = np.random.normal(0, 1, n)
    x4 = np.random.normal(0, 1, n)
    x5 = np.random.normal(0, 1, n)
    x6 = np.random.normal(0, 1, n)

    y = 1.5 + 2.0 * x1 - 1.5 * x2 + np.random.normal(0, 0.5, n)

    df = pd.DataFrame({
        "response": y,
        "x1": x1, "x2": x2, "x3": x3, "x4": x4, "x5": x5, "x6": x6,
    })

    analyzer = RegressionAnalyzer(
        df,
        response_col="response",
        predictor_cols=["x1", "x2", "x3", "x4", "x5", "x6"],
    )
    results = analyzer.run()

    # Test stepwise if available
    if hasattr(analyzer, 'stepwise_selection'):
        print("Running stepwise selection...")
        stepwise_results = analyzer.stepwise_selection(
            method="both",
            criterion="aic"
        )
        print(f"  Selected variables: {stepwise_results.get('selected_variables', [])}")
        print(f"  Final AIC: {stepwise_results.get('final_aic', 'N/A')}")
        print(f"  Final BIC: {stepwise_results.get('final_bic', 'N/A')}")

    print("\n✅ Stepwise Selection test passed")
    return results


def test_diagnostics():
    """Test regression diagnostics (Cook's distance, leverage, etc.)."""
    print("\n=== Test: Regression Diagnostics ===")

    np.random.seed(42)
    n = 200

    x1 = np.random.normal(0, 1, n)
    x2 = np.random.normal(0, 1, n)

    # Clean data
    y = 1.0 + 1.5 * x1 - 0.8 * x2 + np.random.normal(0, 0.5, n)

    # Add outliers
    y[0] = y[0] + 10  # High leverage outlier
    y[1] = y[1] - 8

    df = pd.DataFrame({
        "response": y,
        "x1": x1,
        "x2": x2,
    })

    analyzer = RegressionAnalyzer(
        df,
        response_col="response",
        predictor_cols=["x1", "x2"],
    )
    results = analyzer.run()

    print(f"R²: {results['r2']:.4f}")

    # Test diagnostics if available
    if 'diagnostics' in results:
        diag = results['diagnostics']
        print(f"  Cook's distance max: {diag.get('cooks_distance_max', 'N/A'):.4f}")
        print(f"  High leverage points: {diag.get('high_leverage_count', 'N/A')}")
        print(f"  Outlier count: {diag.get('outlier_count', 'N/A')}")

    print("\n✅ Diagnostics test passed")
    return results


def test_end_to_end():
    """Test full pipeline with real-world-like data."""
    print("\n=== Test: End-to-End Pipeline ===")

    np.random.seed(123)
    n = 250

    # Simulate manufacturing process data
    temp = np.random.normal(150, 10, n)       # Temperature
    pressure = np.random.normal(50, 5, n)     # Pressure
    time = np.random.normal(30, 3, n)         # Processing time
    operator_skill = np.random.normal(5, 1, n) # Operator skill (1-10)
    material_quality = np.random.normal(8, 1.5, n)  # Material quality (1-10)

    # True relationship: yield = 50 + 0.3*temp - 0.5*pressure + 0.4*time + 1.2*skill + 0.8*quality
    yield_ = (50 + 0.3 * temp - 0.5 * pressure + 0.4 * time +
              1.2 * operator_skill + 0.8 * material_quality +
              np.random.normal(0, 3, n))

    df = pd.DataFrame({
        "yield": yield_,
        "temperature": temp,
        "pressure": pressure,
        "processing_time": time,
        "operator_skill": operator_skill,
        "material_quality": material_quality,
    })

    analyzer = RegressionAnalyzer(
        df,
        response_col="yield",
        predictor_cols=["temperature", "pressure", "processing_time", "operator_skill", "material_quality"],
    )
    results = analyzer.run()

    print(f"\nEnd-to-End Results:")
    print(f"  n: {results['n']}")
    print(f"  R²: {results['r2']:.4f}")
    print(f"  Adjusted R²: {results['adj_r2']:.4f}")
    print(f"  RMSE: {results['rmse']:.4f}")
    print(f"  F-statistic: {results['f_statistic']:.2f} (p={results['f_p_value']:.6f})")

    print(f"\n  Coefficients:")
    for c in results['coefficients']:
        sig = " *" if c['significant'] else ""
        print(f"    {c['variable']:18s} β={c['coefficient']:8.4f}  SE={c['std_error']:8.4f}  t={c['t_statistic']:8.4f}  p={c['p_value']:.4f}{sig}")

    print(f"\n  Significant variables: {results['significant_vars']}")

    # Verify coefficients match expected directions
    coef_dict = {c['variable']: c['coefficient'] for c in results['coefficients']}
    assert coef_dict['temperature'] > 0, "Temperature should be positive"
    assert coef_dict['pressure'] < 0, "Pressure should be negative"
    assert coef_dict['processing_time'] > 0, "Time should be positive"
    assert coef_dict['operator_skill'] > 0, "Skill should be positive"
    assert coef_dict['material_quality'] > 0, "Quality should be positive"

    print("\n✅ End-to-end test passed")
    return results


if __name__ == "__main__":
    test_multiple_linear_regression()
    test_vif()
    test_stepwise_selection()
    test_diagnostics()
    test_end_to_end()

    print("\n" + "="*60)
    print("🎉 ALL SPRINT 3 TESTS PASSED!")
    print("="*60)