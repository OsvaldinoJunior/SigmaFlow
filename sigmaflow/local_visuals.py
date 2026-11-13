"""Gráficos e interpretação descritiva para resultados locais já calculados."""
from __future__ import annotations


def _fmt(value):
    if isinstance(value, int):
        return f"{value:,}".replace(",", ".")
    return f"{float(value):,.3f}".rstrip("0").rstrip(".").replace(",", "_").replace(".", ",").replace("_", ".")


def _bars(title, axis, rows, label_index, value_index, limit=10):
    items = [{"label": str(row[label_index]), "value": row[value_index]} for row in rows[:limit]]
    return {"tipo": "barras", "titulo": title, "eixo": axis, "itens": items,
            "mostrados": len(items), "total": len(rows)}


def _pareto(title, axis, rows, limit=10):
    items = [{"label": str(row[0]), "value": row[1], "cumulative": row[3]} for row in rows[:limit]]
    return {"tipo": "pareto", "titulo": title, "eixo": axis, "itens": items,
            "mostrados": len(items), "total": len(rows)}


def _lines(title, axis, rows, series, limit=100):
    shown = rows[:limit]
    return {"tipo": "linhas", "titulo": title, "eixo": axis,
            "rotulos": [str(row[0]) for row in shown],
            "series": [{"nome": name, "valores": [row[index] for row in shown]} for name, index in series],
            "mostrados": len(shown), "total": len(rows)}


def _leader(rows, index):
    highest = max(float(row[index]) for row in rows)
    leaders = [str(row[0]) for row in rows if float(row[index]) == highest]
    name = leaders[0] if len(leaders) == 1 else f"{leaders[0]} e mais {len(leaders)-1} em empate"
    return name, highest


def present(scenario, result):
    rows = result["linhas"]
    metrics = dict(result["indicadores"])
    if scenario == "confiabilidade" and metrics.get("Registros") == 0:
        return {"grafico": None, "insight": "Nenhuma falha foi observada nos registros enviados. As unidades censuradas não foram contadas como falhas.",
                "proximo_passo": "Use o cenário de vida útil com os tempos e eventos para considerar o acompanhamento das unidades ainda sem falha."}
    if not rows:
        return {"grafico": None, "insight": "Não há linhas disponíveis para apresentar.", "proximo_passo": "Revise os dados usados."}

    if scenario == "refugo":
        name, value = _leader(rows, 1)
        total_label = next(label for label, _ in result["indicadores"] if str(label).startswith("Total de "))
        total = metrics[total_label]
        pct = value / total * 100
        chart = _pareto("Pareto por contagem", "Contagem absoluta; linha = percentual acumulado", rows)
        insight = f"A maior contagem foi {_fmt(value)} para {name}, equivalente a {_fmt(pct)}% de {total_label.lower()}."
        next_step = "Investigue a categoria e valide as causas com evidencias. A concentracao observada, sozinha, nao prova qual processo ou condicao gera a perda."
        output = {"grafico": chart, "insight": insight, "proximo_passo": next_step}
        if result.get("linhas_custo"):
            cost_name, cost_value = _leader(result["linhas_custo"], 1)
            cost_total = result.get("custo_total", 0)
            cost_pct = cost_value / cost_total * 100 if cost_total else None
            if cost_total > 0:
                output["grafico_custo"] = _pareto("Pareto por custo registrado", "Valor monetário informado; linha = percentual acumulado", result["linhas_custo"])
            else:
                output["insight"] += " Os custos informados somam zero; participação e acumulado por custo não foram calculados."
            share = f" ({_fmt(cost_pct)}% do custo registrado)" if cost_pct is not None else " (total de custo igual a zero; participacao nao calculada)"
            output["insight"] += f" O maior custo foi para {cost_name}: {_fmt(cost_value)}{share}."
            output["proximo_passo"] += " Compare o Pareto de quantidade com o de custo antes de priorizar; custos indiretos, retrabalho e impacto ao cliente podem nao estar incluidos."
        if result.get("linhas_estratificacao"):
            output["proximo_passo"] += " A tabela estratificada mostra as categorias dentro do grupo selecionado; diferencas devem ser investigadas, nao atribuidas causalmente ao grupo."
        return output

    if scenario == "atributos":
        signals = metrics["Pontos além dos limites"]
        chart = _lines("Carta p — taxa e limites", "Taxa de unidades rejeitadas (%)", rows, [("Taxa (%)", 3), ("LIC (%)", 4), ("LSC (%)", 5)])
        chart["series"].append({"nome": "Linha central (%)", "valores": [metrics["Taxa global (%)"]] * chart["mostrados"]})
        output = {"grafico": chart,
                  "insight": f"A taxa global observada foi {_fmt(metrics['Taxa global (%)'])}% e {signals} ponto(s) ficaram além dos limites calculados.",
                  "proximo_passo": "Revise os pontos sinalizados e as condi\u00e7\u00f5es de coleta. Valide a linha de base antes do acompanhamento."}
        if result.get("linhas_np"):
            output["grafico_np"] = _lines("Carta np: contagem de unidades rejeitadas", "Unidades defeituosas por subgrupo de tamanho fixo", result["linhas_np"], [("Rejeitadas",1),("LIC np",2),("Linha central np",3),("LSC np",4)])
            output["insight"] += f" A carta np também foi calculada para tamanho fixo ({metrics.get('Pontos np além dos limites', 0)} sinal(is))."
        return output

    if scenario == "spc":
        signals = metrics["Sinais individuais"]
        return {"grafico": _lines("Carta de individuais", "Medição na unidade original", rows, [("Medição", 1), ("LIC", 2), ("Linha central", 3), ("LSC", 4)]),
                "insight": f"A média das medições foi {_fmt(metrics['Média'])}; {signals} ponto(s) ficaram fora dos limites individuais calculados.",
                "proximo_passo": "Investigue o contexto dos pontos sinalizados e revise a sequência e a linha de base; ausência de sinais neste teste não comprova estabilidade."}

    if scenario == "capacidade":
        total = metrics["Medições"]; outside = metrics["Fora da especificação"]
        bars = [["Dentro da especificação", total - outside], ["Fora da especificação", outside]]
        return {"grafico": _bars("Medições e especificação", "Quantidade de medições", bars, 0, 1),
                "insight": f"Das {_fmt(total)} medições, {_fmt(outside)} ficaram fora dos limites informados ({_fmt(metrics['Fora da especificação (%)'])}%).",
                "proximo_passo": "Confirme os limites, a confiabilidade da medição e a estabilidade antes de usar os índices preliminares para decisões de capacidade."}

    if scenario == "grupos" and result.get("group_comparison", {}).get("kind") == "proportion":
        comparison = result["group_comparison"]
        summaries = comparison["groups"]
        name, value = _leader([[item["label"], item["rate"]] for item in summaries], 1)
        insight = f"A maior taxa observada foi {_fmt(value)}% em {name}. As taxas dividem as unidades rejeitadas pelas unidades inspecionadas de cada grupo."
        contrast = comparison.get("difference")
        if contrast:
            low, high = contrast["ci95_pp"]
            insight += f" A diferença {contrast['group_b']} − {contrast['group_a']} foi {_fmt(contrast['estimate_pp'])} pontos percentuais, com IC95% de {_fmt(low)} a {_fmt(high)} p.p."
        items = [{"label": item["label"], "value": item["rate"], "lower": item["ci95"][0], "upper": item["ci95"][1]} for item in summaries[:20]]
        return {"grafico": {"tipo": "intervalos", "titulo": "Taxa por grupo e IC95% Wilson", "eixo": "Unidades rejeitadas / inspecionadas (%)",
                            "itens": items, "mostrados": len(items), "total": len(summaries),
                            "interval_label": "Ponto: taxa observada · segmento: IC95% Wilson por grupo",
                            "interval_note": "Os intervalos individuais não são simultâneos. Para dois grupos, consulte o IC da diferença de taxas; a sobreposição dos ICs individuais não substitui essa comparação.",
                            "nota": "Os denominadores de cada grupo estão na tabela. Tamanhos diferentes de amostra afetam a incerteza."},
                "insight": insight,
                "proximo_passo": "Compare o tamanho e o contexto de cada grupo. Revise mix de produtos, períodos, medição e independência; taxas diferentes orientam investigação e não identificam a causa automaticamente."}

    if scenario in {"grupos", "fluxo", "doe"}:
        index = 3 if "Taxa (%)" in result["colunas"] else 2
        name, value = _leader(rows, index)
        what = "taxa observada (%)" if index == 3 else "média observada"
        title = {"grupos": "Comparação entre grupos", "fluxo": "Tempo médio por etapa", "doe": "Resposta média por nível do fator"}[scenario]
        insight = f"A maior {what} foi {_fmt(value)} em {name}. Os grupos podem ter tamanhos e condi\u00e7\u00f5es diferentes."
        if scenario == "doe" and result.get("comparacoes"):
            significant = [item for item in result["comparacoes"] if item["p_holm"] < 0.05]
            if significant:
                pairs = "; ".join(f"{item['grupo_a']} vs. {item['grupo_b']}" for item in significant)
                insight += f" Diferen\u00e7as m\u00e9dias entre pares foram sinalizadas ap\u00f3s ajuste de Holm: {pairs}."
            else:
                insight += " Nenhuma diferen\u00e7a pareada atingiu p-Holm < 0,05; isso n\u00e3o demonstra igualdade entre os n\u00edveis."
        return {"grafico": _bars(title, what, rows, 0, index),
                "insight": insight,
                "proximo_passo": "Compare os tamanhos das amostras e o contexto de cada grupo; use uma investiga\u00e7\u00e3o ou experimento adequado para validar hip\u00f3teses."}

    if scenario == "fmea":
        name, value = _leader(rows, 4)
        return {"grafico": _bars("RPN por modo de falha", "RPN (S × O × D)", rows, 0, 4),
                "insight": f"O maior RPN informado é {_fmt(value)} em {name}.",
                "proximo_passo": "Revise também a severidade, os controles e os critérios da equipe; o RPN sozinho não determina a prioridade de risco."}

    if scenario == "msa":
        return {"grafico": _bars("Variação do estudo por componente", "% da variação de estudo", rows, 0, 2),
                "insight": f"O Gauge R&R corresponde a {_fmt(metrics['% variação do estudo Gage R&R'])}% da variação estimada neste estudo cruzado.",
                "proximo_passo": "Revise o desenho e a interação peça × operador com um especialista antes de aceitar o sistema de medição. Os componentes do gráfico se sobrepõem e não devem ser somados."}

    if scenario == "oee":
        bars = [["Disponibilidade", metrics["Disponibilidade (%)"]], ["Desempenho", metrics["Desempenho (%)"]], ["Qualidade", metrics["Qualidade (%)"]], ["OEE", metrics["OEE (%)"]]]
        value = min(item[1] for item in bars[:3])
        names = [item[0].lower() for item in bars[:3] if item[1] == value]
        name = " e ".join(names)
        return {"grafico": _bars("Componentes do OEE", "Percentual (%)", bars, 0, 1),
                "insight": f"O OEE calculado no período foi {_fmt(metrics['OEE (%)'])}%. O menor valor entre os componentes foi {_fmt(value)}% em {name}.",
                "proximo_passo": "Compare a decomposição das perdas em tempo equivalente e investigue as causas e os custos; confirme as definições antes de comparar linhas."}

    if scenario == "energia":
        return {"grafico": _lines("Consumo por unidade", "Consumo por unidade produzida", rows, [("Consumo por unidade", 3)]),
                "insight": f"O consumo específico global foi {_fmt(metrics['Consumo por unidade'])} por unidade produzida, calculado pela divisão dos totais.",
                "proximo_passo": "Compare registros com produção e mix semelhantes para investigar alterações de consumo; confira a unidade e os períodos."}

    if scenario == "sobrevivencia":
        km = result["sobrevivencia"]
        median = f"A mediana de vida estimada foi {_fmt(km['mediana'])}." if km["mediana"] is not None else "A curva não atingiu 50% de sobrevivência; a mediana de vida não foi alcançada."
        return {"grafico": result["grafico"],
                "insight": f"Em {_fmt(km['n'])} unidades, ocorreram {_fmt(km['falhas'])} falhas e {_fmt(km['censuras'])} censuras. No horizonte observado {_fmt(km['tau'])}, a sobrevivência estimada foi {_fmt(100*km['sobrevivencia_final'])}%. {median}",
                "proximo_passo": "Use a curva e as unidades em risco para planejar o acompanhamento de vida útil. Revise motivos de retirada, representatividade e custos antes de decidir uma política de manutenção; a curva não identifica causas de falha."}

    if scenario == "confiabilidade":
        name, value = _leader(rows, 1)
        return {"grafico": _bars("Registros de falha por equipamento", "Número de registros", rows, 0, 1),
                "insight": f"A maior contagem foi {_fmt(value)} registro(s) em {name}; a contagem total é {_fmt(metrics['Registros'])}.",
                "proximo_passo": "Revise o histórico, os modos de falha e as horas em operação. Equipamentos com exposições diferentes não são diretamente comparáveis pela contagem."}
    return {"grafico": None, "insight": "Confira os indicadores e a tabela para interpretar os resultados.", "proximo_passo": "Revise as condições e os dados com o responsável pelo processo."}
