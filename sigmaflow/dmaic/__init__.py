"""
sigmaflow.dmaic
===============
DMAIC phase implementations.

Each sub-package contains a ``phase.py`` module with a phase class
that accepts a DataFrame and returns structured deliverables.

Phases
------
define.phase  : DefinePhase  — project charter, SIPOC, CTQ
measure.phase : MeasurePhase — baseline sigma, MSA, normality
analyze.phase : AnalyzePhase — root cause, hypothesis tests, regression
improve.phase : ImprovePhase — DOE, solution design, piloting
control.phase : ControlPhase — control charts, SPC plan, sustainability
"""
