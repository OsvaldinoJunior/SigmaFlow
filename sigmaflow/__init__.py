"""
SigmaFlow — Lean Six Sigma statistical analysis framework.

Quick start
-----------
    from sigmaflow import DMAICEngine

    engine  = DMAICEngine()
    results = engine.run("process_data.csv")
"""
from sigmaflow.core.dmaic_engine    import DMAICEngine          # noqa: F401
from sigmaflow.core.data_profiler   import DataProfiler         # noqa: F401
from sigmaflow.core.analysis_planner import AnalysisPlanner     # noqa: F401

__all__ = ["DMAICEngine", "DataProfiler", "AnalysisPlanner"]
__version__ = "11.0.0"
