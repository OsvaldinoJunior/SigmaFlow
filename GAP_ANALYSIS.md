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
| **Capability - Non-Normal (Box-Cox / Johnson)** | ❌ | **Crítico**. Minitab faz auto-transformação Box-Cox/Johnson e calcula Cpk non-paramétrico (percentil method). SigmaFlow falha silenciosamente em dados não-normais. |
| **Capability - Attribute (Binomial/Poisson)** | ❌ | DPMO para defectives (p-chart) e defects (c/u-chart). Não confundir com variável contínua. |
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
| **Logistic Regression (Binary/Ordinal/Nominal)** | ❌ | **Gap crítico**. Para Y binário (defectivo/sim-não) ou ordinal. Minitab faz stepwise, odds ratios, Hosmer-Lemeshow, ROC curve. |
| **Nonlinear Regression** | ❌ | Modelos não-lineares customizados (ex: crescimento, decaimento, Michaelis-Menten). |
| **DOE - Full Factorial** | ✅ | `DOEAnalyzer` com 2-level full factorial. Main effects + interactions. |
| **DOE - Fractional Factorial** | ❌ | Resolution III/IV/V, alias structure, foldover. Essencial para screening com muitos fatores (custo↓). |
| **DOE - Response Surface (RSM)** | ❌ | Central Composite Design (CCD), Box-Behnken. Otimização de curvatura. Minitab: contour/surface plots. |
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
| **DOE - Otimização (RSM)** | ❌ | Ver MEASURE/DOE section. Contour/surface plots, stationary point, ridge analysis. |
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
| **Western Electric Rules (8 rules)** | 🟡 | Regras 1-4 implementadas. **Faltam**: Regra 5 (2 of 3 > 2σ), Regra 6 (4 of 5 > 1σ), Regra 7 (15 in zone C), Regra 8 (8 on both sides of CL). |
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
| **MEASURE** | 18 | 6 | 2 | 10 | **33%** |
| **ANALYZE** | 16 | 5 | 2 | 9 | **31%** |
| **IMPROVE** | 7 | 1 | 0 | 6 | **14%** |
| **CONTROL** | 7 | 1 | 3 | 3 | **29%** |
| **LEAN** | 7 | 0 | 0 | 7 | **0%** |
| **ESTATÍSTICA GERAL** | 10 | 2 | 1 | 7 | **20%** |
| **TOTAL** | **72** | **22** | **9** | **46** | **~30%** |

---

## PRIORIZAÇÃO SUGERIDA (Impacto × Esforço)

| Prioridade | Item | Fase | Impacto MBB | Esforço Estimado | Comentário |
|------------|------|------|-------------|------------------|------------|
| **P0 - Crítico** | Capacidade não-normal (Box-Cox/Johnson) | MEASURE | 🔴 Bloqueia projetos reais | Médio | Muitos processos industriais não-normais |
| **P0 - Crítico** | Gráficos de controle de atributos (p,np,c,u) | MEASURE | 🔴 Essencial para qualidade discreta | Médio | Defeitos vs defeitos é distinção fundamental |
| **P0 - Crítico** | Regressão Logística (binária/ordinal) | ANALYZE | 🔴 Y binário é comum (defeitivo/sim-não) | Alto | Requer redesign do `RegressionAnalyzer` |
| **P0 - Crítico** | DOE Fracionado + RSM | IMPROVE | 🔴 Otimização real precisa curvatura | Alto | Core do Improve phase |
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
- Sync semanal via API contract
- Risco: API breaking changes se gaps exigirem redesign

### Opção C: **Stage 3 First (Web UI)** → Stage 2.5 depois
- Entrega valor visual rápido (dashboard, project management UI)
- Gaps estatísticos ficam "under the hood" para usuários menos técnicos
- Risco: MBBs reais vão testar e rejeitar se core estatístico fraco

---

## MINHA RECOMENDAÇÃO: **Opção A (Stage 2.5 dedicado)**

**Razão**: SigmaFlow se posiciona como "plataforma de automação DMAIC para empresas reais". Um Master Black Belt **não adotará** a ferramenta se:
1. Não calcular Cpk correto em dados não-normais (Box-Cox/Johnson)
2. Não tiver gráficos p/np/c/u para defeitos
3. Não fizer regressão logística para Y binário
4. Não tiver DOE fracionado + RSM para otimização

Esses são **table stakes** para credibilidade técnica. A Web UI sem isso é "lipstick on a pig".

**Sugestão de cronograma Stage 2.5 (4 sprints de 1 semana):**

| Sprint | Foco | Entregáveis |
|--------|------|-------------|
| 1 | Capacidade não-normal + MSA Attribute | Box-Cox/Johnson transform, Kappa/Fleiss |
| 2 | Gráficos de atributos + 8 regras WE | p/np/c/u charts, regras 5-8 |
| 3 | Regressão Logística + DOE Fracionado/RSM | Binary/ordinal logistic, fractional factorial, CCD/Box-Behnken |
| 4 | Monte Carlo + Control Plan completo | `SimulateResponse`, FMEA→Control Plan linkage, post-improvement capability comparison |

---

## PRÓXIMOS PASSOS IMEDIATOS

1. **Corrigir test_rule_3** ✅ (feito)
2. **Rodar suite completa** ✅ (21/21 passing)
3. **Decidir: Stage 2.5 ou Paralelo?**
4. Se **Stage 2.5**: Criar branch `stage-2.5-statistical-core`, iniciar Sprint 1 (Box-Cox + MSA Attribute)
5. Se **Paralelo**: Definir API contracts estáveis para Web UI team

---

**Qual sua decisão?** Posso iniciar o Stage 2.5 (branch dedicado) ou preparar os contratos de API para o Stage 3 paralelo.