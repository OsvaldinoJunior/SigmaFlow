"""
sigmaflow/report/template_engine/
===================================
Sistema de geracao de relatorios LaTeX academicos (padrao ABNT).

Uso:
    from sigmaflow.report.template_engine import LatexEngine

    pdf = LatexEngine(
        all_results   = engine.run(),   # lista completa de resultados
        output_dir    = "output/reports/relatorio_final",
        organization  = "Engenharia de Qualidade",
    ).generate()
"""
from .latex_engine      import LatexEngine
from .template_manager  import TemplateManager
from .section_generator import SectionGenerator

__all__ = ["LatexEngine", "TemplateManager", "SectionGenerator"]
