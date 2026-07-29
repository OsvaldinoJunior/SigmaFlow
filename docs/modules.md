# SigmaFlow — Module Reference

## `sigmaflow.core`

### `Engine`
Central orchestration class. Runs the complete pipeline for all files in `input_dir`.

```python
from sigmaflow.core.engine import Engine

engine = Engine(
    input_dir      = "input/datasets",
    output_dir     = "output",
    run_root_cause = True,
    run_dashboard  = True,
    run_statistics = True,
)
results = engine.run()   # list[dict]
```

**Result dict schema:**
```python
{
    "file": str,
    "name": str,
    "dataset_type": str,
    "shape": tuple[int, int],
    "analysis": dict,
    "plots": list[str],         # file paths to PNGs
    "insights": list[str],
    "structured_insights": list[dict],
    "root_cause": dict,
    "abstract": str,
    "statistics": dict,
    "advanced": dict,
    "elapsed_s": float,
    "errors": dict,
}
```

### `DatasetRegistry`
Auto-discovers and manages dataset analyzers.

```python
from sigmaflow.core.dataset_registry import DatasetRegistry

registry = DatasetRegistry().discover()
print(registry.summary())          # dict of registered types
analyzer = registry.match(df)      # returns best-fit BaseDataset instance
```

---

## `sigmaflow.analysis`

### `compute_capability(series, usl, lsl)`
Computes Cp, Cpk, Cpu, Cpl, DPMO, sigma level, and normality test.

```python
from sigmaflow.analysis.capability_analysis import compute_capability

result = compute_capability(series, usl=10.3, lsl=9.7)
# result["Cpk"], result["dpmo"], result["sigma_level"]
```

### `compute_xmr_chart(series)`
Computes XmR (Individuals & Moving Range) control chart limits.

```python
from sigmaflow.analysis.spc_analysis import compute_xmr_chart

result = compute_xmr_chart(series)
# result["x_chart"]["UCL"], result["x_chart"]["LCL"], result["x_chart"]["CL"]
# result["x_chart"]["ooc_points"]
```

### `compute_pareto(df, category_col, count_col)`
Computes Pareto rankings and identifies the vital few (80/20).

```python
from sigmaflow.analysis.pareto_analysis import compute_pareto

result = compute_pareto(df, "defect_type", "count")
# result["vital_few"], result["cumulative_pct"], result["counts"]
```

### `RegressionAnalyzer(df)`
Multi-variable OLS regression. Auto-selects target and predictors.

```python
from sigmaflow.analysis.regression_analysis import RegressionAnalyzer

ra     = RegressionAnalyzer(df)
result = ra.run()
plots  = ra.generate_plots(output_folder)
```

### `DOEAnalyzer(df, factor_cols)`
Design of Experiments with ANOVA significance testing.

### `MSAAnalyzer(df, part_col, operator_col, measurement_col)`
Gauge R&R (Measurement System Analysis) using ANOVA method.

### `FMEAAnalyzer(df, failure_mode_col, severity_col, occurrence_col, detection_col)`
Risk Priority Number (RPN) computation and failure mode ranking.

---

## `sigmaflow.statistics`

### `run_normality_tests(df, columns)`
Runs Shapiro-Wilk, Anderson-Darling, and Kolmogorov-Smirnov for each column.

```python
from sigmaflow.statistics.normality_tests import run_normality_tests

results = run_normality_tests(df, columns=["thickness", "weight"])
# results["thickness"]["overall_verdict"]  →  "Normal" | "Non-Normal"
```

### `HypothesisTester(df)`
Automated hypothesis testing: t-test, ANOVA, Mann-Whitney U.

```python
from sigmaflow.statistics.hypothesis_tests import HypothesisTester

ht      = HypothesisTester(df)
results = ht.run_all()
# results["tests"]  →  list of test result dicts
```

---

## `sigmaflow.visualization`

| Function | Chart |
|---|---|
| `plot_cusum_chart(series, path)` | CUSUM control chart |
| `plot_ewma_chart(series, path)` | EWMA control chart |
| `plot_xbar_r_chart(series, path, n)` | X-bar and R chart |
| `plot_correlation_heatmap(df, path)` | Pearson correlation matrix |
| `plot_variable_importance(ranked, target, path)` | Variable importance bar chart |

---

## `sigmaflow.insights`

### `RulesEngine`
Evaluates statistical rules against analysis results and returns `Insight` objects.

```python
from sigmaflow.insights.rules_engine import RulesEngine

engine   = RulesEngine()
insights = engine.evaluate(df, analysis_dict, dataset_type="capability")

for i in insights:
    print(f"[{i.severity.upper()}] {i.rule}: {i.description}")
    print(f"  → {i.recommendation}")
```

### `Insight` dataclass fields
- `rule: str` — rule identifier (e.g. `"western_electric_rule_1"`)
- `description: str` — human-readable finding
- `meaning: str` — statistical interpretation
- `recommendation: str` — suggested action
- `severity: str` — `"info"` | `"warning"` | `"critical"`

---

## `sigmaflow.datasets`

### `BaseDataset` (ABC)
All dataset analyzers inherit from this class.

```python
from sigmaflow.datasets.base_dataset import BaseDataset

class MyDataset(BaseDataset):
    name        = "my_type"
    description = "Description shown in --list"
    priority    = 55          # checked before analyzers with lower priority

    def detect(self, df: pd.DataFrame) -> bool: ...
    def run_analysis(self, df: pd.DataFrame) -> dict: ...
    def generate_plots(self, df: pd.DataFrame, output_folder: Path) -> list[str]: ...
    def generate_insights(self, df: pd.DataFrame) -> list[str]: ...
```

---

## `sigmaflow.dmaic`

Each phase is a class with `run(df, context) → dict` returning structured deliverables.

```python
from sigmaflow.dmaic.define.phase  import DefinePhase
from sigmaflow.dmaic.measure.phase import MeasurePhase
from sigmaflow.dmaic.analyze.phase import AnalyzePhase
from sigmaflow.dmaic.improve.phase import ImprovePhase
from sigmaflow.dmaic.control.phase import ControlPhase
```

Use `DMAICEngine` to run all phases in sequence:

```python
from sigmaflow.core.dmaic_engine import DMAICEngine

engine = DMAICEngine(df)
result = engine.run_all()
```
