# SigmaFlow

> **Plataforma Python para automação de projetos Lean Six Sigma com o framework DMAIC.**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-orange)](sigmaflow/__init__.py)

---

## Descrição

O **SigmaFlow** é uma biblioteca Python de código aberto que automatiza a execução de projetos Lean Six Sigma. Ele aceita dados de processo brutos (CSV ou Excel) e executa automaticamente um pipeline completo: detecta o tipo de dataset, aplica os testes estatísticos adequados, gera gráficos de controle, identifica causas raiz e produz relatórios prontos para apresentação.

---

## Objetivos

- Reduzir o tempo de análise estatística em projetos de melhoria de processos
- Padronizar a aplicação do framework DMAIC com saídas consistentes e auditáveis
- Democratizar o acesso a ferramentas de Lean Six Sigma através de Python
- Fornecer uma base extensível para equipes de qualidade e engenharia

---

## Funcionalidades Principais

| Funcionalidade | Descrição |
|---|---|
| **Auto-detecção de dataset** | Identifica automaticamente SPC, Capability, Pareto, DOE, Logística, Serviço |
| **Pipeline DMAIC completo** | Define → Measure → Analyze → Improve → Control |
| **Capacidade de processo** | Cp, Cpk, Cpu, Cpl, DPMO, nível sigma |
| **Cartas de controle** | XmR, X-bar/R, CUSUM, EWMA com regras Western Electric |
| **Testes estatísticos** | Shapiro-Wilk, Anderson-Darling, t-test, ANOVA, Mann-Whitney |
| **Root cause analysis** | Matriz de correlação + ranking de variáveis |
| **DOE / Regressão** | ANOVA, efeitos principais, R², preditores significativos |
| **MSA / Gauge R&R** | Análise de sistema de medição |
| **FMEA** | Cálculo de RPN e ranking de modos de falha |
| **Relatórios** | Dashboard HTML interativo + relatório LaTeX/PDF |
| **Arquitetura modular** | Adicionar novo tipo de dataset = criar 1 arquivo |

---

## Arquitetura do Sistema

O SigmaFlow processa cada dataset através de um pipeline de 6 camadas:

```
┌─────────────────────────────────────────────┐
│                  Dataset                    │
│         (CSV / XLSX — input/datasets/)      │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│                  Profiler                   │
│   core/data_profiler.py                     │
│   • shape, dtypes, missing values           │
│   • numeric vs categorical summary          │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│             Analysis Planner                │
│   core/analysis_planner.py                  │
│   • DatasetRegistry (auto-discovery)        │
│   • match() → seleciona o analisador certo  │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│            Statistics Engine                │
│   analysis/ + statistics/                   │
│   • Cp, Cpk, XmR, DOE, Regressão, MSA      │
│   • Normalidade + Hipóteses                 │
│   • FMEA, Root Cause                        │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│             Insights Engine                 │
│   insights/rules_engine.py                  │
│   • Western Electric Rules                  │
│   • Thresholds de Cpk / DPMO               │
│   • Objetos Insight com severity            │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│            Report Generator                 │
│   report/html_dashboard.py                  │
│   report/latex_report.py                    │
│   • Dashboard HTML interativo               │
│   • Relatório LaTeX + PDF                   │
│   • insights.json                           │
└─────────────────────────────────────────────┘
```

---

## Estrutura do Projeto

```
SigmaFlow/
│
├── sigmaflow/                   ← Pacote Python principal
│   ├── core/                    ← Motor, registry, logger
│   │   ├── engine.py            ← Orquestrador do pipeline
│   │   ├── dmaic_engine.py      ← Motor DMAIC por fases
│   │   ├── dataset_registry.py  ← Auto-discovery de analisadores
│   │   ├── analysis_planner.py  ← Planejamento de análises
│   │   ├── data_profiler.py     ← Profiling de dataset
│   │   ├── logger.py            ← Logger estruturado
│   │   └── output_manager.py   ← Gerenciamento de outputs
│   │
│   ├── analysis/                ← Módulos de análise estatística
│   │   ├── capability_analysis.py   → Cp, Cpk, DPMO
│   │   ├── spc_analysis.py          → XmR, Western Electric
│   │   ├── pareto_analysis.py       → Análise 80/20
│   │   ├── regression_analysis.py   → OLS multivariada
│   │   ├── doe_analysis.py          → DOE + ANOVA
│   │   ├── msa_analysis.py          → Gauge R&R
│   │   ├── fmea_analysis.py         → RPN + ranking
│   │   └── root_cause_analysis.py   → Correlação + importância
│   │
│   ├── statistics/              ← Testes estatísticos
│   │   ├── normality_tests.py       → Shapiro-Wilk, AD, KS
│   │   └── hypothesis_tests.py      → t-test, ANOVA, Mann-Whitney
│   │
│   ├── visualization/           ← Gráficos e cartas de controle
│   │   ├── control_charts.py        → XmR
│   │   ├── cusum_chart.py           → CUSUM
│   │   ├── ewma_chart.py            → EWMA
│   │   ├── xbar_r_chart.py          → X-bar/R
│   │   ├── capability_plots.py      → Histograma + QQ-plot
│   │   ├── pareto_chart.py          → Gráfico de Pareto
│   │   ├── histograms.py            → Distribuições
│   │   └── correlation_heatmap.py   → Matriz de correlação
│   │
│   ├── datasets/                ← Analisadores auto-descobertos
│   │   ├── base_dataset.py          → ABC BaseDataset
│   │   ├── capability_dataset.py    → priority=60
│   │   ├── spc_dataset.py           → priority=70
│   │   ├── root_cause_dataset.py    → priority=50
│   │   ├── doe_dataset.py           → priority=80
│   │   ├── logistics_dataset.py     → priority=45
│   │   └── service_dataset.py       → priority=40
│   │
│   ├── insights/                ← Motor de regras
│   │   ├── rules_engine.py          → RulesEngine, Insight
│   │   └── statistical_rules.py     → Western Electric + Cpk
│   │
│   ├── report/                  ← Geração de relatórios
│   │   ├── html_dashboard.py        → Dashboard Jinja2
│   │   ├── latex_report.py          → Relatório LaTeX/PDF
│   │   └── latex_templates/         → Templates .tex
│   │
│   ├── dmaic/                   ← Fases DMAIC
│   │   ├── define/phase.py          → DefinePhase
│   │   ├── measure/phase.py         → MeasurePhase
│   │   ├── analyze/phase.py         → AnalyzePhase
│   │   ├── improve/phase.py         → ImprovePhase
│   │   └── control/phase.py         → ControlPhase
│   │
│   └── __init__.py
│
├── input/datasets/              ← Coloque seus arquivos aqui
├── tests/                       ← Suite pytest
├── examples/                    ← Scripts de exemplo
│   ├── basic_dmaic.py
│   ├── manufacturing_example.py
│   └── statistical_analysis.py
├── docs/                        ← Documentação
│
├── main.py                      ← Execução zero-argumento
├── cli.py                       ← Interface de linha de comando
├── requirements.txt
├── pyproject.toml
├── setup.py
├── LICENSE
└── .gitignore
```

---

## Instalação

### Via pip (recomendado)

```bash
git clone https://github.com/<user>/sigmaflow.git
cd sigmaflow
pip install -e .
```

### Apenas dependências

```bash
pip install -r requirements.txt
```

### Opcional: relatórios PDF (LaTeX)

```bash
# Ubuntu / Debian
sudo apt install texlive-latex-extra

# macOS
brew install --cask mactex

# Conda
conda install -c conda-forge texlive-core
```

---

## Exemplo de Uso

### 1. Zero-argumento — coloque um arquivo e execute

```bash
# Copie seu dataset para input/datasets/
cp meu_processo.xlsx input/datasets/

# Execute o pipeline completo
python main.py
```

### 2. Via CLI

```bash
# Análise completa de um arquivo
sigmaflow run dataset.xlsx

# Pipeline DMAIC
sigmaflow dmaic dataset.xlsx

# Demonstração com dados sintéticos
sigmaflow demo

# Listar analisadores disponíveis
sigmaflow list
```

### 3. Via Python API

```python
from sigmaflow.core.engine import Engine

engine = Engine(
    input_dir  = "input/datasets",
    output_dir = "output",
)
results = engine.run()

for r in results:
    cap = r["analysis"].get("capability", {})
    print(f"{r['name']}  Cpk={cap.get('Cpk', 'N/A')}  DPMO={cap.get('dpmo', 'N/A')}")
```

### 4. Análise de capacidade direta

```python
import pandas as pd
import numpy as np
from sigmaflow.analysis.capability_analysis import compute_capability

data   = pd.Series(np.random.normal(10.0, 0.08, 300))
result = compute_capability(data, usl=10.3, lsl=9.7)

print(f"Cpk         = {result['Cpk']:.3f}")
print(f"DPMO        = {result['dpmo']:.1f}")
print(f"Sigma level = {result['sigma_level']:.2f}σ")
```

### 5. Pipeline DMAIC completo

```python
import pandas as pd
from sigmaflow.core.dmaic_engine import DMAICEngine

df     = pd.read_excel("input/datasets/process_data.xlsx")
engine = DMAICEngine(df)
result = engine.run_all()

print(result["measure"]["sigma_level"])
print(result["analyze"]["significant_variables"])
```

---

## Saídas Geradas

Após executar o pipeline, os arquivos ficam em `output/`:

```
output/
├── figures/<dataset>/   ← Gráficos PNG (controle, pareto, regressão...)
├── reports/             ← process_analysis_report.pdf + .tex
├── dashboard/           ← report.html  (abra no navegador)
└── insights.json        ← Insights estruturados em JSON
```

---

## Adicionando Novos Tipos de Dataset

A arquitetura de auto-discovery permite adicionar um novo analisador **sem modificar nenhum arquivo existente**:

```python
# sigmaflow/datasets/meu_dataset.py
from sigmaflow.datasets.base_dataset import BaseDataset

class MeuDataset(BaseDataset):
    name     = "meu_tipo"
    priority = 55

    def detect(self, df):
        return "minha_coluna" in df.columns

    def run_analysis(self, df):
        return {"media": float(df["minha_coluna"].mean())}

    def generate_plots(self, df, output_folder):
        return []  # lista de caminhos PNG gerados

    def generate_insights(self, df):
        return ["Meu insight personalizado."]
```

---

## Executando os Testes

```bash
pytest tests/ -v
pytest tests/ -v --cov=sigmaflow --cov-report=term-missing
```

---

## Exemplos

```bash
python examples/basic_dmaic.py            # Pipeline DMAIC básico
python examples/manufacturing_example.py  # Processo de manufatura completo
python examples/statistical_analysis.py  # Módulos estatísticos individuais
```

---

## Documentação

- [`docs/architecture.md`](docs/architecture.md) — Arquitetura do sistema
- [`docs/dmaic_workflow.md`](docs/dmaic_workflow.md) — Guia do pipeline DMAIC
- [`docs/statistics_module.md`](docs/statistics_module.md) — Módulo estatístico

---

## Contribuindo

1. Faça um fork do repositório
2. Crie uma branch: `git checkout -b feat/minha-feature`
3. Adicione testes para a nova funcionalidade
4. Abra um Pull Request

---

## Licença

MIT License — veja [LICENSE](LICENSE) para detalhes.
