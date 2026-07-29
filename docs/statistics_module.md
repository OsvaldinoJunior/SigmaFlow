# SigmaFlow — Módulo Estatístico

## Visão Geral

O módulo estatístico do SigmaFlow é composto por dois pacotes:

- `sigmaflow/analysis/` — análises específicas de processo (Cp/Cpk, SPC, Pareto, DOE...)
- `sigmaflow/statistics/` — testes estatísticos gerais (normalidade e hipóteses)

Todos os módulos retornam dicts com schema consistente, prontos para o pipeline.

---

## `sigmaflow/analysis/`

### `capability_analysis.py`

Índices de capacidade de processo.

**Funções:**
- `compute_capability(series, usl, lsl)` → dict com Cp, Cpk, Cpu, Cpl, DPMO, sigma_level
- `compute_normality(series)` → dict com resultado do Shapiro-Wilk / Anderson-Darling
- `dpmo_to_sigma(dpmo)` → float (nível sigma com deslocamento de 1.5σ)

**Fórmulas:**
```
Cp  = (USL - LSL) / (6σ)
Cpk = min(Cpu, Cpl)
Cpu = (USL - μ) / (3σ)
Cpl = (μ - LSL) / (3σ)
DPMO = (n_fora_spec / n_total) × 1.000.000
```

---

### `spc_analysis.py`

Controle Estatístico de Processo.

**Funções:**
- `compute_xmr_chart(series)` → dict com x_chart (CL, UCL, LCL, ooc_points) e mr_chart
- `compute_trend(series)` → dict com direction, spearman_r, p_value

**Limites XmR (individuais):**
```
d2 = 1.128  (fator de constante para n=2)
MR_i = |x_i - x_{i-1}|   (amplitude móvel)
MR̄ = média das amplitudes móveis

CL  = x̄
UCL = x̄ + 3 × (MR̄ / d2)
LCL = x̄ - 3 × (MR̄ / d2)
```

---

### `pareto_analysis.py`

Análise de Pareto (regra 80/20).

**Funções:**
- `compute_pareto(df, category_col, count_col)` → dict com categories, counts, cumulative_pct, vital_few

**Vital few:** categorias cujo cumulativo ≤ 80% do total.

---

### `regression_analysis.py`

Regressão linear múltipla (OLS).

**Classe:** `RegressionAnalyzer(df)`
- `.run()` → dict com r2, adj_r2, coefficients, p_values, significant_vars, predictions
- `.generate_plots(output_folder)` → lista de caminhos PNG

**Seleção automática de target:** coluna mais correlacionada com as demais.

---

### `doe_analysis.py`

Design of Experiments com ANOVA.

**Classe:** `DOEAnalyzer(df, factor_cols)`
- `.run()` → dict com anova_table, main_effects, r2
- `.generate_plots(output_folder)` → efeitos principais + interações

---

### `msa_analysis.py`

Measurement System Analysis — Gauge R&R.

**Classe:** `MSAAnalyzer(df, part_col, operator_col, measurement_col)`
- `.run()` → dict com percent_contribution (pct_GRR, pct_part_to_part), ndc
- `.generate_plots(output_folder)` → gráficos de componentes de variância

**Critérios:**
- Gauge R&R < 10% → sistema aceitável
- Gauge R&R 10–30% → marginal
- Gauge R&R > 30% → não aceitável

---

### `fmea_analysis.py`

Failure Mode and Effects Analysis.

**Classe:** `FMEAAnalyzer(df, failure_mode_col, sev_col, occ_col, det_col)`
- `.run()` → dict com ranked_modes (RPN), n_critical, total_risk_score
- `.generate_plots(output_folder)` → gráfico de RPN por modo de falha

**RPN = Severidade × Ocorrência × Detecção** (1–10 cada)

---

### `root_cause_analysis.py`

Análise de causa raiz por correlação.

**Classe:** `RootCauseAnalyzer(df)`
- `.run()` → dict com target_col, ranked_variables (pearson_r, strength), strong_candidates

**Classificação de força:**
- |r| ≥ 0.70 → forte
- |r| ≥ 0.50 → moderado
- |r| ≥ 0.30 → fraco
- |r| < 0.30 → muito fraco

---

## `sigmaflow/statistics/`

### `normality_tests.py`

**Função:** `run_normality_tests(df, columns)` → dict por coluna

Testes executados por coluna:
1. **Shapiro-Wilk** (n ≤ 5.000) — mais poderoso para amostras pequenas
2. **Anderson-Darling** (n > 5.000) — alternativa para grandes amostras
3. **Kolmogorov-Smirnov** — teste complementar

Veredicto: `"Normal"` se p > 0.05 em pelo menos 2 dos testes.

```python
from sigmaflow.statistics.normality_tests import run_normality_tests
import pandas as pd

results = run_normality_tests(df, columns=["espessura", "temperatura"])
print(results["espessura"]["overall_verdict"])   # "Normal" ou "Non-Normal"
print(results["espessura"]["shapiro"]["p_value"])
```

---

### `hypothesis_tests.py`

**Classe:** `HypothesisTester(df)`
- `.run_all()` → dict com lista de tests

Testes executados automaticamente com base na estrutura do dataset:

| Teste | Quando é aplicado |
|---|---|
| t-test independente | 1 coluna numérica + 1 binária |
| ANOVA one-way | 1 coluna numérica + 1 categórica (> 2 grupos) |
| Mann-Whitney U | Quando os dados não são normais (não-paramétrico) |

```python
from sigmaflow.statistics.hypothesis_tests import HypothesisTester

ht      = HypothesisTester(df)
results = ht.run_all()

for test in results["tests"]:
    print(f"{test['test_name']:20s} p={test['p_value']:.4f}  {test['conclusion']}")
```

---

## Motor de Regras — `sigmaflow/insights/`

### `rules_engine.py`

**Classe:** `RulesEngine`
- `.evaluate(df, analysis, dataset_type)` → list[Insight]

**Dataclass Insight:**
```python
@dataclass
class Insight:
    rule:           str   # identificador único
    description:    str   # achado legível
    meaning:        str   # interpretação estatística
    recommendation: str   # ação sugerida
    severity:       str   # "info" | "warning" | "critical"
```

### `statistical_rules.py`

**Regras implementadas:**

| Regra | Condição | Severity |
|---|---|---|
| `western_electric_rule_1` | Ponto além de 3σ | critical |
| `western_electric_rule_2` | 9 pontos consecutivos no mesmo lado da média | warning |
| `western_electric_rule_3` | 6 pontos consecutivos em tendência | warning |
| `western_electric_rule_4` | 14 pontos alternando acima/abaixo | info |
| `capability_incapable` | Cpk < 1.0 | critical |
| `capability_marginal` | 1.0 ≤ Cpk < 1.33 | warning |
| `capability_acceptable` | 1.33 ≤ Cpk < 1.67 | info |
| `capability_excellent` | Cpk ≥ 1.67 | info |
| `high_dpmo` | DPMO > 66.807 (< 3σ) | critical |
