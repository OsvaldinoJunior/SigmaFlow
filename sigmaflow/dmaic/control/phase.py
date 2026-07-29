"""
sigmaflow/dmaic/control/phase.py
==================================
Control Phase — SigmaFlow DMAIC Engine.

Analyses performed (depending on analysis_list):
    • spc            — X-mR individuals chart with OOC detection
    • time_series    — Trend and autocorrelation analysis
    • cusum          — Cumulative Sum chart
    • ewma           — Exponentially Weighted Moving Average chart
    • control_plan   — Auto-generated process control plan summary
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from sigmaflow.dmaic.base_phase import BasePhase

logger = logging.getLogger(__name__)


class ControlPhase(BasePhase):
    """
    DMAIC Control Phase.

    Establishes ongoing monitoring and control:
    - SPC charts (XmR) to detect process shifts
    - Time-series trend analysis
    - CUSUM and EWMA sensitivity charts
    - Auto-generated control plan with response rules
    """

    phase_name = "control"

    def run(
        self,
        data:          pd.DataFrame,
        analysis_list: List[str],
        metadata:      Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        logger.info("[Control] Starting Control phase (%d analyses)", len(analysis_list))
        m = metadata or {}

        if "spc" in analysis_list:
            self.results["spc"] = self._safe_run("spc", self._spc, data, m)

        if "time_series" in analysis_list:
            self.results["time_series"] = self._safe_run(
                "time_series", self._time_series, data, m
            )

        if "cusum" in analysis_list:
            self.results["cusum"] = self._safe_run("cusum", self._cusum, data, m)

        if "ewma" in analysis_list:
            self.results["ewma"] = self._safe_run("ewma", self._ewma, data, m)

        if "control_plan" in analysis_list:
            self.results["control_plan"] = self._safe_run(
                "control_plan", self._control_plan, data, m
            )

        self._build_insights()
        return self._phase_result()

    # ── Analyses ──────────────────────────────────────────────────────────────

    def _spc(self, df: pd.DataFrame, m: Dict[str, Any]) -> Dict[str, Any]:
        from sigmaflow.analysis.spc_analysis import compute_xmr_chart  # noqa
        target = self._primary_numeric(df, m)
        if not target:
            return {"skipped": True, "reason": "No numeric column found."}

        series = df[target].dropna()
        if len(series) < 5:
            return {"skipped": True, "reason": "Need ≥ 5 data points for XmR chart."}

        result = compute_xmr_chart(series)
        result["target_column"] = target
        return result

    def _time_series(self, df: pd.DataFrame, m: Dict[str, Any]) -> Dict[str, Any]:
        from sigmaflow.analysis.spc_analysis import compute_trend  # noqa
        from scipy import stats as sc  # noqa

        target = self._primary_numeric(df, m)
        if not target:
            return {"skipped": True, "reason": "No numeric column found."}

        series = df[target].dropna().reset_index(drop=True)
        if len(series) < 6:
            return {"skipped": True, "reason": "Need ≥ 6 data points."}

        trend   = compute_trend(series)
        acf_lag1 = float(series.autocorr(lag=1)) if len(series) > 5 else None

        return {
            "target_column":   target,
            "trend":           trend,
            "autocorrelation_lag1": round(acf_lag1, 4) if acf_lag1 else None,
            "n":               int(len(series)),
        }

    def _cusum(self, df: pd.DataFrame, m: Dict[str, Any]) -> Dict[str, Any]:
        """Compute CUSUM statistics (without plotting)."""
        target = self._primary_numeric(df, m)
        if not target:
            return {"skipped": True}
        series = df[target].dropna().values
        if len(series) < 8:
            return {"skipped": True, "reason": "Need ≥ 8 data points."}

        mu     = float(np.mean(series))
        sigma  = float(np.std(series, ddof=1)) or 1.0
        k      = 0.5   # allowance (half the shift size)
        h      = 5.0   # decision interval

        cusum_pos = np.zeros(len(series))
        cusum_neg = np.zeros(len(series))
        for i in range(1, len(series)):
            cusum_pos[i] = max(0, cusum_pos[i-1] + (series[i] - mu) / sigma - k)
            cusum_neg[i] = max(0, cusum_neg[i-1] - (series[i] - mu) / sigma - k)

        ooc_pos = [int(i) for i in range(len(series)) if cusum_pos[i] > h]
        ooc_neg = [int(i) for i in range(len(series)) if cusum_neg[i] > h]

        return {
            "target_column": target,
            "k_allowance":   k,
            "h_threshold":   h,
            "ooc_upper":     ooc_pos,
            "ooc_lower":     ooc_neg,
            "n_ooc":         len(ooc_pos) + len(ooc_neg),
            "in_control":    len(ooc_pos) + len(ooc_neg) == 0,
        }

    def _ewma(self, df: pd.DataFrame, m: Dict[str, Any]) -> Dict[str, Any]:
        """Compute EWMA statistics (without plotting)."""
        target = self._primary_numeric(df, m)
        if not target:
            return {"skipped": True}
        series = df[target].dropna().values
        if len(series) < 8:
            return {"skipped": True, "reason": "Need ≥ 8 data points."}

        lam    = 0.2
        mu     = float(np.mean(series))
        sigma  = float(np.std(series, ddof=1)) or 1.0
        L      = 3.0

        ewma = np.zeros(len(series))
        ewma[0] = series[0]
        for i in range(1, len(series)):
            ewma[i] = lam * series[i] + (1 - lam) * ewma[i-1]

        ucl = mu + L * sigma * np.sqrt(lam / (2 - lam))
        lcl = mu - L * sigma * np.sqrt(lam / (2 - lam))

        ooc = [int(i) for i in range(len(ewma)) if ewma[i] > ucl or ewma[i] < lcl]

        return {
            "target_column": target,
            "lambda":        lam,
            "UCL":           round(ucl, 6),
            "CL":            round(mu, 6),
            "LCL":           round(lcl, 6),
            "ooc_points":    ooc,
            "n_ooc":         len(ooc),
            "in_control":    len(ooc) == 0,
        }

    def _control_plan(
        self,
        df: pd.DataFrame,
        m: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a basic process control plan."""
        num_cols = self._numeric_cols(df, m)
        target   = self._primary_numeric(df, m)

        control_items: List[Dict[str, Any]] = []
        for col in num_cols[:6]:
            s     = df[col].dropna()
            mu    = float(s.mean())
            sigma = float(s.std(ddof=1)) if len(s) > 1 else 0.0
            control_items.append({
                "variable":        col,
                "is_target":       col == target,
                "control_method":  "XmR Chart" if len(s) >= 5 else "Manual Inspection",
                "ucl":             round(mu + 3 * sigma, 4),
                "nominal":         round(mu, 4),
                "lcl":             round(mu - 3 * sigma, 4),
                "measurement_freq":"Every batch / shift",
                "response_rule":   "Stop and investigate if OOC",
            })

        return {
            "control_items":      control_items,
            "n_items":            len(control_items),
            "primary_target":     target,
            "monitoring_method":  "Statistical Process Control (XmR)",
            "review_frequency":   "Weekly trend review",
        }

    # ── Insights ──────────────────────────────────────────────────────────────

    def _build_insights(self) -> None:
        spc = self.results.get("spc") or {}
        n_ooc = spc.get("x_chart", {}).get("n_ooc")
        if n_ooc is not None:
            if n_ooc == 0:
                self.insights.append("✅ SPC: Process is IN CONTROL — no out-of-control points.")
            else:
                self.insights.append(
                    f"🔴 SPC: {n_ooc} out-of-control point(s) detected. "
                    "Investigate special causes."
                )

        ts = self.results.get("time_series") or {}
        trend = (ts.get("trend") or {}).get("direction")
        if trend and trend != "stable":
            self.insights.append(
                f"⚠ Time series: significant {trend.upper()} trend detected. "
                "Process mean is drifting."
            )

        cusum = self.results.get("cusum") or {}
        if not cusum.get("in_control") and cusum.get("n_ooc"):
            self.insights.append(
                f"⚠ CUSUM: {cusum['n_ooc']} signal(s) detected — "
                "process may have shifted."
            )

        cp = self.results.get("control_plan") or {}
        if cp.get("n_items"):
            self.insights.append(
                f"📋 Control plan generated for {cp['n_items']} variable(s). "
                "Implement XmR monitoring to sustain improvements."
            )
