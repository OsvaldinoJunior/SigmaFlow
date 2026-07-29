"""
sigmaflow.insights
==================
Modulo de geracao automatica de insights e recomendacoes.

Modulos
-------
rules_engine          : RulesEngine / Insight — regras Western Electric, Capability, Trend
statistical_rules     : WesternElectricRules, CapabilityRules, TrendRules
insight_engine        : InsightEngine — interpreta cada tipo de analise
recommendation_engine : RecommendationEngine — executive summary e recomendacoes
"""
from sigmaflow.insights.rules_engine          import RulesEngine, Insight          # noqa
from sigmaflow.insights.insight_engine        import InsightEngine, AnalysisInsight # noqa
from sigmaflow.insights.recommendation_engine import RecommendationEngine            # noqa
