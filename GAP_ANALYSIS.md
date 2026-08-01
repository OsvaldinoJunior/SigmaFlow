# Gap Analysis: SigmaFlow vs Minitab/JMP (Master Black Belt Level)
## Data: 2026-07-28 | Versão: 0.2.0

---

## Legenda
| Símbolo | Significado |
|---------|-------------|
| ✅ | Implementado e testado |
| 🟡 | Parcial / Básico (precisa expansão) |
| ❌ | Ausente |
| 🔧 | Em desenvolvimento / planejado |

---

## DEFINE

| Ferramenta Metodológica | Status | Detalhes / Gap |
|-------------------------|--------|----------------|
| **Project Charter** | ✅ | Modelo básico em `DefinePhase` (problem_statement, goal, scope, team). Falta: business case quantificado, timeline Gantt, risk register, communication plan. |
| **SIPOC** | ✅ | Auto-gerado do dataset (suppliers, inputs, process, outputs, customers). Básico - falta: detailed process map linkage, CTQ flowdown. |
| **VOC / Kano** | ❌ | Não existe. Um MBB usa: entrevistas estruturadas, surveys, complaint analysis → Kano classification (Must-be, One-dimensional, Attractive, Indifferent, Reverse). |
| **CTQ Tree / Y-to-x Flowdown** | 🟡 | CTQ identification existe (target column + strong correlations). Falta: decomposição hierárquica VOC→CTQ→CQP→CTP, operational definitions, measurement system validation por CTQ. |
| **Stakeholder Analysis / RACI** | ❌ | Não existe. Matriz poder×interesse, comunicação plan, change readiness assessment. |
| **Project Selection Matrix** | ❌ | Critérios: impacto financeiro, esforço, risco, alinhamento estratégico. |
| **Team Charter** | ❌ | Roles (Sponsor, MBB, BB, GB, YB, SME), ground rules, meeting cadence. |

---

## MEASURE

| Ferramenta Metodológica | Status | Detalhes / Gap |
|-------------------------|--------|----------------|
| **MSA - Gauge R&R (Crossed)** | ✅ | ANOVA method implementado em `MSAAnalyzer`. Falta: nested designs, destructive testing, short-term vs long-term. |
| **MSA - Gauge R&R (Nested)** | ❌ | Para hierarquias (part → operator → gauge). Crítico para processos com múltiplos níveis de variação. |
| **MSA - Attribute Agreement** | ❌ | Kappa de Fleiss/Cohen para dados categóricos (pass/falha, classificação visual). Essencial para inspeção visual. |
| **MSA - Linearity** | ❌ | Bias ao longo da faixa de medição. Requerido por AIAG MSA 4th ed. |
| **MSA - Bias** | ❌ | Bias vs reference value (master sample). |
| **MSA - Stability** | ❌ | Drift do sistema de medição ao longo do tempo (control chart de medições de referência). |
| **Process Capability (Normal)** | ✅ | Cp, Cpk, Pp, Ppk, DPMO, sigma level. Shapiro-Wilk test integrado. |
| **Capability - Non-Normal (Box-Cox / Johnson)** | ✅ | **Implementado** em `capability_analysis.py` (`boxcox_transform`, `johnson_transform`). Auto-detecta não-normalidade, aplica transformação ótima, recalcula Cpk. |
| **Capability - Attribute (Binomial/Poisson)** | ✅ | **Implementado** em `capability_analysis.py` (`p_chart`, `np_chart`, `c_chart`, `u_chart`). DPMO para defectives/defeitos com limites de controle corretos. |
| **Control Charts - I-MR (XmR)** | ✅ | Western Electric Rules 1-4 + trend. CUSUM, EWMA também. |
| **Control Charts - Xbar-R / Xbar-S** | ✅ | Para subgrupos. Falta: lógica de tamanho de subgrupo ótimo (n=2..10 vs >10). |
| **Control Charts - Attributes (p, np, c, u)** | ❌ | **Gap crítico**. Para contagem de defeitos/defeitivos. Diferente de variáveis contínuas. |
| **Control Charts - Rare Events (T, G)** | ❌ | Time-between-events (T) e oportunidades-between-events (G). Para eventos raros (safety incidents, etc). |
| **Control Charts - Multivariate (Hotelling T² / MEWMA)** | ❌ | Correlação entre múltiplas CTQs simultaneamente. Minitab: T² chart, MEWMA. |
| **Control Charts - Short Run / Batch** | ❌ | Z-chart, difference chart para lotes pequenos. |
| **Value Stream Mapping (VSM)** | ❌ | Mapeamento de fluxo de valor com lead time, %VA, takt time, WIP. Ferramenta Lean essencial. |
| **OEE** |
| **Takt Time / Cycle Time / Lead Time** | ❌ | Cálculos Lean básicos. Takt = Available time / Demand. |
| **Process Mapping (Swimlane / BPMN)** | ❌ | Visualização do processo com handoffs, decisões, loops. |

---

## ANALYZE

| Ferramenta Metodológica | Status | Detalhes / Gap |
|-------------------------|--------|----------------|
| **Hypothesis Tests - Parametric** | ✅ | t-test (1-sample, 2-sample, paired), ANOVA (1-way), Levene/Bartlett. Via `HypothesisTester`. |
| **Hypothesis Tests - Non-Parametric** | 🟡 | Mann-Whitney U, Kruskal-Wallis implementados. Falta: Wilcoxon signed-rank, Friedman, Mood's median, runs test. |
| **Hypothesis Tests - Proportions / Chi-Square** | ❌ | 1-proportion, 2-proportion, Chi-square goodness-of-fit, Chi-square independence. Para dados categóricos. |
| **Power & Sample Size** | ❌ | Cálculo de poder estatístico, tamanho de amostra para testes de hipótese, DOE, capability. MBB sempre valida n antes de coletar dados. |
| **Correlation / Simple Regression** | ✅ | Pearson, Spearman + OLS simples. R², p-values, residual plots. |
| **Multiple Linear Regression** | ✅ | Stepwise, best subsets, VIF, residual diagnostics (normalidade, homocedasticidade, independência). |
| **Logistic Regression (Binary/Ordinal/Nominal)** | ✅ | **Implementado** em `logistic_regression.py` (`BinaryLogisticRegression`, `OrdinalLogisticRegression`). Integrado ao pipeline via `Engine._dispatch_advanced()` — detecta targets binários/categóricos automaticamente. Testado com AUC/accuracy. |
| **Nonlinear Regression** | ❌ | Modelos não-lineares customizados (ex: crescimento, decaimento, Michaelis-Menten). |
| **DOE - Full Factorial** | ✅ | `DOEAnalyzer` com 2-level full factorial. Main effects + interactions. |
| **DOE - Fractional Factorial** | 🟡 | **Código existe** em `doe_analysis.py` (`fractional_factorial_2k_p`, `central_composite_design`, `fit_rsm`). **Não integrado** ao pipeline — aguardando critério de detecção seguro (ver item 3.2). |
| **DOE - Response Surface (RSM)** | 🟡 | **Código existe** em `doe_analysis.py` (`central_composite_design`, `fit_rsm`). **Não integrado** — aguardando critério de detecção seguro. |
| **DOE - Taguchi / Robust Design** | ❌ | Signal-to-noise ratio (S/N), dynamic/static, outer/inner arrays. Para robustez a ruído. |
| **DOE - Mixture Designs** | ❌ | Para formulações (ingredientes que somam 100%). Simplex lattice/centroid. |
| **DOE - Multi-Response Optimization** | ❌ | Desirability function (Derringer-Suich) para otimizar múltiplas Ys simultâneas. |
| **FMEA - Design (DFMEA)** | 🟡 | `FMEAAnalyzer` calcula RPN (S×O×D), ranking. Falta: action priority (AP), occurrence detection linkage, DFMEA↔PFMEA linkage, FMEA-MSR. |
| **FMEA - Process (PFMEA)** | 🟡 | Mesmo gap acima. Falta: linkage com Control Plan, critical characteristics (CC/SC). |
| **5 Whys** | ❌ | Template estruturado com evidence, counter-measure verification. |
| **Ishikawa / Fishbone** | ❌ | Diagrama 6Ms/8Ps gerado automaticamente a partir de variáveis significativas. |
| **Fault Tree Analysis (FTA)** | ❌ | Top-down: evento indesejado → causas básicas. Quantitative (cut sets, probability). |
| **Root Cause Analysis - Statistical** | ✅ | Correlation matrix + variable importance ranking. Boa base, mas falta validação causal. |

---

## IMPROVE

| Ferramenta Metodológica | Status | Detalhes / Gap |
|-------------------------|--------|----------------|
| **DOE - Otimização (RSM)** | 🟡 | **Código existe** em `doe_analysis.py` (`central_composite_design`, `fit_rsm`). **Não integrado** — aguardando critério de detecção seguro. |
| **Monte Carlo Simulation** | ❌ | **Gap crítico**. Propagação de incerteza: input distributions → output distribution. Sensitivity analysis (Tornado chart). Minitab: `Simulate Responses`. |
| **Pugh Matrix (Concept Selection)** | ❌ | Critérios ponderados vs datum. Para seleção de soluções de melhoria. |
| **Design for Six Sigma (DFSS) / DMADV** | ❌ | Metodologia completa para novo produto/processo. |
| **Tolerance Analysis (Stack-up)** | ❌ | Worst-case, RSS, Monte Carlo para tolerâncias geométricas. |
| **Robust Parameter Design** | ❌ | Taguchi inner/outer arrays, S/N ratios. |
| **Quick Changeover / SMED** | ❌ | Análise de setup interno/externo, tempo de troca. |

---

## CONTROL

| Ferramenta Metodológica | Status | Detalhes / Gap |
|-------------------------|--------|----------------|
| **Control Plan (Automated)** | 🟡 | `ControlPhase` gera itens básicos (variable, chart type, limits, frequency). **Falta**: linkage com FMEA (high RPN → special controls), reaction plan (what/when/who), special characteristics (CC/SC), gauge calibration schedule. |
| **Western Electric Rules (8 rules)** | 🟡 | Regras 1-4 implementadas e testadas. **Faltam**: Regra 5 (2 of 3 > 2σ), Regra 6 (4 of 5 > 1σ), Regra 7 (15 in zone C), Regra 8 (8 on both sides of CL). Fix da Rule 3 aplicado (commit de7015c). |
| **SPC Real-time / Auto-ingest** | 🟡 | Pipeline aceita CSV/Excel/SQL/API. **Falta**: OPC-UA, MQTT, Kafka, historian tags, streaming contínuo, alertas Webhooks/Teams/Slack. |
| **Re-test Capability Post-Improvement** | ❌ | Comparação before/after com teste de equivalência (TOST) ou non-inferiority. Cpk delta com CI. |
| **Short-term vs Long-term Capability** | 🟡 | Calcula Cp/Cpk (curto) e Pp/Ppk (longo). **Falta**: estudo de estabilidade temporal (re-test ao longo de semanas). |
| **Process Management Chart** | ❌ | Dashboard executivo: KPIs, trends, capability summary, action items. |
| **Audit / Layered Process Audit (LPA)** | ❌ | Checklists, frequência por camada (operador, supervisor, gerente), scoring, trending. |

---

## LEAN

| Ferramenta Metodológica | Status | Detalhes / Gap |
|-------------------------|--------|----------------|
| **OEE (Availability × Performance × Quality)** | ❌ | Cálculo automático a partir de: tempo planejado, downtime, tempo de ciclo ideal, contadores bom/ruim. Perdas: breakdown, setup, minor stops, reduced speed, startup rejects, production rejects. |
| **Takt Time / Cycle Time / Lead Time** | ❌ | Takt = Tempo disponível / Demanda. Cycle time por etapa. Lead time total (Little's Law: WIP = TH × CT). |
| **5S Audit Scoring** | ❌ | Checklist padronizado, radar chart, foto evidence, scoring, trending. |
| **Standard Work / Standardized Work** | ❌ | Combinação: takt, sequence, WIP padrão. Visual management board. |
| **Kanban / Pull System Design** | ❌ | Cálculo de kanbans: (Demanda × Lead Time × Safety) / Container size. SUPERMARKET sizing. |
| **Heijunka (Level Loading)** | ❌ | Box de nivelamento, pitch, sequence pattern. |
| **Value Stream Mapping (Current/Future State)** | ❌ | Ver MEASURE. |

---

## ESTATÍSTICA GERAL / AVANÇADA

| Ferramenta Metodológica | Status | Detalhes / Gap |
|-------------------------|--------|----------------|
| **Normality Tests** | ✅ | Shapiro-Wilk, Anderson-Darling, Kolmogorov-Smirnov, Ryan-Joiner. |
| **Outlier Detection** | 🟡 | Boxplot (IQR), Grubbs, Dixon, Rosner. **Falta**: Mahalanobis distance (multivariado), Isolation Forest (ML). |
| **Bootstrap / Permutation Tests** | ❌ | IC bootstrap (percentile, BCa), permutation tests para hipóteses sem distribuição conhecida. |
| **PCA (Principal Component Analysis)** | ❌ | Redução de dimensionalidade, scree plot, biplot, loadings. Para datasets com muitas variáveis correlacionadas. |
| **Factor Analysis** | ❌ | EFA/CFA, rotation (varimax, promax), communalities. |
| **Cluster Analysis** | ❌ | K-means, hierarchical, DBSCAN. Para segmentação de clientes/processos/produtos. |
| **Discriminant Analysis** | ❌ | Classificação supervisionada, canonical functions. |
| **Time Series / Forecasting** | 🟡 | Trend/seasonal decomposition. **Falta**: ARIMA, ETS, Prophet, Holt-Winters. Para demand planning. |
| **Reliability / Survival Analysis** | ❌ | Weibull analysis, Kaplan-Meier, Cox regression, accelerated life testing. Para life data (MTBF, B10 life). |
| **Measurement Invariance / DIF** | ❌ | Para comparar sistemas de medição entre grupos/labs/turnos. |

---

## RESUMO QUANTITATIVO

| Fase DMAIC | Total Ferramentas | ✅ Implementadas | 🟡 Parciais | ❌ Ausentes | Cobertura |
|------------|-------------------|------------------|-------------|------------|-----------|
| **DEFINE** | 7 | 2 | 1 | 4 | **29%** |
| **MEASURE** | 18 | 8 | 2 | 8 | **44%** |
| **ANALYZE** | 16 | 7 | 2 | 7 | **44%** |
| **IMPROVE** | 7 | 1 | 2 | 4 | **29%** |
| **CONTROL** | 7 | 1 | 3 | 3 | **29%** |
| **LEAN** | 7 | 0 | 0 | 7 | **0%** |
| **ESTATÍSTICA GERAL** | 10 | 2 | 1 | 7 | **20%** |
| **TOTAL** | **72** | **27** | **11** | **40** | **~37%** |

---

## PRIORIZAÇÃO SUGERIDA (Impacto × Esforço)

| Prioridade | Item | Fase | Impacto MBB | Esforço Estimado | Comentário |
|------------|------|------|-------------|------------------|------------|
| **P0 - Crítico** | Capacidade não-normal (Box-Cox/Johnson) | MEASURE | 🔴 Bloqueia projetos reais | Médio | Muitos processos industriais não-normais |
| **P0 - Crítico** | Gráficos de controle de atributos (p,np,c,u) | MEASURE | 🔴 Essencial para qualidade discreta | Médio | Defeitos vs defeitos é distinção fundamental |
| **P0 - Crítico** | Regressão Logística (binária/ordinal) | ANALYZE | ✅ **RESOLVIDO** — Implementado e integrado (commit 2becdf4 + teste dfa3bd2) | — | — |
| **P0 - Crítico** | DOE Fracionado + RSM | IMPROVE | 🟡 **Código existe** (restaurado e8aab6d), **não integrado** — aguardando critério de detecção seguro (item 3.2) | — | — |
| **P0 - Crítico** | Simulação Monte Carlo | IMPROVE | 🔴 Propagação de incerteza / tolerâncias | Médio | Pode usar `numpy.random` + parallel |
| **P1 - Alto** | Control Plan automático completo (FMEA link) | CONTROL | 🟡 Entregável final do projeto | Médio | Requer integração FMEA→Control Plan |
| **P1 - Alto** | 8 Regras Western Electric completas | CONTROL | 🟡 Padrão AIAG | Baixo | Fix simples em `statistical_rules.py` |
| **P1 - Alto** | MSA Attribute Agreement (Kappa) | MEASURE | 🟡 Inspeção visual comum | Médio | `scipy.stats` + custom |
| **P2 - Médio** | Testes não-paramétricos completos | ANALYZE | 🟡 Dados não-normais/ordinais | Baixo | `scipy.stats` já tem base |
| **P2 - Médio** | Testes de proporção / Chi-square | ANALYZE | 🟡 Dados categóricos | Baixo | `statsmodels` ou `scipy` |
| **P2 - Médio** | Power & Sample Size | ANALYZE | 🟡 Validação antes de coletar | Médio | Fórmulas analíticas + simulação |
| **P3 - Baixo** | OEE / Lean Tools | LEAN | 🟢 Diferencial competitivo | Alto | Novo módulo `sigmaflow/lean/` |
| **P3 - Baixo** | PCA / Factor Analysis / Clustering | STATS | 🟢 Exploratório | Médio | `sklearn` já disponível |
| **P3 - Baixo** | Reliability / Weibull | STATS | 🟢 Vida útil / MTBF | Médio | `reliability` lib ou custom |

---

## RECOMENDAÇÃO DE ARQUITETURA

### Opção A: **Stage 2.5 - "Statistical Core Hardening"** (4-6 semanas)
Foco exclusivo em fechar gaps **P0/P1** do core estatístico antes de Web UI.
- Prós: Base sólida, Web UI consome API estável, evita retrabalho
- Contras: Atraso na UI visível para stakeholders

### Opção B: **Paralelo - Stage 2.5 + Stage 3** (6-8 semanas)
- Core team (2-3 devs) foca em gaps estatísticos P0/P1
- Frontend team (1-2 devs) inicia Web UI consumindo API atual
## PRÓXIMOS PASSOS IMEDIATOS

1. **Corrigir test_rule_3** ✅ (feito — commit de7015c)
2. **Rodar suite completa** ✅ (22/22 passing)
3. **Regressão Logística** ✅ (integrado + testado — commits 2becdf4 + dfa3bd2)
4. **DOE Fracionado + RSM** 🟡 — Código restaurado (e8aab6d), pendente critério de detecção (item 3.2)
5. **Atualizar GAP_ANALYSIS.md** ✅ (este documento atualizado)

---

## DECISÃO PENDENTE: Item 3.2 — Critério de detecção DOE fracionado/RSM

**Proposta** (ver discussão no item 3.2): detecção opt-in via padrão numérico exato (−1/0/+1, contagem de linhas consistente com 2^(k-p) ou CCD). Evita heurística solta.

**Próximo passo**: Decidir se implementa esse critério no `DOEAnalyzer.run()` ou mantém como opt-in manual.

1. **Corrigir test_rule_3** ✅ (feito)
2. **Rodar suite completa** ✅ (21/21 passing)
3. **Decidir: Stage 2.5 ou Paralelo?**
4. Se **Stage 2.5**: Criar branch `stage-2.5-statistical-core`, iniciar Sprint 1 (Box-Cox + MSA Attribute)
5. Se **Paralelo**: Definir API contracts estáveis para Web UI team

---

**Qual sua decisão?** Posso iniciar o Stage 2.5 (branch dedicado) ou preparar os contratos de API para o Stage 3 paralelo.