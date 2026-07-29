"""
sigmaflow/report/section_builder.py
=====================================
Constroi os dicionarios de contexto que alimentam cada template Jinja2.

Cada metodo retorna um dict pronto para ser passado ao TemplateRenderer.render().
Textos interpretativos vem do InterpretationEngine.

Uso:
    from sigmaflow.report.section_builder import SectionBuilder

    sb  = SectionBuilder(results, dataset_name="processo_x")
    ctx = sb.build_all()   # dict completo para todas as secoes
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .interpretation_engine import InterpretationEngine, _fmt, _tex

logger = logging.getLogger(__name__)


class SectionBuilder:
    """
    Constroi contextos Jinja2 para todos os templates de secao.

    Parameters
    ----------
    results : dict
        Saida de Engine.run() adaptada (formato DMAICEngine).
    dataset_name : str
    organization : str
    """

    def __init__(
        self,
        results:      Dict[str, Any],
        dataset_name: str = "processo",
        organization: str = "",
        dataset_type: str = "geral",
    ) -> None:
        self.r    = results
        self.name = dataset_name
        self.org  = organization
        self.dtype = dataset_type
        self._meta    = results.get("metadata", {})
        self._measure = results.get("measure", {})
        self._analyze = results.get("analyze", {})
        self._improve = results.get("improve", {})
        self._summary = results.get("summary", {})
        self.ie = InterpretationEngine(results, dataset_name, organization)

    # ── API principal ────────────────────────────────────────────────────────

    def build_all(self) -> Dict[str, Dict[str, Any]]:
        """Retorna contexto completo para todas as secoes + main."""
        return {
            "main":              self.build_main(),
            "executive_summary": self.build_executive_summary(),
            "intro":             self.build_intro(),
            "detection":         self.build_detection(),
            "dataset":           self.build_dataset(),
            "metodologia":       self.build_metodologia(),
            "measure":           self.build_measure(),
            "analyze":           self.build_analyze(),
            "improve":           self.build_improve(),
            "control":           self.build_control(),
            "results":           self.build_results(),
            "key_insights":      self.build_key_insights(),
            "discussion":        self.build_discussion(),
            "conclusion":        self.build_conclusion(),
        }

    # ── Executive Summary ─────────────────────────────────────────────────────

    def build_executive_summary(self) -> Dict[str, Any]:
        """Constroi contexto para o Sumario Executivo."""
        exec_sum  = self.r.get("executive_summary", "")
        risk_lv   = self.r.get("risk_level", "info")
        risk_lb   = self.r.get("risk_label", r"BAIXO")
        risk_col  = self.r.get("risk_color", "corInfo")
        insights  = self.r.get("analysis_insights", [])

        n_critical = sum(1 for i in insights if i.get("severity") == "critical")
        n_warning  = sum(1 for i in insights if i.get("severity") == "warning")

        # Fallback: gerar executive summary se nao veio do engine
        if not exec_sum:
            from sigmaflow.insights.insight_engine        import InsightEngine
            from sigmaflow.insights.recommendation_engine import RecommendationEngine
            ai  = InsightEngine().generate(self.r)
            rec = RecommendationEngine(self.r, ai)
            exec_sum  = rec.executive_summary()
            risk_lv   = rec.risk_level()
            risk_lb   = rec.risk_label()
            risk_col  = rec.risk_color()
            n_critical = sum(1 for i in ai if i.severity == "critical")
            n_warning  = sum(1 for i in ai if i.severity == "warning")

        return {
            "executive_summary": {
                "text":         exec_sum,
                "risk_level":   risk_lv,
                "risk_label":   risk_lb,
                "risk_color":   risk_col,
                "n_insights":   len(insights),
                "n_critical":   n_critical,
                "n_warning":    n_warning,
                "has_critical": n_critical > 0,
                "has_warning":  n_warning > 0,
            }
        }

    # ── Key Insights & Recommendations ───────────────────────────────────────

    def build_key_insights(self) -> Dict[str, Any]:
        """Constroi contexto para a secao de Insights e Recomendacoes."""
        insights = self.r.get("analysis_insights", [])
        recs     = self.r.get("recommendations", [])

        # Fallback
        if not insights:
            from sigmaflow.insights.insight_engine        import InsightEngine
            from sigmaflow.insights.recommendation_engine import RecommendationEngine
            ai   = InsightEngine().generate(self.r)
            rec  = RecommendationEngine(self.r, ai)
            insights = [i.as_dict() for i in ai]
            recs     = rec.prioritized_recommendations()

        return {
            "key_insights": {
                "insights":          insights,
                "has_insights":      bool(insights),
                "recommendations":   recs,
                "has_recommendations": bool(recs),
                "n_total":           len(insights),
            }
        }

    # ── Detection section (Problem Identification) ────────────────────────────

    def build_detection(self) -> Dict[str, Any]:
        """
        Constroi o contexto para a secao de Identificacao Automatica do Problema.
        Alimentada pelos dados do ProblemDetector e AnalysisSelector.
        """
        det   = self.r.get("detection", {})
        plan  = self.r.get("analysis_plan", {})

        problems  = det.get("problems", [])
        primary   = det.get("primary_problem", "exploratory")
        response  = det.get("response_variable") or self._meta.get("primary_target", "N/A")
        features  = det.get("feature_variables", [])
        rationale = det.get("rationale", {})
        confidence= det.get("confidence", {})

        # Problem display names
        _labels = {
            "spc":        r"Controle Estat'istico de Processos (SPC)",
            "capability": r"An'alise de Capacidade do Processo",
            "regression": r"Regress\~{a}o e Correla\c{c}\~{a}o Multivariada",
            "anova":      r"An'alise de Vari\^{a}ncia (ANOVA)",
            "pareto":     r"An'alise de Pareto",
            "msa":        r"An'alise do Sistema de Medi\c{c}\~{a}o (MSA/Gauge R\&R)",
            "fmea":       r"An'alise de Modo e Efeito de Falha (FMEA)",
            "doe":        r"Delineamento de Experimentos (DOE)",
            "exploratory":r"An'alise Explorat'oria de Dados",
        }

        problem_rows = []
        for p in problems:
            conf = confidence.get(p, 0.0)
            reasons = rationale.get(p, [])
            problem_rows.append({
                "label":      _labels.get(p, _tex(p).title()),
                "id":         p.upper(),
                "confidence": rf"{conf*100:.0f}\%",
                "reason":     _tex(reasons[0]) if reasons else "---",
            })

        # Selected analyses flat list for display
        all_analyses = []
        for tokens in plan.values():
            for t in tokens:
                label = _tex(t.replace("_", " ").title())
                if label not in all_analyses:
                    all_analyses.append(label)

        # Build opening paragraph
        if len(problems) == 1:
            prob_str = rf"\textbf{{{_labels.get(problems[0], problems[0])}}}"
            opening = (
                rf"O motor de detec\c{{c}}\~{{a}}o autom'atica do SigmaFlow analisou "
                rf"a estrutura do dataset \textbf{{{_tex(self.name)}}} e identificou "
                rf"o seguinte tipo de problema estat'istico: {prob_str}. "
            )
        else:
            labs = ", ".join(
                rf"\textbf{{{_labels.get(p, p)}}}"
                for p in problems
            )
            opening = (
                rf"O motor de detec\c{{c}}\~{{a}}o autom'atica do SigmaFlow analisou "
                rf"a estrutura do dataset \textbf{{{_tex(self.name)}}} e identificou "
                rf"os seguintes tipos de problema estat'istico: {labs}. "
            )

        opening += (
            r"Com base nessa detec\c{c}\~{a}o, o sistema selecionou automaticamente "
            r"as t'ecnicas anal'iticas mais adequadas e configurou o pipeline "
            r"DMAIC correspondente."
        )

        primary_label = _labels.get(primary, primary)
        snap = det.get("metadata_snapshot", {})

        return {
            "detection": {
                "opening":        opening,
                "primary_label":  primary_label,
                "primary_id":     primary.upper(),
                "response":       _tex(str(response)),
                "features":       [_tex(f) for f in features[:8]],
                "has_features":   bool(features),
                "problem_rows":   problem_rows,
                "has_problems":   bool(problem_rows),
                "all_analyses":   all_analyses[:16],
                "has_analyses":   bool(all_analyses),
                "n_rows":         snap.get("n_rows", "N/A"),
                "n_num":          snap.get("n_num", "N/A"),
                "n_cat":          snap.get("n_cat", "N/A"),
                "has_time":       snap.get("has_time", False),
                "has_spec":       snap.get("has_spec", False),
                "plan_phases": {
                    phase: [_tex(t.replace("_", " ").title()) for t in tokens]
                    for phase, tokens in plan.items()
                    if tokens
                },
            }
        }

    # ── main.tex ─────────────────────────────────────────────────────────────

    def build_main(self) -> Dict[str, Any]:
        n_rows = self._meta.get("n_rows", "N/A")
        n_cols = self._meta.get("n_columns", "N/A")
        return {
            "meta": {
                "title":        rf"Relatorio DMAIC --- {_tex(self.name)}",
                "dataset_name": _tex(self.name),
                "dataset_type": _tex(self.dtype),
                "n_rows":       n_rows,
                "n_cols":       n_cols,
                "organization": _tex(self.org or "SigmaFlow v10"),
                "date":         datetime.now().strftime("%d/%m/%Y"),
            },
            "abstract": self.ie.generate_abstract(),
        }

    # ── Introducao ────────────────────────────────────────────────────────────

    def build_intro(self) -> Dict[str, Any]:
        target  = _tex(self._meta.get("primary_target", "vari\'avel-resposta"))
        n_rows  = self._meta.get("n_rows", "N/A")
        n_cols  = self._meta.get("n_columns", "N/A")
        n_num   = len(self._meta.get("numeric_columns", []))
        n_cat   = len(self._meta.get("categorical_columns", []))
        elapsed = _fmt(self.r.get("elapsed_s", 0), 2)

        return {
            "intro": {
                "opening": (
                    rf"O presente relat\'orio documenta os resultados de uma an\'alise "
                    rf"estat\'istica automatizada conduzida pelo sistema "
                    rf"\textbf{{SigmaFlow v10}}, aplicando o \textit{{framework}} "
                    rf"DMAIC (\textit{{Define, Measure, Analyze, Improve, Control}}) "
                    rf"ao conjunto de dados denominado \textbf{{{_tex(self.name)}}}. "
                    rf"O DMAIC constitui a metodologia estruturada de resolu\c{{c}}\~{{a}}o "
                    rf"de problemas do Lean Six Sigma, amplamente utilizada em projetos "
                    rf"de melhoria de processos industriais, de servi\c{{c}}os e "
                    rf"log\'isticos (Montgomery, 2009)."
                ),
                "dataset_description": (
                    rf"O dataset submetido \`{{a}} an\'alise \'e composto por "
                    rf"\textbf{{{n_rows} observa\c{{c}}\~{{o}}es}} e "
                    rf"\textbf{{{n_cols} vari\'aveis}}, das quais {n_num} s\~{{a}}o "
                    rf"de natureza num\'erica cont\'inua e {n_cat} s\~{{a}}o categ\'oricas. "
                    rf"A vari\'avel de interesse prim\'ario identificada automaticamente "
                    rf"pelo SigmaFlow foi \textbf{{{target}}}, sobre a qual foram "
                    rf"concentrados os esfor\c{{c}}os anal\'iticos das fases de "
                    rf"Medi\c{{c}}\~{{a}}o e An\'alise."
                ),
                "objective": (
                    r"O objetivo central desta an\'alise \'e caracterizar o desempenho "
                    r"do processo, avaliar sua estabilidade estat\'istica, estimar os "
                    r"\'indices de capacidade em rela\c{c}\~{a}o \`{a}s especifica\c{c}\~{o}es "
                    r"t\'ecnicas estabelecidas e identificar as principais fontes de "
                    r"varia\c{c}\~{a}o que impactam negativamente a qualidade do produto "
                    r"ou servi\c{c}o. As conclus\~{o}es apresentadas fundamentam-se em "
                    r"m\'etodos estat\'isticos rigorosos, incluindo cartas de controle, "
                    r"testes de normalidade, an\'alise de capacidade de processo e "
                    r"an\'alise de causa raiz por correla\c{c}\~{a}o multivariada."
                ),
                "pipeline_note": (
                    rf"Todo o pipeline anal\'itico foi executado em "
                    rf"\textbf{{{elapsed} segundos}}, cobrindo as cinco fases do "
                    rf"ciclo DMAIC de forma integrada e reprodut\'ivel."
                ),
            }
        }

    # ── Dataset ───────────────────────────────────────────────────────────────

    def build_dataset(self) -> Dict[str, Any]:
        target   = _tex(self._meta.get("primary_target", "N/A"))
        n_rows   = self._meta.get("n_rows", 0)
        n_cols   = self._meta.get("n_columns", 0)
        num_cols = self._meta.get("numeric_columns", [])
        miss_pct = self._meta.get("missing_pct", 0.0)

        desc = self._measure.get("descriptive", {})

        stats_rows = []
        for col in num_cols[:8]:
            mean   = desc.get(rf"{col}_mean", desc.get("mean"))
            std    = desc.get(rf"{col}_std",  desc.get("std"))
            mn     = desc.get(rf"{col}_min",  desc.get("min"))
            mx     = desc.get(rf"{col}_max",  desc.get("max"))
            median = desc.get(rf"{col}_median", desc.get("median"))
            cv     = (abs(float(std)/float(mean))*100) if mean and std and float(mean) != 0 else None
            stats_rows.append({
                "variable": _tex(col),
                "mean":   _fmt(mean, 4) if mean is not None else "---",
                "std":    _fmt(std, 4)  if std  is not None else "---",
                "min":    _fmt(mn, 4)   if mn   is not None else "---",
                "median": _fmt(median, 4) if median is not None else "---",
                "max":    _fmt(mx, 4)   if mx   is not None else "---",
                "cv":     _fmt(cv, 1)   if cv   is not None else "---",
            })

        miss_text = ""
        if miss_pct and float(miss_pct) > 0:
            miss_text = (
                rf"Foram identificados {_fmt(miss_pct, 1)}\\% de valores ausentes "
                rf"no conjunto de dados, fato que requer aten\c{{c}}\~{{a}}o na "
                rf"interpreta\c{{c}}\~{{a}}o dos resultados."
            )

        return {
            "dataset": {
                "scope_text": (
                    rf"O presente projeto de an\'alise tem como objeto o processo "
                    rf"representado pelo dataset \textbf{{{_tex(self.name)}}}, "
                    rf"classificado pelo SigmaFlow como do tipo "
                    rf"\textbf{{{_tex(self.dtype).upper()}}}. "
                    rf"A vari\'avel-resposta primaria identificada \'e "
                    rf"\textbf{{{target}}}, em torno da qual foram estruturadas "
                    rf"as hip\'oteses de causa raiz e os \'indices de desempenho."
                ),
                "profile_text": (
                    rf"O dataset cont\'em {n_rows} registros e {n_cols} atributos, "
                    rf"sendo {len(num_cols)} num\'ericos. {miss_text}"
                ),
                "has_stats":       bool(stats_rows),
                "stats_rows":      stats_rows,
                "stats_interpretation": (
                    r"As estat\'isticas descritivas fornecem uma vis\~{a}o inicial "
                    r"da distribui\c{c}\~{a}o e da magnitude da variabilidade "
                    r"presente no processo. O coeficiente de varia\c{c}\~{a}o (CV) "
                    r"indica a variabilidade relativa: valores acima de 30\% "
                    r"geralmente sinalizam alta instabilidade processual."
                ) if stats_rows else "",
            }
        }

    # ── Metodologia ───────────────────────────────────────────────────────────

    def build_metodologia(self) -> Dict[str, Any]:
        phases_run = self._summary.get(
            "phases_run",
            ["define", "measure", "analyze", "improve", "control"]
        )
        target = _tex(self._meta.get("primary_target", "vari\'avel-resposta"))

        _desc = {
            "define":  ("Definir",   r"identifica\c{c}\~{a}o do problema, escopo do projeto e vari\'avel-resposta"),
            "measure": ("Medir",     r"coleta e caracteriza\c{c}\~{a}o dos dados, an\'alise de capacidade e normalidade"),
            "analyze": ("Analisar",  r"identifica\c{c}\~{a}o de causas raiz, correla\c{c}\~{a}o e regress\~{a}o"),
            "improve": ("Melhorar",  r"Design of Experiments (DOE) e defini\c{c}\~{a}o de janelas operacionais \'otimas"),
            "control": ("Controlar", r"implanta\c{c}\~{a}o de cartas de controle e monitoramento cont\'inuo"),
        }

        phases = [
            {"label": _desc[p][0], "description": _desc[p][1]}
            for p in phases_run if p in _desc
        ]

        return {
            "metodologia": {
                "intro": (
                    r"A metodologia adotada baseia-se no ciclo DMAIC, estrutura "
                    r"consagrada do Lean Six Sigma que prov\^{e} um processo de "
                    r"melhoria orientado por dados, sistem\'atico e audit\'avel. "
                    r"As fases do ciclo foram executadas sequencialmente pelo "
                    r"motor \textbf{SigmaFlow v10}:"
                ),
                "phases": phases,
                "planning_text": (
                    rf"Na fase de Defini\c{{c}}\~{{a}}o, o perfil do dataset foi "
                    rf"constru\'ido pelo m\'odulo \texttt{{DataProfiler}}, que "
                    rf"identificou automaticamente tipos de vari\'aveis, dados "
                    rf"ausentes e a vari\'avel-resposta principal "
                    rf"(\textbf{{{target}}}). O m\'odulo \texttt{{AnalysisPlanner}} "
                    rf"selecionou os m\'etodos estat\'isticos mais adequados."
                ),
                "normality_text": (
                    r"A verifica\c{c}\~{a}o da normalidade foi conduzida por "
                    r"Shapiro--Wilk e Anderson--Darling. A hip\'otese nula "
                    r"($H_0$) pressup\~{o}e distribui\c{c}\~{a}o normal; "
                    r"$p < 0{,}05$ conduz \`{a} rejei\c{c}\~{a}o com "
                    r"signific\^{a}ncia de 5\%."
                ),
                "hypothesis_text": (
                    r"Para compara\c{c}\~{o}es entre grupos foram empregados "
                    r"teste \textit{t} de Student, ANOVA e Mann--Whitney "
                    r"(n\~{a}o param\'etrico), selecionados automaticamente "
                    r"conforme resultados dos testes de normalidade."
                ),
                "spc_text": (
                    r"O Controle Estat\'istico de Processos (CEP) foi "
                    r"implementado por cartas XmR (\textit{Individuals and "
                    r"Moving Range}), com limites calculados a "
                    r"$\mu \pm 3\sigma$. A capacidade foi quantificada "
                    r"pelos \'indices $C_p$ e $C_{pk}$:"
                ),
                "capability_eq_note": (
                    r"onde $USL$ e $LSL$ s\~{a}o os limites superior e inferior "
                    r"de especifica\c{c}\~{a}o, $\bar{x}$ a m\'edia e "
                    r"$\hat{\sigma}$ o desvio padr\~{a}o estimado do processo."
                ),
                "rca_text": (
                    r"A identifica\c{c}\~{a}o das vari\'aveis de maior "
                    r"influ\^{e}ncia foi realizada por correla\c{c}\~{a}o de "
                    r"Pearson e Spearman, com ranqueamento por import\^{a}ncia "
                    r"relativa. $|r| \geq 0{,}70$: correla\c{c}\~{a}o forte; "
                    r"$0{,}50 \leq |r| < 0{,}70$: associa\c{c}\~{a}o moderada."
                ),
            }
        }

    # ── Measure ───────────────────────────────────────────────────────────────

    def build_measure(self) -> Dict[str, Any]:
        cap  = self._measure.get("capability", {})
        norm = self._measure.get("normality",  {})
        hyp  = self._analyze.get("hypothesis_tests", {})
        target = _tex(self._meta.get("primary_target", "N/A"))

        # Tabela de normalidade
        norm_rows = []
        if isinstance(norm, dict):
            for var, res in list(norm.items())[:8]:
                if not isinstance(res, dict):
                    continue
                sw_p = res.get("shapiro_p", res.get("p_value"))
                ad_p = res.get("anderson_p", res.get("anderson_critical"))
                is_n = res.get("is_normal",
                               sw_p > 0.05 if sw_p is not None else None)
                verdict = (
                    r"\textcolor{info}{\textbf{Normal}}"
                    if is_n else
                    r"\textcolor{critico}{\textbf{N\~{a}o Normal}}"
                )
                norm_rows.append({
                    "variable": _tex(var),
                    "sw_p":     _fmt(sw_p, 4) if sw_p is not None else "---",
                    "ad_p":     _fmt(ad_p, 4) if ad_p is not None else "---",
                    "verdict":  verdict,
                })

        # Tabela de capacidade
        cpk      = cap.get("Cpk")
        cp       = cap.get("Cp")
        dpmo     = cap.get("dpmo")
        sigma_lv = cap.get("sigma_level")
        usl      = cap.get("usl")
        lsl      = cap.get("lsl")

        # Tabela de hipoteses
        hyp_rows = []
        if isinstance(hyp, dict):
            for test_name, res in list(hyp.items())[:4]:
                if not isinstance(res, dict):
                    continue
                p   = res.get("p_value")
                h   = res.get("statistic")
                sig = (r"\textcolor{critico}{sim}" if p is not None and p < 0.05
                       else r"\textcolor{info}{n\~{a}o}")
                hyp_rows.append({
                    "test":        _tex(test_name.replace("_", " ").title()),
                    "stat":        _fmt(h, 4) if h is not None else "---",
                    "pvalue":      _fmt(p, 4) if p is not None else "---",
                    "significant": sig,
                })

        return {
            "measure": {
                "intro": (
                    r"Esta se\c{c}\~{a}o apresenta os resultados da fase de "
                    r"Medi\c{c}\~{a}o (Measure) do ciclo DMAIC, incluindo a "
                    r"avalia\c{c}\~{a}o da normalidade das vari\'aveis cont\'inuas, "
                    r"os \'indices de capacidade do processo e os testes de "
                    r"hip\'otese conduzidos."
                ),
                "normality_intro": (
                    r"A verifica\c{c}\~{a}o da ader\^{e}ncia \`{a} distribui\c{c}\~{a}o "
                    r"normal \'e etapa fundamental para a escolha adequada dos "
                    r"m\'etodos estat\'isticos subsequentes. A Tabela~\ref{tab:normalidade} "
                    r"apresenta os resultados dos testes aplicados."
                ),
                "has_normality_table": bool(norm_rows),
                "normality_rows":      norm_rows,
                "normality_interpretation": self.ie.interpret_normality(norm),
                "capability_text": (
                    rf"A an\'alise de capacidade foi conduzida com base na vari\'avel "
                    rf"\textbf{{{target}}}."
                ),
                "has_capability_table": cpk is not None,
                "target": target,
                "cap": {
                    "cpk":   _fmt(cpk, 3)      if cpk      is not None else "---",
                    "cp":    _fmt(cp, 3)        if cp       is not None else "---",
                    "dpmo":  rf"{dpmo:,.0f}"     if dpmo     is not None else "---",
                    "sigma": _fmt(sigma_lv, 2)  if sigma_lv is not None else "---",
                    "usl":   _fmt(usl, 4)       if usl      is not None else "---",
                    "lsl":   _fmt(lsl, 4)       if lsl      is not None else "---",
                },
                "capability_interpretation": self.ie.interpret_capability(cap),
                "has_hypothesis": bool(hyp_rows),
                "hypothesis_intro": (
                    r"Os testes de hip\'otese a seguir foram selecionados "
                    r"automaticamente pelo SigmaFlow com base no perfil dos dados:"
                ),
                "hypothesis_rows":       hyp_rows,
                "hypothesis_interpretation": self.ie.interpret_hypothesis(hyp),
            }
        }

    # ── Analyze ───────────────────────────────────────────────────────────────

    def build_analyze(self) -> Dict[str, Any]:
        rca = self._analyze.get("root_cause", {})
        reg = self._analyze.get("regression", {})
        target = _tex(self._meta.get("primary_target", "N/A"))

        # Tabela RCA
        rca_rows = []
        ranked = rca.get("ranked_variables", []) if isinstance(rca, dict) else []
        for v in ranked[:10]:
            pr  = v.get("pearson_r", 0)
            sr  = v.get("spearman_r", 0)
            st  = v.get("strength", "fraca").capitalize()
            pearson_tex = (
                rf"\textcolor{{critico}}{{\textbf{{{_fmt(pr, 3)}}}}}"
                if abs(pr) >= 0.70 else
                rf"\textcolor{{aviso}}{{\textbf{{{_fmt(pr, 3)}}}}}"
                if abs(pr) >= 0.50 else
                _fmt(pr, 3)
            )
            rca_rows.append({
                "variable": _tex(v.get("variable", "?")),
                "pearson":  pearson_tex,
                "spearman": _fmt(sr, 3),
                "strength": _tex(st),
            })

        # Tabela regressao
        reg_rows = []
        if isinstance(reg, dict) and reg.get("coefficients"):
            coefs = reg["coefficients"]
            ses   = reg.get("standard_errors", {})
            ts    = reg.get("t_statistics", {})
            ps    = reg.get("p_values", {})
            for var, coef in list(coefs.items())[:8]:
                reg_rows.append({
                    "variable": _tex(var),
                    "coerf":  _fmt(coef, 4),
                    "se":    _fmt(ses.get(var), 4)  if ses.get(var)  is not None else "---",
                    "t":     _fmt(ts.get(var), 3)   if ts.get(var)   is not None else "---",
                    "p":     _fmt(ps.get(var), 4)   if ps.get(var)   is not None else "---",
                })

        r2 = reg.get("r_squared") if isinstance(reg, dict) else None
        reg_text = ""
        if r2 is not None:
            reg_text = (
                rf"O modelo de regress\~{{a}}o m\'ultipla explicou "
                rf"\textbf{{{_fmt(r2*100, 1)}\\%}} da vari\^{{a}}ncia da "
                rf"vari\'avel-resposta ($R^2 = {_fmt(r2, 4)}$). "
            )
            if r2 >= 0.7:
                reg_text += (
                    r"Esse resultado indica poder explicativo elevado do modelo, "
                    r"sugerindo que as vari\'aveis preditoras selecionadas "
                    r"capturam adequadamente a din\^{a}mica do processo."
                )
            elif r2 >= 0.4:
                reg_text += (
                    r"O modelo tem poder explicativo moderado. "
                    r"Vari\'aveis n\~{a}o mensuradas podem explicar parcela "
                    r"relevante da variabilidade residual."
                )
            else:
                reg_text += (
                    r"O poder explicativo \'e baixo, indicando que outras "
                    r"vari\'aveis causais importantes podem n\~{a}o estar "
                    r"inclu\'idas no dataset."
                )

        return {
            "analyze": {
                "intro": (
                    r"Esta se\c{c}\~{a}o apresenta os resultados da fase de "
                    r"An\'alise (Analyze), cujo objetivo \'e identificar as "
                    r"causas raiz da variabilidade do processo por meio de "
                    r"an\'alise de correla\c{c}\~{a}o multivariada e "
                    r"modelagem de regress\~{a}o."
                ),
                "rca_intro": self.ie.interpret_rca(rca),
                "target": target,
                "has_rca_table": bool(rca_rows),
                "rca_rows": rca_rows,
                "rca_interpretation": (
                    r"As vari\'aveis destacadas em vermelho apresentam "
                    r"correla\c{c}\~{a}o forte ($|r| \geq 0{,}70$) e devem "
                    r"ser priorizadas na conduc\~{a}o de experimentos controlados."
                ) if rca_rows else "",
                "has_regression": bool(r2 is not None),
                "regression_text": reg_text,
                "has_regression_table": bool(reg_rows),
                "regression_rows": reg_rows,
            }
        }

    # ── Improve ───────────────────────────────────────────────────────────────

    def build_improve(self) -> Dict[str, Any]:
        recs = self.ie.generate_recommendations()
        doe  = self._analyze.get("doe", {})

        doe_text = ""
        if doe and not doe.get("error"):
            factors = doe.get("factors", [])
            resp    = doe.get("response", "N/A")
            doe_text = (
                rf"O m\'odulo DOE aplicou an\'alise fatorial sobre "
                rf"{len(factors)} fator(es) (\textbf{{{', '.join(_tex(f) for f in factors[:4])}}}) "
                rf"com vari\'avel-resposta \textbf{{{_tex(resp)}}}. "
                r"Os efeitos principais e intera\c{c}\~{o}es foram avaliados "
                r"por ANOVA com n\'ivel de signific\^{a}ncia de 5\%."
            )

        return {
            "improve": {
                "intro": (
                    r"A fase de Melhoria (Improve) concentra as propostas de "
                    r"a\c{c}\~{a}o baseadas nos achados das fases anteriores, "
                    r"priorizadas por potencial de impacto e viabilidade "
                    r"de implementa\c{c}\~{a}o."
                ),
                "has_doe": bool(doe_text),
                "doe_text": doe_text,
                "has_recommendations": bool(recs),
                "recommendations_intro": (
                    r"Com base na an\'alise integrada das cinco fases do DMAIC, "
                    r"as seguintes a\c{c}\~{o}es s\~{a}o recomendadas em "
                    r"ordem de prioridade:"
                ),
                "recommendations": recs,
                "recommendations_note": (
                    r"A implementa\c{c}\~{a}o deve ser acompanhada de plano de "
                    r"a\c{c}\~{a}o estruturado com respons\'aveis, prazos e "
                    r"indicadores de verifica\c{c}\~{a}o da efic\'acia."
                ),
            }
        }

    # ── Control ───────────────────────────────────────────────────────────────

    def build_control(self) -> Dict[str, Any]:
        insights = self.r.get("structured_insights", [])
        violations = [
            _tex(ins.get("description", str(ins)))
            for ins in insights
            if isinstance(ins, dict) and ins.get("severity") == "critical"
        ]

        return {
            "control": {
                "intro": (
                    r"A fase de Controle (Control) estabelece as barreiras "
                    r"para garantir a sustentabilidade das melhorias implementadas, "
                    r"prevenindo o retorno do processo ao estado anterior."
                ),
                "spc_text": (
                    r"Cartas de controle avan\c{c}adas (CUSUM, EWMA e X-bar/R) "
                    r"foram geradas automaticamente para detec\c{c}\~{a}o precoce "
                    r"de desvios de tend\^{e}ncia e mudan\c{c}as de n\'ivel. "
                    r"Os limites de controle devem ser recalculados a cada "
                    r"25 novos subgrupos ou ap\'os qualquer interven\c{c}\~{a}o "
                    r"no processo."
                ),
                "has_violations": bool(violations),
                "violations_text": self.ie.interpret_spc_violations(insights),
                "violations": violations[:6],
                "monitoring_plan": (
                    r"Recomenda-se: (i) revis\~{a}o di\'aria das cartas de "
                    r"controle pelo operador respons\'avel; (ii) reuni\~{a}o "
                    r"semanal de an\'alise cr\'tica dos indicadores; "
                    r"(iii) auditoria mensal da efic\'acia do sistema de controle. "
                    r"O dashboard do SigmaFlow pode ser utilizado para "
                    r"monitoramento em tempo real."
                ),
            }
        }

    # ── Results ───────────────────────────────────────────────────────────────

    def build_results(self) -> Dict[str, Any]:
        plots    = self.r.get("plots", [])
        insights = self.r.get("structured_insights", [])

        _figure_labels = {
            "capability": r"Gr\'afico de capacidade do processo",
            "histogram":  r"Histograma com curva normal ajustada",
            "control":    r"Carta de controle do processo (XmR)",
            "pareto":     r"Gr\'afico de Pareto --- defici\^{e}ncias",
            "regression": r"Diagn\'ostico do modelo de regress\~{a}o",
            "cusum":      r"Carta CUSUM --- detec\c{c}\~{a}o de tend\^{e}ncias",
            "ewma":       r"Carta EWMA --- m\'edia m\'ovel exponencial",
            "xbar":       r"Carta X-bar/R --- subgrupos racionais",
            "correlation":r"Mapa de correla\c{c}\~{a}o entre vari\'aveis",
            "spc":        r"Carta de controle SPC",
            "logistics":  r"An\'alise de desempenho log\'istico",
            "defect":     r"Distribui\c{c}\~{a}o de categorias de defeito",
        }

        figures = []
        for p in plots[:10]:
            stem = Path(p).stem.lower()
            cap  = next(
                (label for key, label in _figure_labels.items() if key in stem),
                _tex(Path(p).stem.replace("_", " ").title())
            )
            figures.append({
                "caption": cap,
                "path":    "figures/" + Path(p).name,
            })

        critical_insights = [
            _tex(ins.get("description", str(ins)))
            for ins in insights
            if isinstance(ins, dict) and ins.get("severity") == "critical"
        ]
        warning_insights = [
            _tex(ins.get("description", str(ins)))
            for ins in insights
            if isinstance(ins, dict) and ins.get("severity") == "warning"
        ]
        info_insights = [
            _tex(ins.get("description", str(ins)))
            for ins in insights
            if isinstance(ins, dict) and
               ins.get("severity") not in ("critical", "warning")
        ]

        return {
            "results": {
                "intro": (
                    r"Esta se\c{c}\~{a}o consolida as representa\c{c}\~{o}es "
                    r"gr\'aficas e a s\'intese dos achados estat\'isticamente "
                    r"relevantes obtidos ao longo do pipeline DMAIC."
                ),
                "figures_intro": (
                    r"As figuras a seguir foram geradas automaticamente pelo "
                    r"SigmaFlow. Cada representa\c{c}\~{a}o foi selecionada "
                    r"conforme o tipo de dataset identificado na fase de "
                    r"Defini\c{c}\~{a}o."
                ),
                "figures":          figures,
                "insights_intro": (
                    r"Os achados a seguir foram classificados por severidade "
                    r"pelo motor de regras do SigmaFlow:"
                ),
                "has_critical":    bool(critical_insights),
                "critical_insights": critical_insights,
                "has_warning":     bool(warning_insights),
                "warning_insights": warning_insights,
                "has_info":        bool(info_insights),
                "info_insights":   info_insights,
            }
        }

    # ── Discussion ────────────────────────────────────────────────────────────

    def build_discussion(self) -> Dict[str, Any]:
        cap     = self._measure.get("capability", {})
        rca     = self._analyze.get("root_cause", {})
        ins     = self.r.get("structured_insights", [])
        target  = _tex(self._meta.get("primary_target", "vari\'avel principal"))
        recs    = self.ie.generate_recommendations()

        cpk     = cap.get("Cpk")
        ranked  = rca.get("ranked_variables", []) if isinstance(rca, dict) else []
        top_vars = [v["variable"] for v in ranked[:3] if abs(v.get("pearson_r", 0)) >= 0.5]

        rca_para = ""
        if top_vars:
            vars_fmt = ", ".join(rf"\textbf{{{_tex(v)}}}" for v in top_vars)
            rca_para = (
                rf"A an\'alise de correla\c{{c}}\~{{a}}o identificou {vars_fmt} "
                rf"como as vari\'aveis de maior associa\c{{c}}\~{{a}}o estat\'istica "
                rf"com \textbf{{{target}}}. Esses resultados sugerem que "
                rf"interven\c{{c}}\~{{o}}es nesses fatores t\^{{e}}m o maior "
                rf"potencial de impacto na melhoria da qualidade do processo. "
                rf"Ressalta-se que correla\c{{c}}\~{{a}}o estat\'istica n\~{{a}}o "
                rf"implica causalidade; a conduc\~{{a}}o de experimentos controlados "
                rf"(DOE) \'e recomendada para confirmar as hip\'oteses levantadas "
                r"(Montgomery; Runger, 2014)."
            )

        return {
            "discussion": {
                "capability_para": self.ie.interpret_capability(cap) if cpk is not None else "",
                "rca_para": rca_para,
                "anomaly_para": self.ie.interpret_spc_violations(ins),
                "integration_para": (
                    r"A interpreta\c{c}\~{a}o conjunta dos indicadores estat\'isticos "
                    r"obtidos nas fases de Medi\c{c}\~{a}o e An\'alise permite "
                    r"construir um diagn\'ostico abrangente do estado atual do "
                    r"processo. Os resultados apontam oportunidades de melhoria "
                    r"que, se endere\c{c}adas sistematicamente, t\^{e}m potencial "
                    r"de reduzir a taxa de n\~{a}o conformidades e elevar o "
                    r"n\'ivel sigma do processo."
                ),
                "has_recommendations": bool(recs),
                "recommendations_text": (
                    r"Com base no diagn\'ostico integrado, as seguintes "
                    r"a\c{c}\~{o}es s\~{a}o priorit\'arias:"
                ),
                "recommendations": recs[:5],
            }
        }

    # ── Conclusion ────────────────────────────────────────────────────────────

    def build_conclusion(self) -> Dict[str, Any]:
        n_rows  = self._meta.get("n_rows", "N/A")
        n_cols  = self._meta.get("n_columns", "N/A")
        target  = _tex(self._meta.get("primary_target", "vari\'avel-resposta"))
        cap     = self._measure.get("capability", {})
        cpk     = cap.get("Cpk")
        sig_lv  = cap.get("sigma_level")
        n_ins   = self._summary.get("n_insights", 0)
        elapsed = _fmt(self.r.get("elapsed_s", 0), 2)

        cap_line = ""
        if cpk is not None:
            verdict = self.ie.cpk_verdict(cpk)
            cap_line = (
                rf"O \'indice de capacidade $C_{{pk}} = {_fmt(cpk, 3)}$ "
                rf"classificou o processo como \textbf{{{verdict}}}. "
            )
            if sig_lv:
                cap_line += (
                    rf"O n\'ivel sigma estimado \'e de "
                    rf"\textbf{{{_fmt(sig_lv, 2)}$\sigma$}}. "
                )

        return {
            "conclusion": {
                "summary": (
                    rf"O presente estudo aplicou o ciclo DMAIC de forma "
                    rf"automatizada ao dataset \textbf{{{_tex(self.name)}}}, "
                    rf"composto por {n_rows} observa\c{{c}}\~{{o}}es e "
                    rf"{n_cols} vari\'aveis. A execu\c{{c}}\~{{a}}o completa "
                    rf"do pipeline anal\'itico --- incluindo profiling, "
                    rf"an\'alise estat\'istica, gera\c{{c}}\~{{a}}o de gr\'aficos "
                    rf"e produ\c{{c}}\~{{a}}o deste relat\'orio --- foi conclu\'ido "
                    rf"em \textbf{{{elapsed} segundos}}, demonstrando a efici\^{{e}}ncia "
                    rf"do SigmaFlow para suporte \`{{a}} tomada de decis\~{{a}}o."
                ),
                "capability_line": cap_line,
                "insights_line": (
                    rf"No total, \textbf{{{n_ins} \textit{{insights}} estat\'isticos}} "
                    rf"foram gerados ao longo das fases do DMAIC, sinalizando "
                    rf"aspectos cr\'iticos que requerem aten\c{{c}}\~{{a}}o da "
                    rf"equipe de engenharia."
                ),
                "rca_line": (
                    rf"A an\'alise de causa raiz por correla\c{{c}}\~{{a}}o "
                    rf"multivariada identificou as vari\'aveis de maior impacto "
                    rf"sobre \textbf{{{target}}}, fornecendo subs\'idios para "
                    rf"o planejamento de experimentos controlados e a "
                    rf"prioriza\c{{c}}\~{{a}}o de a\c{{c}}\~{{o}}es corretivas."
                ),
                "final_statement": (
                    r"Conclui-se que o SigmaFlow automatizou, de forma rigorosa "
                    r"e reprodut\'ivel, uma an\'alise que demandaria horas de "
                    r"trabalho manual. Os resultados constituem a base para a "
                    r"fase de Implementa\c{c}\~{a}o e o estabelecimento de um "
                    r"plano de monitoramento cont\'inuo, concluindo o ciclo "
                    r"DMAIC para o processo analisado."
                ),
            }
        }
