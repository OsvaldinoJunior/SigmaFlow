"""
SigmaFlow — Lean Six Sigma statistical analysis framework.

A Python platform for automating DMAIC projects:
  - Automated dataset detection (SPC, Capability, Pareto, DOE, Logistics, Service)
  - Full statistical analysis pipeline (Cp, Cpk, XmR, Regression, MSA, FMEA)
  - Control charts with Western Electric rule detection
  - HTML dashboard + LaTeX/PDF report generation

Quick start
-----------
    from sigmaflow.core.engine import Engine

    engine  = Engine(input_dir="input/datasets", output_dir="output")
    results = engine.run()
"""
from sigmaflow.core.dmaic_engine     import DMAICEngine      # noqa: F401
from sigmaflow.core.data_profiler    import DataProfiler     # noqa: F401
from sigmaflow.core.analysis_planner import AnalysisPlanner  # noqa: F401

__version__ = "0.1.0"
__all__ = ["DMAICEngine", "DataProfiler", "AnalysisPlanner"]
