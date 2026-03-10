# SigmaFlow — Arquitetura do Sistema

## Visão Geral

O SigmaFlow é estruturado em 6 camadas funcionais que processam o dado de entrada até a
geração dos relatórios. Cada camada é independente e testável isoladamente.

```
┌────────────────────────────────────────────────────────────┐
│                         Dataset                            │
│                  (CSV / XLSX)                              │
└────────────────────────┬───────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│                       Profiler                             │
│  sigmaflow/core/data_profiler.py                           │
│                                                            │
│  • Shape, dtypes, nulos, cardinalidade                     │
│  • Estatísticas descritivas (mean, std, skew, kurtosis)    │
│  • Identificação de colunas numéricas e categóricas        │
└────────────────────────┬───────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│                  Analysis Planner                          │
│  sigmaflow/core/dataset_registry.py                        │
│  sigmaflow/core/analysis_planner.py                        │
│                                                            │
│  • Auto-discovery de analisadores (pkgutil + importlib)    │
│  • DatasetRegistry: ordena por priority, chama detect()    │
│  • Seleciona o analisador correto para cada dataset        │
└────────────────────────┬───────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│                  Statistics Engine                         │
│  sigmaflow/analysis/  +  sigmaflow/statistics/             │
│                                                            │
│  Análises primárias (por analisador):                      │
│    capability  → Cp, Cpk, DPMO, sigma level                │
│    spc         → XmR, UCL/LCL, pontos OOC, tendência      │
│    root_cause  → Pareto, vital few, cumulativo             │
│    doe         → ANOVA, efeitos principais, interações     │
│    logistics   → lead time, OTD, regressão distância       │
│    service     → wait time, SLA violations, satisfação     │
│                                                            │
│  Análises avançadas (smart dispatch por estrutura):        │
│    Regressão  → OLS multivariada (≥ 3 colunas numéricas)  │
│    MSA        → Gauge R&R (Part + Operator + Measurement)  │
│    FMEA       → RPN (Severity + Occurrence + Detection)    │
│    DOE        → ANOVA expandida (colunas com {-1, +1})     │
│                                                            │
│  Testes estatísticos:                                      │
│    Normalidade → Shapiro-Wilk, Anderson-Darling, KS        │
│    Hipóteses   → t-test, ANOVA one-way, Mann-Whitney U     │
│                                                            │
│  Cartas de controle avançadas:                             │
│    CUSUM, EWMA, X-bar/R (para dados SPC e Capability)      │
└────────────────────────┬───────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│                   Insights Engine                          │
│  sigmaflow/insights/rules_engine.py                        │
│  sigmaflow/insights/statistical_rules.py                   │
│                                                            │
│  • Avalia regras sobre os resultados de análise            │
│  • Retorna objetos Insight com:                            │
│      rule, description, meaning,                          │
│      recommendation, severity                             │
│  • Regras implementadas:                                   │
│      Western Electric (regras 1–4)                        │
│      Cpk thresholds (< 1.0 = critical, < 1.33 = warning)  │
│      DPMO classificação                                    │
│      Trend detection                                       │
└────────────────────────┬───────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│                  Report Generator                          │
│  sigmaflow/report/html_dashboard.py                        │
│  sigmaflow/report/latex_report.py                          │
│                                                            │
│  • HTML dashboard interativo (Jinja2, autocontido)         │
│  • Relatório LaTeX compilado para PDF (2 passes)           │
│  • insights.json — exportação estruturada de todos insights│
└────────────────────────────────────────────────────────────┘
```

---

## Padrão de Auto-Discovery

O `DatasetRegistry` usa `pkgutil.iter_modules` + `importlib.import_module` +
`inspect.getmembers` para encontrar automaticamente qualquer subclasse de
`BaseDataset` no pacote `sigmaflow.datasets`.

```python
# Como funciona internamente:
for finder, name, ispkg in pkgutil.iter_modules(datasets_path):
    module = importlib.import_module(f"sigmaflow.datasets.{name}")
    for obj_name, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, BaseDataset) and obj is not BaseDataset:
            self._registry[obj.name] = obj
```

Isso significa: **adicionar 1 arquivo em `sigmaflow/datasets/` = novo tipo disponível imediatamente**.

---

## Princípios de Design

| Princípio | Implementação |
|---|---|
| Convention over configuration | `input/datasets/` → `output/` sem config |
| Open/Closed | Extensível via BaseDataset, sem tocar no core |
| Fail-safe | Cada etapa em try/except; falha isolada por estágio |
| Structured outputs | Todos os resultados em dicts com schema consistente |
| Priority-based dispatch | Analisador mais específico vence (priority maior) |

---

## Fluxo de Dados (por arquivo)

```python
# Engine._process_file() — simplificado
result = {}
df = _load(path)                          # 1. Load
analyzer = registry.match(df)             # 2. Detect
result["analysis"] = analyzer.run_analysis(df)     # 3. Analyse
result["plots"]    = analyzer.generate_plots(...)   # 4. Visualize
result["root_cause"] = _run_root_cause(df)          # 5. Root Cause
result["statistics"] = _run_statistics(df)          # 6. Statistics
result["advanced"]   = _dispatch_advanced(df)       # 7. Advanced
result["plots"]     += _run_advanced_spc(df)        # 8. SPC charts
result["insights"]   = analyzer.generate_insights() # 9. Insights
result["abstract"]   = _generate_abstract(result)   # 10. Abstract
```
