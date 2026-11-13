"""Explicit before/after windows: independent means or defective-unit proportions.

This observational comparison records a pilot's measurement, not causal approval.
Formulas and scope are documented in docs/METODO_PILOTO_ANTES_DEPOIS.md.
"""
from __future__ import annotations

from datetime import date, datetime
import math
import re

import numpy as np
import pandas as pd
from scipy import stats

from local_statistics import wilson_interval

MAX_INTEGER = 2**53 - 1


def _text(parameters, key, limit, required=True):
    value = parameters.get(key, "")
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f"O campo '{key}' deve ser um texto de até {limit} caracteres.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"Informe '{key}' para registrar a comparação do piloto.")
    return value


def _parameters(parameters):
    if not isinstance(parameters, dict):
        raise ValueError("Defina os parâmetros da comparação antes/depois no formulário do piloto.")
    kind, direction = parameters.get("kind"), parameters.get("direction")
    if kind not in ("continuous", "proportion"):
        raise ValueError("Escolha medição contínua ou proporção de unidades defeituosas.")
    if direction not in ("decrease", "increase"):
        raise ValueError("Informe se o objetivo do indicador é diminuir ou aumentar.")
    if parameters.get("independence_confirmed") is not True:
        raise ValueError("Confirme o desenho de amostras independentes. Dados pareados, agrupados ou com dependência temporal exigem outra análise.")
    if parameters.get("comparability_confirmed") is not True:
        raise ValueError("Revise e registre a comparabilidade de definição, medição, população e mix dos períodos.")
    target = parameters.get("target")
    if isinstance(target, bool) or not isinstance(target, (int, float)) or not math.isfinite(target) or abs(target) > MAX_INTEGER:
        raise ValueError("Informe uma meta numérica finita na unidade do indicador.")
    if kind == "proportion" and not 0 <= target <= 100:
        raise ValueError("A meta de proporção deve estar entre 0 e 100 por cento.")
    result = {"kind": kind, "direction": direction, "target": target,
              "independence_confirmed": True, "comparability_confirmed": True}
    for key in ("before_start", "before_end", "after_start", "after_end"):
        value = parameters.get(key)
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("As quatro datas do piloto devem usar AAAA-MM-DD.")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Uma data da janela do piloto é inválida.") from exc
        result[key] = value
    if not result["before_start"] <= result["before_end"] < result["after_start"] <= result["after_end"]:
        raise ValueError("As janelas devem ter início até fim, sem sobreposição, com o período antes terminando antes do período depois.")
    for key, limit in (("indicator", 240), ("definition", 1200), ("unit", 64), ("comparability_notes", 2000)):
        result[key] = _text(parameters, key, limit)
    if kind == "proportion" and result["unit"] != "%":
        raise ValueError("Use '%' como unidade da proporção e informe a meta em percentual.")
    result["action_id"] = _text(parameters, "action_id", 64, required=False)
    result["action_label"] = _text(parameters, "action_label", 300, required=False)
    if bool(result["action_id"]) != bool(result["action_label"]):
        raise ValueError("Registre o identificador e a descrição da ação ligada, ou deixe ambos vazios para uma comparação exploratória.")
    return result


def _dates(values):
    parsed = []
    for value in values:
        if isinstance(value, str):
            value = value.strip()
            iso = bool(re.match(r"^\d{4}-\d{2}-\d{2}(?:$|[ T])", value))
            brazilian = bool(re.match(r"^\d{2}/\d{2}/\d{4}(?:$|[ T])", value))
            if not iso and not brazilian:
                raise ValueError("Use datas ISO (AAAA-MM-DD) ou DD/MM/AAAA na coluna de data do piloto.")
            value = pd.to_datetime(value, errors="coerce", format="mixed", dayfirst=not iso)
        elif not isinstance(value, (date, datetime, pd.Timestamp, np.datetime64)):
            raise ValueError("A coluna de data deve conter datas válidas; números de série precisam ser convertidos em datas.")
        value = pd.Timestamp(value)
        if pd.isna(value) or value.tzinfo is not None:
            raise ValueError("Há data inválida ou com fuso horário. Padronize o calendário local dos dois períodos.")
        parsed.append(value.normalize())
    return pd.Series(parsed, index=values.index, dtype="datetime64[ns]")


def _data(df, mapping, parameters):
    roles = ["data", "medida"] if parameters["kind"] == "continuous" else ["data", "defeitos", "total"]
    columns = [mapping.get(role) for role in roles]
    if any(not isinstance(column, str) or not column or column not in df.columns for column in columns):
        raise ValueError("Confirme o mapeamento de data e medição, ou de data, unidades defeituosas e total inspecionado, antes de verificar o piloto.")
    if len(set(columns)) != len(columns):
        raise ValueError("Use colunas diferentes para cada informação do piloto.")
    data = df[columns].copy().reset_index(drop=True)
    data.columns = roles
    data["data"] = _dates(data["data"])
    before = data["data"].between(parameters["before_start"], parameters["before_end"])
    after = data["data"].between(parameters["after_start"], parameters["after_end"])
    selected = data.loc[before | after].copy()
    if not before.any() or not after.any():
        raise ValueError("Cada janela precisa conter registros. Confira as datas e o período de transição excluído.")
    for role in roles[1:]:
        if selected[role].map(lambda value: isinstance(value, (bool, np.bool_))).any():
            raise ValueError("Valores lógicos não substituem medições ou contagens no piloto.")
        selected[role] = pd.to_numeric(selected[role], errors="coerce")
        if selected[role].isna().any() or not np.isfinite(selected[role]).all():
            raise ValueError("Há valor ausente ou não numérico nas colunas usadas dentro das janelas. Não foram excluídas linhas automaticamente.")
        if (selected[role].abs() > MAX_INTEGER).any():
            raise ValueError("Um valor excede a precisão numérica suportada; revise a unidade/escala antes da comparação.")
        if parameters["kind"] == "proportion" and ((selected[role] < 0).any() or (selected[role] % 1 != 0).any()):
            raise ValueError("Unidades defeituosas e total inspecionado devem ser contagens inteiras não negativas.")
    if parameters["kind"] == "proportion":
        if (selected["total"] <= 0).any() or (selected["defeitos"] > selected["total"]).any():
            raise ValueError("Cada registro precisa de total positivo e unidades defeituosas entre zero e o total; número de defeitos não é número de unidades defeituosas.")
    selected["periodo"] = np.where(before.loc[selected.index], "before", "after")
    return selected, len(data) - len(selected)


def _mean_summary(values):
    values = np.asarray(values, dtype=float)
    if len(values) < 2:
        raise ValueError("A comparação de médias requer ao menos duas medições independentes em cada janela.")
    estimate = float(values.mean())
    deviation = float(values.std(ddof=1))
    if not math.isfinite(estimate) or not math.isfinite(deviation):
        raise ValueError("Média ou dispersão não finita; revise a escala dos dados.")
    interval = None
    if deviation > 0:
        half = float(stats.t.ppf(0.975, len(values)-1)) * deviation / math.sqrt(len(values))
        interval = [estimate-half, estimate+half]
    return {"rows": len(values), "n": len(values), "estimate": estimate, "sd": deviation, "ci95": interval}


def _welch(before, after):
    difference = after["estimate"] - before["estimate"]
    a, b = after["sd"]**2 / after["n"], before["sd"]**2 / before["n"]
    standard_error = math.sqrt(a+b)
    if standard_error == 0:
        return {"estimate": difference, "ci95": None, "pvalue": None, "se": 0, "df": None,
                "method": "Diferença descritiva; Welch indisponível com variância zero nos dois períodos"}
    degrees = (a+b)**2 / (a*a/(after["n"]-1) + b*b/(before["n"]-1))
    half = float(stats.t.ppf(0.975, degrees)) * standard_error
    pvalue = float(2*stats.t.sf(abs(difference/standard_error), degrees))
    if not all(math.isfinite(value) for value in (degrees, half, pvalue)):
        raise ValueError("Não foi possível estimar um intervalo finito da diferença de médias.")
    return {"estimate": difference, "ci95": [difference-half, difference+half], "pvalue": pvalue,
            "se": standard_error, "df": degrees, "method": "Welch, diferença de médias depois − antes, IC95% bilateral"}


def _proportion_summary(frame):
    # Python integers avoid int64 overflow and never round exact large counts.
    defective = sum(int(value) for value in frame["defeitos"])
    inspected = sum(int(value) for value in frame["total"])
    if inspected > MAX_INTEGER:
        raise ValueError("A soma dos denominadores excede a precisão suportada pelo navegador; revise o recorte dos dados.")
    lower, upper = wilson_interval(defective, inspected)
    return {"rows": len(frame), "n": inspected, "defective": defective, "estimate": 100*defective/inspected,
            "ci95": [100*lower, 100*upper]}


def _newcombe(before, after):
    # Independent proportions, Newcombe 1998 method 10 WITHOUT continuity
    # correction. Estimates and limits are all expressed in percentage points.
    difference = after["estimate"] - before["estimate"]
    lower = difference - math.hypot(after["estimate"]-after["ci95"][0], before["ci95"][1]-before["estimate"])
    upper = difference + math.hypot(after["ci95"][1]-after["estimate"], before["estimate"]-before["ci95"][0])
    return {"estimate": difference, "ci95": [max(-100.0, lower), min(100.0, upper)], "pvalue": None,
            "method": "Newcombe-Wilson sem correção de continuidade, diferença depois − antes, IC95% aproximado"}


def _number(value):
    return f"{value:.6g}".replace(".", ",")


def compare_pilot(df, mapping, parameters):
    parameters = _parameters(parameters)
    data, excluded = _data(df, mapping, parameters)
    frames = {key: data.loc[data["periodo"] == key] for key in ("before", "after")}
    if parameters["kind"] == "continuous":
        before, after = (_mean_summary(frames[key]["medida"]) for key in ("before", "after"))
        difference = _welch(before, after)
        unit = parameters["unit"]
        columns = ["Período", "Início inclusivo", "Fim inclusivo", "Medições", "Média", "Desvio amostral", "IC95 inferior da média", "IC95 superior da média"]
        rows = [[label, parameters[f"{key}_start"], parameters[f"{key}_end"], summary["n"], summary["estimate"], summary["sd"],
                 *(summary["ci95"] or [None, None])] for key, label, summary in (("before", "Antes", before), ("after", "Depois", after))]
    else:
        before, after = (_proportion_summary(frames[key]) for key in ("before", "after"))
        difference = _newcombe(before, after)
        unit = "pontos percentuais"
        columns = ["Período", "Início inclusivo", "Fim inclusivo", "Registros", "Unidades defeituosas", "Unidades inspecionadas", "Proporção (%)", "IC95 Wilson inferior (%)", "IC95 Wilson superior (%)"]
        rows = [[label, parameters[f"{key}_start"], parameters[f"{key}_end"], summary["rows"], summary["defective"], summary["n"],
                 summary["estimate"], *summary["ci95"]] for key, label, summary in (("before", "Antes", before), ("after", "Depois", after))]
    target = parameters["target"]
    point_met = after["estimate"] <= target if parameters["direction"] == "decrease" else after["estimate"] >= target
    after_interval = after["ci95"]
    uncertainty = "not_estimated"
    if after_interval is not None:
        meets = [value <= target if parameters["direction"] == "decrease" else value >= target for value in after_interval]
        uncertainty = "interval_within" if all(meets) else "interval_outside" if not any(meets) else "crosses"
    evaluation = {"value": target, "direction": parameters["direction"], "point_met": bool(point_met), "uncertainty": uncertainty}
    metrics = [[f"Antes ({parameters['unit']})", before["estimate"]], [f"Depois ({parameters['unit']})", after["estimate"]],
               [f"Diferença depois − antes ({unit})", difference["estimate"]], [f"Meta pós ({parameters['unit']})", target],
               ["Meta na estimativa pós", "Atingida na estimativa pontual" if point_met else "Não atingida na estimativa pontual"],
               ["Registros fora das janelas", excluded]]
    evidence = [f"Antes: {parameters['before_start']} a {parameters['before_end']}; depois: {parameters['after_start']} a {parameters['after_end']}. Fins inclusivos; {len(data)} de {len(df)} registros selecionados.",
                f"Definição registrada: {parameters['definition']}", f"Contexto de comparabilidade declarado pela equipe: {parameters['comparability_notes']}"]
    if parameters["kind"] == "proportion":
        evidence.append(f"Antes: {before['defective']} / {before['n']} unidades; depois: {after['defective']} / {after['n']} unidades. A proporção usa a divisão dos totais, não a média das taxas por registro.")
        evidence.append("Os limites Wilson dos dois períodos são combinados pelo método Newcombe para estimar o IC da diferença; os intervalos são aproximados e podem ter cobertura diferente de 95%.")
    else:
        evidence.append(f"Antes: n={before['n']}, desvio={_number(before['sd'])}; depois: n={after['n']}, desvio={_number(after['sd'])}. Variâncias não são presumidas iguais.")
    delta = _number(difference["estimate"])
    if difference["ci95"] is not None:
        lower, upper = difference["ci95"]
        metrics.extend([[f"IC95 inferior da diferença ({unit})", lower], [f"IC95 superior da diferença ({unit})", upper]])
        evidence.append(f"Diferença depois − antes = {delta} {unit}; IC95% = [{_number(lower)}; {_number(upper)}] {unit}.")
    else:
        evidence.append("A diferença é apenas descritiva: as duas variâncias são zero, sem IC/teste de Welch estimável. Isso não comprova igualdade nem diferença populacional com certeza.")
    if difference["pvalue"] is not None:
        p = difference["pvalue"]
        metrics.append(["p bilateral de Welch", "< 0,000001" if p < 1e-6 else _number(p)])
    notes = ["Comparação observacional de dois períodos. Uma diferença, IC ou p-valor não atribui o resultado à ação; sazonalidade, mix, mudanças simultâneas, seleção de janelas e regressão à média podem explicar a variação.",
             "A independência e a comparabilidade foram declaradas pela equipe, sem comprovação automática. Séries autocorrelacionadas, lotes agrupados, unidades repetidas/pareadas ou dependência entre períodos exigem outro desenho/modelo.",
             "Meta na estimativa pontual, incerteza, eficácia sustentada, aprovação operacional e benefício financeiro são avaliações distintas. Este cálculo não aprova a ação nem a fase DMAIC.",
             "Mantenha as janelas/critério definidos antes de olhar o resultado. Repetir comparações, indicadores ou cortes para obter significância exige controle de multiplicidade."]
    if parameters["kind"] == "proportion":
        notes.append("Conte unidades defeituosas no máximo uma vez por denominador: número de defeitos ou oportunidades não pode substituir esse numerador. Wilson/Newcombe pressupõem unidades Bernoulli independentes com probabilidade comum dentro de cada período; agregação não corrige agrupamento ou sobredispersão.")
    else:
        notes.append("Welch e os IC t pressupõem amostras independentes e médias com aproximação normal adequada; n pequeno, assimetria, extremos e resolução insuficiente requerem revisão. Não foi aplicado teste de normalidade para selecionar automaticamente outro método.")
        if before["sd"] == 0 or after["sd"] == 0:
            notes.append("Há dispersão amostral zero em ao menos um período; o IC dessa média não foi estimado. Revise resolução, representatividade e tamanho da amostra.")
    if uncertainty == "crosses":
        notes.append("O IC95% do indicador pós cruza a meta; o atendimento pontual não elimina a incerteza sobre a média/proporção populacional.")
    target_text = "atinge" if point_met else "não atinge"
    next_step = "Revise comparabilidade, gráfico temporal e medidas de proteção; confirme em nova coleta e registre a revisão humana antes de sustentar eficácia ou benefício."
    if not point_met:
        next_step = "A estimativa pós não atingiu a meta: retome a investigação da ação e das hipóteses, registre o motivo e planeje nova coleta sem apagar esta execução."
    return {"titulo": "Verificação do piloto: antes e depois", "metodo": difference["method"], "indicadores": metrics,
            "colunas": columns, "linhas": rows, "linhas_total": len(rows), "observacoes": notes, "evidencias": evidence,
            "insight": f"{parameters['indicator']}: antes {_number(before['estimate'])} e depois {_number(after['estimate'])} {parameters['unit']}. A diferença depois − antes foi {delta} {unit}. A estimativa pós {target_text} a meta de {_number(target)} {parameters['unit']}; isso não comprova efeito causal nem sustentação.",
            "proximo_passo": next_step,
            "piloto": {"parameters": parameters, "before": before, "after": after, "difference": difference,
                       "target": evaluation, "selected_rows": len(data), "excluded_rows": excluded, "causal_effect_established": False},
            "grafico": {"tipo": "intervalos", "titulo": "Indicador antes/depois e IC95%", "eixo": parameters["unit"],
                        "itens": [{"label": label, "value": summary["estimate"], "lower": summary["ci95"][0] if summary["ci95"] else None,
                                   "upper": summary["ci95"][1] if summary["ci95"] else None} for label, summary in (("Antes", before), ("Depois", after))],
                        "referencia": {"label": "Meta pós (referência)", "value": target}, "mostrados": 2, "total": 2,
                        "nota": "IC95% Wilson por período." if parameters["kind"] == "proportion" else "IC95% t por média; indisponível se a dispersão amostral é zero."}}
