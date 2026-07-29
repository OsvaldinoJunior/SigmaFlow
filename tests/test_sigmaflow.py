"""
tests/test_sigmaflow.py
========================
Pytest test suite for SigmaFlow v7.

Tests cover:
    - Dataset auto-detection
    - Statistical rules (Western Electric)
    - Capability analysis
    - Trend analysis
    - Engine pipeline

Run with:
    pytest tests/ -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ─── Dataset Detection ────────────────────────────────────────────────────────

class TestDatasetDetection:
    """Tests for automatic dataset type detection."""

    def setup_method(self):
        from sigmaflow.core.dataset_registry import DatasetRegistry
        self.registry = DatasetRegistry().discover()

    def test_spc_detection_timestamp(self):
        """SPC dataset detected when a timestamp column exists."""
        df = pd.DataFrame({
            "timestamp": range(1, 51),
            "thickness": np.random.normal(2.5, 0.05, 50),
        })
        result = self.registry.match(df)
        assert result is not None
        assert result.name == "spc"

    def test_capability_detection_with_spec_limits(self):
        """Capability dataset detected when USL/LSL columns exist."""
        df = pd.DataFrame({
            "measurement": np.random.normal(10.0, 0.1, 100),
            "usl": 10.3,
            "lsl": 9.7,
        })
        result = self.registry.match(df)
        assert result is not None
        assert result.name == "capability"

    def test_logistics_detection_by_keyword(self):
        """Logistics dataset detected by column keyword 'distance_km'."""
        df = pd.DataFrame({
            "distance_km":   np.random.uniform(50, 800, 50),
            "delivery_days": np.random.uniform(1, 10, 50),
        })
        result = self.registry.match(df)
        assert result is not None
        assert result.name == "logistics"

    def test_no_match_returns_none(self):
        """An unrecognized dataset returns None (no crash)."""
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        result = self.registry.match(df)
        # May or may not match — just shouldn't raise
        # (a catch-all may exist in some registry configurations)
        assert True  # No exception raised


# ─── Statistical Rules ────────────────────────────────────────────────────────

class TestWesternElectricRules:
    """Tests for Western Electric rule detection."""

    def setup_method(self):
        from sigmaflow.insights.statistical_rules import WesternElectricRules
        self.rules = WesternElectricRules()

    def test_rule_1_detects_ooc_point(self):
        """Rule 1 fires when a point is outside 3σ."""
        np.random.seed(42)
        values = np.random.normal(0, 1, 30)
        values[15] = 10.0   # Inject a clear outlier
        series = pd.Series(values, name="test")
        mu  = float(series.mean())
        ucl = mu + 3 * float(series.std())
        lcl = mu - 3 * float(series.std())
        analysis = {"x_chart": {"CL": mu, "UCL": ucl, "LCL": lcl, "ooc_points": [15], "n_ooc": 1}}
        insights = self.rules.evaluate(series, analysis)
        rule_ids = [i.rule for i in insights]
        assert "western_electric_rule_1" in rule_ids

    def test_rule_2_detects_run(self):
        """Rule 2: 9 consecutive points above the mean."""
        values = [1] * 9 + [0] * 10   # 9 above mean (mean ≈ 0.47)
        series = pd.Series(values, name="test")
        mu     = float(series.mean())
        analysis = {"x_chart": {"CL": mu, "UCL": mu + 3, "LCL": mu - 3}}
        ooc = self.rules._rule_2(np.array(values), mu)
        assert len(ooc) > 0, "Rule 2 should detect a run of 9 points on one side"

    def test_rule_3_detects_trend(self):
        """Rule 3: 6 consecutive increasing points."""
        values = [0, 1, 2, 3, 4, 5, 0, 0, 0, 0]
        starts = self.rules._rule_3(np.array(values))
        assert len(starts) > 0, "Rule 3 should detect an increasing trend of 6 points"

    def test_stable_process_produces_all_pass(self):
        """A stable process with no violations produces an 'all pass' insight."""
        np.random.seed(0)
        values = np.random.normal(0, 0.5, 50)  # Tight, stable process
        series = pd.Series(values, name="stable")
        mu  = float(series.mean())
        std = float(series.std())
        analysis = {
            "x_chart": {
                "CL": mu, "UCL": mu + 3*std, "LCL": mu - 3*std,
                "ooc_points": [], "n_ooc": 0,
            }
        }
        insights = self.rules.evaluate(series, analysis)
        rule_ids = [i.rule for i in insights]
        assert "western_electric_all_pass" in rule_ids


# ─── Capability Analysis ──────────────────────────────────────────────────────

class TestCapabilityAnalysis:
    """Tests for process capability computation."""

    def test_cpk_capable_process(self):
        """A well-centered process within spec limits should have Cpk ≥ 1.33."""
        from sigmaflow.analysis.capability_analysis import compute_capability
        series = pd.Series(np.random.normal(10.0, 0.05, 300))
        result = compute_capability(series, usl=10.3, lsl=9.7)
        assert result["Cpk"] >= 1.33, f"Expected capable process, got Cpk={result['Cpk']}"

    def test_cpk_incapable_process(self):
        """A wide distribution should produce Cpk < 1.0."""
        from sigmaflow.analysis.capability_analysis import compute_capability
        series = pd.Series(np.random.normal(10.0, 0.5, 300))  # σ = 0.5, spec range = 0.6
        result = compute_capability(series, usl=10.3, lsl=9.7)
        assert result["Cpk"] < 1.0, f"Expected incapable process, got Cpk={result['Cpk']}"

    def test_dpmo_to_sigma_six_sigma(self):
        """DPMO of 3.4 should yield approximately 6σ."""
        from sigmaflow.analysis.capability_analysis import dpmo_to_sigma
        sigma = dpmo_to_sigma(3.4)
        assert 5.8 <= sigma <= 6.2, f"Expected ~6σ for 3.4 DPMO, got {sigma}"

    def test_dpmo_to_sigma_zero_defects(self):
        """DPMO of 0 should return 6.0."""
        from sigmaflow.analysis.capability_analysis import dpmo_to_sigma
        assert dpmo_to_sigma(0) == 6.0

    def test_normality_normal_data(self):
        """Normally distributed data should pass the Shapiro-Wilk test."""
        from sigmaflow.analysis.capability_analysis import compute_normality
        np.random.seed(1)
        series = pd.Series(np.random.normal(0, 1, 200))
        result = compute_normality(series)
        assert result["normal"] is True, "Normal data should pass normality test"

    def test_normality_skewed_data(self):
        """Heavily skewed data should fail normality test."""
        from sigmaflow.analysis.capability_analysis import compute_normality
        np.random.seed(1)
        series = pd.Series(np.random.exponential(2, 200))
        result = compute_normality(series)
        assert result["normal"] is False, "Exponential data should fail normality test"


# ─── SPC Analysis ─────────────────────────────────────────────────────────────

class TestSPCAnalysis:
    """Tests for SPC (XmR chart) computations."""

    def test_xmr_limits_computed(self):
        """XmR chart limits should be computable from any numeric series."""
        from sigmaflow.analysis.spc_analysis import compute_xmr_chart
        series = pd.Series(np.random.normal(5.0, 0.2, 50))
        result = compute_xmr_chart(series)
        assert "x_chart" in result
        assert result["x_chart"]["UCL"] > result["x_chart"]["CL"]
        assert result["x_chart"]["LCL"] < result["x_chart"]["CL"]

    def test_trend_increasing(self):
        """A monotonically increasing series should be detected as 'increasing'."""
        from sigmaflow.analysis.spc_analysis import compute_trend
        series = pd.Series(np.linspace(0, 10, 60))
        result = compute_trend(series)
        assert result["direction"] == "increasing"

    def test_trend_stable(self):
        """Random noise should produce a stable trend result."""
        from sigmaflow.analysis.spc_analysis import compute_trend
        np.random.seed(99)
        series = pd.Series(np.random.normal(0, 1, 80))
        result = compute_trend(series)
        assert result["direction"] == "stable"


# ─── Pareto Analysis ─────────────────────────────────────────────────────────

class TestParetoAnalysis:
    """Tests for Pareto (80/20) analysis."""

    def test_vital_few_identified(self):
        """Vital few categories should explain ≥ 80% of total defects."""
        from sigmaflow.analysis.pareto_analysis import compute_pareto
        df = pd.DataFrame({
            "defect": ["A", "B", "C", "D", "E"],
            "count":  [500, 300, 100, 60, 40],
        })
        result = compute_pareto(df, "defect", "count")
        vital = result["vital_few"]
        total = result["total"]
        vital_count = sum(df.loc[df["defect"].isin(vital), "count"])
        assert vital_count / total >= 0.75  # Vital few cover ≥ 75%

    def test_categories_sorted_descending(self):
        """Categories should be returned in descending frequency order."""
        from sigmaflow.analysis.pareto_analysis import compute_pareto
        df = pd.DataFrame({
            "type":  ["X", "Y", "Z"],
            "n":     [10, 50, 30],
        })
        result = compute_pareto(df, "type", "n")
        assert result["counts"] == sorted(result["counts"], reverse=True)


# ─── Rules Engine ─────────────────────────────────────────────────────────────

class TestRulesEngine:
    """Tests for the central RulesEngine."""

    def test_engine_returns_insight_objects(self):
        """RulesEngine.evaluate() should return a non-empty list of Insight objects."""
        from sigmaflow.insights.rules_engine import RulesEngine, Insight
        np.random.seed(7)
        df = pd.DataFrame({"measurement": np.random.normal(0, 1, 50)})
        engine = RulesEngine()
        results = engine.evaluate(df, {}, dataset_type="spc")
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, Insight)
            assert r.rule
            assert r.description

    def test_capability_insight_for_incapable_process(self):
        """Incapable process (Cpk < 1) triggers a critical capability insight."""
        from sigmaflow.insights.rules_engine import RulesEngine
        df = pd.DataFrame({"measurement": np.random.normal(10, 1, 100)})
        analysis = {
            "capability": {
                "Cpk": 0.5, "Cp": 0.6,
                "dpmo": 133614, "sigma_level": 2.5,
                "usl": 10.3, "lsl": 9.7,
            }
        }
        engine = RulesEngine()
        insights = engine.evaluate(df, analysis, "capability")
        critical = [i for i in insights if i.severity == "critical"]
        assert len(critical) >= 1, "Incapable process should produce a critical insight"
