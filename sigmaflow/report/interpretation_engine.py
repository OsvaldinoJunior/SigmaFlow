"""
sigmaflow/report/interpretation_engine.py
==========================================
Motor de interpretacao textual automatica de resultados estatisticos.

Transforma numeros brutos em linguagem academica tecnica.
Todas as strings retornadas sao LaTeX-safe (ASCII puro com comandos LaTeX).

Uso:
    from sigmaflow.report.interpretation_engine import InterpretationEngine

    ie = InterpretationEngine(dmaic_results, dataset_name="processo_x")
    text = ie.interpret_normality(norm_dict)
    text = ie.interpret_capability(cap_dict)
    text = ie.interpret_rca(rca_dict)
    text = ie.generate_abstract()
    recs = ie.generate_recommendations()
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Utilidades LaTeX-safe ────────────────────────────────────────────────────

_ACCENTS = {
    # agudo
    "á": r"\'a", "é": r"\'e", "í": r"\'i", "ó": r"\'o", "ú": r"\'u",
    "Á": r"\'A", "É": r"\'E", "Í": r"\'I", "Ó": r"\'O", "Ú": r"\'U",
    # circunflexo
    "â": r"\^a", "ê": r"\^e", "ô": r"\^o",
    "Â": r"\^A", "Ê": r"\^E", "Ô": r"\^O",
    # til
    "ã": r"\~a", "õ": r"\~o",
    "Ã": r"\~A", "Õ": r"\~O",
    # grave
    "à": r"\`a",
    # cedilha
    "ç": r"\c{c}", "Ç": r"\c{C}",
    # matematicos
    "σ": r"$\sigma$", "μ": r"$\mu$", "α": r"$\alpha$",
    "≥": r"$\geq$",   "≤": r"$\leq$",
    "±": r"$\pm$",
    # pontuacao
    "\u2013": "--", "\u2014": "---",
}


def _tex(text: str) -> str:
    """Converte string para LaTeX-safe ASCII."""
    s = str(text)
    for uni, cmd in _ACCENTS.items():
        s = s.replace(uni, cmd)
    # escapes basicos
    sentinel = "\x00BS\x00"
    s = s.replace("\\", sentinel)
    for ch, esc in [("&", r"\&"), ("%", r"\%"), ("#", r"\#"),
                    ("_", r"\_"), ("{", r"\{"), ("}", r"\}")]:
        s = s.replace(ch, esc)
    s = s.replace(sentinel, r"\textbackslash{}")
    # fallback: drop non-ASCII
    s = "".join(c if ord(c) < 128 else "?" for c in s)
    return s


def _fmt(v: Any, d: int = 3) -> str:
    if v is None:
        return "---"
    try:
        return rf"{float(v):.{d}f}"
    except (TypeError, ValueError):
        return str(v)


# ── Motor de interpretacao ────────────────────────────────────────────────────

class InterpretationEngine:
    """
    Gera interpretacoes textuais automaticas de resultados estatisticos.

    Cada metodo retorna uma ou mais strings LaTeX-safe prontas para
    insercao nos templates Jinja2.
    """

    def __init__(
        self,
        results:      Dict[str, Any],
        dataset_name: str = "processo",
        organization: str = "",
    ) -> None:
        self.r    = results
        self.name = dataset_name
        self.org  = organization
        self._meta    = results.get("metadata", {})
        self._measure = results.get("measure", {})
        self._analyze = results.get("analyze", {})
        self._improve = results.get("improve", {})
        self._summary = results.get("summary", {})

    # ── Abstract ──────────────────────────────────────────────────────────────

    def generate_abstract(self) -> str:
        n_rows  = self._meta.get("n_rows", "N/A")
        n_cols  = self._meta.get("n_columns", "N/A")
        target  = _tex(self._meta.get("primary_target", "vari\'avel-resposta"))
        dtype   = _tex(self._meta.get("dataset_type", "geral").upper())
        cap     = self._measure.get("capability", {})
        cpk     = cap.get("Cpk")
        n_ins   = self._summary.get("n_insights", 0)
        elapsed = _fmt(self.r.get("elapsed_s", 0), 1)

        cap_line = ""
        if cpk is not None:
            cap_line = (
                rf"O \'indice de capacidade $C_{{pk}} = {_fmt(cpk, 3)}$ "
                rf"classificou o processo como \\textbf{{{self.cpk_verdict(cpk)}}}. "
            )

        return (
            rf"Este relat\'orio apresenta a an\'alise estat\'istica automatizada "
            rf"do dataset \\textbf{{{_tex(self.name)}}} ({n_rows} observa\c{{c}}\~{{o}}es "
            rf"$\\times$ {n_cols} vari\'aveis, tipo: {dtype}), conduzida pelo sistema "
            rf"\\textbf{{SigmaFlow v10}} aplicando o \\textit{{framework}} DMAIC "
            rf"(\\textit{{Define, Measure, Analyze, Improve, Control}}). "
            rf"Foram aplicados testes de normalidade (Shapiro--Wilk e Anderson--Darling), "
            rf"an\'alise de capacidade do processo, Controle Estat\'istico de Processos (CEP) "
            rf"e an\'alise de correla\c{{c}}\~{{a}}o multivariada sobre a vari\'avel-resposta "
            rf"\\textbf{{{target}}}. "
            rf"{cap_line}"
            rf"No total, \\textbf{{{n_ins} \\textit{{insights}} estat\'isticos}} foram identificados "
            rf"ao longo das cinco fases do ciclo DMAIC em {elapsed} segundos de processamento."
        )

    # ── Normalidade ───────────────────────────────────────────────────────────

    def interpret_normality(self, norm: Dict[str, Any]) -> str:
        """Interpretacao completa dos resultados de normalidade."""
        if not norm or not isinstance(norm, dict):
            return (
                r"N\~{a}o foram encontrados dados de normalidade para este dataset. "
                r"Recomenda-se a aplica\c{c}\~{a}o de testes de normalidade antes "
                r"de utilizar m\'etodos param\'etricos."
            )

        n_total  = len(norm)
        n_normal = sum(
            1 for res in norm.values()
            if isinstance(res, dict) and res.get("is_normal", False)
        )

        if n_total == 0:
            return r"Nenhuma vari\'avel num\'erica identificada para teste de normalidade."

        pct_normal = round(100 * n_normal / n_total)

        if n_normal == n_total:
            return (
                r"Os resultados dos testes de Shapiro--Wilk e Anderson--Darling "
                r"indicam que \textbf{todas as vari\'aveis analisadas} seguem "
                r"distribui\c{c}\~{a}o aproximadamente normal ($p > 0{,}05$), "
                r"validando o emprego de m\'etodos param\'etricos nas an\'alises "
                r"subsequentes. Essa ader\^{e}ncia \`{a} normalidade tamb\'em "
                r"sustenta a interpreta\c{c}\~{a}o dos \'indices de capacidade "
                r"$C_p$ e $C_{pk}$, calculados sob a hip\'otese de normalidade."
            )
        elif n_normal == 0:
            return (
                r"Os resultados dos testes de normalidade indicam que \textbf{nenhuma} "
                r"das vari\'aveis analisadas segue distribui\c{c}\~{a}o normal "
                r"($p < 0{,}05$). Esse resultado sugere a presen\c{c}a de assimetria, "
                r"caudas pesadas ou outliers no conjunto de dados. "
                r"Recomenda-se fortemente a aplica\c{c}\~{a}o de m\'etodos "
                r"estat\'isticos n\~{a}o param\'etricos (Mann--Whitney, Kruskal--Wallis) "
                r"para compara\c{c}\~{o}es entre grupos, bem como transforma\c{c}\~{o}es "
                r"Box--Cox ou Johnson para normaliza\c{c}\~{a}o dos dados antes "
                r"de calcular \'indices de capacidade."
            )
        else:
            non_normal = n_total - n_normal
            return (
                rf"Dos {n_total} vari\'aveis testadas, \\textbf{{{n_normal} "
                rf"({pct_normal}\\%)}} apresentaram ader\\^{{e}}ncia \\`{{a}} "
                rf"distribui\\c{{c}}\\~{{a}}o normal ($p > 0{{,}}05$), enquanto "
                rf"\\textbf{{{non_normal}}} tiveram a hip\'otese de normalidade "
                rf"rejeitada ao n\'ivel de signific\\^{{a}}ncia de 5\\%. "
                rf"Para as vari\'aveis n\\~{{a}}o normais, recomenda-se o emprego "
                rf"de m\'etodos n\\~{{a}}o param\'etricos ou transforma\\c{{c}}\\~{{o}}es "
                rf"de estabiliza\\c{{c}}\\~{{a}}o de vari\\^{{a}}ncia (Box--Cox, "
                rf"log, ra\\'{z} quadrada)."
            )

    # ── Capacidade ────────────────────────────────────────────────────────────

    def interpret_capability(self, cap: Dict[str, Any]) -> str:
        """Interpretacao profunda dos indices de capacidade."""
        if not cap or cap.get("Cpk") is None:
            return (
                r"\'Indices de capacidade n\~{a}o dispon\'iveis para este dataset. "
                r"Para calcular $C_p$ e $C_{pk}$, \'e necess\'ario informar os "
                r"limites de especifica\c{c}\~{a}o (USL e LSL) do processo."
            )

        cpk      = cap.get("Cpk")
        cp       = cap.get("Cp")
        dpmo     = cap.get("dpmo", 0)
        sigma_lv = cap.get("sigma_level", 0)
        verdict  = self.cpk_verdict(cpk)

        base = (
            rf"O \'indice $C_{{pk}} = {_fmt(cpk, 3)}$ classifica o processo como "
            rf"\\textbf{{{verdict}}}. "
        )

        if cp and cpk:
            diff = cp - cpk
            if diff > 0.2:
                base += (
                    rf"A diferen\\c{{c}}a entre $C_p = {_fmt(cp, 3)}$ e $C_{{pk}} = {_fmt(cpk, 3)}$ "
                    rf"(\\Delta = {_fmt(diff, 3)}) indica que o processo, embora possua "
                    rf"variabilidade compat\'ivel com as especifica\\c{{c}}\\~{{o}}es, "
                    rf"apresenta descentramento da m\'edia em rela\\c{{c}}\\~{{a}}o ao alvo. "
                    rf"A\\c{{c}}\\~{{o}}es de recentramento devem ser priorizadas antes "
                    rf"de investir na redu\\c{{c}}\\~{{a}}o de variabilidade. "
                )

        if dpmo:
            base += (
                rf"A taxa de defeitos estimada \'e de \\textbf{{{dpmo:,.0f} DPMO}} "
                rf"(Defeitos Por Milh\\~{{a}}o de Oportunidades), correspondendo a "
                rf"um n\'ivel sigma de {_fmt(sigma_lv, 2)}$\\sigma$. "
            )

        if cpk < 1.0:
            base += (
                r"Esse resultado evidencia a \textbf{necessidade urgente} de "
                r"interven\c{c}\~{o}es no processo. Segundo Montgomery (2009), "
                r"processos com $C_{pk} < 1{,}00$ apresentam probabilidade "
                r"elevada de gera\c{c}\~{a}o de n\~{a}o conformidades e "
                r"requerem investiga\c{c}\~{a}o imediata de causas especiais "
                r"de varia\c{c}\~{a}o."
            )
        elif cpk < 1.33:
            base += (
                r"Embora o processo atenda minimamente aos requisitos, a margem "
                r"de seguran\c{c}a \'e insuficiente para garantir consist\^{e}ncia "
                r"a longo prazo. O padr\~{a}o industrial m\'inimo aceito \'e "
                r"$C_{pk} \geq 1{,}33$ (Montgomery, 2009). Recomenda-se "
                r"monitoramento intensivo e plano de a\c{c}\~{a}o para melhoria."
            )
        elif cpk < 1.67:
            base += (
                r"O processo atende ao padr\~{a}o industrial m\'inimo "
                r"($C_{pk} \geq 1{,}33$). O monitoramento cont\'inuo por "
                r"cartas de controle \'e recomendado para garantir a "
                r"manuten\c{c}\~{a}o desse desempenho ao longo do tempo."
            )
        else:
            base += (
                r"O processo demonstra desempenho excelente, atingindo "
                r"o padr\~{a}o Six Sigma ($C_{pk} \geq 1{,}67$). "
                r"Manter o monitoramento peri\'odico e as boas pr\'aticas "
                r"operacionais vigentes \'e suficiente para sustentar esse n\'ivel."
            )

        return base

    # ── Testes de hipotese ────────────────────────────────────────────────────

    def interpret_hypothesis(self, hyp: Dict[str, Any]) -> str:
        """Interpretacao dos testes de hipotese."""
        if not hyp or not isinstance(hyp, dict):
            return ""

        significant = [
            name for name, res in hyp.items()
            if isinstance(res, dict) and res.get("p_value", 1.0) < 0.05
        ]
        not_sig = [
            name for name, res in hyp.items()
            if isinstance(res, dict) and res.get("p_value", 1.0) >= 0.05
        ]

        if not significant and not not_sig:
            return ""

        parts = []
        if significant:
            names = ", ".join(
                rf"\\textit{{{_tex(n.replace('_', ' ').title())}}}"
                for n in significant[:3]
            )
            parts.append(
                rf"Os testes {names} revelaram \\textbf{{diferen\\c{{c}}a "
                rf"estatisticamente significativa}} ($p < 0{{,}}05$), "
                rf"indicando que as popula\\c{{c}}\\~{{o}}es comparadas "
                rf"apresentam caracter\'isticas distribicionais distintas. "
                rf"Esse resultado deve orientar a sele\\c{{c}}\\~{{a}}o de "
                rf"m\'etodos de an\'alise n\\~{{a}}o param\'etricos ou a "
                rf"estratifica\\c{{c}}\\~{{a}}o dos dados por grupo."
            )
        if not_sig:
            names = ", ".join(
                rf"\\textit{{{_tex(n.replace('_', ' ').title())}}}"
                for n in not_sig[:3]
            )
            parts.append(
                rf"Para os testes {names}, n\\~{{a}}o foi poss\'ivel rejeitar "
                rf"a hip\'otese nula ($p \\geq 0{{,}}05$), sugerindo "
                rf"aus\\^{{e}}ncia de evid\\^{{e}}ncia estat\'istica de "
                rf"diferen\\c{{c}}a entre os grupos analisados."
            )

        return " ".join(parts)

    # ── Causa raiz ────────────────────────────────────────────────────────────

    def interpret_rca(self, rca: Dict[str, Any]) -> str:
        """Interpretacao da analise de causa raiz."""
        if not rca or rca.get("error") or not rca.get("ranked_variables"):
            return (
                r"An\'alise de correla\c{c}\~{a}o multivariada n\~{a}o dispon\'ivel "
                r"para este tipo de dataset (insufici\^{e}ncia de vari\'aveis "
                r"num\'ericas ou tipo de dados n\~{a}o compat\'ivel)."
            )

        target  = _tex(rca.get("target_col", "vari\'avel-resposta"))
        ranked  = rca.get("ranked_variables", [])
        strong  = [v for v in ranked if abs(v.get("pearson_r", 0)) >= 0.70]
        moderate = [v for v in ranked if 0.50 <= abs(v.get("pearson_r", 0)) < 0.70]
        weak    = [v for v in ranked if abs(v.get("pearson_r", 0)) < 0.50]

        parts = [
            rf"A an\'alise de correla\c{{c}}\\~{{a}}o multivariada identificou "
            rf"{len(ranked)} vari\'aveis preditoras da resposta "
            rf"\\textbf{{{target}}}. "
        ]

        if strong:
            names = ", ".join(rf"\\textbf{{{_tex(v['variable'])}}}" for v in strong[:3])
            top_r = _fmt(strong[0].get("pearson_r", 0), 3)
            parts.append(
                rf"As vari\'aveis {names} apresentaram \\textbf{{correla\c{{c}}\\~{{a}}o "
                rf"forte}} ($|r| \\geq 0{{,}}70$, m\'ax: $r = {top_r}$), "
                rf"constituindo os \\textbf{{candidatos priorit\'arios a causas raiz}}. "
                rf"Interven\c{{c}}\\~{{o}}es nesses fatores t\\^{{e}}m o maior "
                rf"potencial de impacto na qualidade do processo. "
            )

        if moderate:
            names = ", ".join(rf"\\textbf{{{_tex(v['variable'])}}}" for v in moderate[:2])
            parts.append(
                rf"As vari\'aveis {names} demonstraram \\textbf{{correla\c{{c}}\\~{{a}}o "
                rf"moderada}} ($0{{,}}50 \\leq |r| < 0{{,}}70$), devendo ser "
                rf"inclu\'idas no planejamento de experimentos controlados (DOE) "
                rf"para confirma\c{{c}}\\~{{a}}o do efeito causal. "
            )

        parts.append(
            r"Ressalta-se que correla\c{c}\~{a}o estat\'istica n\~{a}o implica "
            r"necessariamente rela\c{c}\~{a}o causal. A conduc\~{a}o de "
            r"experimentos controlados (Montgomery; Runger, 2014) \'e "
            r"recomendada para confirmar as hip\'oteses levantadas."
        )

        return " ".join(parts)

    # ── SPC / anomalias ───────────────────────────────────────────────────────

    def interpret_spc_violations(self, insights: List[Dict]) -> str:
        """Interpretacao das violacoes detectadas nas cartas de controle."""
        violations = [
            ins for ins in insights
            if isinstance(ins, dict) and ins.get("severity") == "critical"
        ]

        if not violations:
            return (
                r"O processo n\~{a}o apresentou viola\c{c}\~{o}es das regras "
                r"de controle de Western Electric durante o per\'iodo analisado, "
                r"indicando aus\^{e}ncia de causas especiais de varia\c{c}\~{a}o "
                r"detectadas estatisticamente."
            )

        n = len(violations)
        return (
            rf"Foram detectadas \\textbf{{{n} viola\\c{{c}}\\~{{o}}es}} das regras "
            rf"de controle estat\'istico do processo (Western Electric Rules). "
            rf"Esses eventos sinalizam \\textbf{{causas especiais de varia\\c{{c}}\\~{{a}}o}} "
            rf"que devem ser investigadas de forma imediata pela equipe de processo. "
            rf"A presen\\c{{c}}a de causas especiais invalida a interpreta\\c{{c}}\\~{{a}}o "
            rf"dos \'indices de capacidade $C_p$ e $C_{{pk}}$, pois esses "
            rf"press-up\\~{{o}}em processo sob controle estat\'istico."
        )

    # ── Recomendacoes automaticas ─────────────────────────────────────────────

    def generate_recommendations(self) -> List[Dict[str, str]]:
        """
        Gera lista de recomendacoes automaticas baseadas nos resultados.
        Cada item: {'category': str, 'action': str, 'priority': int}
        """
        recs = []
        cap  = self._measure.get("capability", {})
        norm = self._measure.get("normality", {})
        rca  = self._analyze.get("root_cause", {})
        ins  = self.r.get("structured_insights", [])

        cpk = cap.get("Cpk")

        # Regra 1: Cpk < 1.0
        if cpk is not None and cpk < 1.0:
            recs.append({
                "category": "Capacidade do Processo",
                "action": (
                    r"Investigar causas especiais de varia\c{c}\~{a}o imediatamente. "
                    "Implementar carta de controle XmR para monitoramento cont\'inuo. "
                    rf"Meta: elevar $C_{{pk}}$ de {_fmt(cpk, 3)} para $\\geq 1{{,}}33$."
                ),
                "priority": 1,
            })

        # Regra 2: Cpk < 1.33 (marginal)
        elif cpk is not None and cpk < 1.33:
            recs.append({
                "category": "Melhoria de Capacidade",
                "action": (
                    "Realizar estudo de variabilidade para identificar as principais "
                    r"fontes de varia\c{c}\~{a}o. Considerar DOE para otimiza\c{c}\~{a}o "
                    rf"do processo. Meta: $C_{{pk}} \\geq 1{{,}}33$."
                ),
                "priority": 2,
            })

        # Regra 3: sem normalidade
        n_not_normal = sum(
            1 for res in norm.values()
            if isinstance(res, dict) and not res.get("is_normal", True)
        ) if isinstance(norm, dict) else 0

        if n_not_normal > 0:
            recs.append({
                "category": "Tratamento de Dados",
                "action": (
                    rf"{n_not_normal} vari\'avel(is) n\~{{a}}o seguem distribui\c{{c}}\\~{{a}}o "
                    r"normal. Aplicar transforma\c{c}\~{o}es Box--Cox ou m\'etodos "
                    r"n\~{a}o param\'etricos (Kruskal--Wallis, Mann--Whitney) para "
                    r"an\'alises comparativas."
                ),
                "priority": 3,
            })

        # Regra 4: causa raiz identificada
        ranked = rca.get("ranked_variables", [])
        strong = [v for v in ranked if abs(v.get("pearson_r", 0)) >= 0.70]
        if strong:
            top = strong[0]
            recs.append({
                "category": "Experimento Controlado (DOE)",
                "action": (
                    rf"A vari\'avel \\textbf{{{_tex(top['variable'])}}} apresentou "
                    rf"correla\c{{c}}\\~{{a}}o forte ($r = {_fmt(top.get('pearson_r'), 3)}$). "
                    r"Conduzir experimento fatorial (2k) para confirmar causalidade "
                    r"e definir janelas operacionais \'otimas."
                ),
                "priority": 4,
            })

        # Regra 5: alta variabilidade
        n_critical = sum(
            1 for i in ins
            if isinstance(i, dict) and i.get("severity") == "critical"
        )
        if n_critical > 2:
            recs.append({
                "category": "Controle de Processo",
                "action": (
                    rf"{n_critical} achados cr\'iticos detectados. "
                    r"Implementar programa de manuten\c{c}\~{a}o preventiva e "
                    r"revisar procedimentos operacionais padr\~{a}o (POP) para "
                    r"reduzir causas comuns de varia\c{c}\~{a}o."
                ),
                "priority": 5,
            })

        # Regra 6: sempre — monitoramento
        recs.append({
            "category": "Monitoramento Cont\'inuo",
            "action": (
                r"Implementar dashboard de indicadores em tempo real com "
                r"alertas autom\'aticos para desvios das cartas de controle. "
                r"Revisar os limites de controle a cada 25 novos subgrupos."
            ),
            "priority": 6,
        })

        return sorted(recs, key=lambda x: x["priority"])

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def cpk_verdict(cpk: float) -> str:
        if cpk >= 1.67:
            return r"excelente (n\'ivel Six Sigma)"
        if cpk >= 1.33:
            return r"aceit\'avel (padr\~{a}o industrial m\'inimo)"
        if cpk >= 1.00:
            return r"marginal (monitoramento intensivo necess\'ario)"
        return r"incapaz (a\c{c}\~{a}o corretiva urgente)"

    @staticmethod
    def cpk_color(cpk: float) -> str:
        if cpk >= 1.33:
            return "info"
        if cpk >= 1.00:
            return "aviso"
        return "critico"
