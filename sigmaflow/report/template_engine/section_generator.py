"""
sigmaflow/report/template_engine/section_generator.py
=======================================================
Gerador de conteúdo LaTeX acadêmico para cada seção do relatório DMAIC.

Cada método público retorna uma string LaTeX pronta para ser inserida
num arquivo .tex via TemplateManager.set().

Estilo de escrita:
    - Linguagem técnica e acadêmica em português
    - Parágrafos completos com interpretação dos resultados
    - Evita frases curtas ou telegráficas
    - Usa terminologia Six Sigma / DMAIC correta

Uso:
    from sigmaflow.report.template_engine.section_generator import SectionGenerator

    gen = SectionGenerator(dmaic_results, dataset_name="processo_xyz")
    intro       = gen.introducao()
    metodologia = gen.metodologia()
    analise     = gen.analise_estatistica()
    resultados  = gen.resultados()
    discussao   = gen.discussao()
    conclusao   = gen.conclusao()
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Utilitários internos ──────────────────────────────────────────────────────

def _e(text: Any) -> str:
    """Escapa caracteres especiais LaTeX e converte unicode para comandos LaTeX."""
    s = str(text)
    _SENTINEL = "\x00BS\x00"
    s = s.replace("\\", _SENTINEL)
    for ch, esc in [
        ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
        ("_", r"\_"), ("{", r"\{"), ("}", r"\}"),
        ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}"),
    ]:
        s = s.replace(ch, esc)
    s = s.replace(_SENTINEL, r"\textbackslash{}")
    # Unicode → LaTeX (caracteres comuns em outputs estatísticos)
    _UMAP = {
        "σ": r"\(\sigma\)", "μ": r"\(\mu\)", "α": r"\(\alpha\)",
        "β": r"\(\beta\)",  "δ": r"\(\delta\)", "ε": r"\(\varepsilon\)",
        "≥": r"\(\geq\)",   "≤": r"\(\leq\)",   "≠": r"\(\neq\)",
        "±": r"\(\pm\)",    "×": r"\(\times\)",  "≈": r"\(\approx\)",
        "→": r"\(\rightarrow\)", "∞": r"\(\infty\)",
        "–": "--", "—": "---", "…": r"\ldots{}",
        "\u00a0": "~",
    }
    for uni, cmd in _UMAP.items():
        s = s.replace(uni, cmd)
    # Fallback: remove qualquer outro não-ASCII que reste
    s = "".join(c if ord(c) < 128 else "?" for c in s)
    return s


def _fmt(v: Any, decimals: int = 4) -> str:
    """Formata números para exibição no texto."""
    if v is None:
        return "---"
    if isinstance(v, float):
        return f"{v:.{decimals}f}"
    return str(v)


def _cap_color(cpk: float) -> str:
    if cpk >= 1.67:
        return "info"
    if cpk >= 1.33:
        return "info"
    if cpk >= 1.00:
        return "aviso"
    return "critico"


def _cap_verdict(cpk: float) -> str:
    if cpk >= 1.67:
        return "excelente (nível Six Sigma)"
    if cpk >= 1.33:
        return "aceitável, atendendo ao padrão industrial mínimo de 1,33"
    if cpk >= 1.00:
        return "marginal, requerendo monitoramento contínuo e ações preventivas"
    return "insatisfatório, indicando que o processo não é capaz de atender " \
           "consistentemente às especificações definidas"


class SectionGenerator:
    """
    Gera conteúdo LaTeX acadêmico para cada seção do relatório DMAIC.

    Parameters
    ----------
    results : dict
        Saída do DMAICEngine.run() ou Engine.run() (lista de dicts).
    dataset_name : str
        Nome do dataset analisado.
    organization : str, optional
        Nome da organização / equipe responsável.
    """

    def __init__(
        self,
        results: Dict[str, Any],
        dataset_name: str = "processo",
        organization: str = "",
    ) -> None:
        self.r            = results
        self.name         = dataset_name
        self.org          = organization
        self._meta        = results.get("metadata", {})
        self._measure     = results.get("measure", {})
        self._analyze     = results.get("analyze", {})
        self._improve     = results.get("improve", {})
        self._control     = results.get("control", {})
        self._define      = results.get("define", {})
        self._summary     = results.get("summary", {})

    # ── Seção 1: Introdução ───────────────────────────────────────────────────

    def introducao(self) -> str:
        n_rows   = self._meta.get("n_rows", "N/A")
        n_cols   = self._meta.get("n_columns", "N/A")
        target   = self._meta.get("primary_target", "variável-resposta")
        n_num    = len(self._meta.get("numeric_columns", []))
        n_cat    = len(self._meta.get("categorical_columns", []))
        elapsed  = _fmt(self.r.get("elapsed_s", 0), 2)

        return rf"""O presente relatório documenta os resultados de uma análise estatística
automatizada conduzida pelo sistema SigmaFlow, aplicando o \textit{{framework}}
DMAIC (\textit{{Define, Measure, Analyze, Improve, Control}}) ao conjunto de
dados denominado \textbf{{{_e(self.name)}}}. O DMAIC constitui a metodologia
estruturada de resolução de problemas do Lean Six Sigma, amplamente utilizada
em projetos de melhoria de processos industriais, de serviços e logísticos
(Montgomery, 2009).

O dataset submetido à análise é composto por \textbf{{{_e(n_rows)} observações}}
e \textbf{{{_e(n_cols)} variáveis}}, das quais {_e(n_num)} são de natureza
numérica contínua e {_e(n_cat)} são categóricas. A variável de interesse
primário identificada automaticamente pelo SigmaFlow foi
\textbf{{{_e(target)}}}, sobre a qual foram concentrados os esforços analíticos
das fases de Medição e Análise.

O objetivo central desta análise é caracterizar o desempenho do processo, avaliar
sua estabilidade estatística, estimar os índices de capacidade em relação às
especificações técnicas estabelecidas e identificar as principais fontes de
variação que impactam negativamente a qualidade do produto ou serviço. As
conclusões aqui apresentadas fundamentam-se em métodos estatísticos rigorosos,
incluindo cartas de controle, testes de normalidade, análise de capacidade de
processo e análise de causa raiz por correlação multivariada.

Todo o pipeline analítico foi executado em \textbf{{{elapsed} segundos}}, cobrindo
as cinco fases do ciclo DMAIC de forma integrada e reprodutível."""

    # ── Seção 2: Metodologia ─────────────────────────────────────────────────

    def metodologia(self) -> str:
        phases_run = self._summary.get("phases_run", ["define", "measure", "analyze", "improve", "control"])
        target     = self._meta.get("primary_target", "variável-resposta")

        phases_desc = {
            "define":  ("Definir", "identificação do problema, escopo do projeto e variável-resposta do processo"),
            "measure": ("Medir",   "coleta e caracterização dos dados, análise de capacidade e normalidade"),
            "analyze": ("Analisar","identificação de causas raiz, análise de correlação multivariada e regressão"),
            "improve": ("Melhorar","Design of Experiments (DOE) e definição de janelas operacionais ótimas"),
            "control": ("Controlar","implantação de cartas de controle e monitoramento contínuo do processo"),
        }

        phases_tex = "\n".join(
            rf"    \item \textbf{{{pt}}} --- {desc}."
            for p, (pt, desc) in phases_desc.items()
            if p in phases_run
        )

        normality_method = "Shapiro--Wilk e Anderson--Darling"
        hyp_method       = "teste \textit{t} de Student, ANOVA e Mann--Whitney (não paramétrico)"

        return rf"""A metodologia adotada neste estudo baseia-se no ciclo DMAIC, estrutura
consagrada do Lean Six Sigma que provê um processo de melhoria orientado por
dados, sistemático e auditável. As cinco fases do ciclo foram executadas
sequencialmente pelo motor \textbf{{SigmaFlow}}, conforme descrito a seguir:

\begin{{enumerate}}
{phases_tex}
\end{{enumerate}}

\subsection{{Caracterização do Dataset}}

Na fase de Definição, o perfil do conjunto de dados foi construído pelo módulo
\texttt{{DataProfiler}}, que identificou automaticamente os tipos de variáveis,
a extensão dos dados ausentes, os limites extremos e a variável de resposta
principal (\textbf{{{_e(target)}}}). Em seguida, o módulo \texttt{{AnalysisPlanner}}
selecionou os métodos estatísticos mais adequados ao perfil identificado.

\subsection{{Testes de Normalidade}}

A verificação da normalidade das variáveis numéricas foi conduzida por meio dos
testes de {normality_method}. A hipótese nula ($H_0$) adotada pressupõe que os
dados seguem distribuição normal; valores de $p < 0{{,}}05$ conduzem à rejeição
dessa hipótese com nível de significância de 5\%.

\subsection{{Testes de Hipótese}}

Para comparações entre grupos e verificação de diferenças estatisticamente
significativas, foram empregados: {hyp_method}. A seleção entre métodos
paramétricos e não paramétricos foi realizada automaticamente com base nos
resultados dos testes de normalidade.

\subsection{{Cartas de Controle e Análise de Capacidade}}

O Controle Estatístico de Processos (CEP) foi implementado por meio de cartas
de controle XmR (\textit{{Individuals and Moving Range}}), com limites de controle
calculados a $\mu \pm 3\sigma$. A capacidade do processo foi quantificada pelos
índices $C_p$ e $C_{{pk}}$, conforme as equações:

\begin{{equation}}
    C_p = \frac{{USL - LSL}}{{6\hat{{\sigma}}}}
    \qquad
    C_{{pk}} = \min\!\left(\frac{{USL - \bar{{x}}}}{{3\hat{{\sigma}}}},\;
                            \frac{{\bar{{x}} - LSL}}{{3\hat{{\sigma}}}}\right)
\end{{equation}}

onde $USL$ e $LSL$ representam os limites superior e inferior de especificação,
$\bar{{x}}$ a média do processo e $\hat{{\sigma}}$ o desvio padrão estimado.

\subsection{{Análise de Causa Raiz}}

A identificação das variáveis de maior influência sobre a qualidade foi realizada
por meio de análise de correlação de Pearson e Spearman, seguida de ranqueamento
por importância relativa. Variáveis com $|r| \geq 0{{,}}70$ foram classificadas
como candidatas prioritárias de investigação (correlação forte), enquanto
$0{{,}}50 \leq |r| < 0{{,}}70$ indica associação moderada."""

    # ── Seção 3: Análise Estatística ─────────────────────────────────────────

    def analise_estatistica(self) -> str:
        target    = self._meta.get("primary_target", "variável-resposta")
        num_cols  = self._meta.get("numeric_columns", [])
        n_rows    = self._meta.get("n_rows", 0)
        miss_pct  = self._meta.get("missing_pct", 0.0)

        # Estatísticas descritivas do target
        desc = self._measure.get("descriptive", {})
        mean = desc.get("mean", desc.get(f"{target}_mean"))
        std  = desc.get("std",  desc.get(f"{target}_std"))
        mn   = desc.get("min",  desc.get(f"{target}_min"))
        mx   = desc.get("max",  desc.get(f"{target}_max"))

        # Normalidade
        norm = self._measure.get("normality", {})
        norm_vars = list(norm.keys())[:3] if isinstance(norm, dict) else []

        # Tabela de normalidade
        norm_table = _build_normality_table(norm, target)

        # Capacidade
        cap      = self._measure.get("capability", {})
        cpk      = cap.get("Cpk")
        cp       = cap.get("Cp")
        dpmo     = cap.get("dpmo")
        sigma_lv = cap.get("sigma_level")

        cap_block = _build_capability_block(cap, target)

        # Testes de hipótese
        hyp = self._analyze.get("hypothesis_tests", {})
        hyp_block = _build_hypothesis_block(hyp)

        # Estatísticas descritivas em forma de texto
        desc_text = ""
        if mean is not None:
            desc_text = (
                rf"A variável \textbf{{{_e(target)}}} apresentou média igual a "
                rf"\textbf{{{_fmt(mean, 4)}}}, desvio padrão de {_fmt(std, 4)}, "
                rf"valor mínimo de {_fmt(mn, 4)} e máximo de {_fmt(mx, 4)}. "
            )

        miss_text = ""
        if miss_pct and miss_pct > 0:
            miss_text = (
                rf"Foram identificados {_fmt(miss_pct, 1)}\% de valores ausentes no "
                rf"conjunto de dados, fato que requer atenção na interpretação dos resultados. "
            )

        return rf"""Esta seção apresenta os resultados da fase de Medição (Measure) do ciclo
DMAIC, incluindo a caracterização descritiva do dataset, a avaliação da
normalidade das variáveis contínuas, os índices de capacidade do processo e
os testes de hipótese conduzidos.

\subsection{{Caracterização Descritiva}}

O conjunto de dados submetido à análise é composto por {_e(n_rows)} observações
distribuídas em {_e(len(num_cols))} variável(is) numérica(s). {miss_text}{desc_text}Esses
parâmetros fornecem uma visão inicial da distribuição dos dados e da magnitude
da variabilidade presente no processo.

\subsection{{Avaliação da Normalidade}}

A verificação da aderência à distribuição normal é etapa fundamental para a
escolha adequada dos métodos estatísticos a serem empregados nas análises
subsequentes. A Tabela~\ref{{tab:normalidade}} apresenta os resultados dos testes
de normalidade aplicados às variáveis numéricas identificadas.

{norm_table}

{_normalidade_interpretacao(norm, target)}

\subsection{{Análise de Capacidade do Processo}}

{cap_block}

{hyp_block}"""

    # ── Seção 4: Resultados ───────────────────────────────────────────────────

    def resultados(self) -> str:
        plots_block = _build_figures_block(self.r.get("plots", []))
        insights    = self.r.get("summary", {}).get("all_insights", [])
        insights_block = _build_insights_block(insights)

        rca = self._analyze.get("root_cause", {})
        rca_block = _build_rca_table(rca)

        return rf"""Esta seção apresenta os resultados obtidos nas fases de Análise (Analyze) e
Controle (Control) do ciclo DMAIC, incluindo as cartas de controle geradas, os
gráficos de capacidade e a síntese dos achados estatisticamente relevantes.

\subsection{{Representações Gráficas}}

As figuras a seguir foram geradas automaticamente pelo SigmaFlow a partir dos
dados brutos do processo. Cada representação gráfica foi selecionada de acordo
com o tipo de dataset identificado na fase de Definição e contribui para a
compreensão visual do comportamento do processo ao longo do tempo.

{plots_block}

\subsection{{Indicadores de Causa Raiz}}

{rca_block}

\subsection{{Síntese dos Achados}}

{insights_block}"""

    # ── Seção 5: Discussão ───────────────────────────────────────────────────

    def discussao(self) -> str:
        cap       = self._measure.get("capability", {})
        cpk       = cap.get("Cpk")
        target    = self._meta.get("primary_target", "variável principal")
        rca       = self._analyze.get("root_cause", {})
        ranked    = rca.get("ranked_variables", [])
        top_vars  = [v["variable"] for v in ranked[:3] if abs(v.get("pearson_r", 0)) >= 0.5]

        # Parágrafo sobre capacidade
        cap_para = ""
        if cpk is not None:
            verdict = _cap_verdict(cpk)
            cap_para = (
                rf"A análise de capacidade do processo revelou um índice $C_{{pk}} = {_fmt(cpk, 3)}$, "
                rf"classificado como \textbf{{{verdict}}}. "
            )
            if cpk < 1.33:
                cap_para += (
                    r"Esse resultado evidencia a necessidade de intervenções no processo, visando à "
                    r"redução da variabilidade e ao recentramento da média em relação às especificações. "
                    r"Segundo a literatura de qualidade (Montgomery, 2009), processos com $C_{pk} < 1{{,}}33$ "
                    r"apresentam risco elevado de geração de não conformidades."
                )
            else:
                cap_para += (
                    r"O processo demonstra consistência operacional satisfatória, contudo o monitoramento "
                    r"contínuo por meio de cartas de controle permanece recomendado para garantir a manutenção "
                    r"desse desempenho ao longo do tempo."
                )

        # Parágrafo sobre causa raiz
        rca_para = ""
        if top_vars:
            vars_fmt = ", ".join(rf"\textbf{{{_e(v)}}}" for v in top_vars)
            rca_para = (
                rf"A análise de correlação identificou {vars_fmt} como as variáveis de maior "
                rf"associação estatística com \textbf{{{_e(target)}}}. "
                r"Esses resultados sugerem que intervenções nesses fatores têm o maior potencial "
                r"de impacto na melhoria da qualidade do processo. Ressalta-se, contudo, que "
                r"correlação estatística não implica necessariamente relação causal, sendo "
                r"recomendada a condução de experimentos controlados (DOE) para confirmar as "
                r"hipóteses levantadas (Montgomery; Runger, 2014)."
            )

        # Parágrafo sobre anomalias detectadas
        n_critical = sum(
            1 for ins in self.r.get("structured_insights", [])
            if ins.get("severity") == "critical"
        )
        anomaly_para = ""
        if n_critical > 0:
            anomaly_para = (
                rf"Foram detectados \textbf{{{n_critical} ponto(s) fora dos limites de controle}} "
                r"ou padrões não aleatórios pela aplicação das Regras de Western Electric. "
                r"Esses eventos sinalizam causas especiais de variação que devem ser investigadas "
                r"de forma imediata pela equipe de processo. A não remoção de causas especiais "
                r"inviabiliza a interpretação confiável dos índices de capacidade calculados."
            )

        improve = self._improve.get("recommendations", {})
        recs    = improve.get("recommendations", [])
        recs_tex = ""
        if recs:
            items = "\n".join(
                rf"    \item \textbf{{{_e(rec.get('category',''))}}}: {_e(rec.get('action',''))}"
                for rec in recs[:5]
            )
            recs_tex = rf"""
\subsection{{Recomendações de Melhoria}}

Com base na análise integrada das cinco fases do ciclo DMAIC, as seguintes
ações de melhoria são recomendadas em ordem de prioridade:

\begin{{enumerate}}
{items}
\end{{enumerate}}

A implementação dessas recomendações deve ser acompanhada de um plano de
ação estruturado, com responsáveis, prazos e indicadores de verificação
da eficácia das melhorias introduzidas."""

        return rf"""{cap_para}

{rca_para}

{anomaly_para}

A interpretação conjunta dos indicadores estatísticos obtidos nas fases de
Medição e Análise permite construir um diagnóstico abrangente do estado atual
do processo. Os resultados indicam oportunidades de melhoria que, se endereçadas
de forma sistemática, têm potencial de reduzir significativamente a taxa de
não conformidades e elevar o nível sigma do processo.

{recs_tex}"""

    # ── Seção 6: Conclusão ────────────────────────────────────────────────────

    def conclusao(self) -> str:
        n_rows   = self._meta.get("n_rows", "N/A")
        n_cols   = self._meta.get("n_columns", "N/A")
        target   = self._meta.get("primary_target", "variável-resposta")
        cap      = self._measure.get("capability", {})
        cpk      = cap.get("Cpk")
        sigma_lv = cap.get("sigma_level")
        n_ins    = self._summary.get("n_insights", 0)
        elapsed  = _fmt(self.r.get("elapsed_s", 0), 2)

        cap_line = ""
        if cpk is not None:
            cap_line = (
                rf"O índice de capacidade $C_{{pk}} = {_fmt(cpk, 3)}$ classificou o processo como "
                rf"\textbf{{{_cap_verdict(cpk)}}}. "
            )
            if sigma_lv:
                cap_line += rf"O nível sigma estimado é de \textbf{{{_fmt(sigma_lv, 2)}$\sigma$}}. "

        return rf"""O presente estudo aplicou o ciclo DMAIC de forma automatizada ao dataset
\textbf{{{_e(self.name)}}}, composto por {_e(n_rows)} observações e {_e(n_cols)} variáveis.
A execução completa do pipeline analítico, incluindo profiling, planejamento,
análise estatística, geração de gráficos e produção deste relatório, foi
concluída em \textbf{{{elapsed} segundos}}, demonstrando a eficiência computacional
do SigmaFlow para suporte à tomada de decisão em projetos de qualidade.

{cap_line}No total, \textbf{{{n_ins} \textit{{insights}} estatísticos}} foram gerados ao longo
das fases do DMAIC, sinalizando aspectos críticos do processo que requerem
atenção da equipe de engenharia.

A análise de causa raiz por correlação multivariada identificou as variáveis
de maior impacto sobre \textbf{{{_e(target)}}}, fornecendo subsídios para o
planejamento de experimentos controlados e a priorização de ações corretivas.

Conclui-se que o SigmaFlow foi capaz de automatizar, de forma rigorosa e
reprodutível, uma análise que demandaria horas de trabalho manual por parte
de um especialista em qualidade. Os resultados deste relatório constituem
a base para a fase de Implementação e o estabelecimento de um plano de
monitoramento contínuo, concluindo assim o ciclo DMAIC para o processo
analisado.

\vspace{{0.5cm}}

\noindent\textbf{{Trabalhos futuros}} poderão incluir: (i) condução de experimentos
fatoriais completos para confirmação das hipóteses de causa raiz; (ii) expansão
da base de dados para aumentar o poder estatístico das análises; e (iii)
integração do SigmaFlow com sistemas de aquisição de dados em tempo real para
monitoramento on-line do processo."""


# ── Helpers internos ──────────────────────────────────────────────────────────

def _build_normality_table(norm: Dict[str, Any], target: str) -> str:
    if not norm or not isinstance(norm, dict):
        return r"\textit{Dados de normalidade não disponíveis para este dataset.}"

    rows = []
    for var, res in list(norm.items())[:8]:
        if not isinstance(res, dict):
            continue
        sw_p  = res.get("shapiro_p", res.get("p_value"))
        ad_p  = res.get("anderson_p", res.get("anderson_critical"))
        is_n  = res.get("is_normal", sw_p > 0.05 if sw_p is not None else None)
        verd  = r"\textcolor{info}{\textbf{Normal}}" if is_n else r"\textcolor{critico}{\textbf{Não Normal}}"
        rows.append(
            rf"    {_e(var)} & {_fmt(sw_p, 4) if sw_p is not None else '---'} "
            rf"& {_fmt(ad_p, 4) if ad_p is not None else '---'} & {verd} \\"
        )

    if not rows:
        return r"\textit{Resultados de normalidade não disponíveis.}"

    body = "\n".join(rows)
    return rf"""
\begin{{table}}[H]
\caption{{Resultados dos testes de normalidade (nível de significância: $\alpha = 0{{,}}05$)}}
\label{{tab:normalidade}}
\centering
\begin{{tabular}}{{p{{5cm}}ccc}}
\toprule
\textbf{{Variável}} & \textbf{{Shapiro--Wilk ($p$)}} & \textbf{{Anderson--Darling}} & \textbf{{Veredicto}} \\
\midrule
{body}
\bottomrule
\end{{tabular}}
\fonte{{SigmaFlow (análise automática)}}
\end{{table}}"""


def _normalidade_interpretacao(norm: Dict[str, Any], target: str) -> str:
    if not norm or not isinstance(norm, dict):
        return ""
    n_total   = len(norm)
    n_normal  = sum(
        1 for res in norm.values()
        if isinstance(res, dict) and res.get("is_normal", False)
    )
    if n_total == 0:
        return ""
    if n_normal == n_total:
        return (
            r"Os resultados dos testes de normalidade indicam que todas as variáveis "
            r"analisadas seguem distribuição aproximadamente normal ($p > 0{{,}}05$), "
            r"validando a aplicação de métodos paramétricos nas análises subsequentes."
        )
    elif n_normal == 0:
        return (
            r"Os resultados dos testes de normalidade indicam que nenhuma das variáveis "
            r"analisadas segue distribuição normal ($p < 0{{,}}05$), sugerindo a necessidade "
            r"da aplicação de métodos estatísticos não paramétricos para análises "
            r"subsequentes e recomendando cautela na interpretação dos índices de "
            r"capacidade calculados com base na distribuição normal."
        )
    else:
        return (
            rf"Dos {n_total} variáveis testadas, {n_normal} apresentaram aderência à "
            r"distribuição normal ($p > 0{{,}}05$). Para as demais variáveis, a hipótese "
            r"de normalidade foi rejeitada ao nível de significância de 5\%, "
            r"recomendando-se o emprego de métodos não paramétricos ou transformações "
            r"Box--Cox para normalização."
        )


def _build_capability_block(cap: Dict[str, Any], target: str) -> str:
    if not cap or not isinstance(cap, dict):
        return r"\textit{Índices de capacidade não disponíveis (especificações não fornecidas).}"

    cpk      = cap.get("Cpk")
    cp       = cap.get("Cp")
    usl      = cap.get("usl")
    lsl      = cap.get("lsl")
    dpmo     = cap.get("dpmo")
    sigma_lv = cap.get("sigma_level")

    if cpk is None:
        return r"\textit{Índices de capacidade não calculados para este dataset.}"

    verdict = _cap_verdict(cpk)
    color   = _cap_color(cpk)

    return rf"""A análise de capacidade do processo foi conduzida com base na variável
\textbf{{{_e(target)}}}, tendo como referência os limites de especificação
informados ($USL = {_fmt(usl, 4)}$; $LSL = {_fmt(lsl, 4)}$). A
Tabela~\ref{{tab:capacidade}} apresenta os índices calculados.

\begin{{table}}[H]
\caption{{Índices de capacidade do processo --- \textbf{{{_e(target)}}}}}
\label{{tab:capacidade}}
\centering
\begin{{tabular}}{{lclc}}
\toprule
\textbf{{Índice}} & \textbf{{Valor}} & \textbf{{Índice}} & \textbf{{Valor}} \\
\midrule
$C_p$         & {_fmt(cp, 3) if cp else '---'}  &
$C_{{pk}}$    & \textbf{{{_fmt(cpk, 3)}}} \\
DPMO          & {f"{dpmo:,.0f}" if dpmo else '---'} &
Nível sigma   & {_fmt(sigma_lv, 2) if sigma_lv else '---'}$\sigma$ \\
\bottomrule
\end{{tabular}}
\fonte{{SigmaFlow (análise automática)}}
\end{{table}}

O índice $C_{{pk}} = {_fmt(cpk, 3)}$ classifica o processo como
\begin{{insightinfo}}\end{{insightinfo}}
\textbf{{{verdict}}}.
{"Recomenda-se investigação imediata das fontes de variação e ações corretivas prioritárias." if cpk < 1.0 else
 "O monitoramento contínuo por cartas de controle é recomendado para manutenção desse desempenho." if cpk >= 1.33 else
 "Atenção especial deve ser dispensada ao processo para evitar a geração de não conformidades."}"""


def _build_hypothesis_block(hyp: Dict[str, Any]) -> str:
    if not hyp or not isinstance(hyp, dict):
        return ""
    tests = []
    for test_name, res in list(hyp.items())[:4]:
        if not isinstance(res, dict):
            continue
        p  = res.get("p_value")
        h  = res.get("statistic")
        sig = r"\textcolor{critico}{sim}" if (p is not None and p < 0.05) else r"\textcolor{info}{não}"
        tests.append(
            rf"    {_e(test_name.replace('_', ' ').title())} & "
            rf"{_fmt(h, 4) if h is not None else '---'} & "
            rf"{_fmt(p, 4) if p is not None else '---'} & {sig} \\"
        )
    if not tests:
        return ""
    body = "\n".join(tests)
    return rf"""
\subsection{{Testes de Hipótese}}

\begin{{table}}[H]
\caption{{Resultados dos testes de hipótese ($\alpha = 0{{,}}05$)}}
\label{{tab:hipoteses}}
\centering
\begin{{tabular}}{{p{{5.5cm}}ccc}}
\toprule
\textbf{{Teste}} & \textbf{{Estatística}} & \textbf{{Valor-$p$}} & \textbf{{Significativo?}} \\
\midrule
{body}
\bottomrule
\end{{tabular}}
\fonte{{SigmaFlow (análise automática)}}
\end{{table}}"""


def _build_rca_table(rca: Dict[str, Any]) -> str:
    if not rca or rca.get("error") or not rca.get("ranked_variables"):
        return r"\textit{Análise de correlação não disponível para este tipo de dataset.}"

    target  = rca.get("target_col", "variável-resposta")
    ranked  = rca.get("ranked_variables", [])
    interp  = rca.get("interpretation", "")

    rows = []
    for v in ranked[:10]:
        pr = v.get("pearson_r", 0)
        sr = v.get("spearman_r", 0)
        st = v.get("strength", "fraca").capitalize()
        color = (
            r"\textcolor{critico}{\textbf{" if abs(pr) >= 0.7 else
            r"\textcolor{aviso}{\textbf{"  if abs(pr) >= 0.5 else
            r"\textcolor{black}{"
        )
        rows.append(
            rf"    {_e(v['variable'])} & "
            rf"{color}{_fmt(pr, 3)}{'}}' if abs(pr) >= 0.5 else '}'} & "
            rf"{_fmt(sr, 3)} & {_e(st)} \\"
        )

    body = "\n".join(rows)
    interp_text = _e(interp) if interp else (
        rf"A Tabela~\ref{{tab:rca}} apresenta o ranqueamento das variáveis pela força "
        rf"de associação com \textbf{{{_e(target)}}}."
    )

    return rf"""{interp_text}

\begin{{table}}[H]
\caption{{Ranqueamento de variáveis por correlação com \textbf{{{_e(target)}}}}}
\label{{tab:rca}}
\centering
\begin{{tabular}}{{p{{4.5cm}}ccc}}
\toprule
\textbf{{Variável}} & \textbf{{Pearson $r$}} & \textbf{{Spearman $r$}} & \textbf{{Força}} \\
\midrule
{body}
\bottomrule
\end{{tabular}}
\fonte{{SigmaFlow (análise automática)}}
\end{{table}}"""


def _build_figures_block(plots: List[str]) -> str:
    if not plots:
        return r"\textit{Nenhuma figura foi gerada para este dataset.}"

    blocks = []
    for p in plots[:6]:
        name = Path(p).stem.replace("_", " ").title()
        # Caminho relativo ao diretório do main.tex
        rel_path = "figures/" + Path(p).name
        blocks.append(rf"""
\begin{{figure}}[H]
\centering
\caption{{{_e(name)}}}
\includegraphics[width=0.92\textwidth]{{{rel_path}}}
\fonte{{SigmaFlow (gerado automaticamente)}}
\end{{figure}}
""")
    return "\n".join(blocks)


def _build_insights_block(insights: List[str]) -> str:
    if not insights:
        return r"\textit{Nenhum \textit{insight} estatístico foi gerado para este dataset.}"

    items = "\n".join(rf"    \item {_e(ins)}" for ins in insights[:12])
    return rf"""Os \textit{{insights}} a seguir foram gerados automaticamente pelo motor de
regras do SigmaFlow com base nos dados analisados:

\begin{{itemize}}
{items}
\end{{itemize}}"""
