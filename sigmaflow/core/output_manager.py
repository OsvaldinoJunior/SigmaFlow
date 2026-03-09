"""
sigmaflow/core/output_manager.py
=================================
Output directory lifecycle management for SigmaFlow.

Two public functions:

``clear_outputs(base)``
    Wipe every file and sub-directory inside *base*, then recreate the
    standard skeleton.  Used by ``main.py --force``.

``ensure_output_dirs(base)``
    Idempotent: create *base* and all standard sub-directories if they do
    not already exist.  Called on every normal run so the engine never
    crashes on a missing folder.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# Sub-directories the SigmaFlow pipeline writes into.
_SUBDIRS = ("figures", "reports", "dashboard", "logs")


# ── Public API ─────────────────────────────────────────────────────────────────

def clear_outputs(base: str | Path = "output") -> None:
    """Delete all previous outputs and recreate a clean directory skeleton.

    Every child of *base* (both files and sub-directories) is removed so
    the subsequent pipeline run starts from a completely clean state.

    Parameters
    ----------
    base:
        Root output directory, e.g. ``"output"`` (default).

    Notes
    -----
    * If *base* does not exist the function creates it silently.
    * After clearing, the standard sub-directories (``figures/``,
      ``reports/``, ``dashboard/``, ``logs/``) are recreated via
      :func:`ensure_output_dirs`.
    """
    base_path = Path(base)

    if not base_path.exists():
        logger.info("Output directory '%s' not found — will be created.", base_path)
        ensure_output_dirs(base_path)
        return

    logger.info("Clearing output directory: %s", base_path.resolve())

    for child in list(base_path.iterdir()):
        try:
            if child.is_dir():
                shutil.rmtree(child)
                logger.debug("  Removed directory: %s", child.name)
            else:
                child.unlink()
                logger.debug("  Removed file: %s", child.name)
        except Exception as exc:
            logger.warning("  Could not remove '%s': %s", child, exc)

    # Recreate the standard folder skeleton.
    ensure_output_dirs(base_path)
    logger.info("Output directories cleared — starting fresh pipeline run.")


def ensure_output_dirs(base: str | Path = "output") -> None:
    """Ensure *base* and all standard sub-directories exist (idempotent).

    Uses ``mkdir(parents=True, exist_ok=True)`` so existing directories
    are never touched.

    Parameters
    ----------
    base:
        Root output directory.
    """
    base_path = Path(base)
    base_path.mkdir(parents=True, exist_ok=True)

    for sub in _SUBDIRS:
        (base_path / sub).mkdir(parents=True, exist_ok=True)

    logger.debug("Output dirs ensured under '%s': %s", base_path, ", ".join(_SUBDIRS))
