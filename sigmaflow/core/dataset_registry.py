"""
sigmaflow/core/dataset_registry.py
====================================
Auto-discovery registry for dataset analyzers.

Uses the standard library (pkgutil, importlib, inspect) to scan
``sigmaflow/datasets/`` and register every class that:
    - Is defined in that package
    - Inherits from BaseDataset
    - Is NOT BaseDataset itself (not abstract)

Adding a new analyzer type requires ZERO changes to this file —
just drop a new ``*_dataset.py`` file in ``sigmaflow/datasets/``.

Usage
-----
    from sigmaflow.core.dataset_registry import DatasetRegistry

    registry = DatasetRegistry()
    registry.discover()

    for cls in registry.all():
        print(cls.name)

    best = registry.match(df)   # returns the best analyzer instance
"""
from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import List, Optional, Type

import pandas as pd

logger = logging.getLogger(__name__)


class DatasetRegistry:
    """
    Maintains the catalog of all available dataset analyzers.

    The registry is populated lazily: ``discover()`` must be called once
    before ``match()`` or ``all()`` can be used.
    """

    def __init__(self) -> None:
        self._registry: List[Type] = []
        self._discovered: bool = False

    # ── Public API ───────────────────────────────────────────────────────────

    def discover(self) -> "DatasetRegistry":
        """
        Scan ``sigmaflow.datasets`` and auto-register every concrete
        subclass of ``BaseDataset``.

        Returns self for fluent chaining:
            registry = DatasetRegistry().discover()
        """
        from sigmaflow.datasets.base_dataset import BaseDataset
        import sigmaflow.datasets as pkg

        pkg_path = pkg.__path__
        pkg_name = pkg.__name__

        logger.info("Auto-discovering dataset analyzers in '%s'", pkg_name)

        found: List[Type] = []

        for finder, module_name, is_pkg in pkgutil.iter_modules(pkg_path):
            full_name = f"{pkg_name}.{module_name}"
            try:
                module = importlib.import_module(full_name)
            except Exception as exc:
                logger.warning("Could not import '%s': %s", full_name, exc)
                continue

            for attr_name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, BaseDataset)
                    and obj is not BaseDataset
                    and obj.__module__ == full_name   # defined here, not imported
                ):
                    found.append(obj)
                    logger.debug("  ✓ Registered: %s (name='%s', priority=%d)",
                                 obj.__name__, obj.name, obj.priority)

        # Sort by descending priority so high-priority analyzers are tried first
        self._registry = sorted(found, key=lambda c: -c.priority)
        self._discovered = True
        logger.info("Registry: %d analyzer(s) discovered.", len(self._registry))
        return self

    def all(self) -> List[Type]:
        """Return all registered analyzer classes, ordered by priority."""
        self._ensure_discovered()
        return list(self._registry)

    def get(self, name: str) -> Optional[Type]:
        """Return the analyzer class with the given ``name``, or None."""
        self._ensure_discovered()
        for cls in self._registry:
            if cls.name == name:
                return cls
        return None

    def match(self, df: pd.DataFrame) -> Optional[object]:
        """
        Instantiate and return the first (highest-priority) analyzer whose
        ``detect(df)`` returns True.

        Returns None if no analyzer matches.
        """
        self._ensure_discovered()
        for cls in self._registry:
            try:
                instance = cls()
                if instance.detect(df):
                    logger.info("Matched analyzer: '%s'", cls.name)
                    return instance
            except Exception as exc:
                logger.warning("Error during detect() for '%s': %s", cls.name, exc)
        logger.warning("No analyzer matched — returning None.")
        return None

    def summary(self) -> str:
        """Human-readable summary of registered analyzers."""
        self._ensure_discovered()
        lines = [f"DatasetRegistry — {len(self._registry)} analyzer(s):"]
        for cls in self._registry:
            lines.append(f"  [{cls.priority:>3}] {cls.name:<20} {cls.description}")
        return "\n".join(lines)

    # ── Internal ─────────────────────────────────────────────────────────────

    def _ensure_discovered(self) -> None:
        if not self._discovered:
            self.discover()
