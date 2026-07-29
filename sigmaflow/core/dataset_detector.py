"""
sigmaflow/core/dataset_detector.py
=====================================
Orchestrates the full pipeline:

    input/datasets/  →  load  →  detect  →  analyse  →  plots  →  insights

This module is intentionally thin: all analysis logic lives inside
individual dataset modules. Adding a new dataset type never touches this file.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import pandas as pd

from sigmaflow.core.dataset_registry import DatasetRegistry

logger = logging.getLogger(__name__)

_SUPPORTED_EXT = {".csv", ".xlsx", ".xls"}


class DatasetDetectionEngine:
    """
    Scans an input folder, detects the dataset type of each file, and
    runs the full analysis pipeline.

    Parameters
    ----------
    input_dir : str | Path
        Folder containing the input dataset files.
    output_plots_dir : str | Path
        Where plot images are saved.
    registry : DatasetRegistry, optional
        Pre-built registry. A new one will be created and discovered if
        not provided.
    """

    def __init__(
        self,
        input_dir: str | Path = "input/datasets",
        output_plots_dir: str | Path = "output/plots",
        registry: Optional[DatasetRegistry] = None,
    ) -> None:
        self.input_dir = Path(input_dir)
        self.plots_dir = Path(output_plots_dir)
        self.registry  = registry or DatasetRegistry().discover()
        self._results: List[Dict[str, Any]] = []

    # ── Public API ───────────────────────────────────────────────────────────

    def run(self) -> List[Dict[str, Any]]:
        """
        Process every supported file in *input_dir*.

        Returns
        -------
        list[dict]
            One result dict per file, containing keys:
            ``file``, ``dataset_type``, ``shape``, ``analysis``,
            ``plots``, ``insights``, ``elapsed_s``, ``errors``.
        """
        files = self._scan()
        if not files:
            logger.warning("No supported files found in '%s'", self.input_dir)
            print(f"\n  No files found in '{self.input_dir}'.\n"
                  f"  Place .csv or .xlsx files there and re-run.\n")
            return []

        logger.info("Found %d file(s) — starting pipeline.", len(files))
        self._results = []

        for path in files:
            result = self._process_file(path)
            self._results.append(result)

        logger.info("Pipeline complete. Processed %d file(s).", len(self._results))
        return self._results

    @property
    def results(self) -> List[Dict[str, Any]]:
        return self._results

    # ── File scanning ────────────────────────────────────────────────────────

    def _scan(self) -> List[Path]:
        if not self.input_dir.exists():
            self.input_dir.mkdir(parents=True, exist_ok=True)
        return sorted(
            p for p in self.input_dir.iterdir()
            if p.suffix.lower() in _SUPPORTED_EXT and not p.name.startswith("~")
        )

    # ── Single-file pipeline ─────────────────────────────────────────────────

    def _process_file(self, path: Path) -> Dict[str, Any]:
        logger.info("─" * 50)
        logger.info("Processing: %s", path.name)
        t0 = time.time()
        result: Dict[str, Any] = {
            "file":         str(path),
            "name":         path.stem,
            "dataset_type": "unknown",
            "shape":        None,
            "analysis":     {},
            "plots":        [],
            "insights":     [],
            "elapsed_s":    0.0,
            "errors":       {},
        }

        # 1. Load ─────────────────────────────────────────────────────────────
        try:
            df = _load(path)
            result["shape"] = df.shape
            logger.info("  Loaded  (%d rows × %d cols)", *df.shape)
        except Exception as exc:
            logger.error("  Load failed: %s", exc)
            result["errors"]["load"] = str(exc)
            return result

        # 2. Detect ───────────────────────────────────────────────────────────
        analyzer = self.registry.match(df)
        if analyzer is None:
            logger.warning("  No matching analyzer found — skipping.")
            result["errors"]["detect"] = "No analyzer matched this dataset."
            return result

        result["dataset_type"] = analyzer.name
        logger.info("  Detected type: %s", analyzer.name.upper())
        print(f"\n  📂 {path.name}")
        print(f"     Type: {analyzer.name.upper()}  |  "
              f"Shape: {df.shape[0]} × {df.shape[1]}")

        # 3. Analysis ─────────────────────────────────────────────────────────
        try:
            result["analysis"] = analyzer.run_analysis(df)
            logger.info("  Analysis complete.")
        except Exception as exc:
            logger.error("  Analysis error: %s", exc)
            result["errors"]["analysis"] = str(exc)

        # 4. Plots ────────────────────────────────────────────────────────────
        plot_subdir = self.plots_dir / path.stem
        try:
            result["plots"] = analyzer.generate_plots(df, plot_subdir)
            for p in result["plots"]:
                print(f"     ✓ {Path(p).name}")
        except Exception as exc:
            logger.error("  Plot error: %s", exc)
            result["errors"]["plots"] = str(exc)

        # 5. Insights ─────────────────────────────────────────────────────────
        try:
            result["insights"] = analyzer.generate_insights(df)
        except Exception as exc:
            logger.error("  Insights error: %s", exc)
            result["errors"]["insights"] = str(exc)

        result["elapsed_s"] = round(time.time() - t0, 2)
        return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load(path: Path) -> pd.DataFrame:
    """Load CSV or Excel into a DataFrame."""
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
