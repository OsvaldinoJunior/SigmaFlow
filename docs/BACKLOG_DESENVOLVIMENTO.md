# Próximas melhorias no código do SigmaFlow

Revisão em **13/11/2026**, baseada no código, na [avaliação de completude](AVALIACAO_COMPLETUDE.md) e em revisão de um subagente. Esta lista orienta as próximas entregas; os itens abaixo ainda precisam ser implementados ou concluídos no escopo descrito.

## Ponto de partida

A interface local já importa planilhas, sugere métodos, calcula análises, organiza a investigação DMAIC e preserva projetos, execuções e relatórios. A revisão atual acrescenta comparações explícitas de medições ou taxas entre grupos, Pareto acumulado, bloqueios para bases de custo ambíguas e registro de revisão das evidências por requisito de fase.

Essas funcionalidades não equivalem a uma liberação industrial. O produto compartilhado precisa de integração, validação estatística, governança e operação verificadas. Os critérios estão em [CRITERIOS_CONCLUSAO_LOCAL.md](CRITERIOS_CONCLUSAO_LOCAL.md).

## Prioridades

- **P0:** concluir antes de liberar os métodos selecionados para decisões industriais.
- **P1:** implementar para colaboração e acompanhamento sustentado nas empresas.
- **P2:** expandir depois que o fluxo principal e sua operação estiverem estáveis.

### P0 — Qualidade dos dados, cálculos e entrega

| ID | Trabalho no código | Áreas principais | Critério de aceite |
|---|---|---|---|
| 01 | Identificar unidades e subgrupos; detectar duplicação de denominadores, repetição de unidades e contagens incompatíveis. Registrar a estrutura da amostragem e explicar o que não puder ser verificado. | `sigmaflow/local_data.py`, `local_diagnosis.py`, `local_analysis.py` e mapeamento em `frontend/local/app.js` | Exemplos com a mesma produção repetida por categoria são sinalizados antes da comparação. Agrupamentos legítimos permanecem utilizáveis e a decisão do analista fica registrada. Ausência de identificadores continua explícita. |
| 02 | Criar uma matriz de liberação por método, com entradas, pressupostos, limites, referências numéricas independentes e revisão estatística. Ampliar casos de borda e consistência entre tela, relatório e pacote. | `sigmaflow/local_analysis.py`, `local_statistics.py`, `local_pilot.py`, `local_survival.py`, `tests/` e documentação dos métodos | Cada método liberado tem casos de referência com tolerâncias justificadas, entradas inválidas cobertas e revisão documentada do desenho de aplicação. Um teste aprovado não libera automaticamente outros métodos. |
| 03 | Automatizar as verificações do navegador já feitas manualmente: upload, mapeamento, parâmetros, bloqueios, requisição em andamento, erro, salvamento/reabertura e relatório. | `frontend/local/`, `sigmaflow/local_app.py` e futuros testes de navegador em `tests/` | A jornada de refugo e grupos roda com dados sintéticos, incluindo volumes diferentes, custo ambíguo e troca de arquivo; resultados e parâmetros persistidos conferem com o relatório. |
| 04 | Tornar a integração contínua executável no checkout padrão; revisar caminhos fixos como `/opt/data/SigmaFlow`, dependências e configuração. Resolver a execução dos testes de inicialização da API que ficaram fora da validação local. | `.github/workflows/ci-cd.yml`, `pyproject.toml`, `tests/test_auto_seed.py` e configuração da API | Um checkout limpo instala o ambiente documentado, executa os testes aplicáveis e informa claramente falhas e exclusões justificadas. O resultado da CI é conferido no GitHub. |

### P1 — Jornada completa e uso por empresas

| ID | Trabalho no código | Áreas principais | Critério de aceite |
|---|---|---|---|
| 05 | Dividir a interface local em módulos de diagnóstico, execução, investigação, histórico e piloto, preservando os contratos de projeto. | `frontend/local/app.js`, `case-store.js`, `report.js` e `charts.js` | Módulos têm responsabilidades definidas; a jornada do item 03 e os projetos salvos continuam funcionando, com migração explícita quando necessária. |
| 06 | Ampliar a estratificação para produto × linha × turno, com filtros revisáveis, dados ausentes explícitos e denominadores compatíveis. | `sigmaflow/local_diagnosis.py`, `local_analysis.py`, `local_visuals.py` e `frontend/local/` | Cada resultado mostra filtros, período, tamanho da amostra, denominador e unidades. Filtros e transformações são preservados na execução; combinações vazias ou repetidas são tratadas. Depende do item 01. |
| 07 | Fechar o controle sustentável: linha de base aprovada e versionada, plano amostral, limites congelados, regras de sinal e registro da reação. | `sigmaflow/local_analysis.py`, `local_visuals.py`, `sigmaflow/dmaic/control/` e painel de controle local | Novos dados são comparados à versão escolhida da linha de base; recalcular limites exige nova versão. Um sinal gera uma ocorrência com responsável, prazo, ação e evidência de fechamento. |
| 08 | Suportar desenhos adicionais de comparação conforme demanda: dados pareados, dependência temporal e agrupamento por lote. | `sigmaflow/local_statistics.py`, `local_pilot.py`, `local_analysis.py` e seleção de parâmetros | O desenho é declarado, validado com referências independentes e preservado no relatório. Os fluxos independentes atuais não são aplicados silenciosamente a esses dados. Depende do item 02 para cada método novo. |
| 09 | Unificar os contratos de projeto, análise, evidência e erro entre a interface local e a aplicação corporativa. Integrar execução, estado dos trabalhos e resultados. | `sigmaflow/api/main.py`, `sigmaflow/core/models.py`, `frontend/src/`, `sigmaflow/local_app.py` e módulos de execução existentes | Uma jornada de importação até o relatório funciona pela API corporativa com os mesmos parâmetros e resultados de referência, incluindo falha e repetição de requisição sem duplicar execução. |
| 10 | Preparar persistência compartilhada transacional, migração dos projetos locais, concorrência, backup e recuperação. | `sigmaflow/local_project_store.py`, `sigmaflow/core/database.py`, modelos e migrações existentes | Dois usuários ou processos não sobrescrevem revisões; uma restauração recupera dados, histórico e anexos com integridade conferida. Depende do contrato definido no item 09. |
| 11 | Vincular revisões e decisões de fase à identidade autenticada e a papéis; verificar isolamento entre empresas e plantas em todas as operações relevantes. | `sigmaflow/auth/rbac.py`, `sigmaflow/api/`, persistência e telas DMAIC | Testes tentam acesso cruzado a projetos, arquivos e exportações. Revisão guarda autor, decisão, evidência, horário e versão; aprovação independente segue a política definida pela empresa. Depende dos itens 09 e 10. |
| 12 | Criar registro de benefícios previstos e realizados com premissas versionadas, revisão de Finanças e prevenção de dupla contagem. | Modelos de projeto/benefício a acrescentar, telas DMAIC e `frontend/local/report.js` | Cálculo preserva período, moeda, volume, custo evitável, investimento, recorrência e fonte. Capacidade liberada, economia de caixa e projeção ficam identificadas; iniciativas concorrentes têm regra explícita de alocação. |

### P2 — Expansão e experiência

| ID | Trabalho no código | Áreas principais | Critério de aceite |
|---|---|---|---|
| 13 | Expor gradualmente os métodos avançados da biblioteca, como MSA e DOE, com coleta adequada e estado de liberação por método. | `sigmaflow/analysis/`, `local_diagnosis.py`, `local_analysis.py` e interface | Cada método mostra a pergunta, dados exigidos, pressupostos, resultado e limites. Apenas métodos que cumprirem o item 02 ficam liberados no escopo industrial. |
| 14 | Acrescentar conectores ERP/MES e importações agendadas com rastreabilidade, tratamento de falhas e controle de acesso. | `sigmaflow/connectors/` e execução corporativa | A mesma origem não gera dados duplicados após falha ou repetição; versão, janela, fuso horário e unidade acompanham os dados até o relatório. Depende dos itens 09 a 11. |
| 15 | Melhorar acessibilidade e desempenho para tabelas e gráficos maiores; oferecer navegação por teclado, foco e progresso de operações. | `frontend/local/` e `frontend/src/` | Upload, revisão, execução e leitura de resultados funcionam por teclado e em tela menor. Limites e tempos são medidos com conjuntos representativos e documentados, sem travar a página. |

## Ordem sugerida de execução

1. **Próximo ciclo local:** itens 01 a 04, usando refugo e comparação entre grupos como primeiros fluxos de referência.
2. **Investigar e sustentar melhorias:** itens 05 a 08 e 12; podem avançar em paralelo quando não alterarem o mesmo contrato.
3. **Preparar colaboração:** itens 09 a 11 antes de liberar dados e decisões compartilhados entre empresas.
4. **Expandir:** itens 13 a 15 de acordo com os casos reais priorizados.

Além do código, concluir um caso representativo e anonimizado do problema ao controle com operação, Black Belt e Finanças. Registrar resultado, incerteza, limitações e decisões pendentes. Esse aceite orienta a versão; não há porcentagem global de conclusão estimada nesta lista.

## Verificação disponível nesta revisão

A execução anterior de `python -m pytest tests -q --ignore=tests/test_auto_seed.py` terminou com **186 testes aprovados e 1 ignorado** por indisponibilidade de symlinks no ambiente. Os testes de inicialização da API ficaram fora dessa execução. A jornada local também foi verificada manualmente no navegador, conforme [AVALIACAO_COMPLETUDE.md](AVALIACAO_COMPLETUDE.md). A inclusão deste backlog não altera o código executável nem representa nova execução desses testes.
