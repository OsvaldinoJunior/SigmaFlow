# SigmaFlow — Pipeline DMAIC

## O que é DMAIC?

DMAIC é o método de resolução de problemas central no Lean Six Sigma:

```
Define → Measure → Analyze → Improve → Control
```

O SigmaFlow automatiza cada fase com análise baseada em dados e gera
entregáveis estruturados por fase.

---

## Diagrama do Pipeline

```
┌─────────────────────────────────────────────────────┐
│  D — DEFINE                                         │
│  Problema, escopo, CTQ, SIPOC, charter              │
│  sigmaflow/dmaic/define/phase.py                    │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│  M — MEASURE                                        │
│  Sigma baseline, MSA, normalidade, estatísticas     │
│  sigmaflow/dmaic/measure/phase.py                   │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│  A — ANALYZE                                        │
│  Root cause, hipóteses, regressão, Pareto, FMEA     │
│  sigmaflow/dmaic/analyze/phase.py                   │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│  I — IMPROVE                                        │
│  DOE, efeitos principais, condições ótimas          │
│  sigmaflow/dmaic/improve/phase.py                   │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│  C — CONTROL                                        │
│  Plano de controle, cartas SPC, dashboard           │
│  sigmaflow/dmaic/control/phase.py                   │
└─────────────────────────────────────────────────────┘
```

---

## Fases em Detalhe

### D — Define
**Objetivo:** Definir claramente o problema e o escopo.

Entregáveis do SigmaFlow:
- `problem_statement` — declaração estruturada do problema
- `project_charter` — campos de sponsor, escopo, CTQ, cronograma
- `sipoc` — Supplier–Input–Process–Output–Customer

Pergunta central: *O que estamos tentando melhorar e por quê?*

---

### M — Measure
**Objetivo:** Quantificar o estado atual e validar o sistema de medição.

Entregáveis do SigmaFlow:
- `baseline_cpk` — Cpk atual do processo
- `sigma_level` — nível sigma da linha de base
- `dpmo` — defeitos por milhão de oportunidades
- `gauge_rr` — resultado do MSA (se colunas Part/Operator/Measurement existirem)
- `normality` — Shapiro-Wilk, Anderson-Darling, Kolmogorov-Smirnov
- `xmr_chart` — carta de controle XmR com limites calculados

Pergunta central: *Quão ruim é o problema, e podemos confiar nas medições?*

---

### A — Analyze
**Objetivo:** Identificar as causas raiz da variação ou defeitos.

Entregáveis do SigmaFlow:
- `correlation_matrix` — Pearson entre todas as variáveis
- `ranked_variables` — variáveis ordenadas por correlação com a resposta
- `regression` — R², preditores significativos, coeficientes
- `hypothesis_tests` — t-test, ANOVA, Mann-Whitney por par de variáveis
- `pareto` — categorias de defeito em ordem decrescente
- `fmea` — RPN = Severidade × Ocorrência × Detecção
- `western_electric` — violações das Regras de Western Electric

Pergunta central: *O que está causando a variação ou os defeitos?*

---

### I — Improve
**Objetivo:** Projetar, testar e implementar soluções para as causas raiz.

Entregáveis do SigmaFlow:
- `doe_results` — tabela ANOVA de efeitos principais e interações
- `significant_factors` — fatores com p-value < 0.05
- `optimal_settings` — configurações que maximizam/minimizam a resposta
- `interaction_plots` — gráficos de interação entre fatores

Pergunta central: *Que mudanças mais melhoram o processo?*

---

### C — Control
**Objetivo:** Sustentar os ganhos. Evitar regressão ao comportamento anterior.

Entregáveis do SigmaFlow:
- `updated_control_limits` — novos UCL/LCL pós-melhoria
- `cusum_chart` — carta CUSUM para detecção rápida de mudanças
- `ewma_chart` — carta EWMA para monitoramento contínuo
- `control_plan` — recomendações de plano de controle
- `html_dashboard` — dashboard para monitoramento contínuo

Pergunta central: *Como garantimos que a melhoria é permanente?*

---

## Executando o Pipeline DMAIC

### Via CLI
```bash
sigmaflow dmaic meu_processo.xlsx
```

### Via Python API
```python
import pandas as pd
from sigmaflow.core.dmaic_engine import DMAICEngine

df     = pd.read_excel("input/datasets/process_data.xlsx")
engine = DMAICEngine(df)
result = engine.run_all()

# Acessar resultados por fase
print(result["define"]["problem_statement"])
print(result["measure"]["sigma_level"])
print(result["analyze"]["significant_variables"])
print(result["improve"]["optimal_settings"])
print(result["control"]["updated_control_limits"])
```

---

## Interpretando as Métricas Chave

| Métrica | Threshold | Interpretação |
|---|---|---|
| Cpk ≥ 1.67 | Excelente | Processo classe mundial |
| Cpk ≥ 1.33 | Bom | Aceitável para a maioria dos setores |
| Cpk ≥ 1.00 | Marginal | Em risco — melhoria necessária |
| Cpk < 1.00 | Incapaz | Produzindo defeitos — ação urgente |
| DPMO ≤ 3.4 | 6σ | Quase perfeito |
| DPMO ≤ 233 | 5σ | Excelente |
| DPMO ≤ 6.210 | 4σ | Boa qualidade |
| DPMO ≤ 66.807 | 3σ | Nível mínimo aceitável |
| Gauge R&R < 10% | Ideal | Sistema de medição confiável |
| Gauge R&R < 30% | Aceitável | Pode ser usado com cautela |
| RPN > 200 | Crítico | Modo de falha prioritário para ação |
