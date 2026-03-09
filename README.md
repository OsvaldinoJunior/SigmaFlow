# SigmaFlow v10 — Automated Six Sigma Analysis Platform

A modular Python framework for full-spectrum industrial process analysis using Statistical Process Control (SPC) and Six Sigma/DMAIC methodologies.

## Pipeline

```
Dataset → Detection → Statistical Analysis → Visualization →
Root Cause Analysis → Statistical Tests → Advanced Analyses →
Advanced SPC Charts → Insight Engine → LaTeX Report → HTML Dashboard
```

## Quick Start

```bash
pip install -r requirements.txt
python cli.py demo          # Generate demo data + full analysis
python cli.py analyze your_data.csv
python cli.py insights      # Print insights to console
python cli.py dashboard     # Regenerate HTML dashboard
python cli.py report        # Regenerate LaTeX/PDF report
python cli.py list          # List registered analyzers
```

## New in v10 — Full Six Sigma Toolkit

| Module | Capability |
|---|---|
| `statistics/normality_tests.py` | Shapiro-Wilk, Anderson-Darling, KS test |
| `statistics/hypothesis_tests.py` | t-test (1/2 sample), Chi-square |
| `analysis/regression_analysis.py` | Linear/Multiple regression, R², coefficients |
| `analysis/doe_analysis.py` | ANOVA, main effects plots, interaction plots |
| `analysis/msa_analysis.py` | Gauge R&R (ANOVA method), %GRR, ndc |
| `analysis/fmea_analysis.py` | FMEA RPN = S×O×D, risk ranking, risk matrix |
| `visualization/cusum_chart.py` | CUSUM control chart |
| `visualization/ewma_chart.py` | EWMA control chart (λ, L configurable) |
| `visualization/xbar_r_chart.py` | X-bar and R chart (subgroup data) |

## Smart Auto-Dispatch (Engine v10)

The engine automatically runs analyses based on dataset structure:

| Dataset contains | Analysis triggered |
|---|---|
| `USL` / `LSL` columns | Capability analysis (Cp, Cpk, DPMO) |
| `Part` + `Operator` + `Measurement` | MSA / Gauge R&R |
| `Severity` + `Occurrence` + `Detection` | FMEA (RPN scoring) |
| Categorical + numeric columns | DOE (ANOVA, main effects, interaction plots) |
| ≥ 3 numeric columns | Multiple regression |
| Any numeric columns | Normality tests + hypothesis tests |
| Time-series data | CUSUM + EWMA + X-bar/R charts |

## Architecture

```
sigmaflow/
├── core/
│   ├── engine.py            Smart pipeline orchestrator (v10)
│   ├── dataset_registry.py  Auto-discovers analyzers
│   ├── dataset_detector.py  Type detection logic
│   └── logger.py            Structured logging
├── statistics/              ← NEW v10
│   ├── normality_tests.py   Shapiro-Wilk, AD, KS
│   └── hypothesis_tests.py  t-tests, chi-square
├── analysis/
│   ├── spc_analysis.py      XmR charts, trends
│   ├── capability_analysis.py  Cp, Cpk, DPMO
│   ├── pareto_analysis.py   80/20 analysis
│   ├── root_cause_analysis.py  Pearson/Spearman correlation
│   ├── regression_analysis.py  ← NEW: Linear/multiple regression
│   ├── doe_analysis.py      ← NEW: ANOVA, main effects, interactions
│   ├── msa_analysis.py      ← NEW: Gauge R&R
│   └── fmea_analysis.py     ← NEW: RPN analysis
├── visualization/
│   ├── control_charts.py    XmR charts
│   ├── histograms.py        Distribution plots
│   ├── capability_plots.py  Capability curves
│   ├── pareto_chart.py      Pareto with vital-few coloring
│   ├── correlation_heatmap.py  Heatmap + variable importance
│   ├── cusum_chart.py       ← NEW: CUSUM control chart
│   ├── ewma_chart.py        ← NEW: EWMA control chart
│   └── xbar_r_chart.py      ← NEW: X-bar and R chart
├── insights/
│   ├── rules_engine.py      RulesEngine orchestrator
│   └── statistical_rules.py WE Rules 1-4, Capability, Trend
├── report/
│   ├── latex_report.py      Scientific LaTeX report
│   ├── html_dashboard.py    Self-contained HTML dashboard
│   └── latex_templates/main.tex  Editable template
└── datasets/                6 built-in dataset analyzers
```

## Output Structure

```
output/
├── figures/<dataset>/
│   ├── spc_xmr_chart.png
│   ├── cusum_chart.png        ← NEW
│   ├── ewma_chart.png         ← NEW
│   ├── xbar_r_chart.png       ← NEW
│   ├── regression_coefficients.png  ← NEW
│   ├── regression_diagnostics.png   ← NEW
│   ├── doe_main_effects.png   ← NEW
│   ├── doe_interaction_plot.png ← NEW
│   ├── msa_grr_components.png ← NEW
│   ├── fmea_rpn_ranking.png   ← NEW
│   ├── fmea_risk_matrix.png   ← NEW
│   └── correlation_heatmap.png
├── reports/
│   ├── process_analysis_report.tex
│   └── process_analysis_report.pdf
├── dashboard/
│   └── report.html   ← Self-contained, open in browser
├── insights.json
└── logs/
```
