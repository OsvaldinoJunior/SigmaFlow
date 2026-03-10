# SigmaFlow — Prompt de Refatoração para GitHub

> Use este prompt com um LLM (ex: Claude) para continuar o desenvolvimento e publicação profissional do SigmaFlow.

---

Você é um engenheiro de software especialista em Python, arquitetura de projetos científicos e bibliotecas open-source.

Analise completamente o projeto chamado **SigmaFlow** presente no diretório atual e realize uma refatoração estrutural para deixá-lo pronto para publicação profissional no GitHub.

O objetivo do projeto é ser uma **plataforma Python para automação de projetos Lean Six Sigma utilizando o framework DMAIC**, com módulos de análise estatística, geração de relatórios e insights automáticos.

Execute cuidadosamente as seguintes etapas.

---

## 1. Corrigir estrutura de diretórios

Identifique pastas criadas incorretamente com **chaves `{}` no nome**, por exemplo:

```
sigmaflow/dmaic/{define,measure,analyze,improve,control}/
```

Essas pastas foram criadas incorretamente e devem ser convertidas para diretórios reais.

Transforme em:

```
sigmaflow/dmaic/
  define/
  measure/
  analyze/
  improve/
  control/
```

Garanta que cada fase do DMAIC seja uma pasta separada.

---

## 2. Garantir estrutura profissional do projeto

Organize o projeto exatamente nesta estrutura:

```
SigmaFlow/
│
├── sigmaflow/
│   ├── core/
│   │   ├── engine.py
│   │   ├── dmaic_engine.py
│   │   ├── analysis_planner.py
│   │   ├── dataset_detector.py
│   │   ├── dataset_registry.py
│   │   ├── data_profiler.py
│   │   ├── logger.py
│   │   └── output_manager.py
│
│   ├── statistics/
│   │   ├── hypothesis_tests.py
│   │   └── normality_tests.py
│
│   ├── insights/
│   │   ├── rules_engine.py
│   │   └── statistical_rules.py
│
│   ├── report/
│   │   ├── html_dashboard.py
│   │   ├── latex_report.py
│   │   └── latex_templates/
│
│   ├── dmaic/
│   │   ├── define/
│   │   ├── measure/
│   │   ├── analyze/
│   │   ├── improve/
│   │   └── control/
│
│   └── __init__.py
│
├── input/
│   └── datasets/
│
├── tests/
├── examples/
├── docs/
│
├── cli.py
├── run_dmaic.py
├── main.py
│
├── README.md
├── requirements.txt
├── pyproject.toml
├── setup.py
├── LICENSE
└── .gitignore
```

---

## 3. Criar pasta de exemplos

Crie uma pasta `examples/` com scripts demonstrando o uso da biblioteca:

- `examples/basic_dmaic.py`
- `examples/manufacturing_example.py`
- `examples/statistical_analysis.py`

Cada exemplo deve carregar um dataset e executar um fluxo do SigmaFlow.

---

## 4. Melhorar o README

Reescreva o `README.md` para torná-lo profissional.

Ele deve conter:

- Descrição do projeto
- Objetivos
- Funcionalidades principais
- Arquitetura do sistema
- Estrutura do projeto
- Exemplo de uso
- Instruções de instalação
- Exemplo de execução

Adicionar também uma explicação da arquitetura:

```
Dataset
  ↓
Profiler
  ↓
Analysis Planner
  ↓
Statistics Engine
  ↓
Insights Engine
  ↓
Report Generator
```

---

## 5. Adicionar documentação

Criar pasta `docs/` com arquivos:

- `architecture.md`
- `dmaic_workflow.md`
- `statistics_module.md`

Explicando:

- Arquitetura do SigmaFlow
- Funcionamento do pipeline DMAIC
- Como os testes estatísticos são executados

---

## 6. Melhorar o CLI

Melhorar o arquivo `cli.py` para permitir execução via terminal.

Exemplo de comandos:

```bash
sigmaflow run dataset.xlsx
sigmaflow dmaic dataset.xlsx
```

Utilize `argparse` para criar a interface de linha de comando.

---

## 7. Adicionar versionamento

No arquivo `sigmaflow/__init__.py` adicione:

```python
__version__ = "0.1.0"
```

---

## 8. Garantir empacotamento Python

Revise `pyproject.toml` e `setup.py` para permitir instalação com:

```bash
pip install .
```

E garantir que o pacote instalável seja `sigmaflow`.

---

## 9. Adicionar docstrings

Percorra todos os arquivos Python e adicione docstrings padrão:

```python
"""
Description

Parameters
----------
param : type
    description

Returns
-------
type
"""
```

Isso deve ser feito para todas as funções e classes principais.

---

## 10. Garantir limpeza do repositório

Verifique o `.gitignore` para incluir:

```
__pycache__/
*.pyc
.env
venv/
output/
logs/
.ipynb_checkpoints
```

Outputs gerados automaticamente não devem ser versionados.

---

## 11. Validar testes

Execute os arquivos da pasta `tests/` e corrija erros.

---

## 12. Preparar para publicação no GitHub

Organize commits iniciais como:

```
feat: initial sigmaflow architecture
feat: add dmaic modules
feat: add statistical engine
feat: add reporting system
docs: add documentation
```

---

## Resultado esperado

Após a refatoração, o projeto deve:

- Possuir arquitetura clara
- Estar empacotado como biblioteca Python
- Ter CLI funcional
- Possuir documentação
- Possuir exemplos executáveis
- Estar pronto para publicação open-source no GitHub
