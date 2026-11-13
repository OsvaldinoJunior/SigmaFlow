"""Triagem exploratória para a interface local do SigmaFlow.

As regras identificam dados candidatos e perguntas possíveis; não executam
testes estatísticos nem confirmam causas ou adequação metodológica.
"""
from __future__ import annotations

import unicodedata
import importlib.util
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd

def _load_existing(name: str):
    """Carrega os módulos analíticos sem inicializar a API corporativa."""
    module_name = f"sigmaflow_local_{name}"
    spec = importlib.util.spec_from_file_location(module_name, Path(__file__).parent / "core" / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"Não foi possível carregar {name}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


DataProfiler = _load_existing("data_profiler").DataProfiler
ProblemDetector = _load_existing("problem_detector").ProblemDetector


class _LocalProblemDetector(ProblemDetector):
    def _log(self, result):
        # O detector original imprime emojis que podem falhar em consoles Windows.
        # A interface apresenta seus resultados sem depender da saída do terminal.
        return None


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value).lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in text).split())


# A correspondência usa nomes completos normalizados; não usa substrings.
ROLES = {
    "data": ("Data ou sequência", ["data", "data de producao", "data da medicao", "data de medicao", "data da coleta", "data da falha", "data do registro", "date", "timestamp", "datetime", "horario", "sequencia", "amostra"]),
    "categoria": ("Tipo de defeito ou causa", ["tipo defeito", "tipo de defeito", "categoria do defeito", "tipo refugo", "motivo rejeicao", "motivo de rejeicao", "scrap reason", "defeito", "defect type", "failure mode", "modo de falha", "modo da falha", "motivo parada", "motivo de parada", "causa parada"]),
    "defeitos": ("Quantidade rejeitada", ["rejeitados", "rejeitadas", "quantidade rejeitada", "quantidade rejeitados", "unidades rejeitadas", "unidades refugadas", "pecas refugadas", "quantidade de refugos", "qtd rejeitada", "refugo", "pecas rejeitadas", "unidades defeituosas", "itens nao conformes", "defect count", "defective units", "nonconforming units", "rejects", "scrap"]),
    "total": ("Quantidade produzida ou inspecionada", ["produzido", "produzida", "producao", "quantidade produzida", "pecas produzidas", "unidades produzidas", "inspecionado", "inspecionadas", "unidades inspecionadas", "total produzido", "total inspecionado", "produced", "sample size"]),
    "medida": ("Medição do processo", ["medicao", "medida", "resultado da medicao", "medicao do processo", "measurement", "valor", "value", "peso", "peso g", "espessura", "espessura mm", "diametro", "diametro mm", "comprimento"]),
    "grupo": ("Máquina, turno ou grupo", ["maquina", "equipamento", "linha", "linha de producao", "turno", "fornecedor", "produto", "grupo", "etapa", "etapa do processo", "machine", "equipment", "shift", "supplier", "line"]),
    "lsl": ("Limite inferior de especificação", ["lsl", "lie", "limite inferior", "lower spec"]),
    "usl": ("Limite superior de especificação", ["usl", "lse", "limite superior", "upper spec"]),
    "peca": ("Peça ou amostra para MSA", ["peca", "numero da peca", "identificacao da peca", "parte", "part", "part id", "peca id"]),
    "operador": ("Operador ou avaliador", ["operador", "avaliador", "operator", "appraiser"]),
    "severidade": ("Severidade", ["severidade", "severity"]),
    "ocorrencia": ("Ocorrência", ["ocorrencia", "occurrence"]),
    "deteccao": ("Detecção", ["deteccao", "detection"]),
    "fator": ("Fator de experimento", ["fator", "factor", "temperatura", "temperatura c", "temperature", "pressao", "pressure", "velocidade", "speed"]),
    "parada": ("Tempo de parada", ["tempo parada", "tempo de parada", "tempo de parada minutos", "downtime", "parada minutos"]),
    "tempo_planejado": ("Tempo planejado", ["tempo planejado", "tempo planejado minutos", "planned time", "tempo disponivel"]),
    "ciclo_ideal": ("Tempo de ciclo ideal", ["ciclo ideal", "ideal cycle", "tempo ciclo ideal", "ciclo ideal minutos por peca"]),
    "tempo": ("Tempo de processo ou entrega", ["lead time", "lead time minutos", "tempo ciclo", "tempo de ciclo", "tempo atendimento", "tempo de atendimento minutos", "duracao", "duration"]),
    "energia": ("Consumo de energia", ["energia", "consumo energia", "consumo de energia", "consumo de energia kwh", "energy", "kwh"]),
    "ativo": ("Equipamento ou ativo", ["ativo", "equipamento", "asset", "equipment"]),
    "falha": ("Tipo ou registro de falha", ["falha", "failure"]),
    "tempo_falha": ("Tempo até falha ou fim do acompanhamento", ["tempo ate falha", "tempo ate falha horas", "time to failure", "tempo observado", "tempo observado horas", "tempo acompanhamento", "tempo de acompanhamento", "follow up time", "observed time"]),
    "evento": ("Evento: falha = 1; censura à direita = 0", ["evento", "evento observado", "falha observada", "event observed", "failure observed"]),
    "custo": ("Custo da perda (legado)", ["custo", "cost", "custo refugo"]),
    "custo_unitario": ("Custo por unidade rejeitada", ["custo unitario", "custo unitario r", "custo por unidade", "custo por unidade rejeitada", "unit cost", "cost per rejected unit"]),
    "custo_total": ("Custo total da perda por registro", ["custo total", "custo total r", "custo total refugo", "valor total perdido", "total scrap cost", "total loss cost"]),
}


CATALOG = [
    ("piloto", "Verificação de piloto antes e depois", "O indicador mudou nas janelas de referência e após a ação?", [["data", "medida"], ["data", "defeitos", "total"]], ["Comparação de médias: Welch", "Proporções: Wilson e Newcombe", "Meta e incerteza"], "Defina as janelas e o indicador no formulário do piloto. Requer amostras independentes e períodos comparáveis; medições pareadas, lotes agrupados e séries autocorrelacionadas exigem outro método. A diferença observada não atribui o efeito à ação nem aprova eficácia."),
    ("refugo", "Refugo e retrabalho", "Qual perda concentra mais unidades ou custo?", [["categoria", "defeitos"]], ["Pareto por unidades/ocorrencias", "Pareto por custo", "Estratificacao por linha ou turno"], "Refugo pode contar unidades ou ocorrências; confirme o significado e a unidade."),
    ("atributos", "Taxa de defeitos ao longo do tempo", "A proporção de unidades rejeitadas mudou?", [["data", "defeitos", "total"]], ["Carta p", "Carta np quando o tamanho e fixo", "Taxa por periodo"], "Carta p/np exige a contagem de unidades não conformes, não o total de ocorrências de defeitos. p aceita tamanhos variáveis; np requer tamanho fixo. Confirme denominador, independência e ordem temporal."),
    ("capacidade", "Capacidade e especificação", "As medições atendem aos limites do produto?", [["medida", "lsl"], ["medida", "usl"]], ["Estabilidade do processo", "Capacidade de processo"], "Confirme limites e unidade; verifique estabilidade e sistema de medição antes de interpretar capacidade."),
    ("spc", "Variação ao longo do tempo", "O processo apresenta mudanças ou sinais especiais?", [["data", "medida"]], ["Carta de controle", "Análise de tendência"], "Confirme ordem, subgrupos e amostragem antes de selecionar a carta."),
    ("grupos", "Diferenças entre grupos", "O resultado difere entre máquinas, turnos ou fornecedores?", [["grupo", "medida"], ["grupo", "defeitos", "total"]], ["Estratificação", "Comparação de grupos"], "Diferenças observadas podem refletir produto, período ou outros fatores."),
    ("msa", "Sistema de medição", "As medições são consistentes entre peças e operadores?", [["peca", "operador", "medida"]], ["Gauge R&R"], "É necessário confirmar repetições, desenho do estudo e condições de medição."),
    ("fmea", "Riscos e modos de falha", "Quais modos de falha devem ser investigados primeiro?", [["categoria", "severidade", "ocorrencia", "deteccao"]], ["FMEA", "Priorização e plano de ação"], "Confirme escalas, critérios e responsabilidade; RPN isolado não substitui revisão de risco."),
    ("doe", "Fatores de processo e experimentos", "Como a resposta observada varia entre os níveis deste fator?", [["fator", "medida"]], ["Exploração por fator", "ANOVA de um fator (exploratória)"], "Esta análise compara níveis observados de um fator. Ela não projeta nem valida DOE; desenho planejado, randomização, replicação, bloqueio e limites seguros precisam ser definidos antes do experimento. Associação observada não confirma causa."),
    ("oee", "Paradas e eficiência do equipamento", "Onde o tempo produtivo está sendo perdido?", [["parada", "tempo_planejado", "total", "defeitos", "ciclo_ideal"]], ["Pareto de paradas", "OEE"], "OEE exige definições consistentes de tempo, produção boa e ciclo ideal por produto."),
    ("fluxo", "Fluxo e tempo de atendimento", "Em quais etapas ocorre maior espera ou variação?", [["tempo", "grupo"]], ["Distribuição de tempos", "Comparação entre etapas"], "Confirme início e fim das etapas, unidade de tempo e período analisado."),
    ("energia", "Consumo de energia", "O consumo varia com a produção?", [["energia", "total"]], ["Consumo por unidade", "Comparação por período"], "Considere mix, horário e condições de operação; associação não comprova causa."),
    ("confiabilidade", "Histórico de falhas por ativo", "Quais ativos concentram mais registros de falha?", [["ativo", "falha"], ["ativo", "tempo_falha"]], ["Contagem de falhas por ativo"], "Contagem não é taxa nem MTBF: a exposição dos ativos pode ser diferente. Se o evento 0/1 estiver mapeado, censuras são excluídas da contagem. Para vida útil, use tempos e censura no cenário Kaplan–Meier."),
    ("sobrevivencia", "Vida útil e dados censurados", "Como a probabilidade de permanecer sem falha muda com o tempo?", [["ativo", "tempo_falha", "evento"]], ["Kaplan–Meier", "Mediana de vida e tempo médio restrito"], "Uma linha por unidade independente. Use tempo até falha ou fim do acompanhamento e evento 1 = falha, 0 = censura à direita. Confirme unidade, origem do tempo e censura não informativa; repetições, entrada tardia e riscos competitivos exigem outro desenho."),
]


def _match_roles(columns: list[str]) -> dict[str, list[str]]:
    matches = {}
    for role, (_, aliases) in ROLES.items():
        normalized_aliases = [_normalize(a) for a in aliases]
        candidates = []
        for col in columns:
            name = _normalize(col)
            if any(name == alias for alias in normalized_aliases):
                candidates.append(col)
        matches[role] = candidates
    return matches


def _quality_findings(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Return descriptive data checks; none of these alone proves bad data."""
    findings: list[dict[str, Any]] = []
    total = len(df)
    date_columns = set(_match_roles([str(column) for column in df.columns]).get("data", []))
    for column in df.columns:
        count = int(df[column].isna().sum())
        if count:
            findings.append({"type": "missing", "column": str(column), "count": count,
                             "message": f"{count} células vazias ({count / total:.1%}) em {column}.",
                             "caveat": "Verifique se a ausência é esperada e como o método escolhido lida com ela."})
        unique = int(df[column].nunique(dropna=True))
        if total >= 2 and unique <= 1 and df[column].notna().any():
            findings.append({"type": "constant", "column": str(column), "count": unique,
                             "message": f"{column} tem apenas {unique} valor distinto.",
                             "caveat": "A coluna pode ser constante neste recorte ou ter sido importada incorretamente."})
        if str(column) not in date_columns and total >= 20 and unique / max(1, total) >= 0.9 and unique > 10:
            findings.append({"type": "id_candidate", "column": str(column), "count": unique,
                             "message": f"{column} parece ter alta cardinalidade ({unique} valores distintos em {total} linhas).",
                             "caveat": "Pode ser identificador; confirme antes de usar como fator ou preditor."})
        values = pd.to_numeric(df[column], errors="coerce").replace([float("inf"), float("-inf")], float("nan")).dropna()
        if len(values) >= 8 and values.nunique() >= 4:
            q1, q3 = values.quantile([0.25, 0.75])
            spread = q3 - q1
            if spread > 0:
                flagged = int(((values < q1 - 1.5 * spread) | (values > q3 + 1.5 * spread)).sum())
                if flagged:
                    findings.append({"type": "outlier_candidate", "column": str(column), "count": flagged,
                                     "message": f"{flagged} valores em {column} estão fora de 1,5 × IQR.",
                                     "caveat": "Sinal exploratório, não erro: investigue contexto, processo e instrumento; não exclua automaticamente."})
    duplicate_rows = int(df.duplicated().sum())
    if duplicate_rows:
        findings.append({"type": "duplicate_rows", "column": "", "count": duplicate_rows,
                         "message": f"{duplicate_rows} linhas são duplicatas exatas.",
                         "caveat": "Confirme se são registros repetidos ou ocorrências legítimas do processo."})
    return findings[:100]


def diagnose(df: pd.DataFrame, mapping: dict[str, str] | None = None, objective: str = "") -> dict[str, Any]:
    if df.empty or not len(df.columns):
        raise ValueError("A planilha não contém linhas de dados para analisar.")
    df = df.copy()
    df.columns = [str(c) for c in df.columns]
    if len(set(df.columns)) != len(df.columns):
        raise ValueError("A planilha tem nomes de colunas repetidos. Renomeie as colunas e tente novamente.")
    mapping = mapping or {}
    candidates = _match_roles(list(df.columns))
    selected = {}
    for role in ROLES:
        if role in mapping:
            value = mapping[role]
            if value and value not in df.columns:
                raise ValueError(f"A coluna selecionada para {ROLES[role][0]} não existe no arquivo.")
            selected[role] = value or None
        else:
            selected[role] = candidates[role][0] if len(candidates[role]) == 1 else None

    # O motor existente contribui com o perfil e suas detecções; sugestões da
    # interface seguem as regras explícitas acima e exigem revisão do usuário.
    engine_warning = None
    try:
        profile = DataProfiler().profile(df)
        legacy = _LocalProblemDetector().detect(profile).as_dict()
    except Exception:
        profile = {"numeric_columns": list(df.select_dtypes(include="number").columns),
                   "categorical_columns": list(df.select_dtypes(exclude="number").columns)}
        legacy = {"problems": [], "primary_problem": "exploratory", "response_variable": None,
                  "feature_variables": [], "confidence": {}, "rationale": {}}
        engine_warning = "O perfil avançado não pôde ser concluído para esta planilha. A triagem básica continua disponível."

    suggestions = []
    objective_text = _normalize(objective)
    for key, title, question, alternatives, methods, caveat in CATALOG:
        comparison_options = None
        if key == "grupos":
            option_specs = [
                ("measurement", "Medições entre grupos", alternatives[0]),
                ("proportion", "Taxa de unidades rejeitadas (%)", alternatives[1]),
            ]
            comparison_options = []
            for value, label, required_roles in option_specs:
                missing_roles = [role for role in required_roles if not selected.get(role)]
                comparison_options.append({
                    "value": value,
                    "label": label,
                    "available": not missing_roles,
                    "missing": [ROLES[role][0] for role in missing_roles],
                })
            available_options = [option for option in comparison_options if option["available"]]
            # Do not choose a route from column order when both data structures exist.
            # `found` reports the mapped inputs for every available route.
            if available_options:
                best = list(dict.fromkeys(role for option in option_specs
                                          if any(candidate["value"] == option[0] and candidate["available"]
                                                 for candidate in comparison_options)
                                          for role in option[2]))
                present = [role for role in best if selected.get(role)]
                missing = []
            else:
                best = min(alternatives, key=lambda group: sum(not selected.get(role) for role in group))
                present = [role for role in best if selected.get(role)]
                missing = [ROLES[role][0] for role in best if not selected.get(role)]
            suggested_methods = [
                "Medições: comparação exploratória entre grupos",
                "Proporção: intervalo de Wilson por grupo",
                "Proporções: teste global; Newcombe para comparação entre dois grupos",
            ]
            caveat = (
                "Escolha explicitamente medições ou taxa de unidades rejeitadas. Para proporções, confirme que cada unidade "
                "é contada uma única vez como defeituosa, que o denominador representa as unidades inspecionadas no mesmo "
                "grupo e que os denominadores são disjuntos entre grupos. O método de Newcombe aplica-se à comparação de "
                "dois grupos; intervalos por grupo usam Wilson. Diferenças observadas não demonstram causalidade e podem "
                "refletir produto, período ou outras condições."
            )
        else:
            best = min(alternatives, key=lambda group: sum(not selected.get(role) for role in group))
            present = [role for role in best if selected.get(role)]
            missing = [role for role in best if not selected.get(role)]
        optional_found = []
        blockers = []
        if key != "grupos":
            suggested_methods = methods
        if key == "refugo":
            optional_roles = ["grupo", "custo_unitario", "custo_total", "custo"]
            optional_found = [{"role": ROLES[r][0], "column": selected[r]} for r in optional_roles if selected.get(r)]
            cost_roles = [r for r in ("custo_unitario", "custo_total") if selected.get(r)]
            if selected.get("custo"):
                blockers.append("A coluna legado 'custo' nao informa se e custo unitario ou custo total por registro. Mapeie uma coluna com definicao explicita.")
            if len(cost_roles) > 1:
                blockers.append("Duas bases de custo foram mapeadas. Deixe apenas custo unitário ou custo total por registro.")
                cost_method = "Pareto por custo: escolha uma única base de custo"
            elif cost_roles:
                cost_method = "Pareto por custo (" + ROLES[cost_roles[0]][0].lower() + ")"
            elif selected.get("custo"):
                cost_method = "Pareto por custo: defina uma coluna de custo"
            else:
                cost_method = "Pareto por custo (mapeie custo opcional)"
            group_method = "Estratificação por " + str(selected["grupo"]) if selected.get("grupo") else "Estratificação (mapeie linha/turno opcional)"
            suggested_methods = ["Pareto por contagem", cost_method, group_method]
        goal_match = any(word in objective_text.split() for word in _normalize(title).split() if len(word) > 4)
        suggestions.append({"id": key, "title": title, "question": question,
                            "methods": suggested_methods, "caveat": caveat,
                            "status": "revisar" if (any(option["available"] for option in comparison_options)
                                                     if comparison_options is not None else not missing)
                            else "faltam dados",
                            "found": [{"role": ROLES[r][0], "column": selected[r]} for r in present],
                            "optional_found": optional_found, "blockers": blockers,
                            "missing": [ROLES[r][0] for r in missing] if comparison_options is None else missing,
                            **({"comparison_options": comparison_options} if comparison_options is not None else {}),
                            "_score": len(present) / len(best) + (0.15 if goal_match else 0)})
    suggestions.sort(key=lambda item: (-item["_score"], item["title"]))
    for item in suggestions:
        del item["_score"]

    numeric_summary = []
    for column in df.select_dtypes(include="number").columns:
        values = pd.to_numeric(df[column], errors="coerce").replace([float("inf"), float("-inf")], float("nan")).dropna()
        if values.empty:
            continue
        minimum, mean, maximum = float(values.min()), float(values.mean()), float(values.max())
        if all(math.isfinite(value) for value in (minimum, mean, maximum)):
            numeric_summary.append({"column": column, "count": int(values.count()),
                                    "min": minimum, "mean": mean, "max": maximum})

    preview = df.head(5).astype(object).where(pd.notna(df.head(5)), None)
    return {"rows": len(df), "columns": list(df.columns),
            "numeric_count": len(profile.get("numeric_columns", [])),
            "missing_cells": int(df.isna().sum().sum()), "numeric_summary": numeric_summary,
            "preview": [[str(value) if value is not None else "" for value in row] for row in preview.values.tolist()],
            "roles": [{"id": key, "label": label, "candidates": candidates[key], "selected": selected[key]}
                      for key, (label, _) in ROLES.items()],
            "suggestions": suggestions, "legacy_problems": legacy, "quality_findings": _quality_findings(df),
            "quality_note": "Verificações exploratórias para orientar revisão. Nenhum alerta confirma defeito, causa ou necessidade de excluir dados.",
            "warning": engine_warning}
