"""
sigmaflow/report/
==================
Sistema de geracao de relatorios LaTeX/PDF academicos (padrao ABNT + DMAIC).

Arquitetura:
  latex_engine.py        -- motor principal, gera PDF consolidado
  section_builder.py     -- constroi contextos Jinja2 por secao
  interpretation_engine.py -- gera interpretacoes textuais automaticas
  template_renderer.py   -- renderiza templates Jinja2 para .tex

Uso rapido:
    from sigmaflow.report import LatexEngine

    pdf = LatexEngine(
        all_results   = engine_results,
        output_dir    = "output/reports/final",
        organization  = "Engenharia de Qualidade",
    ).generate()
"""
from .latex_engine          import LatexEngine
from .interpretation_engine import InterpretationEngine
from .section_builder       import SectionBuilder
from .template_renderer     import TemplateRenderer

__all__ = [
    "LatexEngine",
    "InterpretationEngine",
    "SectionBuilder",
    "TemplateRenderer",
]
