"""Análises locais sob demanda, com validação explícita dos dados."""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd
from local_diagnosis import ROLES
from local_visuals import present
from local_statistics import crossed_grr, wilson_interval, newcombe_difference, compare_numeric_groups, compare_proportions, factor_anova
from local_survival import kaplan_meier
from local_pilot import compare_pilot


def _existing(name):
    path = Path(__file__).parent / "analysis" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"sigmaflow_local_analysis_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _required(mapping, role):
    col = mapping.get(role)
    if not col:
        raise ValueError(f"Informe a coluna '{ROLES[role][0]}' no mapeamento e atualize as sugestões.")
    return col


def _table(df, mapping, roles, numeric=(), counts=()):
    columns = [_required(mapping, role) for role in roles]
    if len(set(columns)) != len(columns):
        raise ValueError("Selecione uma coluna diferente para cada informação necessária à análise.")
    if any(col not in df.columns for col in columns):
        raise ValueError("Uma das colunas selecionadas não existe na planilha.")
    data = df[columns].copy()
    data.columns = roles
    if data.isna().any().any() or any(data[r].astype(str).str.strip().eq("").any() for r in roles):
        raise ValueError("Há células vazias nas colunas usadas. Revise os dados antes de executar.")
    for role in numeric:
        data[role] = pd.to_numeric(data[role], errors="coerce")
        if data[role].isna().any() or not np.isfinite(data[role]).all():
            raise ValueError(f"A coluna '{mapping[role]}' deve conter somente números válidos.")
    for role in counts:
        if (data[role] < 0).any() or (data[role] % 1 != 0).any():
            raise ValueError(f"A coluna '{mapping[role]}' deve conter contagens inteiras não negativas.")
    return data


def _dated(data):
    parsed = pd.to_datetime(data["data"], errors="coerce", format="mixed", dayfirst=True)
    if parsed.isna().any():
        raise ValueError("Há datas inválidas. Confira a coluna de data antes de executar.")
    data = data.copy()
    data["_ordem"] = parsed
    return data.sort_values("_ordem", kind="stable").reset_index(drop=True)


def _result(title, method, metrics, columns, rows, notes):
    return {"titulo": title, "metodo": method, "indicadores": metrics,
            "colunas": columns, "linhas": rows, "linhas_total": len(rows), "observacoes": notes}


def _date_label(value):
    return str(value.date()) if value == value.normalize() else value.isoformat(sep=" ")


def _n(value, decimals=4):
    val = float(value)
    if not math.isfinite(val):
        raise ValueError("Não foi possível calcular um resultado finito. Revise os dados.")
    return round(val, decimals)


def _p(value):
    return "< 0,000001" if value < 0.000001 else str(round(float(value), 6)).replace(".", ",")


def execute(df: pd.DataFrame, mapping: dict, scenario: str, *, row_limit: int | None = 100, parameters: dict | None = None):
    if row_limit is not None and (isinstance(row_limit, bool) or not isinstance(row_limit, int) or row_limit < 1):
        raise ValueError("O limite de linhas deve ser positivo ou None para a tabela integral.")
    parameters = {} if parameters is None else parameters
    if not isinstance(parameters, dict):
        raise ValueError("Os parâmetros da análise devem ser um objeto JSON.")
    if scenario == "piloto":
        return compare_pilot(df, mapping, parameters)
    if scenario == "atributos":
        if parameters != {"count_basis": "defective_units"}:
            raise ValueError("A carta p/np exige uma contagem confirmada de unidades defeituosas, nao ocorrencias de defeitos.")
        result = _execute(df, mapping, scenario)
        result["parameters"] = {"count_basis": "defective_units"}
        _enrich(df, mapping, scenario, result)
        result.update(present(scenario, result))
        if row_limit is not None:
            result["linhas"] = result["linhas"][:row_limit]
            if isinstance(result.get("linhas_np"), list): result["linhas_np"] = result["linhas_np"][:row_limit]
        return result
    if scenario == "refugo":
        result = _execute(df, mapping, scenario, parameters=parameters)
        _enrich(df, mapping, scenario, result)
        result.update(present(scenario, result))
        if row_limit is not None:
            for key in ("linhas", "linhas_custo", "linhas_estratificacao"):
                if isinstance(result.get(key), list): result[key] = result[key][:row_limit]
        return result
    if scenario == "grupos":
        if not isinstance(mapping, dict):
            raise ValueError("Mapeamento de colunas inválido.")
        if not parameters:
            # Preserve unambiguous legacy measurement runs. Counts and mixed
            # workbooks require the explicit semantic declarations below.
            if mapping.get("medida") and not (mapping.get("defeitos") and mapping.get("total")):
                parameters = {"comparison_kind": "measurement"}
            else:
                raise ValueError("Escolha comparar medições ou a proporção de unidades rejeitadas entre grupos.")
        kind = parameters.get("comparison_kind")
        if kind == "measurement":
            if parameters != {"comparison_kind": "measurement"}:
                raise ValueError("A comparação de medições aceita apenas comparison_kind='measurement'.")
        elif kind == "proportion":
            if (set(parameters) != {"comparison_kind", "count_basis", "denominators_disjoint"}
                    or parameters.get("count_basis") != "defective_units"
                    or parameters.get("denominators_disjoint") is not True):
                raise ValueError("Confirme unidades defeituosas e denominadores distintos por linha: não repita o mesmo total por categoria de defeito.")
        else:
            raise ValueError("Escolha comparar medições ou a proporção de unidades rejeitadas entre grupos.")
        result = _execute(df, mapping, scenario, parameters=parameters)
        result["parameters"] = dict(parameters)
        _enrich(df, mapping, scenario, result)
        result.update(present(scenario, result))
        if row_limit is not None:
            result["linhas"] = result["linhas"][:row_limit]
        return result
    if parameters:
        raise ValueError("Este cenário não aceita parâmetros adicionais.")
    result = _execute(df, mapping, scenario)
    _enrich(df, mapping, scenario, result)
    result.update(present(scenario, result))
    if row_limit is not None:
        result["linhas"] = result["linhas"][:row_limit]
    return result


def _enrich(df, mapping, scenario, result):
    """Acrescenta evidências quantitativas e condições de interpretação."""
    evidence = []
    metrics = result["indicadores"]
    notes = result["observacoes"]
    rows = result["linhas"]
    if scenario == "refugo":
        total = sum(row[1] for row in rows)
        cumulative = 0
        basis = (result.get("parameters") or {}).get("count_unit", "contagem")
        for index, row in enumerate(rows, 1):
            cumulative += row[1]
            if cumulative / total >= 0.8:
                evidence.append(f"As {index} primeiras categorias acumulam {100*cumulative/total:.2f}% da contagem de {basis}; a categoria que cruza 80% está incluída.")
                metrics.append(["Categorias para atingir 80% da contagem", index])
                break
    elif scenario in {"atributos", "capacidade"}:
        if scenario == "atributos":
            data = _table(df, mapping, ["defeitos", "total"], ["defeitos", "total"], ["defeitos", "total"])
            successes = int(data["defeitos"].sum()); trials = int(data["total"].sum())
        else:
            roles = ["medida"] + [key for key in ("lsl", "usl") if mapping.get(key)]
            data = _table(df, mapping, roles, roles)
            outside = pd.Series(False, index=data.index)
            if "lsl" in data: outside |= data["medida"] < data["lsl"]
            if "usl" in data: outside |= data["medida"] > data["usl"]
            successes = int(outside.sum()); trials = len(data)
        lower, upper = wilson_interval(successes, trials)
        metrics.extend([["IC 95% da proporção — inferior (%)", _n(lower*100, 3)], ["IC 95% da proporção — superior (%)", _n(upper*100, 3)]])
        evidence.append(f"Proporção observada: {successes} em {trials}; intervalo de Wilson de 95%: {_n(lower*100, 3)}% a {_n(upper*100, 3)}%.")
        notes.append("O intervalo binomial pressupõe observações independentes e probabilidade comum; lotes, dependência temporal ou medições repetidas podem invalidá-lo.")
    elif scenario == "spc":
        data = _dated(_table(df, mapping, ["data", "medida"], ["medida"]))
        ranges = data["medida"].diff().abs().dropna()
        ucl = 3.267 * float(ranges.mean())
        signals = int((ranges > ucl).sum())
        metrics.extend([["LSC da amplitude móvel", _n(ucl)], ["Sinais na amplitude móvel", signals]])
        evidence.append(f"A carta de amplitude móvel identificou {signals} amplitude(s) acima do LSC {_n(ucl)}; cada amplitude compara duas medições consecutivas.")
        notes[-1] = "Foram verificados pontos além dos limites na carta de individuais e na amplitude móvel; outras regras de sinal não foram avaliadas."
    elif scenario == "grupos":
        if result.get("parameters", {}).get("comparison_kind") == "proportion":
            summaries = result["group_comparison"]["groups"]
            grouped = pd.DataFrame({"defeitos": [item["defective"] for item in summaries],
                                    "total": [item["inspected"] for item in summaries]})
            result_test, reason = compare_proportions(grouped)
            evidence.append("Cada taxa é soma das unidades rejeitadas / soma das unidades inspecionadas no grupo; não é a média simples das taxas por linha.")
            contrast = result["group_comparison"].get("difference")
            if contrast:
                a, b = contrast["group_a"], contrast["group_b"]
                evidence.append(f"Diferença de taxas ({b} − {a}): {_n(contrast['estimate_pp'])} pontos percentuais; IC95% Newcombe-Wilson: {_n(contrast['ci95_pp'][0])} a {_n(contrast['ci95_pp'][1])} p.p.")
        else:
            data = _table(df, mapping, ["grupo", "medida"], ["medida"])
            result_test, reason = compare_numeric_groups(data)
        if result_test:
            pvalue = _p(result_test["p"])
            metrics.extend([["Teste exploratório", result_test["teste"]], ["p-valor", pvalue]])
            evidence.append(f"{result_test['teste']}: p-valor {pvalue if pvalue.startswith('<') else '= ' + pvalue}. O teste avalia evidência de diferença sob suas hipóteses, não causa nem relevância prática.")
            if "ic" in result_test:
                a, b = result_test["grupos"]
                evidence.append(f"Diferença de médias ({a} − {b}): {_n(result_test['diferenca'])}; IC 95%: {_n(result_test['ic'][0])} a {_n(result_test['ic'][1])}.")
        else:
            evidence.append(reason)
        notes.append("Testes exploratórios pressupõem amostras independentes; Welch requer condições adequadas para médias, e contagens exigem unidades independentes. Considere múltiplas comparações e diferenças de contexto.")
    elif scenario == "doe":
        data = _table(df, mapping, ["fator", "medida"], ["medida"])
        test, reason = factor_anova(data)
        if test:
            result["metodo"] = f"{test['teste']} exploratória + descrição por nível"
            pvalue = _p(test["p"])
            variance_p = _p(test["variancia_p"]) if math.isfinite(test["variancia_p"]) else "Não calculado"
            normality_p = _p(test["normalidade_residuos_p"]) if test["normalidade_residuos_p"] is not None else "Não calculado (N fora de 3–5.000)"
            metrics.extend([["Teste F", test["teste"]], ["F observado", _n(test["f"])], ["Graus de liberdade", f"{_n(test['df1'], 2)}; {_n(test['df2'], 2)}"], ["p-valor (exploratório)", pvalue], ["Eta² descritivo", _n(test["eta2"], 4)], ["Levene (p; variâncias)", variance_p], ["Shapiro (p; resíduos)", normality_p]])
            evidence.append(f"{test['teste']}: F = {_n(test['f'])}, gl = {_n(test['df1'], 2)}; {_n(test['df2'], 2)}, p {pvalue if pvalue.startswith('<') else '= ' + pvalue}, eta² descritivo = {_n(test['eta2'], 4)}. Levene p = {variance_p}; Shapiro dos resíduos p = {normality_p}.")
            comparisons = test.get("comparacoes", [])
            result["comparacoes"] = comparisons
            significant_pairs = sum(item["p_holm"] < 0.05 for item in comparisons)
            metrics.append(["Pares com p-Holm < 0,05", significant_pairs])
            for item in comparisons:
                ci_low, ci_high = item["ic_simultaneo"]
                evidence.append(
                    f"Welch pareado {item['grupo_a']} vs. {item['grupo_b']}: diferen\u00e7a de m\u00e9dias = {_n(item['diferenca'])}; "
                    f"IC simult\u00e2neo 95% Bonferroni = {_n(ci_low)} a {_n(ci_high)}; "
                    f"p bruto = {_p(item['p_bruto'])}; p ajustado por Holm = {_p(item['p_holm'])}."
                )
            notes.append("Diagnósticos de Levene e Shapiro são sinais para revisão, não provas de que os pressupostos estejam satisfeitos ou violados. A ANOVA clássica pressupõe independência, resíduos aproximadamente normais e variâncias comparáveis; Welch acomoda variâncias diferentes, mas não dependência nem problemas de distribuição. ANOVA de um fator não estima interações ou prova causalidade.")
            notes.append("As compara\u00e7\u00f5es pareadas usam testes t de Welch; p-valores ajustados por Holm controlam a fam\u00edlia de contrastes. Os intervalos simult\u00e2neos de 95% usam Bonferroni. Pressup\u00f5em grupos independentes e n\u00e3o corrigem vieses de coleta nem tornam o resultado causal.")
        else:
            result["metodo"] = "Descrição por nível (ANOVA não calculada)"
            evidence.append(reason)
            notes.append("A comparação inferencial não foi calculada porque os dados não atenderam ao requisito mínimo descrito na evidência.")
    elif scenario == "oee":
        data = _table(df, mapping, ["parada", "tempo_planejado", "total", "defeitos", "ciclo_ideal"], ["parada", "tempo_planejado", "total", "defeitos", "ciclo_ideal"], ["total", "defeitos"])
        planned = float(data["tempo_planejado"].sum()); stopped = float(data["parada"].sum())
        ideal = float(data["ciclo_ideal"].iloc[0]); operating = planned-stopped
        perf_loss = operating - ideal * float(data["total"].sum())
        quality_loss = ideal * float(data["defeitos"].sum())
        loss_items = [("paradas", stopped), ("desempenho", max(0.0, perf_loss)), ("qualidade", quality_loss)]
        for name, val in loss_items:
            metrics.append([f"Perda de {name} (% do tempo planejado)", _n(100*val/planned, 2)])
        largest = max(item[1] for item in loss_items)
        names = ", ".join(name for name, val in loss_items if abs(val-largest) < 1e-9)
        evidence.append(f"Maior perda equivalente no tempo planejado: {names} ({_n(100*largest/planned, 2)}%). Os três componentes repartem a perda total de OEE quando as definições e o ciclo ideal são consistentes.")
        notes.append("A decomposição de perdas é tempo equivalente, não custo financeiro; a mesma unidade deve ser usada em tempos e ciclo ideal.")
    elif scenario == "fluxo":
        data = _table(df, mapping, ["grupo", "tempo"], ["tempo"])
        longest = data.groupby("grupo", observed=True)["tempo"].median().sort_values(ascending=False)
        evidence.append(f"Maior mediana observada: {longest.index[0]} = {_n(longest.iloc[0])}. Compare também a dispersão e o contexto antes de concluir que essa etapa é o gargalo.")
    elif scenario == "energia":
        data = _table(df, mapping, ["energia", "total"], ["energia", "total"], ["total"])
        specific = data["energia"] / data["total"]
        evidence.append(f"Consumo por unidade nos registros: mínimo {_n(specific.min(), 5)} e máximo {_n(specific.max(), 5)}; o valor global é ponderado pela produção.")
    elif scenario == "confiabilidade":
        evidence.append(f"Foram contados {dict(metrics)['Registros']} registros de falha, agrupados pelo ativo. A contagem não ajusta a exposição ou o tempo em operação de cada equipamento.")
        if mapping.get("tempo_falha"):
            roles = ["ativo", "tempo_falha"] + (["evento"] if mapping.get("evento") else [])
            data = _table(df, mapping, roles, roles[1:])
            if "evento" in data:
                data = data[data["evento"] == 1]
            if (data["tempo_falha"] < 0).any():
                raise ValueError("Tempo até falha não pode ser negativo.")
            if len(data):
                evidence.append(f"Nos registros de falha, o tempo até falha teve mediana {_n(data['tempo_falha'].median())} e média {_n(data['tempo_falha'].mean())}. Esses valores descritivos não são estimativas de MTBF ou confiabilidade com censura.")
            else:
                evidence.append("Não há falhas observadas nos registros; as unidades censuradas não foram contadas como falhas.")
    elif scenario == "sobrevivencia":
        km = result["sobrevivencia"]
        evidence.append(f"Coorte: {km['n']} unidades, {km['falhas']} falhas e {km['censuras']} censuras à direita; horizonte observado τ = {_n(km['tau'])}.")
        evidence.append("Em cada tempo, S(t) = S(anterior) × (1 − falhas / unidades em risco). Censuras no mesmo instante entram no risco daquela falha e são retiradas depois.")
        evidence.append(f"Área sob a curva até τ: RMST = {_n(km['rmst'])}. Não foi extrapolada a curva além do acompanhamento observado.")
        evidence.append("A mediana é o primeiro tempo com S(t) ≤ 50%, reconhecendo o platô de 50%. IC95% pontuais usam Greenwood na escala log-log; nas fronteiras S = 0 ou 1 são apresentados como não estimados.")
    elif scenario == "fmea":
        severity = max(row[1] for row in rows)
        high = [str(row[0]) for row in rows if row[1] == severity]
        evidence.append(f"Maior severidade registrada: {severity}; modo(s): {', '.join(high[:5])}{' e outros' if len(high) > 5 else ''}. Examine a severidade separadamente da ordenação por RPN.")
    elif scenario == "msa":
        interaction = next(row for row in rows if row[0] == "Interação peça × operador")
        evidence.append(f"Interação peça × operador: {_n(interaction[2], 2)}% da variação de estudo estimada. Os percentuais de estudo não são parcelas aditivas.")
    result["evidencias"] = evidence


def _proportion_groups(df, mapping):
    data = _table(df, mapping, ["grupo", "defeitos", "total"], ["defeitos", "total"], ["defeitos", "total"])
    maximum_integer = 2**53 - 1
    for role in ("defeitos", "total"):
        if df[mapping[role]].map(lambda value: isinstance(value, (bool, np.bool_))).any():
            raise ValueError("Valores lógicos não substituem contagens de unidades.")
        if (data[role] > maximum_integer).any():
            raise ValueError("Uma contagem excede a precisão suportada pelo navegador; reduza o recorte dos dados.")
    if (data["total"] <= 0).any() or (data["defeitos"] > data["total"]).any():
        raise ValueError("Cada linha precisa de total positivo e unidades rejeitadas entre zero e o total.")
    data["grupo"] = data["grupo"].astype(str).str.strip()
    if not 2 <= data["grupo"].nunique() <= 50:
        raise ValueError("A comparação de proporções aceita de 2 a 50 grupos; revise se a coluna representa grupos ou identificadores.")
    summaries = []
    for label, part in data.groupby("grupo", sort=False, observed=True):
        defective = sum(int(value) for value in part["defeitos"])
        inspected = sum(int(value) for value in part["total"])
        if inspected > maximum_integer:
            raise ValueError("A soma de unidades inspecionadas excede a precisão suportada pelo navegador.")
        lower, upper = wilson_interval(defective, inspected)
        summaries.append({"label": label, "records": len(part), "defective": defective,
                          "inspected": inspected, "rate": 100*defective/inspected,
                          "ci95": [100*lower, 100*upper]})
    all_defective = sum(item["defective"] for item in summaries)
    all_inspected = sum(item["inspected"] for item in summaries)
    if all_inspected > maximum_integer:
        raise ValueError("A soma de unidades inspecionadas excede a precisão suportada pelo navegador.")
    metrics = [["Grupos", len(summaries)], ["Unidades rejeitadas", all_defective],
               ["Unidades inspecionadas", all_inspected], ["Taxa global ponderada (%)", _n(100*all_defective/all_inspected, 6)]]
    rows = [[item["label"], item["defective"], item["inspected"], _n(item["rate"], 6),
             _n(item["ci95"][0], 6), _n(item["ci95"][1], 6), item["records"]] for item in summaries]
    notes = ["O numerador representa unidades defeituosas contadas uma vez, e o denominador deve corresponder às mesmas unidades inspecionadas. A confirmação de denominadores distintos foi declarada pelo analista; o sistema não detecta repetição do mesmo lote por categoria de defeito.",
             "Wilson e o teste global pressupõem unidades independentes com probabilidade comum dentro de cada grupo. Dependência temporal, lotes correlacionados, repetições e diferenças de produto/mix exigem revisão do desenho.",
             "IC95% Wilson são intervalos pontuais por grupo, não intervalos simultâneos. A comparação é observacional: diferenças não demonstram causa nem eficácia de uma ação."]
    comparison = {"kind": "proportion", "group_column": mapping["grupo"], "groups": summaries, "difference": None}
    if len(summaries) == 2:
        a, b = summaries
        estimate, interval = newcombe_difference(a["defective"], a["inspected"], b["defective"], b["inspected"])
        comparison["difference"] = {"group_a": a["label"], "group_b": b["label"],
                                     "estimate_pp": 100*estimate, "ci95_pp": [100*value for value in interval],
                                     "method": "Newcombe-Wilson sem correção de continuidade"}
        metrics.extend([[f"Diferença {b['label']} − {a['label']} (p.p.)", _n(100*estimate, 6)],
                        ["IC95% da diferença — inferior (p.p.)", _n(100*interval[0], 6)],
                        ["IC95% da diferença — superior (p.p.)", _n(100*interval[1], 6)]])
        notes.append("A diferença em pontos percentuais é grupo B menos grupo A, na ordem de primeira aparição dos grupos. IC95% aproximado de Newcombe-Wilson para duas proporções independentes; não infira o teste a partir da sobreposição dos ICs individuais.")
    else:
        notes.append("Com três ou mais grupos, o teste é global: não identifica quais pares diferem. Não foram calculados contrastes pareados ou intervalos simultâneos.")
    result = _result("Taxa de unidades rejeitadas entre grupos", "Proporções ponderadas; IC95% Wilson; teste global exploratório",
                     metrics, ["Grupo", "Unidades rejeitadas", "Unidades inspecionadas", "Taxa (%)", "IC95% inferior (%)", "IC95% superior (%)", "Registros"], rows, notes)
    result["group_comparison"] = comparison
    return result


def _execute(df: pd.DataFrame, mapping: dict, scenario: str, *, parameters=None):
    if not isinstance(mapping, dict):
        raise ValueError("Mapeamento de colunas inválido.")
    if df.empty:
        raise ValueError("A planilha não possui dados.")

    if scenario == "refugo":
        parameters = parameters or {}
        basis = parameters.get("count_basis")
        if basis not in {"defective_units", "defect_occurrences"}:
            raise ValueError("Confirme se a coluna representa unidades defeituosas ou ocorrencias de defeitos.")
        selected_costs = [role for role in ("custo_unitario", "custo_total") if mapping.get(role)]
        if len(selected_costs) > 1 or mapping.get("custo"):
            raise ValueError("Selecione apenas custo unitario por unidade rejeitada ou custo total por registro. O campo legado 'custo' e ambiguo.")
        roles = ["categoria", "defeitos"]
        numeric = ["defeitos"]
        counts = ["defeitos"]
        if mapping.get("grupo"):
            roles.append("grupo")
        roles.extend(selected_costs)
        numeric.extend(selected_costs)
        data = _table(df, mapping, roles, numeric, counts)
        if data["categoria"].astype(str).str.strip().eq("").any():
            raise ValueError("Preencha a categoria de defeito em todas as linhas usadas.")
        data["categoria"] = data["categoria"].astype(str).str.strip()
        if data["defeitos"].sum() <= 0:
            raise ValueError("E necessario haver pelo menos uma unidade/ocorrencia rejeitada para calcular o Pareto.")
        if selected_costs == ["custo_unitario"] and basis != "defective_units":
            raise ValueError("Custo unitario so pode ser multiplicado por contagem confirmada de unidades defeituosas. Use custo total por registro para ocorrencias.")
        if selected_costs and (data[selected_costs[0]] < 0).any():
            raise ValueError("Custos negativos exigem classificacao contabil explicita e nao podem ser somados neste Pareto.")
        cost_col = None
        if selected_costs:
            cost_col = "_custo_total"
            if selected_costs[0] == "custo_unitario":
                data[cost_col] = data["defeitos"] * data["custo_unitario"]
            else:
                data[cost_col] = data["custo_total"]
        quantity = data.groupby("categoria", as_index=False, sort=False)["defeitos"].sum()
        quantity = quantity.sort_values(["defeitos", "categoria"], ascending=[False, True], kind="stable").reset_index(drop=True)
        total = int(quantity["defeitos"].sum())
        quantity["percent"] = quantity["defeitos"] / total * 100
        quantity["cumulative"] = quantity["percent"].cumsum()
        basis_label = "unidades defeituosas" if basis == "defective_units" else "ocorrencias de defeitos"
        rows = [[str(row.categoria), int(row.defeitos), _n(row.percent, 2), _n(row.cumulative, 2)] for row in quantity.itertuples()]
        title = "Pareto de unidades defeituosas" if basis == "defective_units" else "Pareto de ocorrencias de defeitos"
        metrics = [["Total de " + basis_label, total], ["Categorias", len(rows)]]
        result = _result(title, "Pareto de contagem confirmada pelo analista", metrics,
                         ["Categoria", "Quantidade", "% da contagem", "% acumulado"], rows,
                         ["Confirme se cada linha representa unidade independente ou ocorrencia; contagens de defeitos nao equivalem necessariamente a unidades defeituosas.",
                          "Prioridade de Pareto indica concentracao observada, nao causa comprovada. Custos nao incluem custos indiretos ou de oportunidade."])
        result["observacoes"].append("O Pareto por quantidade ordena contagens absolutas; sem denominador de produção, não compara taxas entre períodos, linhas ou turnos. O corte de 80% é uma heurística de priorização, não uma regra universal.")
        result["parameters"] = {"count_basis": basis, "count_unit": basis_label}
        if cost_col:
            costs = data.groupby("categoria", as_index=False, sort=False)[cost_col].sum().rename(columns={cost_col:"cost"})
            costs = costs.sort_values(["cost", "categoria"], ascending=[False, True], kind="stable").reset_index(drop=True)
            cost_total = float(costs["cost"].sum())
            if cost_total > 0:
                costs["percent"] = costs["cost"] / cost_total * 100
                costs["cumulative"] = costs["percent"].cumsum()
                result["linhas_custo"] = [[str(row.categoria), _n(row.cost, 2), _n(row.percent, 2), _n(row.cumulative, 2)] for row in costs.itertuples()]
            else:
                result["linhas_custo"] = [[str(row.categoria), _n(row.cost, 2), None, None] for row in costs.itertuples()]
            result["colunas_custo"] = ["Categoria", "Custo da perda (unidade monetaria informada)", "% do custo", "% acumulado"]
            result["custo_total"] = _n(cost_total, 2)
            result["indicadores"].append(["Custo total registrado", _n(cost_total, 2)])
            result["custo_tipo"] = "unitario_multiplicado" if selected_costs[0] == "custo_unitario" else "total_por_registro"
            result["parameters"]["cost_basis"] = result["custo_tipo"]
            result["parameters"]["cost_column"] = mapping[selected_costs[0]]
            result["observacoes"].append("Para custo unitario, o custo da perda foi calculado como quantidade rejeitada x custo unitario. Para custo total, os valores informados por registro foram somados. Confirme moeda, periodo e ausencia de duplicacao.")
            if selected_costs[0] == "custo_unitario":
                result["observacoes"].append("Confirme o grão dos dados: cada unidade rejeitada deve ser contada uma única vez para evitar multiplicar novamente o mesmo custo em registros ou categorias duplicados.")
        if mapping.get("grupo"):
            group_cols = ["grupo", "categoria"]
            aggregated = data.groupby(group_cols, as_index=False, sort=False).agg(quantity=("defeitos", "sum"))
            if cost_col:
                cost_data = data.groupby(group_cols, as_index=False, sort=False)[cost_col].sum().rename(columns={cost_col:"cost"})
                aggregated = aggregated.merge(cost_data, on=group_cols, how="left")
            strata = []
            for group, subset in aggregated.groupby("grupo", sort=False):
                qtotal = float(subset["quantity"].sum())
                ctotal = float(subset["cost"].sum()) if cost_col else 0
                for row in subset.sort_values(["quantity", "categoria"], ascending=[False, True], kind="stable").itertuples():
                    entry = [str(group), str(row.categoria), int(row.quantity), _n(100*row.quantity/qtotal, 2)]
                    if cost_col: entry.extend([_n(row.cost, 2), _n(100*row.cost/ctotal, 2) if ctotal else None])
                    strata.append(entry)
            result["linhas_estratificacao"] = strata
            result["colunas_estratificacao"] = ["Grupo", "Categoria", "Contagem", "% da contagem do grupo"] + (["Custo", "% do custo do grupo"] if cost_col else [])
            result["observacoes"].append("A estratificação compara a composição das contagens dentro de cada grupo; não ajusta pelo volume produzido e não estima taxa de defeito ou causa. Para comparar desempenho entre grupos, use o denominador de produção e um método apropriado para proporções.")
            result["estratificacao_total"] = len(strata)
        return result

    if scenario == "atributos":
        data = _dated(_table(df, mapping, ["data", "defeitos", "total"], ["defeitos", "total"], ["defeitos", "total"]))
        if len(data) < 2 or (data["total"] <= 0).any() or (data["defeitos"] > data["total"]).any():
            raise ValueError("São necessários pelo menos dois registros, com quantidade inspecionada positiva e rejeitados menores ou iguais ao total.")
        p = _existing("transformations").compute_p_chart(data["defeitos"].to_numpy(), data["total"].to_numpy())
        rows = [[_date_label(date), int(d), int(n), _n(100 * ratio, 3), _n(100 * lo, 3), _n(100 * min(hi, 1), 3)]
                for date, d, n, ratio, lo, hi in zip(data["_ordem"], data["defeitos"], data["total"], p["p_values"], p["LCL"], p["UCL"])]
        result = _result("Carta p: proporção de unidades rejeitadas", "Carta p com limites de 3 desvios por tamanho de amostra", [["Taxa global (%)", _n(p["p_bar"] * 100, 3)], ["Amostras", len(data)], ["Pontos além dos limites", len(p["ooc_indices"])]],
                         ["Data", "Rejeitados", "Inspecionados", "Taxa (%)", "LIC (%)", "LSC (%)"], rows,
                         ["Limites calculados com toda a amostra como linha de base explorat\u00f3ria; validar antes do uso em produ\u00e7\u00e3o. Cada linha deve representar um subgrupo independente.", "Apenas pontos fora dos limites s\u00e3o contados; outras regras de sinal n?o foram avaliadas."])
        if data["total"].nunique() == 1:
            n = int(data["total"].iloc[0]); center = n * float(p["p_bar"])
            sigma = math.sqrt(n * float(p["p_bar"]) * (1 - float(p["p_bar"])))
            lo, hi = max(0.0, center - 3*sigma), min(float(n), center + 3*sigma)
            np_rows = [[_date_label(date), int(defects), _n(lo), _n(center), _n(hi), "Sim" if defects < lo or defects > hi else "N\u00e3o"]
                       for date, defects in zip(data["_ordem"], data["defeitos"])]
            result["indicadores"].append(["Pontos np além dos limites", sum(row[-1] == "Sim" for row in np_rows)])
            result["linhas_np_total"] = len(np_rows)
            result["linhas_np"] = np_rows
            result["colunas_np"] = ["Data", "Unidades defeituosas", "LIC np", "Linha central np", "LSC np", "Fora dos limites"]
            result["observacoes"].append("A carta np foi calculada porque todos os subgrupos t\u00eam o mesmo tamanho. Ela expressa a mesma contagem em unidades; escolha a apresenta\u00e7\u00e3o mais clara para a equipe.")
        return result

    if scenario == "spc":
        data = _dated(_table(df, mapping, ["data", "medida"], ["medida"]))
        if len(data) < 5:
            raise ValueError("Informe ao menos cinco medições individuais ordenadas para uma carta exploratória.")
        values = data["medida"].to_numpy(dtype=float)
        mr = np.abs(np.diff(values))
        mrbar = float(mr.mean())
        if mrbar == 0:
            raise ValueError("A amplitude móvel média é zero; não é possível estimar limites de controle úteis.")
        mean = float(values.mean()); sigma = mrbar / 1.128
        lo, hi = mean - 3 * sigma, mean + 3 * sigma
        rows = [[_date_label(date), _n(value), _n(lo), _n(mean), _n(hi), "Sim" if value < lo or value > hi else "Não"] for date, value in zip(data["_ordem"], values)]
        return _result("Carta de individuais e amplitude móvel", "I-MR: desvio dentro estimado por amplitude móvel média / 1,128", [["Média", _n(mean)], ["Amplitude móvel média", _n(mrbar)], ["Sinais individuais", sum(row[-1] == "Sim" for row in rows)]],
                       ["Data", "Medição", "LIC", "Linha central", "LSC", "Fora dos limites"], rows,
                       ["Limites exploratórios estimados com os próprios dados. Confirme a ordem e a linha de base antes do monitoramento; não equivale a uma avaliação completa de estabilidade.", "Apenas pontos individuais fora dos limites foram contados; outras regras e a carta MR não foram avaliadas como sinais."])

    if scenario == "capacidade":
        roles = ["medida"] + [key for key in ("lsl", "usl") if mapping.get(key)]
        if len(roles) < 2:
            raise ValueError("Informe a medição e ao menos um limite de especificação.")
        data = _table(df, mapping, roles, roles)
        if len(data) < 2:
            raise ValueError("São necessárias pelo menos duas medições.")
        for role in roles[1:]:
            if data[role].nunique() != 1:
                raise ValueError("Os limites de especificação variam. Separe produtos ou períodos com especificações diferentes.")
        lsl = float(data["lsl"].iloc[0]) if "lsl" in data else None
        usl = float(data["usl"].iloc[0]) if "usl" in data else None
        if lsl is not None and usl is not None and lsl >= usl:
            raise ValueError("O limite inferior deve ser menor que o limite superior.")
        values = data["medida"]; mean = float(values.mean()); sd = float(values.std(ddof=1))
        outside = pd.Series(False, index=values.index)
        if lsl is not None: outside |= values < lsl
        if usl is not None: outside |= values > usl
        metrics = [["Medições", len(values)], ["Fora da especificação", int(outside.sum())], ["Fora da especificação (%)", _n(outside.mean()*100, 2)], ["Média", _n(mean)], ["Desvio padrão global", _n(sd)]]
        rows = [["Limite inferior", lsl if lsl is not None else "Não informado"], ["Limite superior", usl if usl is not None else "Não informado"]]
        if sd > 0:
            if lsl is not None and usl is not None:
                base = _existing("capability_analysis").compute_capability(values, usl=usl, lsl=lsl)
                rows += [["Pp preliminar", base["Pp"]], ["Ppk preliminar", base["Ppk"]]]
            elif usl is not None: rows += [["Ppu preliminar", _n((usl - mean)/(3*sd))]]
            else: rows += [["Ppl preliminar", _n((mean - lsl)/(3*sd))]]
        return _result("Desempenho frente às especificações", "Contagem observada e índices preliminares com desvio global", metrics, ["Indicador", "Valor"], rows,
                       ["Os índices são preliminares e dependem de estabilidade, sistema de medição e distribuição adequados; não são uma declaração de capacidade. Não se estima Cpk com esta análise.", "Uma amostra sem rejeições não demonstra que a taxa real de defeitos seja zero."] + (["O desvio global é zero; índices não foram calculados."] if sd == 0 else []))

    if scenario in {"grupos", "fluxo", "doe"}:
        if scenario == "fluxo": group, value, title = "grupo", "tempo", "Tempo por etapa"
        elif scenario == "doe": group, value, title = "fator", "medida", "Resposta por nível do fator"
        else: group, value, title = "grupo", "medida", "Comparação de grupos"
        if scenario == "grupos" and parameters.get("comparison_kind") == "proportion":
            return _proportion_groups(df, mapping)
        data = _table(df, mapping, [group, value], [value])
        if scenario == "fluxo" and (data[value] < 0).any():
            raise ValueError("O tempo de processo não pode ser negativo.")
        groups = data.groupby(group, sort=True, dropna=False)[value]
        rows = [[str(name), int(len(series)), _n(series.mean()), _n(series.median()), _n(series.min()), _n(series.max())] for name, series in groups]
        notes = ["As diferenças observadas não comprovam causalidade. Revise os pressupostos e as condições de coleta antes de interpretar qualquer teste."]
        if scenario == "doe": notes.append("Agrupamento por um fator não valida um DOE; confirme randomização, replicação, interações e condições do experimento.")
        method = "ANOVA exploratória de um fator + descrição por nível" if scenario == "doe" else "Estatística descritiva estratificada"
        return _result(title, method, [["Registros", len(data)], ["Grupos", len(rows)]], ["Grupo / nível", "N", "Média", "Mediana", "Mínimo", "Máximo"], rows, notes)

    if scenario == "fmea":
        roles = ["categoria", "severidade", "ocorrencia", "deteccao"]
        data = _table(df, mapping, roles, roles[1:], roles[1:])
        if any(((data[r] < 1) | (data[r] > 10)).any() for r in roles[1:]):
            raise ValueError("Severidade, ocorrência e detecção devem ser inteiros de 1 a 10 para este cálculo.")
        output = _existing("fmea_analysis").FMEAAnalyzer(data, "categoria", "severidade", "ocorrencia", "deteccao").run()
        rows = [[item["failure_mode"], item["severity"], item["occurrence"], item["detection"], item["rpn"]] for item in output["ranked_modes"]]
        return _result("FMEA: ranking por RPN", "RPN = severidade × ocorrência × detecção", [["Modos de falha", len(rows)], ["Maior RPN", output["max_rpn"]]], ["Modo de falha", "S", "O", "D", "RPN"], rows, ["O RPN é apenas uma ordenação numérica. A equipe deve considerar severidade, controles e critérios de prioridade adotados; ele não substitui uma avaliação completa de risco."])

    if scenario == "msa":
        data = _table(df, mapping, ["peca", "operador", "medida"], ["medida"])
        out = crossed_grr(data)
        rows = [[name, _n(variation), _n(percent, 2)] for name, variation, percent in out["componentes"]]
        grr = next(row[2] for row in rows if row[0] == "Gauge R&R")
        metrics = [["Peças", out["pecas"]], ["Operadores", out["operadores"]], ["Repetições por combinação", out["repeticoes"]], ["% variação do estudo Gage R&R", grr], ["NDC estimado", out["ndc"] if out["ndc"] is not None else "Não definido (R&R zero)"]]
        if out["interacao_p"] is not None:
            metrics.append(["p-valor interação", _p(out["interacao_p"])])
        return _result("MSA cruzado: Gauge R&R preliminar", "ANOVA cruzada balanceada com interação peça × operador", metrics, ["Componente", "Variação de estudo (5,15σ)", "% variação do estudo"], rows, ["Componentes negativos estimados são truncados em zero; a interação não é agrupada automaticamente no erro. Os percentuais de estudo incluem componentes sobrepostos e não podem ser somados.", "Revise aleatorização, estabilidade, resolução, representatividade e pressupostos com um especialista antes de aceitar o sistema de medição."])

    if scenario == "oee":
        roles = ["parada", "tempo_planejado", "total", "defeitos", "ciclo_ideal"]
        data = _table(df, mapping, roles, roles, ["total", "defeitos"])
        if (data["tempo_planejado"] <= 0).any() or (data["parada"] < 0).any() or (data["parada"] >= data["tempo_planejado"]).any() or (data["total"] <= 0).any() or (data["defeitos"] > data["total"]).any() or (data["ciclo_ideal"] <= 0).any():
            raise ValueError("Confira tempos positivos, parada menor que tempo planejado e rejeitados não superiores à produção.")
        if data["ciclo_ideal"].nunique() != 1:
            raise ValueError("Separe produtos com ciclos ideais diferentes antes de calcular este OEE.")
        planned = float(data["tempo_planejado"].sum()); operating = planned - float(data["parada"].sum())
        total = int(data["total"].sum()); rejected = int(data["defeitos"].sum()); ideal = float(data["ciclo_ideal"].iloc[0])
        availability = operating / planned; performance = total*ideal / operating; quality = (total-rejected)/total
        if performance > 1 + 1e-9:
            raise ValueError("A produção e o ciclo ideal implicam desempenho acima de 100%. Confira unidades e tempos.")
        return _result("OEE do período", "Disponibilidade × desempenho × qualidade", [["OEE (%)", _n(availability*performance*quality*100, 2)], ["Disponibilidade (%)", _n(availability*100, 2)], ["Desempenho (%)", _n(performance*100, 2)], ["Qualidade (%)", _n(quality*100, 2)]], ["Componente", "Quantidade"], [["Tempo planejado", _n(planned)], ["Tempo de parada", _n(data["parada"].sum())], ["Produção total", total], ["Unidades boas", total-rejected]], ["Tempo planejado, paradas e ciclo ideal devem usar a mesma unidade. Confirme que os rejeitados são unidades e que os registros não se sobrepõem."])

    if scenario == "energia":
        data = _table(df, mapping, ["energia", "total"], ["energia", "total"], ["total"])
        if (data["energia"] < 0).any() or (data["total"] <= 0).any():
            raise ValueError("Consumo deve ser não negativo e a produção deve ser positiva em cada linha.")
        energy = float(data["energia"].sum()); total = int(data["total"].sum())
        return _result("Consumo específico de energia", "Consumo total dividido pela produção total", [["Consumo total", _n(energy)], ["Unidades produzidas", total], ["Consumo por unidade", _n(energy/total, 5)]], ["Registro", "Consumo", "Produção", "Consumo por unidade"], [[i+1, _n(row.energia), int(row.total), _n(row.energia/row.total, 5)] for i, row in enumerate(data.itertuples(index=False))], ["Confirme unidade de energia, período, produto e coincidência entre consumo e produção. O resultado é descritivo."])

    if scenario == "sobrevivencia":
        data = _table(df, mapping, ["ativo", "tempo_falha", "evento"], ["tempo_falha", "evento"])
        if data["ativo"].duplicated().any():
            raise ValueError("Kaplan–Meier requer uma linha por unidade independente com identificador único. Repetições por ativo podem indicar eventos recorrentes e precisam de outro desenho.")
        km = kaplan_meier(data["tempo_falha"].to_numpy(), data["evento"].to_numpy())
        rows = [[_n(item["tempo"], 6), item["risco"], item["falhas"], item["censuras"], _n(100*item["sobrevivencia"], 6),
                 _n(100*item["inferior"], 6) if item["inferior"] is not None else "Não estimado",
                 _n(100*item["superior"], 6) if item["superior"] is not None else "Não estimado"] for item in km["tabela"]]
        metrics = [["Unidades acompanhadas", km["n"]], ["Falhas observadas", km["falhas"]], ["Censuras à direita", km["censuras"]],
                   ["Horizonte τ (unidade da planilha)", _n(km["tau"])], ["Sobrevivência estimada em τ (%)", _n(100*km["sobrevivencia_final"], 3)],
                   ["Mediana de vida (unidade da planilha)", _n(km["mediana"]) if km["mediana"] is not None else "Não alcançada"],
                   ["Tempo médio restrito a τ (RMST)", _n(km["rmst"])]]
        notes = ["Cada linha deve acompanhar uma unidade desde uma origem de tempo comparável; use a mesma definição de falha e unidade de tempo. Identificadores diferentes não comprovam independência.",
                 "A análise pressupõe censura à direita não informativa. Censura à esquerda/intervalar, entrada tardia, eventos recorrentes e riscos competitivos não são modelados.",
                 "IC95% são pontuais, não bandas simultâneas. Nas fronteiras 0/100% o intervalo log-log não é estimado; isso não demonstra confiabilidade certa ou risco nulo.",
                 "RMST é a área da curva apenas até τ, sem IC nesta versão. Não é MTBF; comparações de RMST exigem horizonte comum definido e populações comparáveis."]
        if not km["falhas"]:
            notes.append("Nenhuma falha foi observada: a curva estimada fica em 100%, mas estes dados não comprovam vida infinita ou confiabilidade de 100%.")
        out = _result("Sobrevivência com censura à direita", "Kaplan–Meier; IC95% pontual log-log de Greenwood; RMST até τ", metrics,
                      ["Tempo observado", "Em risco antes", "Falhas", "Censuras", "S(t) (%)", "IC95 inferior (%)", "IC95 superior (%)"], rows, notes)
        out["sobrevivencia"] = {key: value for key, value in km.items() if key != "tabela"}
        points = [{"tempo": 0.0, "sobrevivencia": 100.0, "inferior": None, "superior": None, "risco": km["n"], "falhas": 0, "censuras": 0}]
        points.extend({**item, "sobrevivencia": 100*item["sobrevivencia"],
                       "inferior": None if item["inferior"] is None else 100*item["inferior"],
                       "superior": None if item["superior"] is None else 100*item["superior"]} for item in km["tabela"])
        out["grafico"] = {"tipo": "sobrevivencia", "titulo": "Curva de sobrevivência — Kaplan–Meier", "eixo": "Probabilidade de permanecer sem falha (%)",
                          "x_label": str(mapping["tempo_falha"]), "pontos": points[:1000], "total": len(points), "mostrados": min(1000, len(points)),
                          "nota": "IC95% pontuais; limites não estimados quando S = 0 ou 100%. + indica censura à direita. A tabela mostra o número de unidades em risco antes de cada tempo."}
        return out

    if scenario == "confiabilidade":
        roles = ["ativo"] + (["falha"] if mapping.get("falha") else ["tempo_falha"]) + (["evento"] if mapping.get("evento") else [])
        numeric = [role for role in ("tempo_falha", "evento") if role in roles]
        data = _table(df, mapping, roles, numeric)
        excluded = 0
        if "evento" in data:
            if not data["evento"].isin([0, 1]).all():
                raise ValueError("Evento deve ser 1 para falha observada ou 0 para censura à direita.")
            excluded = int((data["evento"] == 0).sum())
            data = data[data["evento"] == 1]
        if "tempo_falha" in data and (data["tempo_falha"] < 0).any():
            raise ValueError("Tempo até falha não pode ser negativo.")
        counts = data.groupby("ativo").size().sort_values(ascending=False)
        return _result("Registros de falhas por equipamento", "Contagem descritiva por ativo", [["Registros", len(data)], ["Equipamentos com falha", len(counts)], ["Censuras excluídas da contagem", excluded]], ["Equipamento", "Registros", "% do total"], [[str(name), int(count), _n(count/len(data)*100, 2)] for name, count in counts.items()], ["Cada linha deve representar uma falha ou informar evento 0/1. Censuras mapeadas como evento 0 são excluídas. Esta contagem não estima MTBF nem vida útil; essas análises exigem exposição e registros censurados."])

    raise ValueError("Este cenário ainda não possui análise disponível.")
