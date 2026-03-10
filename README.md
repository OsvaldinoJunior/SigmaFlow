# SigmaFlow

> **A Python platform for automating Lean Six Sigma projects using the DMAIC framework.**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen)](tests/)

SigmaFlow turns raw process data into complete DMAIC project reports — automatically.  
Drop your dataset into `input/datasets/`, run one command, and get:

- Statistical analysis (Cp, Cpk, XmR, Pareto, DOE, Regression, MSA, FMEA)
- Process control charts (CUSUM, EWMA, X-bar/R, XmR)
- Structured insights with severity classification
- HTML dashboard + LaTeX/PDF report

---

## Features

| Capability | Details |
|---|---|
| **Auto-detection** | Automatically identifies dataset type (SPC, Capability, Pareto, DOE, Logistics, Service) |
| **DMAIC pipeline** | Full Define → Measure → Analyze → Improve → Control workflow |
| **Statistical tests** | Normality (Shapiro-Wilk, Anderson-Darling, KS), hypothesis tests (t-test, ANOVA, Mann-Whitney) |
| **Control charts** | XmR, X-bar/R, CUSUM, EWMA — with Western Electric rule detection |
| **Process capability** | Cp, Cpk, Cpu, Cpl, DPMO, sigma level |
| **Root cause analysis** | Correlation matrix, variable importance ranking |
| **Modular datasets** | Add a new dataset type by creating a single file — zero changes to core |
| **Reports** | HTML interactive dashboard + LaTeX/PDF scientific report |

---

## Project Structure

```
SigmaFlow/
│
├── sigmaflow/                  ← Main Python package
│   ├── core/                   ← Engine, registry, logger, output manager
│   ├── analysis/               ← Statistical analysis modules
│   ├── statistics/             ← Hypothesis and normality tests
│   ├── visualization/          ← Charts and plots
│   ├── datasets/               ← Auto-discoverable dataset analyzers
│   ├── insights/               ← Rules engine and statistical rules
│   ├── report/                 ← HTML dashboard + LaTeX report generators
│   └── dmaic/                  ← DMAIC phase implementations
│       ├── define/
│       ├── measure/
│       ├── analyze/
│       ├── improve/
│       └── control/
│
├── input/datasets/             ← Place your CSV / XLSX files here
├── tests/                      ← Pytest test suite
├── examples/                   ← Runnable example scripts
├── docs/                       ← Documentation
│
├── main.py                     ← Zero-argument entry point
├── cli.py                      ← Command-line interface
├── requirements.txt
├── pyproject.toml
└── .gitignore
```

### Module descriptions

| Module | Purpose |
|---|---|
| `core/` | Central engine, dataset registry (auto-discovery via pkgutil), logging, output manager |
| `analysis/` | Capability (Cp/Cpk), SPC (XmR), Pareto, DOE (ANOVA), regression, MSA (Gauge R&R), FMEA |
| `statistics/` | Normality tests (Shapiro-Wilk, Anderson-Darling, KS), hypothesis testing |
| `visualization/` | Control charts (XmR, CUSUM, EWMA, X-bar/R), capability plots, Pareto, heatmap |
| `datasets/` | Auto-discoverable dataset analyzers (BaseDataset ABC + concrete implementations) |
| `insights/` | Rules engine with Western Electric rules and structured Insight objects |
| `report/` | HTML dashboard (Jinja2) and LaTeX/PDF report generator |
| `dmaic/` | Phase-by-phase DMAIC implementations with structured deliverables |

---

## Installation

### From source (recommended)

```bash
git clone https://github.com/<user>/sigmaflow.git
cd sigmaflow
pip install -e .
```

### Requirements only

```bash
pip install -r requirements.txt
```

### Optional: LaTeX PDF reports

```bash
# Ubuntu / Debian
sudo apt install texlive-latex-extra

# macOS
brew install --cask mactex

# Conda
conda install -c conda-forge texlive-core
```

---

## Quick Start

**1. Drop your data in:**
```
input/datasets/your_data.csv
```

**2. Run the pipeline:**
```bash
python main.py
```

**3. Check outputs:**
```
output/figures/<dataset>/    ← PNG charts
output/reports/              ← PDF report
output/dashboard/report.html ← Interactive dashboard
output/insights.json         ← Machine-readable insights
```

**CLI options:**
```bash
python main.py --demo     # Generate 5 demo datasets and run
python main.py --list     # List registered analyzers
```

---

## Python API

```python
from sigmaflow.core.engine import Engine

engine = Engine(input_dir="input/datasets", output_dir="output")
results = engine.run()

for r in results:
    print(f"{r['name']}  [{r['dataset_type'].upper()}]  shape={r['shape']}")
    for insight in r["insights"]:
        print(f"  → {insight}")
```

---

## Capability Analysis

```python
import pandas as pd
import numpy as np
from sigmaflow.analysis.capability_analysis import compute_capability

data   = pd.Series(np.random.normal(10.0, 0.08, 300))
result = compute_capability(data, usl=10.3, lsl=9.7)

print(f"Cpk = {result['Cpk']:.3f}")
print(f"DPMO = {result['dpmo']:.1f}")
print(f"Sigma level = {result['sigma_level']:.2f}σ")
```

---

## Adding a New Dataset Type

Zero changes to core — just create one file:

```python
# sigmaflow/datasets/my_dataset.py
from sigmaflow.datasets.base_dataset import BaseDataset

class MyDataset(BaseDataset):
    name     = "my_type"
    priority = 55

    def detect(self, df):
        return "my_column" in df.columns

    def run_analysis(self, df):
        return {"mean": float(df["my_column"].mean())}

    def generate_plots(self, df, output_folder):
        return []

    def generate_insights(self, df):
        return ["My custom insight."]
```

---

## Supported Dataset Types

| Type | Detection | Key outputs |
|---|---|---|
| `capability` | USL/LSL columns or single numeric ≥30 rows | Cp, Cpk, DPMO, sigma level |
| `spc` | Datetime or monotonic index | XmR chart, Western Electric violations |
| `root_cause` | Categorical + integer defect counts | Pareto chart, vital few |
| `doe` | Columns with {-1, +1} values | Main effects, interaction plots, R² |
| `logistics` | Keywords: km, distance, delivery | Lead time, OTD rate |
| `service` | Keywords: wait, service, satisfaction | Wait time, SLA violations |

---

## Running Tests

```bash
pytest tests/ -v
pytest tests/ -v --cov=sigmaflow --cov-report=term-missing
```

---

## Documentation

- [`docs/overview.md`](docs/overview.md) — Architecture overview
- [`docs/modules.md`](docs/modules.md) — Module API reference
- [`docs/dmaic_workflow.md`](docs/dmaic_workflow.md) — DMAIC phase guide

---

## License

MIT License. See [LICENSE](LICENSE) for details.
