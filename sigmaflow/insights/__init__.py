"""
sigmaflow.insights
==================
Rules engine for generating structured, severity-ranked insights.

The RulesEngine evaluates a set of statistical rules against analysis
results and returns a list of Insight objects, each containing:
  - rule         : unique rule identifier
  - description  : human-readable finding
  - meaning      : statistical interpretation
  - recommendation : suggested action
  - severity     : "info" | "warning" | "critical"

Modules
-------
rules_engine      : Central orchestrator (RulesEngine, Insight)
statistical_rules : Concrete rule implementations (Western Electric, etc.)
"""
