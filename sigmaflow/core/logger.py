"""
sigmaflow/core/logger.py
=========================
Structured logging system for SigmaFlow v8.

Features
--------
- Console handler   : colored, human-readable output
- File handler      : timestamped log files saved to output/logs/
- Named loggers     : each module gets its own logger namespace
- Stage markers     : pipeline steps are clearly labeled

Usage
-----
    from sigmaflow.core.logger import setup_logging, get_logger

    # Call once at startup (in main.py or cli.py)
    setup_logging(log_dir="output/logs", level="INFO")

    # In each module
    logger = get_logger(__name__)
    logger.info("Running SPC analysis")
    logger.warning("Fewer than 30 observations — results may be unreliable")
    logger.error("Analysis failed: %s", exc)

Pipeline stage logging
----------------------
    from sigmaflow.core.logger import log_stage

    log_stage("Loading dataset")         →  [STAGE] ── Loading dataset ──
    log_stage("Generating visualizations")
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Log format strings ────────────────────────────────────────────────────────

_CONSOLE_FMT = "%(asctime)s  %(levelname)-8s  %(name)-30s  %(message)s"
_FILE_FMT    = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"
_DATE_FMT    = "%H:%M:%S"
_FILE_DATE   = "%Y%m%d_%H%M%S"

# Module-level reference to the root sigmaflow logger
_root_logger: Optional[logging.Logger] = None


def setup_logging(
    log_dir: Optional[str | Path] = None,
    level: str = "INFO",
    quiet: bool = False,
) -> logging.Logger:
    """
    Configure the SigmaFlow logging system.

    Call this ONCE at application startup before any module imports
    that use ``get_logger()``.

    Parameters
    ----------
    log_dir : str | Path, optional
        Directory where log files are saved.
        Example: "output/logs". If None, no file handler is created.
    level : str
        Log level for console output: "DEBUG", "INFO", "WARNING", "ERROR".
    quiet : bool
        If True, suppress console output (file logging still active).

    Returns
    -------
    logging.Logger
        The configured root SigmaFlow logger.
    """
    global _root_logger

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger("sigmaflow")
    root.setLevel(logging.DEBUG)  # Capture everything; handlers filter

    # Remove existing handlers to avoid duplicate messages on re-init
    root.handlers.clear()

    # ── Console handler ───────────────────────────────────────────────────────
    if not quiet:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(numeric_level)
        console.setFormatter(logging.Formatter(_CONSOLE_FMT, datefmt=_DATE_FMT))
        root.addHandler(console)

    # ── File handler ──────────────────────────────────────────────────────────
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        timestamp  = datetime.now().strftime(_FILE_DATE)
        log_file   = log_path / f"sigmaflow_{timestamp}.log"

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_handler.setFormatter(logging.Formatter(_FILE_FMT, datefmt="%Y-%m-%d %H:%M:%S"))
        root.addHandler(file_handler)
        root.info("Logging to file: %s", log_file)

    _root_logger = root
    return root


def get_logger(name: str) -> logging.Logger:
    """
    Return a child logger under the 'sigmaflow' namespace.

    Parameters
    ----------
    name : str
        Typically ``__name__`` of the calling module.
        Dots in the name create a hierarchy:
        "sigmaflow.core.engine" → child of "sigmaflow.core".

    Returns
    -------
    logging.Logger
    """
    # Ensure the root logger is set up with at least console output
    if not logging.getLogger("sigmaflow").handlers:
        setup_logging()
    return logging.getLogger(name)


def log_stage(stage_name: str, logger: Optional[logging.Logger] = None) -> None:
    """
    Log a pipeline stage marker — visually separates pipeline steps.

    Output example:
        [INFO]  ── Loading dataset ──────────────────────────

    Parameters
    ----------
    stage_name : str
        Human-readable name of the pipeline stage.
    logger : logging.Logger, optional
        Logger to use. Defaults to the root sigmaflow logger.
    """
    lg = logger or logging.getLogger("sigmaflow")
    separator = "─" * max(0, 50 - len(stage_name))
    lg.info("── %s %s", stage_name, separator)
