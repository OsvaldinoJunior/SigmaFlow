# DMAIC Workflow Guide

DMAIC is the core problem-solving framework in Lean Six Sigma.  
SigmaFlow automates each phase with data-driven analysis and generates structured deliverables.

---

## Overview

```
Define → Measure → Analyze → Improve → Control
  ↓          ↓         ↓         ↓         ↓
Project    Baseline  Root      Solutions  SPC Plan
Charter    Sigma     Cause     Verified   Dashboard
           Level     Analysis  by DOE
```

---

## Phase 1: Define

**Goal:** Clearly state the problem, scope, team, and business impact.

**SigmaFlow outputs:**
- Problem statement
- Project charter fields (sponsor, scope, timeline, CTQ)
- SIPOC summary (Supplier-Input-Process-Output-Customer)

**Key question:** *What are we trying to improve and why does it matter?*

---

## Phase 2: Measure

**Goal:** Quantify the current state of the process. Validate the measurement system.

**SigmaFlow outputs:**
- Baseline Cp, Cpk, DPMO, sigma level
- MSA / Gauge R&R (if Part/Operator/Measurement columns exist)
- Normality tests (Shapiro-Wilk, Anderson-Darling, KS)
- Descriptive statistics (mean, std, skew, kurtosis)
- XmR control chart

**Key question:** *How bad is the problem, and can we trust our measurements?*

---

## Phase 3: Analyze

**Goal:** Identify root causes of the defects or variation.

**SigmaFlow outputs:**
- Correlation matrix + variable importance ranking
- Regression analysis (R², significant predictors)
- Hypothesis tests (t-test, ANOVA, Mann-Whitney U)
- Pareto chart of defect categories
- FMEA / RPN ranking (if failure mode columns exist)
- Western Electric rule violations

**Key question:** *What is causing the variation or defects?*

---

## Phase 4: Improve

**Goal:** Design, test, and implement solutions that address root causes.

**SigmaFlow outputs:**
- DOE (Design of Experiments) main effects and interaction plots
- ANOVA significance table
- Optimum factor settings (highest-response conditions)

**Key question:** *What changes will most improve the process?*

---

## Phase 5: Control

**Goal:** Sustain the gains. Prevent regression to old behavior.

**SigmaFlow outputs:**
- Updated XmR / CUSUM / EWMA control charts with new limits
- Control plan recommendations
- Dashboard for ongoing monitoring

**Key question:** *How do we ensure the improvement is permanent?*

---

## Running the Full DMAIC Pipeline

```python
from sigmaflow.core.engine import Engine

engine  = Engine(input_dir="input/datasets", output_dir="output")
results = engine.run()

# All 5 phases are executed automatically based on data structure.
# Phase results are embedded in each result["advanced"] and result["analysis"] dict.
```

Or run phases individually:

```python
import pandas as pd
from sigmaflow.core.dmaic_engine import DMAICEngine

df     = pd.read_excel("input/datasets/my_process.xlsx")
engine = DMAICEngine(df)
result = engine.run_all()

print(result["define"]["problem_statement"])
print(result["measure"]["sigma_level"])
print(result["analyze"]["significant_variables"])
```

---

## Interpreting Key Metrics

| Metric | Threshold | Interpretation |
|---|---|---|
| Cpk ≥ 1.67 | Excellent | World-class process |
| Cpk ≥ 1.33 | Good | Acceptable for most industries |
| Cpk ≥ 1.00 | Marginal | At risk; improvement needed |
| Cpk < 1.00 | Incapable | Producing defects; urgent action required |
| DPMO | Lower is better | Defects per million opportunities |
| Sigma level | Higher is better | 6σ ≈ 3.4 DPMO (near-perfect) |
| Gauge R&R % | < 10% ideal | % of variation from measurement system |
| RPN (FMEA) | > 200 = critical | Risk Priority Number = S × O × D |
