# SigmaFlow — Architecture Overview

## What is SigmaFlow?

SigmaFlow is a Python library and analysis platform for automating Lean Six Sigma (LSS)
projects using the DMAIC (Define-Measure-Analyze-Improve-Control) framework.

It accepts raw process data (CSV or Excel) and automatically produces:
- Statistical analysis tailored to the dataset type
- Control charts and capability plots
- Structured, severity-ranked insights
- HTML dashboard and PDF report

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Engine (core)                           │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐  │
│  │  Scanner │→ │  Loader  │→ │ Registry  │→ │  Dispatcher  │  │
│  └──────────┘  └──────────┘  └───────────┘  └──────────────┘  │
│                                                      ↓          │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐  │
│  │  Report  │← │ Insights │← │   Stats   │← │   Analyzer   │  │
│  └──────────┘  └──────────┘  └───────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Pipeline steps (per file)

1. **Scan** — find all CSV/XLSX in `input/datasets/`
2. **Load** — auto-detect CSV separator; handle Excel sheets
3. **Detect** — `DatasetRegistry.match(df)` returns the best-fit analyzer
4. **Analyse** — `analyzer.run_analysis(df)` → dict of metrics
5. **Visualize** — `analyzer.generate_plots(df, folder)` → PNG files
6. **Root Cause** — correlation matrix + variable importance
7. **Statistics** — normality tests + hypothesis tests
8. **Advanced** — smart dispatch for MSA / FMEA / DOE / Regression
9. **Advanced SPC** — CUSUM, EWMA, X-bar/R charts (for SPC/capability data)
10. **Insights** — `RulesEngine.evaluate()` → ranked `Insight` objects
11. **Abstract** — auto-generated text summary
12. **Dashboard** — HTML report (Jinja2)
13. **Export** — `insights.json`, figures, PDF

---

## Auto-Discovery Pattern

Dataset analyzers are registered automatically using Python's `pkgutil` and `importlib`.
Any class in `sigmaflow/datasets/` that inherits from `BaseDataset` is discovered
at startup and sorted by `priority` (descending).

This means adding a new dataset type requires **only one new file** — no changes
to the engine, registry, or any other module.

---

## Key Design Principles

- **Convention over configuration**: drop files in, get results out
- **Open/Closed**: open for extension (new dataset types), closed for modification
- **Fail-safe**: every pipeline stage is wrapped in try/except; one failure does not stop others
- **Structured outputs**: all results are dicts with consistent schema for easy downstream use
