"""
sigmaflow/report/latex_engine.py
==================================
Motor principal de geracao de relatorios LaTeX consolidado.

Orquestra:
  1. SectionBuilder  -> constroi contextos
  2. TemplateRenderer -> renderiza Jinja2 templates
  3. Compilacao via pdflatex (2 passes)

Gera UM UNICO relatorio PDF consolidado com todos os datasets analisados.

Uso:
    from sigmaflow.report.latex_engine import LatexEngine

    pdf = LatexEngine(
        all_results   = engine.run(),
        output_dir    = "output/reports/relatorio_final",
        organization  = "Engenharia de Qualidade",
    ).generate()
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .template_renderer  import TemplateRenderer
from .section_builder    import SectionBuilder
from .interpretation_engine import InterpretationEngine, _fmt, _tex

logger = logging.getLogger(__name__)


class LatexEngine:
    """
    Gera um unico relatorio LaTeX/PDF consolidado com todos os datasets.

    Parameters
    ----------
    all_results : list[dict]
        Lista de resultados de Engine.run() (um dict por dataset).
    output_dir : str | Path
    organization : str
    title : str, optional
    compile_pdf : bool
    """

    def __init__(
        self,
        all_results:  List[Dict[str, Any]],
        output_dir:   str | Path           = "output/reports/relatorio_final",
        organization: str                  = "",
        title:        Optional[str]        = None,
        compile_pdf:  bool                 = True,
    ) -> None:
        self.all_results = all_results
        self.output_dir  = Path(output_dir)
        self.org         = organization
        self.title       = title
        self.compile_pdf = compile_pdf

    # ── API publica ───────────────────────────────────────────────────────────

    def generate(self) -> str:
        n         = len(self.all_results)
        names_str = ", ".join(r.get("name", "?") for r in self.all_results[:3])
        if n > 3:
            names_str += f" (+{n-3} mais)"

        logger.info("Gerando relatorio consolidado: %d dataset(s)", n)

        renderer = TemplateRenderer(self.output_dir)

        # Copiar todas as figuras de todos os datasets
        all_plots = []
        for r in self.all_results:
            all_plots.extend(r.get("plots", []))
        renderer.copy_figures(all_plots)

        # Construir contextos por dataset e consolidar
        merged = self._merge_results()

        sb = SectionBuilder(
            merged,
            dataset_name = names_str,
            organization = self.org or "SigmaFlow v10",
            dataset_type = "consolidado",
        )

        contexts = sb.build_all()

        # Injetar lista de todos os datasets na secao de dataset
        contexts["dataset"]["dataset"]["all_datasets"] = [
            {
                "name":    _tex(r.get("name", "?")),
                "type":    _tex(r.get("dataset_type", "?").upper()),
                "n_rows":  (r.get("shape") or (0, 0))[0],
                "n_cols":  (r.get("shape") or (0, 0))[1],
                "elapsed": _fmt(r.get("elapsed_s", 0), 2),
            }
            for r in self.all_results
        ]

        # Renderizar todos os templates
        renderer.render_all(contexts)

        logger.info("Templates renderizados em: %s", self.output_dir)

        tex_path = self.output_dir / "main.tex"
        pdf_path = tex_path.with_suffix(".pdf")

        if self.compile_pdf:
            if self._compile(tex_path, pdf_path):
                logger.info("PDF gerado: %s", pdf_path)
                print(f"\n  PDF consolidado: {pdf_path}")
                return str(pdf_path)
            print(f"\n  LaTeX montado -- compile com:")
            print(f"      cd {self.output_dir} && pdflatex main.tex")

        return str(tex_path)

    # ── Merge de resultados ───────────────────────────────────────────────────

    def _merge_results(self) -> Dict[str, Any]:
        """Consolida a lista de resultados num unico dict DMAICEngine-compativel."""
        if not self.all_results:
            return {}

        total_rows = sum(
            (r.get("shape") or (0, 0))[0] for r in self.all_results
        )
        total_cols = sum(
            (r.get("shape") or (0, 0))[1] for r in self.all_results
        )
        elapsed    = sum(r.get("elapsed_s", 0) for r in self.all_results)

        # Agregar todas as insights
        all_insights = []
        for r in self.all_results:
            all_insights.extend(r.get("structured_insights", []))

        # Capacidade: usar o pior Cpk entre os datasets (mais conservador)
        cap_list = [
            r.get("analysis", {}).get("capability", {})
            for r in self.all_results
            if r.get("analysis", {}).get("capability", {}).get("Cpk") is not None
        ]
        worst_cap = {}
        if cap_list:
            worst_cap = min(cap_list, key=lambda c: c.get("Cpk", 999))

        # Normalidade: agregar todos os resultados
        merged_norm = {}
        for r in self.all_results:
            norm = r.get("statistics", {}).get("normality", {})
            if isinstance(norm, dict):
                merged_norm.update(norm)

        # RCA: usar o mais rico (mais variaveis ranqueadas)
        best_rca = {}
        for r in self.all_results:
            rca = r.get("root_cause", {})
            if len(rca.get("ranked_variables", [])) > len(best_rca.get("ranked_variables", [])):
                best_rca = rca

        # Regressao melhor
        best_reg = {}
        for r in self.all_results:
            reg = r.get("advanced", {}).get("regression", {})
            if reg.get("r_squared", 0) > best_reg.get("r_squared", 0):
                best_reg = reg

        # Todos os plots
        all_plots = []
        for r in self.all_results:
            all_plots.extend(r.get("plots", []))

        # Informacoes consolidadas de hipotese
        merged_hyp = {}
        for r in self.all_results:
            hyp = r.get("statistics", {}).get("hypothesis_tests", {})
            if isinstance(hyp, dict):
                merged_hyp.update(hyp)

        # Identificar dataset principal (mais rico em dados)
        primary = max(
            self.all_results,
            key=lambda r: (r.get("shape") or (0, 0))[0]
        )
        primary_rca    = primary.get("root_cause", {})
        primary_target = primary_rca.get("target_col", "")

        # Aggregate detection results from all datasets
        all_problems: list = []
        seen_p: set = set()
        for r in self.all_results:
            for p in r.get("detection", {}).get("problems", []):
                if p not in seen_p:
                    seen_p.add(p)
                    all_problems.append(p)

        merged_confidence: dict = {}
        merged_rationale: dict  = {}
        merged_plan: dict       = {}
        for r in self.all_results:
            det = r.get("detection", {})
            merged_confidence.update(det.get("confidence", {}))
            merged_rationale.update(det.get("rationale", {}))
            for phase, tokens in r.get("analysis_plan", {}).items():
                if phase not in merged_plan:
                    merged_plan[phase] = []
                for t in tokens:
                    if t not in merged_plan[phase]:
                        merged_plan[phase].append(t)

        merged_detection = {
            "problems":          all_problems,
            "primary_problem":   all_problems[0] if all_problems else "exploratory",
            "response_variable": primary_target,
            "feature_variables": [
                v["variable"]
                for v in best_rca.get("ranked_variables", [])
            ],
            "confidence":  merged_confidence,
            "rationale":   merged_rationale,
            "metadata_snapshot": {
                "n_rows":  total_rows,
                "n_num":   len([v["variable"] for v in best_rca.get("ranked_variables", [])]),
                "n_cat":   0,
                "has_time": any(r.get("detection", {}).get("metadata_snapshot", {}).get("has_time")
                                for r in self.all_results),
                "has_spec": any(r.get("detection", {}).get("metadata_snapshot", {}).get("has_spec")
                                for r in self.all_results),
            },
        }

        # ── Merge InsightEngine results ──────────────────────────────────────
        all_ai: list = []
        for r in self.all_results:
            all_ai.extend(r.get("analysis_insights", []))

        # Consolidate executive summary + risk from worst dataset
        risk_order = {"critical": 0, "warning": 1, "info": 2}
        worst = sorted(
            self.all_results,
            key=lambda r: risk_order.get(r.get("risk_level", "info"), 2)
        )
        worst_result = worst[0] if worst else {}

        merged_exec_summary  = worst_result.get("executive_summary", "")
        merged_risk_level    = worst_result.get("risk_level", "info")
        merged_risk_label    = worst_result.get("risk_label", r"BAIXO")
        merged_risk_color    = worst_result.get("risk_color", "corInfo")

        # Merge all recommendations, dedup by action text
        all_recs: list = []
        seen_actions: set = set()
        for r in sorted(self.all_results,
                        key=lambda r: risk_order.get(r.get("risk_level","info"),2)):
            for rec in r.get("recommendations", []):
                key = rec.get("action", "")[:60]
                if key not in seen_actions:
                    seen_actions.add(key)
                    all_recs.append(rec)

        # Re-number priorities
        for i, rec in enumerate(all_recs, 1):
            rec["priority"] = i

        return {
            "detection":          merged_detection,
            "analysis_plan":      merged_plan,
            "analysis_insights":  all_ai,
            "executive_summary":  merged_exec_summary,
            "recommendations":    all_recs,
            "risk_level":         merged_risk_level,
            "risk_label":         merged_risk_label,
            "risk_color":         merged_risk_color,
            "metadata": {
                "n_rows":             total_rows,
                "n_columns":          total_cols,
                "primary_target":     primary_target,
                "numeric_columns":    [
                    v["variable"]
                    for v in best_rca.get("ranked_variables", [])
                ],
                "categorical_columns": [],
                "missing_pct":        0.0,
                "dataset_type":       "consolidado",
            },
            "measure": {
                "capability":  worst_cap,
                "normality":   merged_norm,
                "descriptive": {
                    k: v
                    for r in self.all_results
                    for k, v in r.get("analysis", {}).items()
                    if isinstance(v, (int, float))
                },
            },
            "analyze": {
                "root_cause":       best_rca,
                "hypothesis_tests": merged_hyp,
                "regression":       best_reg,
                "doe":              next(
                    (r.get("advanced", {}).get("doe", {})
                     for r in self.all_results
                     if r.get("advanced", {}).get("doe")),
                    {}
                ),
            },
            "improve":  {"recommendations": {"recommendations": []}},
            "control":  {},
            "define":   {},
            "summary": {
                "all_insights": [
                    ins.get("description", str(ins))
                    if isinstance(ins, dict) else str(ins)
                    for ins in all_insights
                ],
                "n_insights":  len(all_insights),
                "phases_run":  ["define", "measure", "analyze", "improve", "control"],
            },
            "plots":               all_plots,
            "elapsed_s":           elapsed,
            "structured_insights": all_insights,
        }

    # ── Compilacao ────────────────────────────────────────────────────────────

    def _compile(self, tex_path: Path, pdf_path: Path) -> bool:
        if not shutil.which("pdflatex"):
            logger.warning("pdflatex nao encontrado no PATH.")
            return False
        try:
            compile_dir = tex_path.parent
            # Limpar arquivos auxiliares anteriores
            for ext in (".out", ".aux", ".toc", ".log"):
                aux = compile_dir / (tex_path.stem + ext)
                if aux.exists():
                    aux.unlink()
            # Dois passes para resolver referencias e sumario
            for pass_n in range(1, 3):
                logger.info("pdflatex passo %d/2...", pass_n)
                proc = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", tex_path.name],
                    cwd=str(compile_dir),
                    capture_output=True,
                    encoding="latin-1", errors="replace",
                    timeout=300,
                )
            if pdf_path.exists():
                return True
            # Log de erros
            for line in (proc.stdout + proc.stderr).splitlines():
                if any(k in line for k in ("Error", "!", "Fatal")):
                    logger.error("LaTeX: %s", line)
        except Exception as exc:
            logger.error("Erro na compilacao: %s", exc)
        return False
