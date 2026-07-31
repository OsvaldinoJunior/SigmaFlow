"""
sigmaflow/insights/insight_engine.py
======================================
InsightEngine — interpreta resultados de cada analise estatistica e gera
objetos estruturados com interpretacao, impacto e acoes recomendadas.

Cada metodo recebe um dict de resultados de uma analise especifica e
retorna um AnalysisInsight com:
  - analysis_type  : identificador da analise
  - title          : titulo legivel
  - interpretation : paragrafo de interpretacao estatistica
  - impact         : impacto potencial no processo industrial
  - recommendations: lista de acoes recomendadas
  - severity       : 'info' | 'warning' | 'critical'
  - metrics        : dict com os numeros-chave usados na interpretacao

Uso:
    from sigmaflow.insights.insight_engine import InsightEngine

    engine = InsightEngine()
    insights = engine.generate(engine_result)
    for ins in insights:
        print(ins.title, ins.severity)
        print(ins.interpretation)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Utilidades LaTeX-safe (mesmas do interpretation_engine) ──────────────────

_ACCENTS = {
    "á": r"\\'a", "é": r"\\'e", "í": r"\\'i", "ó": r"\\'o", "ú": r"\\'u",
    "Á": r"\\'A", "É": r"\\'E", "Í": r"\\'I", "Ó": r"\\'O", "Ú": r"\\'U",
    "â": r"\\^a",  "ê": r"\\^e",  "ô": r"\\^o",
    "Â": r"\\^A",  "Ê": r"\\^E",  "Ô": r"\\^O",
    "ã": r"\\~a",  "õ": r"\\~o",
    "Ã": r"\\~A",  "Õ": r"\\~O",
    "à": r"\\`a",
    "ç": r"\\c{c}", "Ç": r"\\c{C}",
    "σ": r"$\\sigma$", "μ": r"$\\mu$", "α": r"$\\alpha$",
    "≥": r"$\\geq$",   "≤": r"$\\leq$",  "±": r"$\\pm$",
    "\u2013": "--", "\u2014": "---",
}


def _t(text: str) -> str:
    """Converte string para LaTeX-safe ASCII."""
    s = str(text)
    for uni, cmd in _ACCENTS.items():
        s = s.replace(uni, cmd)
    sentinel = "\x00BS\x00"
    s = s.replace("\\", sentinel)
    for ch, esc in [("&", r"\&"), ("%", r"\%"), ("#", r"\#"),
                    ("_", r"\_"), ("{", r"\{"), ("}", r"\}")]:
        s = s.replace(ch, esc)
    s = s.replace(sentinel, r"\textbackslash{}")
    s = "".join(c if ord(c) < 128 else "?" for c in s)
    return s


def _f(v: Any, d: int = 3) -> str:
    if v is None:
        return "---"
    try:
        return f"{float(v):.{d}f}"
    except (TypeError, ValueError):
        return str(v)


# ── Dataclass de resultado ────────────────────────────────────────────────────

@dataclass
class AnalysisInsight:
    """
    Insight estruturado gerado para uma analise especifica.

    Attributes
    ----------
    analysis_type   : token da analise (ex: 'capability', 'spc', 'regression')
    title           : titulo legivel em portugues
    interpretation  : paragrafo de interpretacao estatistica (LaTeX-safe)
    impact          : descricao do impacto potencial no processo
    recommendations : lista de acoes recomendadas (strings LaTeX-safe)
    severity        : 'info' | 'warning' | 'critical'
    metrics         : dict com valores numericos usados na interpretacao
    """
    analysis_type:   str
    title:           str
    interpretation:  str
    impact:          str
    recommendations: List[str]       = field(default_factory=list)
    severity:        str             = "info"
    metrics:         Dict[str, Any]  = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "analysis_type":   self.analysis_type,
            "title":           self.title,
            "interpretation":  self.interpretation,
            "impact":          self.impact,
            "recommendations": self.recommendations,
            "severity":        self.severity,
            "metrics":         self.metrics,
        }


# ── Motor principal ───────────────────────────────────────────────────────────

class InsightEngine:
    """
    Gera insights interpretativos automaticos para cada tipo de analise.

    Recebe o resultado completo de Engine.run() (um dict por dataset) e
    produz uma lista de AnalysisInsight, um por analise executada.

    Parameters
    ----------
    language : str
        Idioma das interpretacoes (atualmente apenas 'pt' suportado).
    """

    def __init__(self, language: str = "pt") -> None:
        self.language = language

    # ── API publica ───────────────────────────────────────────────────────────

    def generate(self, engine_result: Dict[str, Any]) -> List[AnalysisInsight]:
        """
        Gera todos os insights para um resultado de Engine.run().

        Parameters
        ----------
        engine_result : dict
            Um elemento da lista retornada por Engine.run().

        Returns
        -------
        list[AnalysisInsight]
            Lista ordenada por severidade (critical → warning → info).
        """
        insights: List[AnalysisInsight] = []

        analysis  = engine_result.get("analysis",   {})
        advanced  = engine_result.get("advanced",   {})
        stats     = engine_result.get("statistics", {})
        rca       = engine_result.get("root_cause", {})
        detection = engine_result.get("detection",  {})
        name      = engine_result.get("name", "dataset")

        # ── Capability ────────────────────────────────────────────────────────
        cap = analysis.get("capability", {})
        if not cap:
            cap = advanced.get("capability", {})
        if cap and isinstance(cap, dict) and "Cpk" in cap:
            ins = self.capability_insight(cap)
            if ins:
                insights.append(ins)

        # ── SPC / control chart ───────────────────────────────────────────────
        spc = analysis.get("spc", {})
        if not spc:
            spc = analysis.get("control_chart", {})
        structured = engine_result.get("structured_insights", [])
        if spc or structured:
            ins = self.spc_insight(spc, structured)
            if ins:
                insights.append(ins)

        # ── Regression ────────────────────────────────────────────────────────
        reg = advanced.get("regression", {})
        if reg and isinstance(reg, dict) and "error" not in reg:
            ins = self.regression_insight(reg)
            if ins:
                insights.append(ins)

        # ── ANOVA / DOE ───────────────────────────────────────────────────────
        doe = advanced.get("doe", {})
        if doe and isinstance(doe, dict) and "error" not in doe:
            ins = self.anova_insight(doe)
            if ins:
                insights.append(ins)

        # ── Pareto ────────────────────────────────────────────────────────────
        pareto = analysis.get("pareto", {})
        if pareto and isinstance(pareto, dict):
            ins = self.pareto_insight(pareto)
            if ins:
                insights.append(ins)

        # ── Normality ────────────────────────────────────────────────────────
        norm = stats.get("normality", {})
        if norm and isinstance(norm, dict):
            ins = self.normality_insight(norm)
            if ins:
                insights.append(ins)

        # ── Root cause ────────────────────────────────────────────────────────
        if rca and isinstance(rca, dict) and "ranked_variables" in rca:
            ins = self.rca_insight(rca)
            if ins:
                insights.append(ins)

        # ── MSA ───────────────────────────────────────────────────────────────
        msa = advanced.get("msa", {})
        if msa and isinstance(msa, dict) and "error" not in msa:
            ins = self.msa_insight(msa)
            if ins:
                insights.append(ins)

        # ── FMEA ──────────────────────────────────────────────────────────────
        fmea = advanced.get("fmea", {})
        if fmea and isinstance(fmea, dict) and "error" not in fmea:
            ins = self.fmea_insight(fmea)
            if ins:
                insights.append(ins)

        # ── Hypothesis tests ──────────────────────────────────────────────────
        hyp = stats.get("hypothesis", {})
        if hyp and isinstance(hyp, dict):
            ins = self.hypothesis_insight(hyp)
            if ins:
                insights.append(ins)

        # Sort: critical first, then warning, then info
        _order = {"critical": 0, "warning": 1, "info": 2}
        insights.sort(key=lambda x: _order.get(x.severity, 3))

        logger.info("InsightEngine: %d insights gerados para '%s'",
                    len(insights), name)
        return insights

    # ── Interpretacoes por tipo de analise ────────────────────────────────────

    def capability_insight(
        self, result: Dict[str, Any]
    ) -> Optional[AnalysisInsight]:
        """Interpreta indices de capacidade Cp/Cpk."""
        cpk = result.get("Cpk")
        cp  = result.get("Cp")
        dpmo = result.get("DPMO") or result.get("dpmo")
        usl  = result.get("USL") or result.get("usl")
        lsl  = result.get("LSL") or result.get("lsl")

        if cpk is None:
            return None

        metrics = {"Cpk": cpk, "Cp": cp, "DPMO": dpmo}

        if cpk < 1.00:
            severity = "critical"
            interp = (
                r"O \'indice $C_{pk} = " + _f(cpk) + r"$ indica que o processo "
                r"\textbf{n\~{a}o \'{{e}} capaz} de atender aos limites de especifica\c{c}\~{a}o. "
                r"Processos com $C_{pk} < 1{,}00$ geram uma propor\c{c}\~{a}o "
                r"significativa de n\~{a}o conformidades, comprometendo diretamente "
                r"a qualidade do produto final (Montgomery, 2009)."
            )
            impact = (
                r"Risco elevado de gera\c{c}\~{a}o de defeitos e rejeitos. "
                r"Poss\'ivel necessidade de inspec\c{c}\~{a}o 100\% ou retrabalho. "
                + (rf"Taxa estimada de \textbf{{{_f(dpmo, 0)} DPMO}}." if dpmo else "")
            )
            recs = [
                r"Parar e investigar causas especiais de varia\c{c}\~{a}o imediatamente",
                r"Implementar carta de controle XmR para monitoramento em tempo real",
                r"Revisar calibra\c{c}\~{a}o de equipamentos e instrumentos de medi\c{c}\~{a}o",
                r"Conduzir an\'{{a}}lise de causa raiz (Ishikawa ou 5 Porqu\^{e}s)",
                rf"Meta de curto prazo: elevar $C_{{pk}}$ para $\geq 1{{,}}33$",
            ]

        elif cpk < 1.33:
            severity = "warning"
            interp = (
                r"O \'indice $C_{pk} = " + _f(cpk) + r"$ classifica o processo como "
                r"\textbf{marginalmente capaz}. Embora o processo esteja dentro dos "
                r"limites de especifica\c{c}\~{a}o na maior parte do tempo, a margem "
                r"de seguran\c{c}a \'{{e}} insuficiente para processos de alta precis\~{a}o "
                r"(Montgomery, 2009). $C_{pk} \geq 1{,}33$ \'{{e}} o padr\~{a}o m\'inimo "
                r"exigido pela ind\'{{u}}stria automotiva (AIAG, 2010)."
            )
            impact = (
                r"Risco moderado de gera\c{c}\~{a}o de n\~{a}o conformidades sob "
                r"condi\c{c}\~{o}es adversas. Monitoramento intensivo necess\'{{a}}rio "
                r"para evitar escapes para o cliente."
            )
            recs = [
                r"Implementar monitoramento intensivo com cartas de controle",
                r"Realizar estudo de variabilidade (componentes de vari\^{a}ncia)",
                r"Avaliar oportunidades de redu\c{c}\~{a}o de variabilidade via DOE",
                r"Revisar tolerancias em conjunto com engenharia do produto",
            ]

        elif cpk < 1.67:
            severity = "info"
            interp = (
                r"O \'indice $C_{pk} = " + _f(cpk) + r"$ indica que o processo \'{{e}} "
                r"\textbf{capaz}, atendendo ao padr\~{a}o industrial m\'inimo de $C_{pk} \geq 1{,}33$. "
                r"Contudo, ainda existe oportunidade de otimiza\c{c}\~{a}o antes de "
                r"atingir o n\'ivel Six Sigma ($C_{pk} \geq 1{,}67$)."
            )
            impact = (
                r"Processo est\'{{a}}vel com baixo risco de n\~{a}o conformidades. "
                r"Oportunidade de redu\c{c}\~{a}o de custos de inspe\c{c}\~{a}o."
            )
            recs = [
                r"Avaliar oportunidades de otimiza\c{c}\~{a}o de par\^{a}metros do processo",
                r"Considerar redu\c{c}\~{a}o de frequ\^{e}ncia de inspe\c{c}\~{a}o",
                r"Documentar melhores pr\'{{a}}ticas operacionais (POP)",
            ]

        else:
            severity = "info"
            interp = (
                r"O \'indice $C_{pk} = " + _f(cpk) + r"$ indica processo "
                r"\textbf{altamente capaz} (n\'ivel Six Sigma). O processo apresenta "
                r"excelente centraliza\c{c}\~{a}o e varia\c{c}\~{a}o m\'inima em "
                r"rela\c{c}\~{a}o aos limites de especifica\c{c}\~{a}o."
            )
            impact = (
                r"Taxa de defeitos m\'inima. Potencial para redu\c{c}\~{a}o "
                r"de custos de inspe\c{c}\~{a}o e qualidade assegurada ao cliente."
            )
            recs = [
                r"Manter monitoramento peri\'{{o}}dico com cartas de controle",
                r"Documentar e padronizar as condi\c{c}\~{o}es operacionais atuais",
                r"Avaliar possibilidade de ampliar as toler\^{a}ncias de projeto",
            ]

        return AnalysisInsight(
            analysis_type   = "capability",
            title           = r"An\'{{a}}lise de Capacidade do Processo",
            interpretation  = interp,
            impact          = impact,
            recommendations = recs,
            severity        = severity,
            metrics         = metrics,
        )

    def spc_insight(
        self,
        spc_result: Dict[str, Any],
        structured_insights: List[Dict] = None,
    ) -> Optional[AnalysisInsight]:
        """Interpreta estabilidade estatistica do processo via SPC."""
        si = structured_insights or []
        ooc_insights = [
            i for i in si
            if isinstance(i, dict) and (
                "western" in i.get("rule", "").lower() or
                i.get("severity") in ("critical", "warning")
            )
        ]
        n_ooc = (
            spc_result.get("out_of_control_points", 0)
            or spc_result.get("n_violations", 0)
            or len(ooc_insights)
        )

        metrics = {"out_of_control_points": n_ooc}

        if n_ooc == 0 and not spc_result:
            return None

        if n_ooc > 3:
            severity = "critical"
            interp = (
                rf"A carta de controle detectou \textbf{{{n_ooc} ponto(s) fora dos "
                r"limites de controle}} (regras de Western Electric). Esse padr\~{a}o "
                r"indica que o processo \textbf{n\~{a}o est\'{{a}} em controle "
                r"estat\'istico}, evidenciando a presen\c{c}a de causas especiais "
                r"de varia\c{c}\~{a}o que devem ser investigadas e eliminadas antes "
                r"de qualquer an\'{{a}}lise de capacidade (Shewhart, 1931; Montgomery, 2009)."
            )
            impact = (
                r"Processo inst\'{{a}}vel. Resultados imprevis\'iveis e risco elevado "
                r"de produ\c{c}\~{a}o fora de especifica\c{c}\~{a}o. \'Indices de "
                r"capacidade n\~{a}o s\~{a}o confi\'{{a}}veis enquanto o processo "
                r"n\~{a}o estiver em controle."
            )
            recs = [
                r"Identificar e eliminar causas especiais de varia\c{c}\~{a}o imediatamente",
                r"Verificar ajustes de m\'{{a}}quina nos per\'iodos dos pontos fora de controle",
                r"Revisar mudan\c{c}as de material, operador ou ambiente nesses per\'iodos",
                r"Recalcular limites de controle ap\'{{o}}s eliminar causas especiais",
                r"Implementar plano de rea\c{c}\~{a}o documentado para desvios",
            ]
        elif n_ooc > 0:
            severity = "warning"
            interp = (
                rf"Foram detectados \textbf{{{n_ooc} ponto(s) fora dos limites de controle}}. "
                r"O processo apresenta sinais de instabilidade que merecem investiga\c{c}\~{a}o. "
                r"Embora o processo possa estar operando dentro das especifica\c{c}\~{o}es "
                r"na maior parte do tempo, a presen\c{c}a de causas especiais "
                r"compromete sua previsibilidade (Montgomery, 2009)."
            )
            impact = (
                r"Instabilidade espor\'{{a}}dica com risco moderado de n\~{a}o "
                r"conformidades. Monitoramento intensificado recomendado."
            )
            recs = [
                r"Investigar os eventos associados aos pontos fora de controle",
                r"Verificar registros de produ\c{c}\~{a}o, manuten\c{c}\~{a}o e insumos",
                r"Considerar implementa\c{c}\~{a}o de carta CUSUM para detec\c{c}\~{a}o precoce",
            ]
        else:
            severity = "info"
            interp = (
                r"A an\'{{a}}lise da carta de controle indica que o processo encontra-se "
                r"\textbf{em controle estat\'istico}. N\~{a}o foram detectadas "
                r"viola\c{c}\~{o}es das regras de Western Electric, sugerindo que "
                r"apenas causas comuns de varia\c{c}\~{a}o est\~{a}o presentes (Shewhart, 1931)."
            )
            impact = (
                r"Processo previs\'ivel e est\'{{a}}vel. Condi\c{c}\~{a}o favor\'{{a}}vel "
                r"para estudos de capacidade e otimiza\c{c}\~{a}o."
            )
            recs = [
                r"Manter monitoramento cont\'inuo com a carta de controle atual",
                r"Avaliar possibilidade de ampliar o intervalo de amostragem",
            ]

        return AnalysisInsight(
            analysis_type   = "spc",
            title           = r"Controle Estat\'istico de Processo (CEP)",
            interpretation  = interp,
            impact          = impact,
            recommendations = recs,
            severity        = severity,
            metrics         = metrics,
        )

    def normality_insight(
        self, norm_result: Dict[str, Any]
    ) -> Optional[AnalysisInsight]:
        """Interpreta resultados de testes de normalidade."""
        if not norm_result:
            return None

        tests = norm_result if isinstance(norm_result, dict) else {}
        n_total    = len(tests)
        n_normal   = sum(
            1 for v in tests.values()
            if isinstance(v, dict) and v.get("is_normal", False)
        )
        n_not      = n_total - n_normal

        if n_total == 0:
            return None

        metrics = {"n_total": n_total, "n_normal": n_normal, "n_not_normal": n_not}
        pct_normal = round(n_normal / n_total * 100) if n_total else 0

        if pct_normal == 0:
            severity = "warning"
            interp = (
                rf"Os testes de normalidade (Shapiro--Wilk e Anderson--Darling) "
                rf"indicam que \textbf{{nenhuma}} das {n_total} vari\'{{a}}vel(is) "
                r"analisada(s) segue distribui\c{c}\~{a}o normal ($p < 0{,}05$). "
                r"Esse resultado pode indicar assimetria, caudas pesadas, "
                r"multimodalidade ou presen\c{c}a de outliers nos dados."
            )
            impact = (
                r"O uso de testes param\'{{e}}tricos (t-test, ANOVA) pode gerar "
                r"conclus\~{o}es err\^{o}neas. \'Indices de capacidade baseados "
                r"na distribui\c{c}\~{a}o normal devem ser interpretados com cuidado."
            )
            recs = [
                r"Aplicar transforma\c{c}\~{o}es Box--Cox ou Johnson para normaliza\c{c}\~{a}o",
                r"Utilizar testes n\~{a}o param\'{{e}}tricos (Mann--Whitney, Kruskal--Wallis)",
                r"Investigar a presen\c{c}a de outliers e causas especiais nos dados",
                r"Considerar modelos de distribui\c{c}\~{a}o alternativa (Weibull, Gamma)",
            ]
        elif pct_normal < 60:
            severity = "warning"
            interp = (
                rf"Os testes de normalidade indicam que apenas \textbf{{{n_normal} "
                rf"de {n_total}}} vari\'{{a}}veis seguem distribui\c{c}\~{a}o normal. "
                r"A mistura de distribui\c{c}\~{o}es normais e n\~{a}o normais exige "
                r"aten\c{c}\~{a}o na escolha dos m\'{{e}}todos estat\'isticos "
                r"subsequentes."
            )
            impact = (
                r"Sele\c{c}\~{a}o criteriosa de testes estat\'isticos necess\'{{a}}ria. "
                r"Risco de conclus\~{o}es incorretas se m\'{{e}}todos param\'{{e}}tricos "
                r"forem aplicados indiscriminadamente."
            )
            recs = [
                r"Verificar normalidade individualmente antes de cada an\'{{a}}lise",
                r"Aplicar transforma\c{c}\~{o}es nas vari\'{{a}}veis n\~{a}o normais",
                r"Utilizar m\'{{e}}todos robustos (bootstrap) para infer\^{e}ncia",
            ]
        else:
            severity = "info"
            interp = (
                rf"Os testes de normalidade indicam que \textbf{{{n_normal} "
                rf"de {n_total}}} vari\'{{a}}vel(is) seguem distribui\c{c}\~{a}o normal. "
                r"Esse resultado valida o uso de m\'{{e}}todos param\'{{e}}tricos cl\'{{a}}ssicos "
                r"para as an\'{{a}}lises subsequentes."
            )
            impact = (
                r"M\'{{e}}todos param\'{{e}}tricos (ANOVA, regress\~{a}o, t-test) "
                r"podem ser aplicados com confian\c{c}a nas vari\'{{a}}veis normais."
            )
            recs = [
                r"Prosseguir com an\'{{a}}lises param\'{{e}}tricas para as vari\'{{a}}veis normais",
                r"Aplicar m\'{{e}}todos alternativos para as vari\'{{a}}veis n\~{a}o normais",
            ]

        return AnalysisInsight(
            analysis_type   = "normality",
            title           = r"Normalidade das Vari\'{{a}}veis",
            interpretation  = interp,
            impact          = impact,
            recommendations = recs,
            severity        = severity,
            metrics         = metrics,
        )

    def regression_insight(
        self, result: Dict[str, Any]
    ) -> Optional[AnalysisInsight]:
        """Interpreta resultado de regressao multipla."""
        r2      = result.get("r_squared") or result.get("R2") or result.get("r2")
        p_value = result.get("p_value") or result.get("model_p_value")
        target  = result.get("target_col") or result.get("target", "resposta")
        top_feat = result.get("top_features") or result.get("ranked_variables", [])

        if r2 is None and p_value is None:
            return None

        metrics = {"r_squared": r2, "p_value": p_value}
        sig = (p_value is not None and p_value < 0.05) or (r2 is not None and r2 > 0.5)

        if sig and r2 is not None and r2 > 0.70:
            severity = "warning"
            interp = (
                rf"O modelo de regress\~{{a}}o apresentou \textbf{{$R^2 = {_f(r2, 3)}$}}, "
                r"indicando que as vari\'{{a}}veis preditoras explicam "
                rf"\textbf{{{round(float(r2)*100, 1)}\% da variabilidade}} "
                rf"de \textbf{{{_t(str(target))}}}. "
                r"A rela\c{c}\~{a}o estat\'isticamente significativa ($p < 0{,}05$) "
                r"sugere forte depend\^{e}ncia entre as vari\'{{a}}veis do processo "
                r"(Montgomery; Runger, 2014)."
            )
            impact = (
                r"Exist\^{e}ncia de rela\c{c}\~{o}es causa--efeito entre vari\'{{a}}veis "
                r"de entrada e sa\'ida do processo. Controlar as vari\'{{a}}veis "
                r"preditoras significativas pode reduzir substancialmente a variabilidade."
            )
            recs = [
                r"Implementar controle ativo das vari\'{{a}}veis preditoras mais influentes",
                r"Conduzir DOE para confirmar causalidade e definir janelas operacionais",
                r"Estabelecer especifica\c{c}\~{o}es para as vari\'{{a}}veis de entrada",
                r"Monitorar as vari\'{{a}}veis preditoras via cartas de controle",
            ]
        elif sig:
            severity = "warning"
            interp = (
                r"O modelo de regress\~{a}o identificou rela\c{c}\~{o}es "
                r"\textbf{estatisticamente significativas} entre as vari\'{{a}}veis "
                rf"do processo e \textbf{{{_t(str(target))}}}. "
                r"Embora o poder explicativo seja moderado, os resultados sugerem "
                r"que interven\c{c}\~{o}es nas vari\'{{a}}veis preditoras ter\~{a}o "
                r"impacto mensur\'{{a}}vel na sa\'ida do processo."
            )
            impact = (
                r"Oportunidade de melhoria identificada. Controle das vari\'{{a}}veis "
                r"preditoras pode reduzir a variabilidade da resposta."
            )
            recs = [
                r"Investigar as vari\'{{a}}veis com maior coeficiente de regress\~{a}o",
                r"Conduzir an\'{{a}}lise de res\'iduos para validar o modelo",
                r"Avaliar inclus\~{a}o de termos de intera\c{c}\~{a}o no modelo",
            ]
        else:
            severity = "info"
            interp = (
                r"O modelo de regress\~{a}o n\~{a}o identificou rela\c{c}\~{o}es "
                r"estatisticamente significativas entre as vari\'{{a}}veis analisadas "
                r"($p \geq 0{,}05$). Isso pode indicar que as vari\'{{a}}veis mais "
                r"relevantes n\~{a}o foram capturadas no dataset, ou que a "
                r"rela\c{c}\~{a}o \'{{e}} n\~{a}o linear."
            )
            impact = (
                r"Sem evid\^{e}ncia de rela\c{c}\~{o}es lineares significativas. "
                r"Pode ser necess\'{{a}}rio explorar modelos n\~{a}o lineares ou "
                r"coletar vari\'{{a}}veis adicionais."
            )
            recs = [
                r"Explorar modelos de regress\~{a}o n\~{a}o linear ou polinomial",
                r"Revisar a sele\c{c}\~{a}o de vari\'{{a}}veis com especialistas do processo",
                r"Considerar an\'{{a}}lise de componentes principais (PCA)",
            ]

        return AnalysisInsight(
            analysis_type   = "regression",
            title           = r"An\'{{a}}lise de Regress\~{a}o",
            interpretation  = interp,
            impact          = impact,
            recommendations = recs,
            severity        = severity,
            metrics         = metrics,
        )

    def anova_insight(
        self, result: Dict[str, Any]
    ) -> Optional[AnalysisInsight]:
        """Interpreta resultado de ANOVA / DOE."""
        p_value    = result.get("p_value") or result.get("anova_p")
        f_stat     = result.get("f_statistic") or result.get("F")
        factor     = result.get("factor_col") or result.get("factor", "fator")
        n_groups   = result.get("n_groups") or result.get("n_levels")
        effect_size = result.get("eta_squared") or result.get("effect_size")

        if p_value is None and f_stat is None:
            return None

        metrics = {"p_value": p_value, "f_statistic": f_stat, "n_groups": n_groups}
        sig = p_value is not None and p_value < 0.05

        if sig:
            severity = "warning"
            interp = (
                rf"A ANOVA revela diferen\c{{c}}a \textbf{{estatisticamente "
                r"significativa}} entre os grupos do fator "
                rf"\textbf{{{_t(str(factor))}}} "
                + (rf"($F = {_f(f_stat, 2)}$, $p = {_f(p_value, 4)}$)" if f_stat else rf"($p = {_f(p_value, 4)}$)")
                + r". Pelo menos um grupo difere significativamente dos demais, "
                r"sugerindo que este fator exerce influ\^{e}ncia real sobre a "
                r"vari\'{{a}}vel resposta (Montgomery, 2009)."
            )
            impact = (
                r"Diferen\c{c}as entre grupos (m\'{{a}}quinas, operadores, turnos, "
                r"fornecedores) representam fontes de variabilidade controlavel que, "
                r"se endere\c{c}adas, podem reduzir a dispers\~{a}o do processo."
            )
            recs = [
                rf"Investigar as diferen\c{{c}}as entre grupos do fator \textbf{{{_t(str(factor))}}}",
                r"Aplicar teste post-hoc (Tukey HSD) para identificar os grupos distintos",
                r"Padronizar procedimentos entre grupos com melhor desempenho",
                r"Verificar calibra\c{c}\~{a}o entre m\'{{a}}quinas/instrumentos/operadores",
            ]
        else:
            severity = "info"
            interp = (
                rf"A ANOVA indica \textbf{{n\~{{a}}o}} haver diferen\c{{c}}a "
                r"estatisticamente significativa entre os grupos do fator "
                rf"\textbf{{{_t(str(factor))}}} ($p \geq 0{{,}}05$). "
                r"As m\'{{e}}dias dos grupos s\~{a}o estatisticamente equivalentes, "
                r"indicando que este fator n\~{a}o \'{{e}} uma fonte significativa "
                r"de variabilidade na resposta analisada."
            )
            impact = (
                r"O fator analisado n\~{a}o representa uma fonte priorit\'{{a}}ria "
                r"de varia\c{c}\~{a}o. Esfor\c{c}os de melhoria podem ser "
                r"direcionados a outros fatores."
            )
            recs = [
                r"Explorar outros fatores como poss\'iveis fontes de variabilidade",
                r"Aumentar o tamanho da amostra para aumentar o poder do teste",
                r"Verificar se a vari\'{{a}}vel de estratifica\c{c}\~{a}o foi bem definida",
            ]

        return AnalysisInsight(
            analysis_type   = "anova",
            title           = r"An\'{{a}}lise de Vari\^{a}ncia (ANOVA)",
            interpretation  = interp,
            impact          = impact,
            recommendations = recs,
            severity        = severity,
            metrics         = metrics,
        )

    def pareto_insight(
        self, result: Dict[str, Any]
    ) -> Optional[AnalysisInsight]:
        """Interpreta analise de Pareto."""
        top_cats   = result.get("top_categories") or result.get("top_defects", [])
        pct_80     = result.get("pct_categories_for_80pct")
        n_cats     = result.get("n_categories") or result.get("total_categories")
        total_def  = result.get("total_defects") or result.get("total_count")

        if not top_cats and not n_cats:
            return None

        n_vital = len(top_cats) if isinstance(top_cats, list) else 0
        metrics = {"n_vital_few": n_vital, "n_categories": n_cats, "total": total_def}

        if n_vital > 0:
            top_str = ", ".join(
                rf"\textbf{{{_t(str(c))}}}"
                for c in (top_cats[:3] if isinstance(top_cats, list) else [])
            )
            severity = "warning"
            interp = (
                r"A an\'{{a}}lise de Pareto confirma o princ\'ipio 80/20: "
                r"um pequeno n\'{{u}}mero de categorias concentra a maioria das "
                r"ocorr\^{e}ncias de falha. "
                + (rf"As categorias {top_str} representam os \textbf{{vitais poucos}} "
                   r"que devem receber aten\c{c}\~{a}o priorit\'{{a}}ria." if top_str else "")
            )
            impact = (
                r"Concentrar os esfor\c{c}os de melhoria nas categorias priorit\'{{a}}rias "
                r"permite maximizar o impacto com o m\'inimo de recursos, "
                r"acelerando a redu\c{c}\~{a}o da taxa global de defeitos."
            )
            recs = [
                r"Focar imediatamente nas categorias de defeito de maior frequ\^{e}ncia",
                r"Executar an\'{{a}}lise de causa raiz (Ishikawa) para cada categoria vital",
                r"Estabelecer metas de redu\c{c}\~{a}o para as 3 principais categorias",
                r"Monitorar o progresso ap\'{{o}}s implementa\c{c}\~{a}o de melhorias",
            ]
        else:
            severity = "info"
            interp = (
                r"A an\'{{a}}lise de Pareto foi realizada. A distribui\c{c}\~{a}o das "
                r"ocorr\^{e}ncias entre as categorias foi mapeada para orientar "
                r"a prioriza\c{c}\~{a}o de a\c{c}\~{o}es corretivas."
            )
            impact = (
                r"Identifica\c{c}\~{a}o das categorias priorit\'{{a}}rias para "
                r"foco das a\c{c}\~{o}es de melhoria."
            )
            recs = [
                r"Revisar a classifica\c{c}\~{a}o das categorias de defeito",
                r"Coletar dados estratificados para an\'{{a}}lise mais detalhada",
            ]

        return AnalysisInsight(
            analysis_type   = "pareto",
            title           = r"An\'{{a}}lise de Pareto",
            interpretation  = interp,
            impact          = impact,
            recommendations = recs,
            severity        = severity,
            metrics         = metrics,
        )

    def rca_insight(
        self, result: Dict[str, Any]
    ) -> Optional[AnalysisInsight]:
        """Interpreta analise de causa raiz por correlacao."""
        ranked  = result.get("ranked_variables", [])
        target  = result.get("target_col", "resposta")
        strong  = [v for v in ranked if abs(v.get("pearson_r", 0)) >= 0.70]
        moderate = [v for v in ranked if 0.50 <= abs(v.get("pearson_r", 0)) < 0.70]

        if not ranked:
            return None

        metrics = {"n_strong": len(strong), "n_moderate": len(moderate)}

        if strong:
            top = strong[0]
            severity = "warning"
            strong_str = ", ".join(
                rf"\textbf{{{_t(v['variable'])}}}"
                + rf" ($r = {_f(v.get('pearson_r'), 3)}$)"
                for v in strong[:3]
            )
            interp = (
                rf"A an\'{{a}}lise de correla\c{{c}}\~{{a}}o identificou "
                + (f"{len(strong)} vari\\'avel(is) com correla\\c{{c}}\\~{{a}}o forte "
                   rf"($|r| \geq 0{{,}}70$) com \textbf{{{_t(str(target))}}}: "
                   + strong_str + r". ")
                + r"Correla\c{c}\~{o}es fortes s\~{a}o fortes candidatas a causas "
                r"raiz, embora a causalidade deva ser confirmada por experimentos "
                r"controlados (Montgomery; Runger, 2014)."
            )
            impact = (
                r"Identifica\c{c}\~{a}o das principais alavancas de controle do processo. "
                r"Interven\c{c}\~{o}es nessas vari\'{{a}}veis t\^{e}m alto potencial de "
                r"impacto na redu\c{c}\~{a}o da variabilidade da resposta."
            )
            recs = [
                r"Conduzir DOE (2k fatorial) para confirmar causalidade das vari\'{{a}}veis fortes",
                r"Implementar cartas de controle para as vari\'{{a}}veis preditoras",
                r"Definir janelas operacionais \'{{o}}timas baseadas na regress\~{a}o",
                r"Documentar os par\^{a}metros cr\'iticos no Plano de Controle",
            ]
        elif moderate:
            severity = "info"
            mod_str = ", ".join(
                rf"\textbf{{{_t(v['variable'])}}}" for v in moderate[:3]
            )
            interp = (
                rf"A an\'{{a}}lise de correla\c{{c}}\~{{a}}o identificou vari\'{{a}}veis com "
                r"correla\c{c}\~{a}o moderada "
                rf"($0{{,}}50 \leq |r| < 0{{,}}70$) com \textbf{{{_t(str(target))}}}: "
                + mod_str
                + r". Essas vari\'{{a}}veis s\~{a}o candidatas a investiga\c{c}\~{a}o adicional."
            )
            impact = (
                r"Oportunidade de melhoria identificada. Controle dessas vari\'{{a}}veis "
                r"pode contribuir para redu\c{c}\~{a}o da variabilidade do processo."
            )
            recs = [
                r"Investigar as vari\'{{a}}veis moderadamente correlacionadas",
                r"Realizar an\'{{a}}lise de regress\~{a}o m\'{{u}}ltipla para quantificar efeitos",
                r"Coletar dados adicionais para confirmar as rela\c{c}\~{o}es identificadas",
            ]
        else:
            severity = "info"
            interp = (
                rf"A an\'{{a}}lise de correla\c{{c}}\~{{a}}o n\~{{a}}o identificou "
                r"vari\'{{a}}veis fortemente associadas \`{a} resposta do processo. "
                r"As causas raiz podem envolver intera\c{c}\~{o}es entre vari\'{{a}}veis "
                r"ou efeitos n\~{a}o lineares n\~{a}o capturados pela correla\c{c}\~{a}o de Pearson."
            )
            impact = (
                r"Causas raiz n\~{a}o identificadas pela an\'{{a}}lise linear. "
                r"Abordagens complementares necess\'{{a}}rias."
            )
            recs = [
                r"Explorar correla\c{c}\~{o}es n\~{a}o lineares (Spearman, Kendall)",
                r"Aplicar an\'{{a}}lise de componentes principais (PCA)",
                r"Consultar especialistas do processo para identifica\c{c}\~{a}o de causas raiz",
            ]

        return AnalysisInsight(
            analysis_type   = "root_cause",
            title           = r"An\'{{a}}lise de Causa Raiz (Correla\c{c}\~{a}o)",
            interpretation  = interp,
            impact          = impact,
            recommendations = recs,
            severity        = severity,
            metrics         = metrics,
        )

    def msa_insight(
        self, result: Dict[str, Any]
    ) -> Optional[AnalysisInsight]:
        """Interpreta resultado de MSA / Gauge R&R."""
        grr_pct   = result.get("grr_pct") or result.get("gauge_rr_pct")
        repeat_pct = result.get("repeatability_pct")
        repro_pct  = result.get("reproducibility_pct")

        if grr_pct is None:
            return None

        metrics = {"grr_pct": grr_pct, "repeatability": repeat_pct, "reproducibility": repro_pct}

        if grr_pct > 30:
            severity = "critical"
            interp = (
                rf"O estudo de Gauge R\&R indica que \textbf{{{_f(grr_pct, 1)}\% "
                r"da variabilidade total}} \'{{e}} atribu\'ida ao sistema de "
                r"medi\c{c}\~{a}o. Valores acima de 30\% indicam sistema de "
                r"medi\c{c}\~{a}o \textbf{inaceit\'{{a}}vel} (AIAG MSA, 4\textordfeminine{} ed.). "
                r"Os dados coletados com este sistema n\~{a}o s\~{a}o confi\'{{a}}veis "
                r"para tomada de decis\~{a}o."
            )
            impact = (
                r"Decis\~{o}es baseadas nesses dados est\~{a}o sujeitas a erros "
                r"significativos. An\'{{a}}lises de capacidade e cartas de controle "
                r"s\~{a}o comprometidas pela incerteza do sistema de medi\c{c}\~{a}o."
            )
            recs = [
                r"Revisar e recalibrar o sistema de medi\c{c}\~{a}o imediatamente",
                r"Investigar fontes de variabilidade do equipamento (repetibilidade)",
                r"Treinar operadores no procedimento correto de medi\c{c}\~{a}o (reprodutibilidade)",
                r"N\~{a}o utilizar os dados atuais para decis\~{o}es cr\'iticas at\'{{e}} a corre\c{c}\~{a}o",
            ]
        elif grr_pct > 10:
            severity = "warning"
            interp = (
                rf"O estudo de Gauge R\&R indica \textbf{{{_f(grr_pct, 1)}\%}} "
                r"de variabilidade atribu\'ida ao sistema de medi\c{c}\~{a}o. "
                r"A AIAG classifica valores entre 10\% e 30\% como \textbf{marginalmente "
                r"aceit\'{{a}}vel}, dependendo da aplica\c{c}\~{a}o. "
                r"Melhorias no sistema de medi\c{c}\~{a}o s\~{a}o recomendadas."
            )
            impact = (
                r"Incerteza de medi\c{c}\~{a}o moderada. Pode mascarar melhorias "
                r"reais no processo e gerar falsas detec\c{c}\~{o}es nas cartas de controle."
            )
            recs = [
                r"Investigar a principal fonte de varia\c{c}\~{a}o do sistema de medi\c{c}\~{a}o",
                r"Padronizar o m\'{{e}}todo de medi\c{c}\~{a}o entre operadores",
                r"Avaliar substitui\c{c}\~{a}o ou recalibra\c{c}\~{a}o do equipamento",
            ]
        else:
            severity = "info"
            interp = (
                rf"O estudo de Gauge R\&R indica \textbf{{{_f(grr_pct, 1)}\%}} "
                r"de variabilidade atribu\'ida ao sistema de medi\c{c}\~{a}o. "
                r"Valor abaixo de 10\% classifica o sistema como \textbf{aceit\'{{a}}vel} "
                r"(AIAG MSA, 4\textordfeminine{} ed.). Os dados de medi\c{c}\~{a}o "
                r"s\~{a}o confi\'{{a}}veis para an\'{{a}}lises e decis\~{o}es de processo."
            )
            impact = (
                r"Sistema de medi\c{c}\~{a}o adequado. As varia\c{c}\~{o}es "
                r"observadas no processo refletem a realidade do processo, "
                r"n\~{a}o artefatos de medi\c{c}\~{a}o."
            )
            recs = [
                r"Manter calibra\c{c}\~{a}o peri\'{{o}}dica do sistema de medi\c{c}\~{a}o",
                r"Documentar o procedimento de medi\c{c}\~{a}o aprovado (POP)",
            ]

        return AnalysisInsight(
            analysis_type   = "msa",
            title           = r"Sistema de Medi\c{c}\~{a}o (Gauge R\&R)",
            interpretation  = interp,
            impact          = impact,
            recommendations = recs,
            severity        = severity,
            metrics         = metrics,
        )

    def fmea_insight(
        self, result: Dict[str, Any]
    ) -> Optional[AnalysisInsight]:
        """Interpreta resultado de FMEA / RPN."""
        high_rpn    = result.get("high_rpn_items") or result.get("critical_items", [])
        max_rpn     = result.get("max_rpn") or result.get("highest_rpn")
        mean_rpn    = result.get("mean_rpn") or result.get("avg_rpn")
        n_critical  = result.get("n_critical") or len(high_rpn) if high_rpn else 0

        if max_rpn is None and not high_rpn:
            return None

        metrics = {"max_rpn": max_rpn, "mean_rpn": mean_rpn, "n_critical": n_critical}

        if max_rpn and max_rpn >= 200:
            severity = "critical"
            interp = (
                rf"A an\'{{a}}lise FMEA identificou \textbf{{RPN m\'{{a}}ximo de {_f(max_rpn, 0)}}}, "
                r"indicando modos de falha cr\'iticos com alto risco de ocorr\^{e}ncia. "
                r"RPN $\geq 200$ requer a\c{c}\~{a}o corretiva imediata segundo as "
                r"diretrizes da AIAG FMEA (5\textordfeminine{} ed., 2019)."
            )
            impact = (
                r"Risco elevado de falha com impacto significativo em seguran\c{c}a, "
                r"qualidade ou custo. A\c{c}\~{a}o imediata \'{{e}} necess\'{{a}}ria "
                r"para mitigar os modos de falha cr\'iticos."
            )
            recs = [
                r"Priorizar a\c{c}\~{o}es corretivas para os modos de falha com maior RPN",
                r"Implementar controles de detec\c{c}\~{a}o adicionais para falhas cr\'iticas",
                r"Revisar o projeto/processo para reduzir a probabilidade de ocorr\^{e}ncia",
                r"Estabelecer plano de monitoramento e resposta a falhas cr\'iticas",
            ]
        elif max_rpn and max_rpn >= 100:
            severity = "warning"
            interp = (
                rf"A FMEA identificou \textbf{{RPN m\'{{a}}ximo de {_f(max_rpn, 0)}}}, "
                r"com modos de falha que requerem aten\c{c}\~{a}o. "
                r"RPN entre 100 e 200 indica risco significativo que deve ser "
                r"monitorado e mitigado no planejamento de qualidade."
            )
            impact = (
                r"Modos de falha identificados com potencial de impacto no produto "
                r"ou processo. Plano de a\c{c}\~{a}o preventiva recomendado."
            )
            recs = [
                r"Desenvolver plano de a\c{c}\~{a}o para os modos de falha com RPN > 100",
                r"Melhorar os controles de detec\c{c}\~{a}o existentes",
                r"Reavaliar o FMEA ap\'{{o}}s implementa\c{c}\~{a}o das melhorias",
            ]
        else:
            severity = "info"
            interp = (
                r"A FMEA indica n\'iveis de RPN dentro de faixas aceit\'{{a}}veis, "
                r"sem modos de falha cr\'iticos imediatos. O processo apresenta "
                r"bom n\'ivel de contr\\ole de riscos."
            )
            impact = (
                r"Risco controlado. Manuten\c{c}\~{a}o das pr\'{{a}}ticas atuais "
                r"de controle de qualidade \'{{e}} recomendada."
            )
            recs = [
                r"Manter e atualizar o FMEA periodicamente ou quando houver mudan\c{c}as no processo",
                r"Documentar as a\c{c}\~{o}es preventivas implementadas",
            ]

        return AnalysisInsight(
            analysis_type   = "fmea",
            title           = r"An\'{{a}}lise de Modo e Efeito de Falha (FMEA)",
            interpretation  = interp,
            impact          = impact,
            recommendations = recs,
            severity        = severity,
            metrics         = metrics,
        )

    def hypothesis_insight(
        self, result: Dict[str, Any]
    ) -> Optional[AnalysisInsight]:
        """Interpreta testes de hipotese."""
        tests   = result.get("tests", [])
        n_sig   = sum(1 for t in tests if isinstance(t, dict)
                      and t.get("p_value", 1) < 0.05)
        n_total = len(tests)

        if n_total == 0:
            return None

        metrics = {"n_significant": n_sig, "n_total": n_total}

        if n_sig > 0:
            severity = "warning"
            interp = (
                rf"\textbf{{{n_sig} de {n_total}}} teste(s) de hip\'{{o}}tese "
                r"revelaram diferen\c{c}as \textbf{estatisticamente significativas} "
                r"($p < 0{,}05$) entre os grupos analisados. Esses resultados "
                r"indicam que as diferen\c{c}as observadas nos dados n\~{a}o "
                r"s\~{a}o atribu\'iveis ao acaso, mas a efeitos reais que "
                r"devem ser investigados e controlados."
            )
            impact = (
                r"Diferen\c{c}as sistematicamente significativas entre grupos "
                r"sugerem fontes de variabilidade control\'{{a}}veis no processo, "
                r"como m\'{{a}}quinas, operadores, turnos ou lotes de material."
            )
            recs = [
                r"Identificar e investigar os grupos com desempenho significativamente diferente",
                r"Padronizar processos entre grupos para reduzir a variabilidade",
                r"Implementar controles espec\'ificos para os fatores identificados",
            ]
        else:
            severity = "info"
            interp = (
                rf"Os {n_total} teste(s) de hip\'{{o}}tese n\~{{a}}o revelaram "
                r"diferen\c{c}as estatisticamente significativas entre os grupos "
                r"($p \geq 0{,}05$). As varia\c{c}\~{o}es observadas s\~{a}o "
                r"consistentes com flutua\c{c}\~{o}es aleat\'{{o}}rias esperadas."
            )
            impact = (
                r"Aus\^{e}ncia de diferen\c{c}as sistem\'{{a}}ticas entre grupos. "
                r"Fontes de variabilidade adicionais podem estar presentes mas "
                r"n\~{a}o foram capturadas nesta an\'{{a}}lise."
            )
            recs = [
                r"Investigar outras fontes de variabilidade n\~{a}o inclu\'idas na an\'{{a}}lise",
                r"Aumentar o tamanho amostral para aumentar o poder estat\'istico",
            ]

        return AnalysisInsight(
            analysis_type   = "hypothesis",
            title           = r"Testes de Hip\'{{o}}tese",
            interpretation  = interp,
            impact          = impact,
            recommendations = recs,
            severity        = severity,
            metrics         = metrics,
        )
