"""Cálculos auxiliares para os métodos disponíveis na interface local."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats


def wilson_interval(successes: int, trials: int, confidence: float = 0.95):
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("A proporção exige contagens entre zero e o total positivo.")
    z = float(stats.norm.ppf((1 + confidence) / 2))
    proportion = successes / trials
    denominator = 1 + z * z / trials
    center = (proportion + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(proportion * (1 - proportion) / trials + z*z / (4*trials*trials)) / denominator
    return max(0.0, center-half), min(1.0, center+half)


def newcombe_difference(successes_a: int, trials_a: int, successes_b: int, trials_b: int):
    """Independent proportions B - A, Newcombe-Wilson 95%, no continuity correction."""
    lower_a, upper_a = wilson_interval(successes_a, trials_a)
    lower_b, upper_b = wilson_interval(successes_b, trials_b)
    a, b = successes_a / trials_a, successes_b / trials_b
    difference = b - a
    lower = difference - math.hypot(b - lower_b, upper_a - a)
    upper = difference + math.hypot(upper_b - b, a - lower_a)
    return difference, (max(-1.0, lower), min(1.0, upper))


def crossed_grr(data: pd.DataFrame, multiplier: float = 5.15):
    """ANOVA cruzada balanceada com interação peça × operador, sem pooling."""
    parts = data["peca"].nunique()
    operators = data["operador"].nunique()
    counts = data.groupby(["peca", "operador"], observed=True).size()
    if parts < 2 or operators < 2 or len(counts) != parts * operators or counts.min() < 2 or counts.nunique() != 1:
        raise ValueError("O MSA requer pelo menos 2 peças, 2 operadores e 2 repetições por combinação, com estudo cruzado balanceado.")
    if data["medida"].nunique() < 2:
        raise ValueError("Todas as medições são iguais; a variação total é zero e o percentual Gage R&R não pode ser estimado.")
    replicates = int(counts.iloc[0])
    grand = float(data["medida"].mean())
    part_means = data.groupby("peca", observed=True)["medida"].mean()
    op_means = data.groupby("operador", observed=True)["medida"].mean()
    cell_means = data.groupby(["peca", "operador"], observed=True)["medida"].mean()
    ss_part = operators * replicates * float(((part_means-grand)**2).sum())
    ss_operator = parts * replicates * float(((op_means-grand)**2).sum())
    interaction = [float(mean) - float(part_means.loc[part]) - float(op_means.loc[operator]) + grand
                   for (part, operator), mean in cell_means.items()]
    ss_interaction = replicates * sum(value*value for value in interaction)
    joined = data.join(cell_means.rename("cell_mean"), on=["peca", "operador"])
    ss_error = float(((joined["medida"] - joined["cell_mean"])**2).sum())
    df_part, df_op = parts-1, operators-1
    df_interaction, df_error = df_part*df_op, parts*operators*(replicates-1)
    ms_part, ms_operator = ss_part/df_part, ss_operator/df_op
    ms_interaction, ms_error = ss_interaction/df_interaction, ss_error/df_error
    var_error = max(ms_error, 0.0)
    var_interaction = max((ms_interaction-ms_error)/replicates, 0.0)
    var_operator = max((ms_operator-ms_interaction)/(parts*replicates), 0.0)
    var_part = max((ms_part-ms_interaction)/(operators*replicates), 0.0)
    var_repro = var_operator + var_interaction
    var_grr = var_error + var_repro
    var_total = var_grr + var_part
    if not math.isfinite(var_total) or var_total <= 0:
        raise ValueError("A variação total estimada não permite calcular o Gauge R&R.")
    variation = lambda value: multiplier * math.sqrt(value)
    percent = lambda value: 100 * math.sqrt(value / var_total)
    ndc = max(1, math.floor(1.41 * math.sqrt(var_part / var_grr))) if var_grr > 0 else None
    interaction_p = float(stats.f.sf(ms_interaction / ms_error, df_interaction, df_error)) if ms_error > 0 else None
    return {"pecas": parts, "operadores": operators, "repeticoes": replicates,
            "ndc": ndc, "interacao_p": interaction_p,
            "componentes": [
                ("Repetibilidade (EV)", variation(var_error), percent(var_error)),
                ("Operador", variation(var_operator), percent(var_operator)),
                ("Interação peça × operador", variation(var_interaction), percent(var_interaction)),
                ("Reprodutibilidade total (AV)", variation(var_repro), percent(var_repro)),
                ("Gauge R&R", variation(var_grr), percent(var_grr)),
                ("Variação entre peças", variation(var_part), percent(var_part)),
            ]}


def compare_numeric_groups(data: pd.DataFrame):
    """Teste exploratório com duas ou mais amostras independentes."""
    samples = [np.asarray(group["medida"], dtype=float) for _, group in data.groupby("grupo", observed=True)]
    if len(samples) < 2 or any(len(group) < 3 for group in samples):
        return None, "Para comparação inferencial, são necessários pelo menos 2 grupos com 3 observações cada."
    if len(samples) == 2:
        if all(np.var(sample, ddof=1) == 0 for sample in samples):
            return None, "Não foi possível estimar o teste de Welch: ambos os grupos têm variação zero."
        out = stats.ttest_ind(samples[0], samples[1], equal_var=False)
        interval = out.confidence_interval(confidence_level=0.95)
        if not all(math.isfinite(float(x)) for x in (out.statistic, out.pvalue, interval.low, interval.high)):
            return None, "Não foi possível calcular um teste de Welch finito."
        return {"teste": "Teste t de Welch bilateral", "p": float(out.pvalue),
                "diferenca": float(np.mean(samples[0])-np.mean(samples[1])),
                "ic": [float(interval.low), float(interval.high)],
                "grupos": [str(name) for name, _ in data.groupby("grupo", observed=True)]}, None
    if np.unique(np.concatenate(samples)).size < 2:
        return None, "Todos os valores são iguais; o teste de Kruskal-Wallis não é aplicável."
    out = stats.kruskal(*samples)
    return {"teste": "Kruskal-Wallis", "p": float(out.pvalue)}, None


def compare_proportions(grouped: pd.DataFrame):
    table = np.column_stack([grouped["defeitos"].to_numpy(), (grouped["total"]-grouped["defeitos"]).to_numpy()])
    if len(table) < 2 or np.any(table.sum(axis=0) == 0):
        return None, "A comparação inferencial exige ao menos dois grupos e ocorrências em ambas as categorias."
    statistic, p, _, expected = stats.chi2_contingency(table, correction=False)
    if (expected < 5).any():
        if len(table) == 2:
            _, p = stats.fisher_exact(table, alternative="two-sided")
            return {"teste": "Teste exato de Fisher bilateral", "p": float(p)}, None
        return None, "Frequências esperadas abaixo de 5; o teste qui-quadrado não foi apresentado."
    return {"teste": "Qui-quadrado de independência", "p": float(p), "estatistica": float(statistic)}, None


def factor_anova(data: pd.DataFrame):
    grouped = list(data.groupby("fator", observed=True, sort=False))
    samples = [np.asarray(group["medida"], dtype=float) for _, group in grouped]
    if not 2 <= len(samples) <= 10 or any(len(group) < 2 for group in samples):
        return None, "A ANOVA exploratória requer de 2 a 10 níveis e pelo menos 2 observações por nível."
    grand = np.mean(np.concatenate(samples))
    ss_between = sum(len(group) * (np.mean(group)-grand)**2 for group in samples)
    ss_within = sum(float(np.sum((group-np.mean(group))**2)) for group in samples)
    if ss_within <= 0:
        return None, "A variação dentro dos níveis é zero; não foi apresentado o teste F."
    try:
        variance_p = float(stats.levene(*samples, center="median").pvalue)
    except (ValueError, FloatingPointError):
        variance_p = float("nan")
    residuals = np.concatenate([group - np.mean(group) for group in samples])
    normality_p = float(stats.shapiro(residuals).pvalue) if 3 <= len(residuals) <= 5000 else None

    # Use Welch directly rather than first testing variances and switching
    # methods. This avoids a two-stage selection procedure; Levene remains a
    # diagnostic to inform interpretation, not an automatic method gate.
    variances = np.asarray([np.var(group, ddof=1) for group in samples], dtype=float)
    if (variances <= 0).any():
        return None, "A ANOVA de Welch requer variância positiva em cada nível; ao menos um nível tem variância zero."
    sizes = np.asarray([len(group) for group in samples], dtype=float)
    means = np.asarray([np.mean(group) for group in samples], dtype=float)
    weights = sizes / variances
    weight_sum = float(weights.sum())
    weighted_mean = float(np.sum(weights * means) / weight_sum)
    k = len(samples)
    correction_term = float(np.sum(((1 - weights / weight_sum) ** 2) / (sizes - 1)))
    if correction_term <= 0:
        return None, "Não foi possível estimar os graus de liberdade do teste de Welch."
    statistic = float(np.sum(weights * (means - weighted_mean) ** 2) / (k - 1))
    correction = 1 + (2 * (k - 2) / (k*k - 1)) * correction_term
    f_value = statistic / correction
    df_denominator = (k*k - 1) / (3 * correction_term)
    pvalue = float(stats.f.sf(f_value, k - 1, df_denominator))
    test_name = "ANOVA de Welch"
    df1, df2 = k - 1, df_denominator
    if not all(math.isfinite(value) for value in (f_value, pvalue, float(df1), float(df2))):
        return None, "Não foi possível calcular um teste F finito."
    pair_count = k * (k - 1) // 2
    comparisons = []
    raw_p_values = []
    for i in range(k):
        for j in range(i + 1, k):
            a, b = samples[i], samples[j]
            var_a, var_b = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
            term_a, term_b = var_a / len(a), var_b / len(b)
            standard_error = math.sqrt(term_a + term_b)
            if standard_error <= 0 or not math.isfinite(standard_error):
                return None, "Uma comparação pareada não tem erro-padrão finito; não foram apresentados pós-testes."
            degrees = (term_a + term_b) ** 2 / (term_a**2 / (len(a)-1) + term_b**2 / (len(b)-1))
            difference = float(np.mean(a) - np.mean(b))
            statistic = difference / standard_error
            raw_p = float(2 * stats.t.sf(abs(statistic), degrees))
            critical = float(stats.t.ppf(1 - 0.05 / (2 * pair_count), degrees))
            if not all(math.isfinite(value) for value in (degrees, raw_p, critical)):
                return None, "Não foi possível calcular comparações pareadas finitas."
            comparisons.append({
                "grupo_a": str(grouped[i][0]), "grupo_b": str(grouped[j][0]),
                "n_a": len(a), "n_b": len(b), "diferenca": difference,
                "ic_simultaneo": [difference - critical*standard_error, difference + critical*standard_error],
                "p_bruto": raw_p,
            })
            raw_p_values.append(raw_p)

    # Holm step-down adjusted p-values, restored to their original pair order.
    order = np.argsort(raw_p_values)
    adjusted_sorted = []
    running_max = 0.0
    for rank, index in enumerate(order):
        adjusted = min(1.0, (pair_count - rank) * raw_p_values[index])
        running_max = max(running_max, adjusted)
        adjusted_sorted.append((int(index), running_max))
    for index, adjusted in adjusted_sorted:
        comparisons[index]["p_holm"] = adjusted

    return {"f": f_value, "p": pvalue, "eta2": float(ss_between/(ss_between+ss_within)),
            "teste": test_name, "df1": float(df1), "df2": float(df2),
            "variancia_p": variance_p, "normalidade_residuos_p": normality_p,
            "comparacoes": comparisons}, None
