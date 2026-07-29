"""
sigmaflow/insights/recommendation_engine.py
=============================================
RecommendationEngine — consolida todos os insights e gera:

  1. Executive Summary automatico (LaTeX-safe, portugues)
  2. Lista priorizada de recomendacoes por categoria e urgencia
  3. Avaliacao de risco geral do processo

Recebe a lista de AnalysisInsight gerada pelo InsightEngine e
produz um dict pronto para ser consumido pelos templates Jinja2.

Uso:
    from sigmaflow.insights.insight_engine       import InsightEngine
    from sigmaflow.insights.recommendation_engine import RecommendationEngine

    insights = InsightEngine().generate(engine_result)
    rec_eng  = RecommendationEngine(engine_result, insights)
    summary  = rec_eng.executive_summary()
    recs     = rec_eng.prioritized_recommendations()
    risk     = rec_eng.risk_level()
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Nivel de risco global ─────────────────────────────────────────────────────

_RISK_LABELS = {
    "critical": r"ELEVADO --- A\c{c}\~{a}o Imediata Necess\'{{a}}ria",
    "warning":  r"MODERADO --- Monitoramento Intensificado",
    "info":     r"BAIXO --- Processo Sob Controle",
}

_RISK_COLORS = {
    "critical": "corCritico",
    "warning":  "corAviso",
    "info":     "corInfo",
}


class RecommendationEngine:
    """
    Consolida insights e gera executive summary e recomendacoes priorizadas.

    Parameters
    ----------
    engine_result : dict
        Um elemento da lista retornada por Engine.run().
    insights : list[AnalysisInsight]
        Lista gerada por InsightEngine.generate().
    """

    def __init__(
        self,
        engine_result: Dict[str, Any],
        insights: List[Any],
    ) -> None:
        self.result   = engine_result
        self.insights = insights
        self._name    = engine_result.get("name", "dataset")
        self._dtype   = engine_result.get("dataset_type", "geral")
        self._shape   = engine_result.get("shape") or (0, 0)

    # ── API publica ───────────────────────────────────────────────────────────

    def risk_level(self) -> str:
        """Retorna 'critical', 'warning', ou 'info'."""
        severities = [i.severity for i in self.insights]
        if "critical" in severities:
            return "critical"
        if "warning" in severities:
            return "warning"
        return "info"

    def risk_label(self) -> str:
        """Retorna o label LaTeX-safe do nivel de risco."""
        return _RISK_LABELS.get(self.risk_level(), "INDETERMINADO")

    def risk_color(self) -> str:
        """Retorna o nome da cor LaTeX para o nivel de risco."""
        return _RISK_COLORS.get(self.risk_level(), "black")

    def executive_summary(self) -> str:
        """
        Gera o texto do Executive Summary em portugues, LaTeX-safe.

        O resumo destaca:
        - dimensoes do dataset
        - problemas detectados
        - principais riscos
        - conclusao com orientacao de acao
        """
        risk    = self.risk_level()
        n_rows  = self._shape[0] if self._shape else "N/D"
        n_cols  = self._shape[1] if len(self._shape) > 1 else "N/D"
        name    = self._name
        dtype   = self._dtype.upper()

        n_critical = sum(1 for i in self.insights if i.severity == "critical")
        n_warning  = sum(1 for i in self.insights if i.severity == "warning")
        n_info     = sum(1 for i in self.insights if i.severity == "info")
        n_total    = len(self.insights)

        # Capability summary
        cap_text = ""
        for ins in self.insights:
            if ins.analysis_type == "capability" and ins.metrics.get("Cpk") is not None:
                cpk = ins.metrics["Cpk"]
                if cpk < 1.00:
                    cap_text = (
                        rf"O \'indice de capacidade $C_{{pk}} = {cpk:.3f}$ "
                        r"classifica o processo como \textbf{incapaz}, com risco "
                        r"elevado de gera\c{c}\~{a}o de n\~{a}o conformidades. "
                    )
                elif cpk < 1.33:
                    cap_text = (
                        rf"O \'indice de capacidade $C_{{pk}} = {cpk:.3f}$ "
                        r"classifica o processo como \textbf{marginalmente capaz}. "
                    )
                elif cpk >= 1.67:
                    cap_text = (
                        rf"O processo apresenta excelente capacidade ($C_{{pk}} = {cpk:.3f}$), "
                        r"atingindo o n\'ivel Six Sigma. "
                    )
                break

        # SPC summary
        spc_text = ""
        for ins in self.insights:
            if ins.analysis_type == "spc":
                n_ooc = ins.metrics.get("out_of_control_points", 0)
                if n_ooc > 0:
                    spc_text = (
                        rf"A an\'{{a}}lise de controle estat\'istico detectou "
                        rf"\textbf{{{n_ooc} ponto(s) fora de controle}}, "
                        r"indicando instabilidade no processo. "
                    )
                else:
                    spc_text = (
                        r"O processo encontra-se \textbf{em controle estat\'istico}. "
                    )
                break

        # RCA summary
        rca_text = ""
        for ins in self.insights:
            if ins.analysis_type == "root_cause":
                n_strong = ins.metrics.get("n_strong", 0)
                if n_strong > 0:
                    rca_text = (
                        rf"Foram identificadas \textbf{{{n_strong} vari\'{{a}}vel(is) "
                        r"com correla\c{c}\~{a}o forte}} como candidatas a causas raiz. "
                    )
                break

        # Opening sentence
        opening = (
            rf"A an\'{{a}}lise autom\'{{a}}tica do SigmaFlow v10 processou o dataset "
            rf"\textbf{{{name}}} "
            rf"({n_rows} observa\c{{c}}\~{{o}}es $\times$ {n_cols} vari\'{{a}}veis, "
            rf"tipo: \textbf{{{dtype}}}) "
            r"aplicando o framework DMAIC completo. "
        )

        # Findings
        findings = cap_text + spc_text + rca_text

        # Insights summary
        if n_total > 0:
            insight_summary = (
                rf"Ao todo, \textbf{{{n_total} insight(s)}} foram gerados: "
                + (rf"\textcolor{{corCritico}}{{\textbf{{{n_critical} cr\'itico(s)}}}}, "
                   if n_critical else "")
                + (rf"\textcolor{{corAviso}}{{\textbf{{{n_warning} aviso(s)}}}}, "
                   if n_warning else "")
                + (rf"\textcolor{{corInfo}}{{{n_info} informativo(s)}}"
                   if n_info else "")
                + ". "
            )
        else:
            insight_summary = ""

        # Closing action
        if risk == "critical":
            closing = (
                r"\textbf{A\c{c}\~{a}o imediata \'{{e}} recomendada.} "
                r"Os achados cr\'iticos identificados requerem investiga\c{c}\~{a}o "
                r"e interven\c{c}\~{a}o urgente para prevenir impacto negativo "
                r"na qualidade do produto ou servi\c{c}o."
            )
        elif risk == "warning":
            closing = (
                r"\textbf{Monitoramento intensificado e plano de a\c{c}\~{a}o s\~{a}o recomendados.} "
                r"Os avisos identificados indicam oportunidades de melhoria que devem "
                r"ser endere\c{c}adas no planejamento de qualidade."
            )
        else:
            closing = (
                r"O processo apresenta desempenho satisfat\'{{o}}rio. "
                r"\textbf{Manuten\c{c}\~{a}o das pr\'{{a}}ticas atuais e monitoramento "
                r"cont\'inuo s\~{a}o recomendados} para sustentar o n\'ivel "
                r"de qualidade alcan\c{c}ado."
            )

        return opening + findings + insight_summary + closing

    def prioritized_recommendations(self) -> List[Dict[str, Any]]:
        """
        Gera lista consolidada de recomendacoes priorizadas.

        Cada item: {
            'priority' : int,
            'category' : str (LaTeX-safe),
            'action'   : str (LaTeX-safe),
            'severity' : str,
            'source'   : str (analysis_type),
        }
        """
        recs: List[Dict[str, Any]] = []
        priority = 1

        # Critical insights first
        for ins in self.insights:
            if ins.severity == "critical":
                for rec_text in ins.recommendations[:2]:  # top 2 per insight
                    recs.append({
                        "priority": priority,
                        "category": ins.title,
                        "action":   rec_text,
                        "severity": "critical",
                        "source":   ins.analysis_type,
                    })
                    priority += 1

        # Warning insights
        for ins in self.insights:
            if ins.severity == "warning":
                for rec_text in ins.recommendations[:2]:
                    recs.append({
                        "priority": priority,
                        "category": ins.title,
                        "action":   rec_text,
                        "severity": "warning",
                        "source":   ins.analysis_type,
                    })
                    priority += 1

        # Info insights (top 1 each)
        for ins in self.insights:
            if ins.severity == "info" and ins.recommendations:
                recs.append({
                    "priority": priority,
                    "category": ins.title,
                    "action":   ins.recommendations[0],
                    "severity": "info",
                    "source":   ins.analysis_type,
                })
                priority += 1

        # Always: continuous monitoring
        recs.append({
            "priority": priority,
            "category": r"Monitoramento Cont\'inuo",
            "action": (
                r"Implementar dashboard de indicadores com alertas autom\'{{a}}ticos "
                r"para desvios das cartas de controle. "
                r"Revisar os limites de controle a cada 25 novos subgrupos."
            ),
            "severity": "info",
            "source": "general",
        })

        return recs

    def as_report_context(self) -> Dict[str, Any]:
        """
        Retorna dict completo pronto para o template Jinja2
        da secao 'executive_summary' e 'insights'.
        """
        recs    = self.prioritized_recommendations()
        risk    = self.risk_level()

        n_critical = sum(1 for i in self.insights if i.severity == "critical")
        n_warning  = sum(1 for i in self.insights if i.severity == "warning")

        return {
            "executive_summary": {
                "text":          self.executive_summary(),
                "risk_level":    risk,
                "risk_label":    self.risk_label(),
                "risk_color":    self.risk_color(),
                "n_insights":    len(self.insights),
                "n_critical":    n_critical,
                "n_warning":     n_warning,
                "has_critical":  n_critical > 0,
                "has_warning":   n_warning > 0,
            },
            "key_insights": {
                "insights": [i.as_dict() for i in self.insights],
                "has_insights": bool(self.insights),
                "recommendations": recs,
                "has_recommendations": bool(recs),
                "n_total": len(self.insights),
            },
        }
