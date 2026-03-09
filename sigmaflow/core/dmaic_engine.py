"""
sigmaflow/core/dmaic_engine.py
================================
DMAICEngine — Automated DMAIC project execution for SigmaFlow.

Orchestrates the full Define → Measure → Analyze → Improve → Control
pipeline automatically from a dataset, without any manual configuration.

Usage
-----
    from sigmaflow.core.dmaic_engine import DMAICEngine
    import pandas as pd

    engine  = DMAICEngine()
    results = engine.run("process_data.csv")
    print(results["measure"]["capability"]["Cpk"])

    # Or with a DataFrame:
    df      = pd.read_csv("data.csv")
    results = engine.run(df)

    # Pretty-print the analysis plan:
    engine.describe_plan()

    # Save results to JSON:
    engine.save_results("output/results.json")
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from sigmaflow.core.data_profiler  import DataProfiler
from sigmaflow.core.analysis_planner import AnalysisPlanner
from sigmaflow.dmaic.define.phase   import DefinePhase
from sigmaflow.dmaic.measure.phase  import MeasurePhase
from sigmaflow.dmaic.analyze.phase  import AnalyzePhase
from sigmaflow.dmaic.improve.phase  import ImprovePhase
from sigmaflow.dmaic.control.phase  import ControlPhase

logger = logging.getLogger(__name__)


class DMAICEngine:
    """
    Automated DMAIC project engine.

    Executes the full Six Sigma DMAIC cycle automatically:
        1. Load and validate dataset
        2. Profile data (DataProfiler)
        3. Build analysis plan (AnalysisPlanner)
        4. Execute Define phase
        5. Execute Measure phase
        6. Execute Analyze phase
        7. Execute Improve phase
        8. Execute Control phase
        9. Aggregate and return structured results

    Parameters
    ----------
    target_col : str, optional
        Name of the response / quality column. Auto-detected if not given.
    output_dir : str or Path, optional
        Directory to save results JSON and logs. If None, no files are saved.
    run_phases : list[str], optional
        Subset of phases to run, e.g. ["measure", "analyze"].
        Defaults to all five phases.
    verbose : bool
        Print per-phase progress banners (default True).
    """

    _ALL_PHASES = ["define", "measure", "analyze", "improve", "control"]

    def __init__(
        self,
        target_col:  Optional[str]         = None,
        output_dir:  Optional[str | Path]  = None,
        run_phases:  Optional[List[str]]   = None,
        verbose:     bool                  = True,
    ) -> None:
        self.target_col  = target_col
        self.output_dir  = Path(output_dir) if output_dir else None
        self.run_phases  = [p.lower() for p in (run_phases or self._ALL_PHASES)]
        self.verbose     = verbose

        # Internal state — populated after run()
        self._metadata:  Dict[str, Any] = {}
        self._plan:      Dict[str, List[str]] = {}
        self._results:   Dict[str, Any] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self, data: pd.DataFrame | str) -> Dict[str, Any]:
        """
        Execute the full DMAIC pipeline.

        Parameters
        ----------
        data : pd.DataFrame or str
            A pandas DataFrame or a path to a CSV / Excel file.

        Returns
        -------
        dict
            Structured results with keys:
            "define", "measure", "analyze", "improve", "control",
            "metadata", "plan", "elapsed_s".
        """
        t0 = time.perf_counter()
        self._banner("SigmaFlow DMAIC Engine — Starting")

        # ── 1. Load ────────────────────────────────────────────────────────────
        df = self._load(data)
        self._banner(f"Dataset loaded: {len(df)} rows × {len(df.columns)} columns")

        # ── 2. Profile ─────────────────────────────────────────────────────────
        self._banner("DataProfiler — Analysing dataset structure")
        profiler = DataProfiler(target_hint=self.target_col)
        self._metadata = profiler.profile(df)

        # ── 3. Plan ────────────────────────────────────────────────────────────
        self._banner("AnalysisPlanner — Building DMAIC analysis plan")
        planner    = AnalysisPlanner()
        self._plan = planner.build_plan(self._metadata)
        if self.verbose:
            print(planner.describe_plan(self._plan))

        # ── 4–8. Execute phases ────────────────────────────────────────────────
        self._results = {
            "metadata": self._metadata,
            "plan":     self._plan,
        }

        # Pass normality results from Measure into Analyze metadata
        extended_meta = dict(self._metadata)

        phase_map = {
            "define":  DefinePhase(),
            "measure": MeasurePhase(),
            "analyze": AnalyzePhase(),
            "improve": ImprovePhase(),
            "control": ControlPhase(),
        }

        for phase_name in self._ALL_PHASES:
            if phase_name not in self.run_phases:
                self._results[phase_name] = {"skipped": True}
                continue

            self._banner(f"Phase: {phase_name.upper()}")
            phase_obj    = phase_map[phase_name]
            analysis_list = self._plan.get(phase_name, [])

            try:
                phase_result = phase_obj.run(df, analysis_list, extended_meta)
                self._results[phase_name] = phase_result

                # Forward measure results into analyze metadata
                if phase_name == "measure":
                    extended_meta["_measure_normality"]   = phase_result.get("normality", {})
                    extended_meta["_measure_capability"]  = phase_result.get("capability", {})

                # Forward analyze results into improve metadata
                if phase_name == "analyze":
                    extended_meta["_analyze_regression"]  = phase_result.get("regression", {})
                    extended_meta["_analyze_root_cause"]  = phase_result.get("root_cause", {})
                    extended_meta["_analyze_correlation"] = phase_result.get("correlation", {})

                if self.verbose:
                    ins = phase_result.get("insights", [])
                    for i in ins:
                        print(f"     {i}")

            except Exception as exc:
                logger.error("Phase '%s' failed: %s", phase_name, exc)
                self._results[phase_name] = {"error": str(exc), "phase": phase_name}

        # ── 9. Finalize ────────────────────────────────────────────────────────
        elapsed = round(time.perf_counter() - t0, 2)
        self._results["elapsed_s"] = elapsed
        self._results["summary"]   = self._build_summary()

        self._banner(f"DMAIC Complete — {elapsed}s")

        if self.output_dir:
            self.save_results()

        return self._results

    def describe_plan(self) -> str:
        """Return a human-readable description of the current analysis plan."""
        if not self._plan:
            return "No plan available. Run engine.run(data) first."
        planner = AnalysisPlanner()
        return planner.describe_plan(self._plan)

    def save_results(self, path: Optional[str | Path] = None) -> str:
        """
        Serialise results to a JSON file.

        Parameters
        ----------
        path : str or Path, optional
            Full file path. Defaults to output_dir/dmaic_results.json.

        Returns
        -------
        str
            Absolute path of the saved file.
        """
        if path is None:
            if self.output_dir is None:
                raise ValueError("Provide path= or set output_dir in constructor.")
            self.output_dir.mkdir(parents=True, exist_ok=True)
            path = self.output_dir / "dmaic_results.json"

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # JSON-safe serialisation (strip non-serialisable objects)
        safe = _json_safe(self._results)
        path.write_text(json.dumps(safe, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Results saved: %s", path)
        return str(path)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _load(self, data: pd.DataFrame | str) -> pd.DataFrame:
        if isinstance(data, pd.DataFrame):
            return data.copy()
        p = str(data)
        if p.endswith(".csv"):
            return pd.read_csv(p)
        if p.endswith((".xlsx", ".xls")):
            return pd.read_excel(p)
        raise ValueError(f"Unsupported file format: {p!r}")

    def _build_summary(self) -> Dict[str, Any]:
        """Aggregate top-level insights across all phases."""
        all_insights: List[str] = []
        errors: Dict[str, str] = {}

        for phase in self._ALL_PHASES:
            pr = self._results.get(phase, {})
            if isinstance(pr, dict):
                all_insights.extend(pr.get("insights", []))
                if pr.get("error"):
                    errors[phase] = pr["error"]

        target   = self._metadata.get("primary_target")
        cap_res  = self._results.get("measure", {}).get("capability", {})
        cpk      = cap_res.get("Cpk") if isinstance(cap_res, dict) else None
        reg_res  = self._results.get("analyze", {}).get("regression", {})
        r2       = reg_res.get("r2") if isinstance(reg_res, dict) else None
        n_ooc    = (
            self._results.get("control", {})
            .get("spc", {})
            .get("x_chart", {})
            .get("n_ooc")
        )

        return {
            "dataset":        {"rows": self._metadata.get("n_rows"),
                               "cols": self._metadata.get("n_columns")},
            "primary_target": target,
            "cpk":            cpk,
            "r2":             r2,
            "n_ooc":          n_ooc,
            "phases_run":     [p for p in self._ALL_PHASES if p in self.run_phases],
            "all_insights":   all_insights,
            "n_insights":     len(all_insights),
            "errors":         errors,
        }

    def _banner(self, msg: str) -> None:
        if self.verbose:
            width = max(len(msg) + 4, 54)
            bar   = "─" * width
            print(f"\n┌{bar}┐")
            print(f"│  {msg:<{width-2}}│")
            print(f"└{bar}┘")
        logger.info(msg)


# ── JSON serialisation helper ─────────────────────────────────────────────────

def _json_safe(obj: Any) -> Any:
    """Recursively convert an object to JSON-serialisable primitives."""
    import numpy as np  # noqa
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Series):
        return obj.tolist()
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if hasattr(obj, "__dict__"):
        return _json_safe(vars(obj))
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)
