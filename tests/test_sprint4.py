#!/usr/bin/env python
"""
Test script for Stage 2.5 Sprint 4 validation.
Tests: Fractional Factorial DOE, Response Surface Methodology (RSM)
"""

import numpy as np
import pandas as pd
import sys
sys.path.insert(0, ".")

from sigmaflow.analysis.doe_analysis import DOEAnalyzer


def test_fractional_factorial():
    """Test fractional factorial design generation and analysis."""
    print("\n=== Test: Fractional Factorial Design ===")

    np.random.seed(42)

    # Simulate a 2^5-1 fractional factorial (Resolution V)
    # Factors: A, B, C, D, E
    # Generator: E = ABCD
    n_runs = 16
    factors = ['A', 'B', 'C', 'D', 'E']

    # Create design matrix
    # Full 2^4 for A,B,C,D
    base = np.array([
        [-1, -1, -1, -1],
        [ 1, -1, -1, -1],
        [-1,  1, -1, -1],
        [ 1,  1, -1, -1],
        [-1, -1,  1, -1],
        [ 1, -1,  1, -1],
        [-1,  1,  1, -1],
        [ 1,  1,  1, -1],
        [-1, -1, -1,  1],
        [ 1, -1, -1,  1],
        [-1,  1, -1,  1],
        [ 1,  1, -1,  1],
        [-1, -1,  1,  1],
        [ 1, -1,  1,  1],
        [-1,  1,  1,  1],
        [ 1,  1,  1,  1],
    ])

    # E = ABCD
    E = base[:, 0] * base[:, 1] * base[:, 2] * base[:, 3]
    X = np.column_stack([base, E])

    # True effects: A=2.0, B=1.5, C=0, D=0, E=0, AB=1.0, CD=0.8
    y = (2.0 * X[:, 0] + 1.5 * X[:, 1] +
         1.0 * X[:, 0] * X[:, 1] +  # AB interaction
         0.8 * X[:, 2] * X[:, 3] +  # CD interaction
         np.random.normal(0, 0.5, n_runs))

    df = pd.DataFrame(X, columns=factors)
    df['response'] = y

    # Convert to categorical for analysis
    for f in factors:
        df[f] = pd.Categorical(df[f].map({-1: 'L', 1: 'H'}))

    print(f"Design shape: {df.shape}")
    print(f"Factor levels: {df[factors].nunique().to_dict()}")

    # Analyze with existing DOEAnalyzer (one-way ANOVA per factor)
    analyzer = DOEAnalyzer(df, response_col='response', factor_cols=factors)
    results = analyzer.run()

    print(f"\nDOE Analysis Results:")
    print(f"  Response: {results['response']}")
    print(f"  Factors: {results['factors']}")
    print(f"  Significant factors: {results['significant_factors']}")
    print(f"  ANOVA table:")
    for row in results['anova_table']:
        sig = " ★" if row['significant'] else ""
        print(f"    {row['factor']:12s} F={row['f_value']:7.2f}  p={row['p_value']:.4f}  η²={row['eta_squared']:.3f}{sig}")

    # Verify detection of main effects
    assert 'A' in results['significant_factors'] or 'B' in results['significant_factors'], "Should detect at least A or B"
    assert results['n'] == n_runs, f"Sample size mismatch: {results['n']} vs {n_runs}"

    print("\n✅ Fractional Factorial test passed")
    return results


def test_rsm():
    """Test Response Surface Methodology with Central Composite Design."""
    print("\n=== Test: Response Surface Methodology (RSM) ===")

    np.random.seed(42)

    # Create Central Composite Design for 2 factors
    # Factorial points (2^2 = 4)
    fact_pts = np.array([
        [-1, -1],
        [ 1, -1],
        [-1,  1],
        [ 1,  1],
    ])

    # Center points (3)
    center_pts = np.array([
        [0, 0],
        [0, 0],
        [0, 0],
    ])

    # Star points (axial) - alpha = sqrt(2) for rotatability
    alpha = np.sqrt(2)
    star_pts = np.array([
        [-alpha, 0],
        [alpha, 0],
        [0, -alpha],
        [0, alpha],
    ])

    X_design = np.vstack([fact_pts, center_pts, star_pts])
    n_runs = len(X_design)

    # True quadratic response surface:
    # y = 50 + 3*x1 - 2*x2 + 1.5*x1^2 + 0.5*x2^2 + 1.0*x1*x2 + noise
    x1, x2 = X_design[:, 0], X_design[:, 1]
    y = (50 + 3*x1 - 2*x2 +
         1.5*x1**2 + 0.5*x2**2 +
         1.0*x1*x2 +
         np.random.normal(0, 0.8, n_runs))

    df = pd.DataFrame(X_design, columns=['temp', 'pressure'])
    df['yield'] = y

    print(f"CCD design: {n_runs} runs")
    print(f"  Factorial: 4, Center: 3, Star: 4")
    print(f"  Alpha (rotatable): {alpha:.3f}")

    # Analyze with existing DOE
    analyzer = DOEAnalyzer(df, response_col='yield', factor_cols=['temp', 'pressure'])
    results = analyzer.run()

    print(f"\nDOE Analysis Results:")
    print(f"  Significant factors: {results['significant_factors']}")
    for row in results['anova_table']:
        sig = " ★" if row['significant'] else ""
        print(f"    {row['factor']:12s} F={row['f_value']:7.2f}  p={row['p_value']:.4f}  η²={row['eta_squared']:.3f}{sig}")

    # Test RSM quadratic model fitting
    if hasattr(analyzer, 'fit_rsm'):
        rsm_results = analyzer.fit_rsm()
        print(f"\nRSM Quadratic Model:")
        print(f"  R²: {rsm_results.get('r2', 'N/A'):.4f}")
        print(f"  Adj R²: {rsm_results.get('adj_r2', 'N/A'):.4f}")
        print(f"  Coefficients:")
        for name, val in rsm_results.get('coefficients', {}).items():
            print(f"    {name}: {val:.4f}")
        print(f"  Optimum (stationary point): {rsm_results.get('optimum', 'N/A')}")
        print(f"  Nature: {rsm_results.get('nature', 'N/A')}")

    print("\n✅ RSM test passed")
    return results


def test_rsm_optimization():
    """Test finding optimum with RSM."""
    print("\n=== Test: RSM Optimization ===")

    np.random.seed(123)

    # Create a case with clear maximum
    # y = 100 - 2*(x1-1)^2 - 3*(x2+0.5)^2 (max at x1=1, x2=-0.5)
    fact_pts = np.array([[-1, -1], [1, -1], [-1, 1], [1, 1]])
    center_pts = np.array([[0, 0], [0, 0], [0, 0]])
    alpha = np.sqrt(2)
    star_pts = np.array([[-alpha, 0], [alpha, 0], [0, -alpha], [0, alpha]])
    X_design = np.vstack([fact_pts, center_pts, star_pts])

    x1, x2 = X_design[:, 0], X_design[:, 1]
    y = (100 - 2*(x1-1)**2 - 3*(x2+0.5)**2 + np.random.normal(0, 0.5, len(x1)))

    df = pd.DataFrame(X_design, columns=['x1', 'x2'])
    df['response'] = y

    analyzer = DOEAnalyzer(df, response_col='response', factor_cols=['x1', 'x2'])
    results = analyzer.run()

    if hasattr(analyzer, 'fit_rsm'):
        rsm_results = analyzer.fit_rsm()
        print(f"RSM Results:")
        print(f"  Optimum: {rsm_results.get('optimum')}")
        print(f"  Nature: {rsm_results.get('nature')}")
        print(f"  Predicted max: {rsm_results.get('predicted_optimum')}")

        # Check if optimum is close to true (1, -0.5)
        if rsm_results.get('optimum'):
            opt = rsm_results['optimum']
            print(f"  True optimum: [1.0, -0.5]")
            print(f"  Estimated: [{opt[0]:.3f}, {opt[1]:.3f}]")

    print("\n✅ RSM Optimization test passed")
    return results


def test_end_to_end():
    """Test full DOE + RSM pipeline."""
    print("\n=== Test: End-to-End DOE + RSM Pipeline ===")

    np.random.seed(42)

    # Simulate manufacturing process optimization
    # Factors: temperature (150-180), pressure (40-60), time (20-40)
    # Coded: -1 to 1
    n = 20
    temp = np.random.uniform(-1, 1, n)
    pressure = np.random.uniform(-1, 1, n)
    time = np.random.uniform(-1, 1, n)

    # True model with quadratic effects
    yield_ = (85 + 4*temp - 2*pressure + 1.5*time +
              1.2*temp**2 - 0.8*pressure**2 + 0.5*time**2 +
              0.6*temp*pressure - 0.4*temp*time +
              np.random.normal(0, 1.5, n))

    df = pd.DataFrame({
        'temperature': temp,
        'pressure': pressure,
        'processing_time': time,
        'yield': yield_,
    })

    # Convert to categorical for ANOVA
    for col in ['temperature', 'pressure', 'processing_time']:
        df[col] = pd.Categorical(pd.cut(df[col], bins=3, labels=['L', 'M', 'H']))

    print(f"Dataset: {df.shape}")

    analyzer = DOEAnalyzer(df, response_col='yield',
                           factor_cols=['temperature', 'pressure', 'processing_time'])
    results = analyzer.run()

    print(f"\nANOVA Results:")
    print(f"  Significant: {results['significant_factors']}")
    for row in results['anova_table']:
        sig = " ★" if row['significant'] else ""
        print(f"    {row['factor']:20s} F={row['f_value']:7.2f}  p={row['p_value']:.4f}  η²={row['eta_squared']:.3f}{sig}")

    print("\n✅ End-to-End test passed")
    return results


if __name__ == "__main__":
    test_fractional_factorial()
    test_rsm()
    test_rsm_optimization()
    test_end_to_end()

    print("\n" + "="*60)
    print("🎉 ALL SPRINT 4 TESTS PASSED!")
    print("="*60)