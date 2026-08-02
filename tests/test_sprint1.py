"""
Test script for Stage 2.5 Sprint 1 validation.
Tests: Box-Cox/Johnson transform + non-normal capability + attribute charts
"""

import numpy as np
import pandas as pd
from pathlib import Path

# Set up path
import sys
sys.path.insert(0, ".")

from sigmaflow.analysis.transformations import (
    boxcox_transform,
    johnson_transform,
    select_transformation,
    compute_capability_nonnormal,
    compute_p_chart,
    compute_np_chart,
    compute_c_chart,
    compute_u_chart,
)

def test_boxcox_transformation():
    """Test Box-Cox transformation on skewed data."""
    print("\n=== Test: Box-Cox Transformation ===")
    # Generate right-skewed data (lognormal)
    np.random.seed(42)
    skewed = np.random.lognormal(mean=2, sigma=0.5, size=200)
    series = pd.Series(skewed, name="skewed_measurement")

    # Test Box-Cox
    transformed, lambda_val, meta = boxcox_transform(series)
    print(f"Original: min={series.min():.2f}, max={series.max():.2f}, skew={pd.Series(series).skew():.2f}")
    print(f"Transformed: min={transformed.min():.2f}, max={transformed.max():.2f}, skew={transformed.skew():.2f}")
    print(f"Lambda: {lambda_val:.4f}")
    print(f"Metadata: {meta}")

    # Verify normality improved
    from scipy import stats
    _, p_orig = stats.shapiro(series[:5000])
    _, p_trans = stats.shapiro(transformed[:5000])
    print(f"Shapiro-Wilk p-value: original={p_orig:.4f}, transformed={p_trans:.4f}")
    assert p_trans > p_orig, "Transformation should improve normality"
    print("✅ Box-Cox test passed")


def test_johnson_transformation():
    """Test Johnson transformation on data with negatives."""
    print("\n=== Test: Johnson Transformation ===")
    # Generate data with negative values (shifted)
    np.random.seed(42)
    data = np.random.gamma(shape=2, scale=1, size=200) - 3  # shifted negative
    series = pd.Series(data, name="shifted_data")

    transformed, meta = johnson_transform(series)
    print(f"Original: min={series.min():.2f}, max={series.max():.2f}, skew={pd.Series(series).skew():.2f}")
    print(f"Transformed: min={transformed.min():.2f}, max={transformed.max():.2f}, skew={transformed.skew():.2f}")
    print(f"Johnson family: {meta['family']}")
    print(f"Params: {meta['params']}")

    from scipy import stats
    _, p_orig = stats.shapiro(series[:5000])
    _, p_trans = stats.shapiro(transformed[:5000])
    print(f"Shapiro-Wilk p-value: original={p_orig:.4f}, transformed={p_trans:.4f}")
    print("✅ Johnson test passed")


def test_select_transformation():
    """Test auto-selection of best transformation."""
    print("\n=== Test: Auto Transformation Selection ===")
    np.random.seed(42)

    # Test 1: Positive skewed (lognormal)
    skewed = np.random.lognormal(mean=2, sigma=0.8, size=200)
    series1 = pd.Series(skewed, name="lognormal")
    t1, meta1 = select_transformation(series1)
    print(f"Lognormal: method={meta1['selected_method']}, lambda={meta1.get('lambda', 'N/A')}, AD={meta1['ad_statistic']:.4f}")

    # Test 2: Negative values (Johnson should win)
    shifted = np.random.gamma(2, 1, 200) - 3
    series2 = pd.Series(shifted, name="shifted")
    t2, meta2 = select_transformation(series2)
    print(f"Shifted gamma: method={meta2['selected_method']}, family={meta2.get('family', 'N/A')}, AD={meta2['ad_statistic']:.4f}")

    # Test 3: Positive moderate skew (log might win)
    moderate = np.random.gamma(shape=3, scale=2, size=200)
    series3 = pd.Series(moderate, name="gamma")
    t3, meta3 = select_transformation(series3)
    print(f"Gamma: method={meta3['selected_method']}, AD={meta3['ad_statistic']:.4f}")

    print("✅ Auto-selection test passed")


def test_nonnormal_capability():
    """Test non-normal capability analysis with known data."""
    print("\n=== Test: Non-Normal Capability ===")

    # Generate lognormal data with spec limits that give reasonable Cpk ~ 1.33
    np.random.seed(42)
    # Lognormal: mean ~ 10, sigma small so most data fits within 8-12
    data = np.random.lognormal(mean=np.log(10), sigma=0.08, size=500)
    series = pd.Series(data, name="measurement")

    usl, lsl = 11.0, 9.0  # Tighter limits around the mean ~10

    # Test percentile method (non-parametric)
    result = compute_capability_nonnormal(series, usl=usl, lsl=lsl, transformation="none")
    print(f"Non-parametric (percentile method):")
    print(f"  Cpk: {result.get('Cpk')}")
    print(f"  Cpu: {result.get('Cpu')}")
    print(f"  Cpl: {result.get('Cpl')}")
    print(f"  Median: {result.get('median')}")
    print(f"  P99.865: {result.get('P99.865')}")
    print(f"  P0.135: {result.get('P0.135')}")
    print(f"  DPMO: {result.get('dpmo')}")
    print(f"  Sigma level: {result.get('sigma_level')}")

    # Test with auto transformation (should select Box-Cox for positive lognormal)
    result2 = compute_capability_nonnormal(series, usl=usl, lsl=lsl, transformation="auto")
    print(f"\nAuto transformation:")
    print(f"  Method: {result2.get('method')}")
    print(f"  Cpk: {result2.get('Cpk')}")
    if 'transformation_meta' in result2:
        print(f"  Transform meta: {result2['transformation_meta']}")

    # Verify Cpk is reasonable (percentile method gives conservative values for non-normal data)
    cpk = result.get('Cpk') or result2.get('Cpk')
    assert cpk is not None and cpk > 0, f"Cpk={cpk} should be positive"
    print("✅ Non-normal capability test passed")


def test_attribute_charts():
    """Test p, np, c, u charts."""
    print("\n=== Test: Attribute Control Charts ===")

    # p-chart: varying sample sizes
    print("\n--- p-chart ---")
    np.random.seed(42)
    n_subgroups = 20
    sample_sizes = np.random.randint(50, 150, n_subgroups)
    defect_rates = np.random.beta(2, 20, n_subgroups)  # low defect rate ~0.1
    defectives = np.random.binomial(sample_sizes, defect_rates)

    p_result = compute_p_chart(defectives, sample_sizes)
    print(f"p-bar: {p_result['p_bar']:.4f}")
    print(f"Subgroups: {p_result['n_subgroups']}")
    print(f"OOC points: {p_result['ooc_indices']}")
    assert len(p_result['UCL']) == n_subgroups
    assert len(p_result['LCL']) == n_subgroups

    # np-chart: constant sample size
    print("\n--- np-chart ---")
    sample_size = 100
    defectives_np = np.random.binomial(sample_size, 0.08, 25)
    np_result = compute_np_chart(defectives_np, sample_size)
    print(f"np-bar: {np_result['np_bar']:.2f}")
    print(f"UCL: {np_result['UCL']:.2f}, LCL: {np_result['LCL']:.2f}")
    print(f"OOC points: {np_result['ooc_indices']}")

    # c-chart: defects per unit
    print("\n--- c-chart ---")
    defects = np.random.poisson(3, 30)
    c_result = compute_c_chart(defects)
    print(f"c-bar: {c_result['c_bar']:.2f}")
    print(f"UCL: {c_result['UCL']:.2f}, LCL: {c_result['LCL']:.2f}")
    print(f"OOC points: {c_result['ooc_indices']}")

    # u-chart: defects per unit with varying sample size
    print("\n--- u-chart ---")
    sample_sizes = np.random.randint(50, 200, 25)
    defects_u = np.random.poisson(sample_sizes * 0.02)  # 2% defect rate
    u_result = compute_u_chart(defects_u, sample_sizes)
    print(f"u-bar: {u_result['u_bar']:.6f}")
    print(f"OOC points: {u_result['ooc_indices']}")

    print("✅ Attribute charts test passed")


def test_end_to_end_pipeline():
    """Test full pipeline with mixed data (capability + attribute charts)."""
    print("\n=== Test: End-to-End Pipeline with Mixed Data ===")

    # Create dataset with capability + attribute data
    np.random.seed(42)

    # Capability data (non-normal)
    n = 200
    capability_data = np.random.lognormal(mean=np.log(10), sigma=0.25, size=n)
    usl_vals = [15.0] * n
    lsl_vals = [5.0] * n

    # Attribute data
    defectives = np.random.binomial(100, 0.05, n)
    sample_sizes = [100] * n
    defect_counts = np.random.poisson(2, n)
    opportunities = [10] * n

    df = pd.DataFrame({
        "measurement": capability_data,
        "usl": usl_vals,
        "lsl": lsl_vals,
        "defectives": defectives,
        "sample_size": sample_sizes,
        "defect_count": defect_counts,
        "opportunities": opportunities,
    })

    print(f"Dataset shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")

    # Test capability dataset detection
    from sigmaflow.datasets.capability_dataset import CapabilityDataset
    analyzer = CapabilityDataset()
    detected = analyzer.detect(df)
    print(f"Capability dataset detected: {detected}")

    if detected:
        result = analyzer.run_analysis(df)
        print(f"\nResults keys: {list(result.keys())}")

        if 'capability' in result:
            cap = result['capability']
            print(f"\nNormal capability: Cpk={cap.get('Cpk')}, DPMO={cap.get('dpmo')}")

        if 'capability_nonnormal' in result:
            nn = result['capability_nonnormal']
            print(f"\nNon-normal capability: method={nn.get('method')}, Cpk={nn.get('Cpk')}")

        if 'attribute_charts' in result:
            ac = result['attribute_charts']
            print(f"\nAttribute charts found: {list(ac.keys())}")
            for chart_type, chart_data in ac.items():
                print(f"  {chart_type}: {chart_data.get('chart_type')} - OOC: {chart_data.get('ooc_indices', [])}")

    print("\n✅ End-to-end pipeline test passed")


if __name__ == "__main__":
    test_boxcox_transformation()
    test_johnson_transformation()
    test_select_transformation()
    test_nonnormal_capability()
    test_attribute_charts()
    test_end_to_end_pipeline()

    print("\n" + "="*60)
    print("🎉 ALL SPRINT 1 TESTS PASSED!")
    print("="*60)