"""
sigmaflow/report/template_engine/latex_engine.py
==================================================
Motor principal — gera UM ÚNICO relatório PDF consolidado com todos os datasets.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .template_manager  import TemplateManager
from .section_generator import SectionGenerator, _e, _fmt

logger = logging.getLogger(__name__)


class LatexEngine:
    def __init__(
        self,
        all_results:  List[Dict[str, Any]],
        output_dir:   str | Path           = "output/reports/relatorio_final",
        organization: str                  = "",
        title:        Optional[str]        = None,
        compile_pdf:  bool                 = True,
    ) -> None:
        self.all_results  = all_results
        self.output_dir   = Path(output_dir)
        self.org          = organization
        self.title        = title
        self.compile_pdf  = compile_pdf

    def generate(self) -> str:
        n        = len(self.all_results)
        names    = ", ".join(r.get("name", "?") for r in self.all_results[:3])
        if n > 3:
            names += f" (+{n-3} mais)"

        date_str = datetime.now().strftime("%d/%m/%Y")
        title    = self.title or f"Relatorio DMAIC Consolidado -- {n} Datasets"

        mgr = TemplateManager(self.output_dir)
        mgr.setup()

        mgr.set("TITLE",        title)
        mgr.set("DATASET",      names)
        mgr.set("ORGANIZATION", self.org or "SigmaFlow v10")
        mgr.set("DATE",         date_str)

        # seção de introdução consolidada
        mgr.set("INTRODUCAO_BODY",  _intro_consolidado(self.all_results))

        # metodologia — usa primeiro dataset
        first_dmaic = _adapt(self.all_results[0])
        first_gen   = SectionGenerator(first_dmaic,
                                       dataset_name=self.all_results[0].get("name","processo"),
                                       organization=self.org)
        mgr.set("METODOLOGIA_BODY", first_gen.metodologia())

        # bloco central: uma \section por dataset
        mgr.set("ALL_DATASETS", _build_datasets_section(self.all_results))

        # discussão e conclusão consolidadas
        mgr.set("DISCUSSAO_BODY", _discussao_consolidada(self.all_results))
        mgr.set("CONCLUSAO_BODY", _conclusao_consolidada(self.all_results))

        # placeholders não usados no template consolidado
        for key in ("ANALISE_BODY", "RESULTADOS_BODY"):
            mgr.set(key, "")

        mgr.apply()

        # copiar todas as figuras de todos os datasets
        all_figures = []
        for r in self.all_results:
            all_figures.extend(r.get("plots", []))
        mgr.finalize_figures(all_figures)

        logger.info("Relatorio consolidado montado em: %s", self.output_dir)

        tex_path = mgr.main_tex_path()
        if self.compile_pdf:
            pdf_path = tex_path.with_suffix(".pdf")
            if self._compile(tex_path, pdf_path):
                logger.info("PDF gerado: %s", pdf_path)
                print(f"\n  PDF consolidado: {pdf_path}\n")
                return str(pdf_path)
            print(f"\n  LaTeX montado -- compile com:")
            print(f"      cd {self.output_dir} && pdflatex main.tex\n")

        return str(tex_path)

    def _compile(self, tex_path: Path, pdf_path: Path) -> bool:
        if not shutil.which("pdflatex"):
            return False
        try:
            compile_dir = tex_path.parent
            stem = tex_path.stem
            # Remove auxiliary files from previous runs to avoid stale data
            for ext in (".out", ".aux", ".toc", ".log"):
                aux = compile_dir / (stem + ext)
                if aux.exists():
                    aux.unlink()
            # Two passes: first builds .aux/.toc, second resolves references
            for _ in range(2):
                proc = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode",
                     tex_path.name],
                    cwd=str(compile_dir),
                    capture_output=True, text=True, timeout=300,
                )
            if pdf_path.exists():
                return True
            for line in (proc.stdout + proc.stderr).splitlines():
                if any(k in line for k in ("Error", "!", "Fatal")):
                    logger.error("LaTeX: %s", line)
        except Exception as exc:
            logger.error("Erro compilacao: %s", exc)
        return False


# ── helpers ───────────────────────────────────────────────────────────────────

def _adapt(result: Dict[str, Any]) -> Dict[str, Any]:
    shape  = result.get("shape") or (0, 0)
    rca    = result.get("root_cause", {})
    ranked = rca.get("ranked_variables", [])
    cap    = result.get("analysis", {}).get("capability", {})
    norm   = result.get("statistics", {}).get("normality", {})
    hyp    = result.get("statistics", {}).get("hypothesis_tests", {})
    ins    = result.get("structured_insights", [])
    return {
        "metadata": {
            "n_rows":             shape[0],
            "n_columns":          shape[1],
            "primary_target":     rca.get("target_col", ""),
            "numeric_columns":    [v["variable"] for v in ranked] if ranked else [],
            "categorical_columns": [],
            "missing_pct":        0.0,
        },
        "measure": {
            "capability":  cap,
            "normality":   norm,
            "descriptive": {k: v for k, v in result.get("analysis", {}).items()
                            if isinstance(v, (int, float))},
        },
        "analyze": {
            "root_cause":       rca,
            "hypothesis_tests": hyp,
            "regression":       result.get("advanced", {}).get("regression", {}),
        },
        "improve":  {"recommendations": {"recommendations": []}},
        "control":  {}, "define": {},
        "summary": {
            "all_insights": [
                i.get("description", str(i)) if isinstance(i, dict) else str(i)
                for i in ins
            ],
            "n_insights":  len(ins),
            "phases_run":  ["define", "measure", "analyze", "improve", "control"],
        },
        "plots":               result.get("plots", []),
        "elapsed_s":           result.get("elapsed_s", 0),
        "structured_insights": ins,
    }


def _e_raw(text: str) -> str:
    """Escapa apenas o necessário sem tocar em acentos já escritos como LaTeX."""
    s = str(text)
    _BS = "\x00BS\x00"
    s = s.replace("\\", _BS)
    for ch, esc in [("&",r"\&"),("%",r"\%"),("$",r"\$"),("#",r"\#"),
                    ("_",r"\_"),("{",r"\{"),("}",r"\}")]:
        s = s.replace(ch, esc)
    s = s.replace(_BS, r"\textbackslash{}")
    s = "".join(c if ord(c) < 128 else "?" for c in s)
    return s


def _intro_consolidado(results: List[Dict[str, Any]]) -> str:
    n       = len(results)
    total_r = sum(r.get("shape",(0,0))[0] for r in results)
    total_c = sum(r.get("shape",(0,0))[1] for r in results)
    types   = sorted({r.get("dataset_type","?").upper() for r in results})
    elapsed = sum(r.get("elapsed_s",0) for r in results)

    rows = "\n".join(
        rf"  {_e_raw(r.get('name','?'))} & "
        rf"{_e_raw(r.get('dataset_type','?').upper())} & "
        rf"{r.get('shape',(0,0))[0]} x {r.get('shape',(0,0))[1]} & "
        rf"{_fmt(r.get('elapsed_s',0),1)}s \\"
        for r in results
    )
    types_str = _e_raw(', '.join(types))

    return rf"""O presente relatorio documenta os resultados de uma analise estatistica
automatizada conduzida pelo sistema \textbf{{SigmaFlow v10}}, aplicando o
\textit{{framework}} DMAIC (\textit{{Define, Measure, Analyze, Improve, Control}})
a \textbf{{{n} conjunto(s) de dados}}. O DMAIC constitui a metodologia estruturada
de resolucao de problemas do Lean Six Sigma, amplamente utilizada em projetos
de melhoria de processos industriais, de servicos e logisticos (Montgomery, 2009).

No total, foram processadas \textbf{{{total_r} observacoes}} distribuidas em
\textbf{{{total_c} variaveis}} ao longo dos datasets analisados, cobrindo os tipos:
{types_str}. Todo o pipeline analitico foi executado em
\textbf{{{_fmt(elapsed,1)} segundos}}.

\begin{{table}}[H]
\caption{{Datasets processados neste relatorio}}
\label{{tab:datasets}}
\centering
\begin{{tabular}}{{p{{5cm}}p{{3cm}}cc}}
\toprule
\textbf{{Dataset}} & \textbf{{Tipo}} & \textbf{{Dimensoes}} & \textbf{{Tempo}} \\
\midrule
{rows}
\bottomrule
\end{{tabular}}
\fonte{{SigmaFlow v10 (analise automatica)}}
\end{{table}}

O objetivo central deste relatorio e caracterizar o desempenho de cada processo
analisado, avaliar sua estabilidade estatistica, estimar os indices de capacidade
e identificar as principais fontes de variacao que impactam negativamente a
qualidade do produto ou servico analisado."""


def _build_datasets_section(results: List[Dict[str, Any]]) -> str:
    blocks = []
    for i, result in enumerate(results, 1):
        name  = result.get("name", f"dataset_{i}")
        dtype = result.get("dataset_type", "unknown").upper()
        shape = result.get("shape") or (0, 0)
        dmaic = _adapt(result)
        gen   = SectionGenerator(dmaic, dataset_name=name)

        analise    = gen.analise_estatistica()
        resultados = gen.resultados()

        block = rf"""
\newpage
\section{{Dataset {i}: {_e_raw(name)}}}

\subsection{{Visao Geral}}

\begin{{description}}[leftmargin=4cm, style=nextline]
  \item[Dataset]    \textbf{{{_e_raw(name)}}}
  \item[Tipo]       \textbf{{{_e_raw(dtype)}}}
  \item[Dimensoes]  {shape[0]} linhas $\times$ {shape[1]} colunas
  \item[Tempo]      {_fmt(result.get('elapsed_s',0),2)} segundos
\end{{description}}

{analise}

{resultados}
"""
        blocks.append(block)
    return "\n".join(blocks)


def _discussao_consolidada(results: List[Dict[str, Any]]) -> str:
    parts = []

    cap_rows = []
    for r in results:
        cap = r.get("analysis", {}).get("capability", {})
        cpk = cap.get("Cpk")
        if cpk is not None:
            if cpk >= 1.67:
                status = r"\textcolor{info}{\textbf{Excelente}}"
            elif cpk >= 1.33:
                status = r"\textcolor{info}{\textbf{Aceitavel}}"
            elif cpk >= 1.00:
                status = r"\textcolor{aviso}{\textbf{Marginal}}"
            else:
                status = r"\textcolor{critico}{\textbf{Incapaz}}"
            dpmo = cap.get("dpmo", 0)
            sig  = cap.get("sigma_level", 0)
            cap_rows.append(
                rf"  {_e_raw(r.get('name','?'))} & {_fmt(cpk,3)} & "
                rf"{f'{dpmo:,.0f}' if dpmo else '---'} & "
                rf"{_fmt(sig,2) if sig else '---'} & {status} \\"
            )

    if cap_rows:
        parts.append(
            r"\subsection{Analise Comparativa de Capacidade}" + "\n\n"
            r"A Tabela~\ref{tab:comparativa} sintetiza os indices de capacidade de todos os"
            " processos analisados.\n\n"
            r"\begin{table}[H]" + "\n"
            r"\caption{Comparacao de capacidade entre os datasets}" + "\n"
            r"\label{tab:comparativa}" + "\n"
            r"\centering" + "\n"
            r"\begin{tabular}{p{5cm}cccc}" + "\n"
            r"\toprule" + "\n"
            r"\textbf{Dataset} & \textbf{$C_{pk}$} & \textbf{DPMO} & "
            r"\textbf{Nivel $\sigma$} & \textbf{Classificacao} \\" + "\n"
            r"\midrule" + "\n" +
            "\n".join(cap_rows) + "\n"
            r"\bottomrule" + "\n"
            r"\end{tabular}" + "\n"
            r"\fonte{SigmaFlow v10}" + "\n"
            r"\end{table}"
        )

    rca_rows = []
    for r in results:
        rca    = r.get("root_cause", {})
        ranked = rca.get("ranked_variables", [])
        target = rca.get("target_col", "")
        if ranked and target:
            top = ranked[0]
            pr  = top.get("pearson_r", 0)
            if abs(pr) >= 0.5:
                color = (r"\textcolor{critico}{\textbf{" if abs(pr) >= 0.7
                         else r"\textcolor{aviso}{\textbf{")
                rca_rows.append(
                    rf"  {_e_raw(r.get('name','?'))} & {_e_raw(target)} & "
                    rf"{_e_raw(top['variable'])} & "
                    rf"{color}{_fmt(pr,3)}}}}} \\"
                )

    if rca_rows:
        parts.append(
            r"\subsection{Indicadores de Causa Raiz Consolidados}" + "\n\n"
            r"As variaveis de maior influencia sobre a qualidade em cada processo"
            " sao sintetizadas na Tabela~\\ref{tab:rca_consolidado}.\n\n"
            r"\begin{table}[H]" + "\n"
            r"\caption{Principais variaveis causais por dataset}" + "\n"
            r"\label{tab:rca_consolidado}" + "\n"
            r"\centering" + "\n"
            r"\begin{tabular}{p{4cm}p{3cm}p{3.5cm}c}" + "\n"
            r"\toprule" + "\n"
            r"\textbf{Dataset} & \textbf{Variavel-alvo} & \textbf{Principal preditor} & \textbf{Pearson $r$} \\" + "\n"
            r"\midrule" + "\n" +
            "\n".join(rca_rows) + "\n"
            r"\bottomrule" + "\n"
            r"\end{tabular}" + "\n"
            r"\fonte{SigmaFlow v10}" + "\n"
            r"\end{table}"
        )

    totais = {"critical": 0, "warning": 0, "info": 0}
    for r in results:
        for ins in r.get("structured_insights", []):
            sev = ins.get("severity", "info") if isinstance(ins, dict) else "info"
            totais[sev] = totais.get(sev, 0) + 1

    total_ins = totais["critical"] + totais["warning"] + totais["info"]
    parts.append(
        rf"""\subsection{{Sintese dos Achados}}

A analise integrada dos {len(results)} datasets revelou \textbf{{{total_ins} achados estatisticos}}.
Os \textbf{{{totais['critical']} achado(s) critico(s)}} requerem investigacao imediata,
os \textbf{{{totais['warning']} aviso(s)}} devem ser tratados no proximo ciclo de melhoria,
e os \textbf{{{totais['info']} achado(s) informacional(is)}} confirmam aspectos estaveis
que devem ser monitorados continuamente."""
    )

    return "\n\n".join(parts)


def _conclusao_consolidada(results: List[Dict[str, Any]]) -> str:
    n       = len(results)
    total_r = sum(r.get("shape",(0,0))[0] for r in results)
    elapsed = sum(r.get("elapsed_s",0) for r in results)
    n_ins   = sum(len(r.get("structured_insights",[])) for r in results)
    n_plots = sum(len(r.get("plots",[])) for r in results)

    n_incapaz  = sum(1 for r in results
                     if (r.get("analysis",{}).get("capability",{}).get("Cpk") or 999) < 1.0)
    n_marginal = sum(1 for r in results
                     if 1.0 <= (r.get("analysis",{}).get("capability",{}).get("Cpk") or 0) < 1.33)
    n_ok       = n - n_incapaz - n_marginal

    return rf"""O presente relatorio consolidou a analise automatica de
\textbf{{{n} dataset(s)}} pelo SigmaFlow v10, totalizando \textbf{{{total_r} observacoes}}
processadas em \textbf{{{_fmt(elapsed,1)} segundos}}. Foram gerados
\textbf{{{n_plots} graficos}} e identificados \textbf{{{n_ins} achados estatisticos}}
ao longo das cinco fases do ciclo DMAIC.

Em termos de capacidade de processo: {n_ok} dataset(s) com indice $C_{{pk}}$ aceitavel
ou superior, {n_marginal} marginais e {n_incapaz} incapazes. Os datasets incapazes
requerem acao corretiva imediata pela equipe de engenharia.

A analise de causa raiz por correlacao multivariada identificou os principais
preditores de qualidade em cada processo, fornecendo base cientifica para o
planejamento de experimentos controlados e a priorizacao de investimentos.

Conclui-se que o SigmaFlow v10 automatizou, de forma rigida e reprodutivel,
uma analise que demandaria dias de trabalho manual. Os resultados constituem
entrada direta para a fase de Implementacao do ciclo DMAIC.

\vspace{{0.5cm}}
\begin{{center}}
\textit{{Todos os resultados devem ser revisados por engenheiro de processos qualificado
antes de implementar acoes corretivas. Correlacao estatistica nao implica causalidade.}}
\end{{center}}"""
