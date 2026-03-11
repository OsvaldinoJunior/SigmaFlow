"""
sigmaflow/core/engine.py  (v10)
================================
Central analysis engine — SigmaFlow v10.

New in v10
----------
- Smart analysis dispatcher: automatically runs additional analyses based
  on dataset structure (MSA, FMEA, DOE, Regression, Normality, Hypothesis)
- Statistics package integration (normality + hypothesis tests)
- All new analysis results flow into LaTeX report and HTML dashboard
- Advanced SPC charts (CUSUM, EWMA, X-bar/R) auto-generated for time-series
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from sigmaflow.core.dataset_registry import DatasetRegistry
from sigmaflow.core.logger import get_logger, log_stage, setup_logging
from sigmaflow.insights.rules_engine import RulesEngine

logger = get_logger(__name__)
_SUPPORTED_EXT = {".csv", ".xlsx", ".xls"}


class Engine:
    """
    Orchestrates the SigmaFlow v10 analysis pipeline.

    Pipeline (per file):
        Load → Detect → Analyse → Visualize → Root Cause →
        Statistics → Advanced Analyses (MSA/FMEA/DOE/Regression/Normality) →
        Advanced Charts (CUSUM/EWMA/XbarR) →
        Insights → Abstract → Dashboard → Export
    """

    def __init__(
        self,
        input_dir:      str | Path = "input/datasets",
        output_dir:     str | Path = "output",
        registry:       Optional[DatasetRegistry] = None,
        run_root_cause: bool = True,
        run_dashboard:  bool = True,
        run_statistics: bool = True,
    ) -> None:
        self.input_dir      = Path(input_dir)
        self.output_dir     = Path(output_dir)
        self.figures_dir    = self.output_dir / "figures"
        self.reports_dir    = self.output_dir / "reports"
        self.dashboard_dir  = self.output_dir / "dashboard"
        self.logs_dir       = self.output_dir / "logs"
        self.run_root_cause = run_root_cause
        self.run_dashboard  = run_dashboard
        self.run_statistics = run_statistics
        self.registry       = registry or DatasetRegistry().discover()
        self._results: List[Dict[str, Any]] = []
        setup_logging(log_dir=self.logs_dir, level="INFO")

    def run(self) -> List[Dict[str, Any]]:
        files = self._scan()
        if not files:
            logger.warning("No supported files in '%s'", self.input_dir)
            return []

        log_stage("SigmaFlow v10 Pipeline Starting")
        logger.info("Found %d file(s) to process.", len(files))
        self._results = []

        for path in files:
            self._results.append(self._process_file(path))

        log_stage("Exporting Results")
        self._export_insights()

        if self.run_dashboard:
            log_stage("Generating HTML Dashboard")
            self._generate_dashboard()

        log_stage("Pipeline Complete")
        logger.info("Processed %d dataset(s). Outputs: %s", len(self._results), self.output_dir)
        return self._results

    @property
    def results(self) -> List[Dict[str, Any]]:
        return list(self._results)

    def generate_dashboard(self) -> str:
        return self._generate_dashboard()

    # ── File scanning ─────────────────────────────────────────────────────────

    def _scan(self) -> List[Path]:
        if not self.input_dir.exists():
            self.input_dir.mkdir(parents=True, exist_ok=True)
        return sorted(p for p in self.input_dir.iterdir()
                      if p.suffix.lower() in _SUPPORTED_EXT and not p.name.startswith("~"))

    # ── Single-file pipeline ──────────────────────────────────────────────────

    def _process_file(self, path: Path) -> Dict[str, Any]:
        log_stage(f"Processing: {path.name}")
        t0 = time.time()

        result: Dict[str, Any] = {
            "file": str(path), "name": path.stem,
            "dataset_type": "unknown", "shape": None,
            "analysis": {}, "plots": [],
            "insights": [], "structured_insights": [],
            "root_cause": {}, "abstract": "",
            "statistics": {}, "advanced": {},
            "elapsed_s": 0.0, "errors": {},
            # ── Problem detection (new in v10.1) ─────────────────────────────
            "detection": {},        # DetectionResult.as_dict()
            "analysis_plan": {},    # AnalysisSelector DMAIC plan
            "profile": {},          # DataProfiler metadata
        }

        # 1. LOAD
        log_stage("Loading dataset")
        try:
            df = _load(path)
            result["shape"] = df.shape
            logger.info("Loaded: %d rows × %d columns", *df.shape)
        except Exception as exc:
            logger.error("Load failed: %s", exc)
            result["errors"]["load"] = str(exc)
            return result

        # 1b. PROFILE (DataProfiler — drives all downstream detection)
        log_stage("Profiling dataset structure")
        try:
            from sigmaflow.core.data_profiler import DataProfiler
            profiler = DataProfiler()
            profile  = profiler.profile(df)
            result["profile"] = profile
        except Exception as exc:
            logger.error("DataProfiler error: %s", exc)
            result["errors"]["profile"] = str(exc)
            profile = {}

        # 1c. PROBLEM DETECTION + ANALYSIS SELECTION
        log_stage("Detecting statistical problem type")
        try:
            from sigmaflow.core.problem_detector  import ProblemDetector
            from sigmaflow.core.analysis_selector import AnalysisSelector

            detection     = ProblemDetector().detect(profile)
            analysis_plan = AnalysisSelector().select(detection)

            result["detection"]     = detection.as_dict()
            result["analysis_plan"] = analysis_plan

            # Propagate response variable if DataProfiler missed it
            if detection.response_variable and not profile.get("primary_target"):
                profile["primary_target"] = detection.response_variable

        except Exception as exc:
            logger.error("Problem detection error: %s", exc)
            result["errors"]["detection"] = str(exc)
            detection     = None
            analysis_plan = {}

        # 2. DETECT (registry type — kept for backward compatibility)
        log_stage("Detecting dataset type")
        analyzer = self.registry.match(df)
        if analyzer is None:
            logger.warning("No analyzer matched '%s'", path.name)
            result["errors"]["detect"] = "No registered analyzer matched."
            return result
        result["dataset_type"] = analyzer.name
        logger.info("Detected type: %s | Problems: %s",
                    analyzer.name.upper(),
                    result["detection"].get("problems", []))
        print(f"\n  📂 {path.name}  |  {analyzer.name.upper()}  |  {df.shape[0]}×{df.shape[1]}")

        # 3. ANALYSE
        log_stage("Running statistical analysis")
        try:
            result["analysis"] = analyzer.run_analysis(df)
        except Exception as exc:
            logger.error("Analysis error: %s", exc)
            result["errors"]["analysis"] = str(exc)

        # 4. VISUALIZE
        log_stage("Generating figures")
        fig_subdir = self.figures_dir / path.stem
        try:
            result["plots"] = analyzer.generate_plots(df, fig_subdir)
            for p in result["plots"]:
                print(f"     ✓ {Path(p).name}")
        except Exception as exc:
            logger.error("Visualization error: %s", exc)
            result["errors"]["visualization"] = str(exc)

        # 5. ROOT CAUSE
        if self.run_root_cause and df.select_dtypes(include="number").shape[1] >= 2:
            log_stage("Running root cause detection")
            try:
                rca_res, rca_plots = self._run_root_cause(df, path.stem, fig_subdir)
                result["root_cause"] = rca_res
                result["plots"].extend(rca_plots)
            except Exception as exc:
                logger.error("Root cause error: %s", exc)
                result["errors"]["root_cause"] = str(exc)

        # 6. STATISTICS (Normality + Hypothesis tests)
        if self.run_statistics:
            log_stage("Running statistical tests")
            result["statistics"] = self._run_statistics(df)

        # 7. ADVANCED ANALYSES (smart dispatch)
        log_stage("Running advanced analyses")
        result["advanced"] = self._dispatch_advanced(df, path.stem, fig_subdir, result["plots"])
        # Merge any new plots from advanced analyses
        for key, adv in result["advanced"].items():
            if isinstance(adv, dict) and "plots" in adv:
                result["plots"].extend(adv["plots"])

        # 8. ADVANCED SPC CHARTS (CUSUM / EWMA / X-bar R)
        if analyzer.name in ("spc", "capability", "service"):
            log_stage("Generating advanced SPC charts")
            spc_plots = self._run_advanced_spc(df, fig_subdir)
            result["plots"].extend(spc_plots)

        # 9. INSIGHTS
        log_stage("Applying statistical rules")
        try:
            result["insights"] = analyzer.generate_insights(df)
            structured = RulesEngine().evaluate(df, result["analysis"], analyzer.name)
            result["structured_insights"] = [s.__dict__ for s in structured]
        except Exception as exc:
            logger.error("Insights error: %s", exc)
            result["errors"]["insights"] = str(exc)

        # 9b. INSIGHT ENGINE + RECOMMENDATION ENGINE (new in v10.2)
        log_stage("Generating analytical insights and recommendations")
        try:
            from sigmaflow.insights.insight_engine        import InsightEngine
            from sigmaflow.insights.recommendation_engine import RecommendationEngine

            analysis_insights = InsightEngine().generate(result)
            rec_engine        = RecommendationEngine(result, analysis_insights)

            result["analysis_insights"]   = [i.as_dict() for i in analysis_insights]
            result["executive_summary"]   = rec_engine.executive_summary()
            result["recommendations"]     = rec_engine.prioritized_recommendations()
            result["risk_level"]          = rec_engine.risk_level()
            result["risk_label"]          = rec_engine.risk_label()
            result["risk_color"]          = rec_engine.risk_color()

            n_crit = sum(1 for i in analysis_insights if i.severity == "critical")
            n_warn = sum(1 for i in analysis_insights if i.severity == "warning")
            print(f"  📊 Insights gerados   : {len(analysis_insights)} "
                  f"({n_crit} críticos, {n_warn} avisos)")
            logger.info("InsightEngine: %d insights, risk=%s",
                        len(analysis_insights), result['risk_level'])
        except Exception as exc:
            logger.error("InsightEngine error: %s", exc)
            result["errors"]["insight_engine"] = str(exc)
            result["analysis_insights"] = []
            result["executive_summary"] = ""
            result["recommendations"]   = []
            result["risk_level"]        = "info"

        # 10. ABSTRACT
        result["abstract"] = self._generate_abstract(result)

        result["elapsed_s"] = round(time.time() - t0, 2)
        logger.info("Finished '%s' in %.2f s.", path.name, result["elapsed_s"])
        return result

    # ── Statistics ────────────────────────────────────────────────────────────

    def _run_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Run normality and hypothesis tests."""
        stats_result = {}
        try:
            from sigmaflow.statistics.normality_tests import run_normality_tests
            num_cols = list(df.select_dtypes(include="number").columns[:4])
            stats_result["normality"] = run_normality_tests(df, columns=num_cols)
            logger.info("Normality tests complete (%d columns).", len(num_cols))
        except Exception as exc:
            logger.error("Normality tests error: %s", exc)
            stats_result["normality_error"] = str(exc)

        try:
            from sigmaflow.statistics.hypothesis_tests import HypothesisTester
            ht = HypothesisTester(df)
            stats_result["hypothesis"] = ht.run_all()
            n_tests = len(stats_result["hypothesis"].get("tests", []))
            logger.info("Hypothesis tests complete (%d tests).", n_tests)
        except Exception as exc:
            logger.error("Hypothesis tests error: %s", exc)
            stats_result["hypothesis_error"] = str(exc)

        return stats_result

    # ── Smart dispatch ────────────────────────────────────────────────────────

    def _dispatch_advanced(
        self,
        df: pd.DataFrame,
        stem: str,
        fig_subdir: Path,
        existing_plots: List[str],
    ) -> Dict[str, Any]:
        """
        Automatically run advanced analyses based on dataset structure.

        Detection logic:
        - MSA  : has Part + Operator + Measurement columns
        - FMEA : has Severity + Occurrence + Detection columns
        - DOE  : has numeric response + categorical/low-cardinality factors
        - Regression : multiple numeric columns (≥ 3)
        """
        advanced = {}

        # ── MSA ───────────────────────────────────────────────────────────────
        msa_cols = {c.lower() for c in df.columns}
        if all(kw in msa_cols for kw in ("part", "operator", "measurement")):
            log_stage("Running MSA (Gauge R&R)")
            try:
                from sigmaflow.analysis.msa_analysis import MSAAnalyzer
                part_col = next(c for c in df.columns if c.lower() == "part")
                op_col   = next(c for c in df.columns if c.lower() == "operator")
                ms_col   = next(c for c in df.columns if c.lower() == "measurement")
                msa      = MSAAnalyzer(df, part_col, op_col, ms_col)
                res      = msa.run()
                plots    = msa.generate_plots(fig_subdir)
                advanced["msa"] = {**res, "plots": plots}
                for p in plots:
                    print(f"     ✓ [MSA] {Path(p).name}")
            except Exception as exc:
                logger.error("MSA error: %s", exc)
                advanced["msa"] = {"error": str(exc), "plots": []}

        # ── FMEA ──────────────────────────────────────────────────────────────
        if all(kw in msa_cols for kw in ("severity", "occurrence", "detection")):
            log_stage("Running FMEA (RPN Analysis)")
            try:
                from sigmaflow.analysis.fmea_analysis import FMEAAnalyzer
                sev_col = next(c for c in df.columns if c.lower() == "severity")
                occ_col = next(c for c in df.columns if c.lower() == "occurrence")
                det_col = next(c for c in df.columns if c.lower() == "detection")
                fm_col  = next((c for c in df.columns if "failure" in c.lower()), sev_col)
                fmea    = FMEAAnalyzer(df, fm_col, sev_col, occ_col, det_col)
                res     = fmea.run()
                plots   = fmea.generate_plots(fig_subdir)
                advanced["fmea"] = {**res, "plots": plots}
                for p in plots:
                    print(f"     ✓ [FMEA] {Path(p).name}")
            except Exception as exc:
                logger.error("FMEA error: %s", exc)
                advanced["fmea"] = {"error": str(exc), "plots": []}

        # ── Regression ────────────────────────────────────────────────────────
        num_df = df.select_dtypes(include="number")
        if num_df.shape[1] >= 3:
            log_stage("Running regression analysis")
            try:
                from sigmaflow.analysis.regression_analysis import RegressionAnalyzer
                ra    = RegressionAnalyzer(df)
                res   = ra.run()
                plots = ra.generate_plots(fig_subdir) if "error" not in res else []
                advanced["regression"] = {**res, "plots": plots}
                for p in plots:
                    print(f"     ✓ [REG] {Path(p).name}")
            except Exception as exc:
                logger.error("Regression error: %s", exc)
                advanced["regression"] = {"error": str(exc), "plots": []}

        # ── DOE ───────────────────────────────────────────────────────────────
        cat_cols = [c for c in df.columns if df[c].dtype in ("object", "category")
                    or (df[c].nunique() <= 6 and df[c].nunique() >= 2)]
        num_cols = [c for c in num_df.columns]
        if len(cat_cols) >= 1 and len(num_cols) >= 1:
            log_stage("Running DOE (ANOVA)")
            try:
                from sigmaflow.analysis.doe_analysis import DOEAnalyzer
                doe   = DOEAnalyzer(df, factor_cols=cat_cols[:3])
                res   = doe.run()
                plots = doe.generate_plots(fig_subdir) if "error" not in res else []
                advanced["doe"] = {**res, "plots": plots}
                for p in plots:
                    print(f"     ✓ [DOE] {Path(p).name}")
            except Exception as exc:
                logger.error("DOE error: %s", exc)
                advanced["doe"] = {"error": str(exc), "plots": []}

        return advanced

    # ── Advanced SPC charts ───────────────────────────────────────────────────

    def _run_advanced_spc(self, df: pd.DataFrame, fig_subdir: Path) -> List[str]:
        """Generate CUSUM, EWMA, and X-bar/R charts for time-series data."""
        plots = []
        num_cols = df.select_dtypes(include="number").columns
        if len(num_cols) == 0:
            return plots

        primary = str(num_cols[0])
        series  = df[primary].dropna()

        if len(series) < 8:
            return plots

        try:
            from sigmaflow.visualization.cusum_chart import plot_cusum_chart
            p = plot_cusum_chart(series, fig_subdir / "cusum_chart.png",
                                 col_name=primary, title=f"CUSUM Chart — {primary}")
            plots.append(p)
            print(f"     ✓ [SPC] cusum_chart.png")
        except Exception as exc:
            logger.error("CUSUM error: %s", exc)

        try:
            from sigmaflow.visualization.ewma_chart import plot_ewma_chart
            p = plot_ewma_chart(series, fig_subdir / "ewma_chart.png",
                                col_name=primary, title=f"EWMA Chart — {primary}")
            plots.append(p)
            print(f"     ✓ [SPC] ewma_chart.png")
        except Exception as exc:
            logger.error("EWMA error: %s", exc)

        # X-bar/R only if enough data
        if len(series) >= 25:
            try:
                from sigmaflow.visualization.xbar_r_chart import plot_xbar_r_chart
                p = plot_xbar_r_chart(series, fig_subdir / "xbar_r_chart.png", n=5,
                                      title=f"X-bar & R Chart — {primary}")
                plots.append(p)
                print(f"     ✓ [SPC] xbar_r_chart.png")
            except Exception as exc:
                logger.error("X-bar/R error: %s", exc)

        return plots

    # ── Root Cause ────────────────────────────────────────────────────────────

    def _run_root_cause(self, df, stem, fig_subdir):
        from sigmaflow.analysis.root_cause_analysis import RootCauseAnalyzer
        from sigmaflow.visualization.correlation_heatmap import (
            plot_correlation_heatmap, plot_variable_importance,
        )
        rca    = RootCauseAnalyzer(df)
        result = rca.run()
        plots  = []
        if "error" in result:
            return result, plots
        target = result.get("target_col", "")
        plots.append(plot_correlation_heatmap(
            df, fig_subdir / "correlation_heatmap.png",
            target_col=target, title=f"Correlation Matrix — {stem}",
        ))
        ranked = result.get("ranked_variables", [])
        if ranked:
            plots.append(plot_variable_importance(
                ranked, target, fig_subdir / "variable_importance.png",
            ))
        return result, plots

    # ── Abstract ──────────────────────────────────────────────────────────────

    def _generate_abstract(self, result: Dict[str, Any]) -> str:
        name  = result.get("name", "unknown")
        dtype = result.get("dataset_type", "unknown").upper()
        shape = result.get("shape")
        rows, cols = (shape[0], shape[1]) if shape else ("?", "?")

        structured = result.get("structured_insights", [])
        n_crit = sum(1 for s in structured if s.get("severity") == "critical")
        n_warn = sum(1 for s in structured if s.get("severity") == "warning")

        anomaly_note = (
            f" {n_crit + n_warn} statistical anomaly(ies) detected ({n_crit} critical, {n_warn} warnings)."
            if (n_crit + n_warn) else " No anomalies detected."
        )

        cap = result.get("analysis", {}).get("capability", {})
        cpk = cap.get("Cpk")
        cap_note = ""
        if cpk is not None:
            if cpk >= 1.67:   cap_note = f" Excellent capability (Cpk={cpk:.3f})."
            elif cpk >= 1.33: cap_note = f" Acceptable capability (Cpk={cpk:.3f})."
            elif cpk >= 1.00: cap_note = f" Marginal capability (Cpk={cpk:.3f})."
            else:             cap_note = f" Process NOT CAPABLE (Cpk={cpk:.3f}) — action required."

        adv = result.get("advanced", {})
        adv_note = ""
        if adv.get("msa"):
            pct = adv["msa"].get("percent_contribution", {}).get("pct_GRR")
            if pct is not None:
                adv_note += f" Gauge R&R: {pct:.1f}% of variation."
        if adv.get("fmea"):
            n_crit_f = adv["fmea"].get("n_critical", 0)
            if n_crit_f:
                adv_note += f" FMEA: {n_crit_f} critical failure mode(s) identified."
        if adv.get("regression"):
            r2 = adv["regression"].get("r2")
            if r2 is not None:
                adv_note += f" Regression R²={r2:.3f}."

        # Normality summary
        norm = result.get("statistics", {}).get("normality", {})
        norm_verdicts = [v.get("overall_verdict", "") for v in norm.values() if isinstance(v, dict)]
        non_normal = [v for v in norm_verdicts if "Non-Normal" in v]
        if non_normal:
            adv_note += f" {len(non_normal)} column(s) flagged as non-normal."

        return (
            f"Automated {dtype} analysis of '{name}' ({rows} observations, {cols} variables) "
            f"by SigmaFlow v10.{anomaly_note}{cap_note}{adv_note}"
        )

    # ── Dashboard ─────────────────────────────────────────────────────────────

    def _generate_dashboard(self) -> str:
        from sigmaflow.report.html_dashboard import HTMLDashboardGenerator
        gen  = HTMLDashboardGenerator(self._results, output_dir=self.dashboard_dir)
        path = gen.generate()
        logger.info("HTML dashboard: %s", path)
        return path

    # ── Insights export ───────────────────────────────────────────────────────

    def _export_insights(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        out    = self.output_dir / "insights.json"
        export = []
        for r in self._results:
            rca = r.get("root_cause", {})
            rca_ins = []
            for v in rca.get("ranked_variables", [])[:10]:
                if abs(v.get("pearson_r", 0)) >= 0.30:
                    rca_ins.append({
                        "rule": "root_cause_correlation",
                        "description": f"'{v['variable']}' correlates with '{rca.get('target_col','?')}' (r={v['pearson_r']:+.3f})",
                        "meaning": f"Strength: {v['strength']}",
                        "recommendation": "Investigate this variable as a potential process driver.",
                        "severity": "warning" if abs(v["pearson_r"]) >= 0.5 else "info",
                    })

            # Include advanced analysis summaries in insights
            adv_ins = []
            adv = r.get("advanced", {})
            if adv.get("fmea", {}).get("ranked_modes"):
                top = adv["fmea"]["ranked_modes"][0]
                adv_ins.append({
                    "rule": "fmea_top_risk",
                    "description": f"FMEA top risk: '{top['failure_mode']}' (RPN={top['rpn']})",
                    "meaning": f"S={top['severity']}, O={top['occurrence']}, D={top['detection']}",
                    "recommendation": top.get("recommendation", ""),
                    "severity": "critical" if top["rpn"] > 200 else "warning",
                })
            if adv.get("regression", {}).get("significant_vars"):
                sig = adv["regression"]["significant_vars"]
                adv_ins.append({
                    "rule": "regression_significant_predictors",
                    "description": f"Significant regression predictors: {', '.join(sig)}",
                    "meaning": f"R²={adv['regression'].get('r2', '?')}",
                    "recommendation": "Monitor and control these variables.",
                    "severity": "info",
                })

            export.append({
                "dataset":   r["name"],
                "type":      r["dataset_type"],
                "abstract":  r.get("abstract", ""),
                "insights":  r.get("structured_insights", []),
                "root_cause": rca_ins,
                "advanced":  adv_ins,
                "summary":   r.get("insights", []),
            })
        out.write_text(json.dumps(export, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        logger.info("insights.json saved: %s", out)


def _load(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        for sep in (",", ";", "\t"):
            try:
                df = pd.read_csv(path, sep=sep)
                if df.shape[1] > 1:
                    return df
            except Exception:
                continue
        return pd.read_csv(path)
    return pd.read_excel(path)
