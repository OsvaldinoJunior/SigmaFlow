# Roadmap SigmaFlow: plataforma Black Belt para melhoria industrial

Data: 13 de novembro de 2026. Roadmap de produto; o fluxo local foi exercitado com exemplos fictícios e testes de regressão. Isso não representa auditoria estatística completa nem liberação para decisões industriais reais.

## 1. Objetivo do produto

O SigmaFlow deve ajudar equipes industriais a transformar um problema de negócio em um projeto DMAIC rastreável: definir uma perda e uma meta, preparar dados confiáveis, identificar hipóteses, validar soluções e acompanhar resultados. O Black Belt continua responsável pelas decisões e pela interpretação; a ferramenta organiza evidências, sugere análises adequadas e torna as limitações visíveis.

**Público inicial:** Black Belts e engenheiros de qualidade/processo de fábricas com dados em planilhas. Patrocinadores e gestores acompanham resultados; operadores e responsáveis pelo processo registram causas e ações.

**Primeiro problema a resolver:** reduzir refugos e retrabalho em uma linha de produção, com um fluxo completo de dados → diagnóstico → ação → validação → controle. Este recorte também cria a base para outros setores e problemas.

## 2. Diagnóstico do que existe

Os estados abaixo significam que há código ou documentação no repositório. Não comprovam que a funcionalidade esteja integrada, correta para todos os casos ou pronta para uso industrial.

| Área | Base identificada | Próximo passo |
|---|---|---|
| Entrada e orquestração | `core/engine.py`, perfil de dados, seleção automática, analisadores de datasets, CLI e exemplos CSV/Excel. | Confirmar integração de ponta a ponta; permitir ao usuário revisar mapeamento, tipos, Y, unidade, tempo e subgrupo. |
| Estatística | Capacidade, XmR, X-bar/R, CUSUM/EWMA, Pareto, regressões, normalidade, testes de hipótese, MSA, FMEA e DOE têm implementações. | Validar métodos e pressupostos com referências independentes; expor escolhas e limitações. |
| Capacidades parciais | `analysis/transformations.py` contém funções de transformação e cartas p, np, c e u; `doe_analysis.py` contém fatoriais fracionados e superfície de resposta. | Verificar cobertura, integração e validade; não presumir que estejam disponíveis no fluxo principal. |
| DMAIC e insights | Workspace local com revisão por critério, referência de evidência, responsável declarado e justificativa N/A persistidos no projeto e apresentados no relatório exportado. | Autenticar papéis, separar execução/revisão/aprovação e auditar mudanças antes de compartilhamento corporativo. |
| Plataforma | API FastAPI, modelos de empresa/planta, usuário, projeto, dataset, execução, ação, agendamento, alertas, workers e Docker. | Completar jornada de uso e verificar autenticação, isolamento, execução assíncrona e recuperação. |
| Interface | `frontend/local` oferece importação/mapeamento, sugestões, cálculos, workspace DMAIC, piloto antes/depois, projetos salvos e relatórios/exportação. `frontend/src` mantém uma base corporativa separada com login/hook, ainda sem integração equivalente. | Completar história/revisões e governança local; integrar a jornada à API corporativa e revisar dependências/rotas daquela interface. |
| Documentação | `README.md`, `docs/` e `GAP_ANALYSIS.md` descrevem escopo e arquitetura. | Atualizar matriz de funcionalidades conforme evidências e execuções reais. |

### Pontos que mudam a priorização

1. **Capacidade e métricas de defeito:** `analysis/capability_analysis.py` calcula Cp e Pp com o mesmo desvio para dados individuais e iguala Cpk a Ppk. O cálculo de não conformes por milhão pressupõe uma oportunidade por unidade; DPMO geral precisa do número correto de oportunidades. Zero ocorrências na amostra também não comprova defeito zero. Validar definição do estimador, limites unilaterais, incerteza, comportamento com desvio zero e convenção de nível sigma antes de apresentar conclusões industriais.
2. **Recomendações:** `dmaic/improve/phase.py` escolhe faixas de preditores por quintis e infere maximizar/minimizar pelo nome da variável. Trata-se de exploração observacional: correlação, seleção de faixa e associação não provam causalidade nem autorizam alterar parâmetros de processo. Exigir objetivo explícito, rotular hipótese e solicitar validação antes de recomendações operacionais.
3. **Estabilidade e cartas:** resultados precisam preservar ordem temporal, definição de subgrupos e limites de referência. Em `control/phase.py`, o plano básico usa média ± 3 desvios para itens rotulados XmR; alinhar os limites ao método efetivamente selecionado e preservar a linha de base aprovada.
4. **Segurança:** a leitura estática mostra rotas de plantas e agendamentos sem dependência de usuário, além de registro que recebe papel do usuário e uma rota de criação de execução sem dependência explícita de autenticação. Auditar todas as rotas, autorização por papel e isolamento entre empresas antes de dados reais de clientes.
5. **Documentação divergente:** `GAP_ANALYSIS.md` classifica cartas de atributos e capacidade não normal de formas contraditórias e aponta funções em arquivo diferente daquele onde há código. Seu resumo também informa 72 ferramentas, mas 27 + 11 + 40 = 78. Recontar e revalidar a matriz; não usar as porcentagens como medida de prontidão.

## 3. Jornada desejada

1. **Definir:** empresa, planta, processo, patrocinador, problema, período, CTQ, unidade, meta, perdas e escopo. Registrar VOC, SIPOC e charter com revisão do responsável.
2. **Medir:** importar arquivo, revisar mapeamento de colunas e tipos; definir ordem temporal, produto, turno, máquina, lote, unidade, especificações e oportunidades de defeito. Exibir completude, duplicatas, distribuição e limitações; registrar MSA aplicável.
3. **Analisar:** selecionar métodos conforme a pergunta, tipo de dado e contexto. Apresentar Pareto, estratificação, estabilidade e, quando cabível, capacidade, testes e modelos. Registrar hipóteses e evidências que possam refutá-las.
4. **Melhorar:** comparar soluções por impacto, esforço e risco. Planejar piloto ou experimento com responsáveis, critérios de aceitação e limites seguros. Registrar o resultado observado e o que não funcionou.
5. **Controlar:** comparar antes e depois em janelas definidas, aprovar uma linha de base e um plano de reação; acompanhar ações, responsável, frequência e sinais. Reportar benefícios validados pela área financeira.

Cada insight deve informar: pergunta, população e período, variável e unidades, resultado e incerteza quando aplicável, método e pressupostos, evidência, limitações, próximo passo e estado de revisão. Um resultado com dados insuficientes ou pressupostos inadequados deve ser marcado como inconclusivo.

## 4. Cenários industriais prioritários

Os insights abaixo são exemplos hipotéticos e devem ser confirmados com os dados e com especialistas do processo.

| Prioridade / cenário | Dados mínimos | Métodos e pergunta | Exemplo de insight acionável | Decisão e validação |
|---|---|---|---|---|
| **P0 — Refugo e retrabalho** | Data, produto, linha, turno, quantidade produzida, quantidade de unidades defeituosas, categoria de defeito e custo unitário. | Pareto por quantidade e custo, estratificação e carta p/np com denominadores. Onde estão as maiores perdas e quando mudam? | Uma categoria concentra parcela relevante do custo, principalmente em certa linha e turno. | Investigar registros de setup e lote; validar causa em campo e acompanhar proporção após piloto. |
| **P0 — Medida fora de especificação** | Medição ordenada, unidade, produto, limites técnicos aprovados, lote/subgrupo e referência de medição. | MSA, XmR ou X-bar/R, estabilidade e capacidade apropriada. O processo é previsível e atende à especificação? | Há sinais de causa especial próximos a trocas de lote; capacidade ainda não é conclusiva. | Investigar ocorrência antes de estimar capacidade estável; confirmar limites e repetibilidade do sistema. |
| **P1 — Paradas e OEE** | Calendário e tempo planejado, eventos de parada com início/fim e causa, produção total/boa e ciclo ideal por produto. | Pareto de perdas; disponibilidade × desempenho × qualidade, com definições de estado acordadas. Onde recuperar tempo produtivo? | Setups representam uma parcela relevante do tempo perdido da máquina gargalo. | Cronometrar atividades, separar setup interno/externo, executar piloto SMED e verificar tempo e qualidade. |
| **P1 — Defeito por máquina, fornecedor ou turno** | Unidade ou lote, resultado conforme/não conforme, fatores anteriores ao resultado e contexto de produção. | Proporções, qui-quadrado quando aplicável e regressão logística validada. Quais fatores estão associados ao defeito? | A taxa difere por máquina após ajuste por produto, com incerteza apresentada. | Verificar confundimento e dados faltantes; testar hipótese com técnico e, quando viável, experimento controlado. |
| **P1 — Redução de variação via DOE** | Resposta mensurável, fatores controláveis, faixas seguras, unidade experimental, ordem e restrições. | Planejamento fatorial, aleatorização, replicação/bloqueio quando cabíveis, efeitos e interações. Qual combinação melhora a resposta? | A interação entre temperatura e velocidade indica uma região candidata de operação. | Confirmar em novas corridas, checar segurança e qualidade; aprovar apenas dentro dos limites estudados. |
| **P2 — Confiabilidade e manutenção** | Identificador do ativo, falhas, tempo em operação, manutenção e unidades ainda sem falha. | Contagem de falhas e Kaplan–Meier para unidades independentes com censura à direita disponíveis no fluxo local. Weibull, comparação de coortes e modelos de manutenção seguem pendentes. | A curva estima probabilidade de permanecer sem falha no horizonte observado; motivos de falha e decisões de manutenção exigem investigação adicional. | Revisar histórico, motivos das censuras, exposição e representatividade; validar hipóteses com manutenção antes de comparar estratégias preventivas. |
| **P2 — Fluxo e entregas** | Etapas, entrada/saída, fila/WIP, quantidade, demanda e calendário. | Lead time, takt, throughput, gargalo e VSM; comparar períodos equivalentes. Onde o pedido espera mais? | A maior parcela do lead time ocorre em espera antes de uma etapa. | Observar o fluxo, testar limite de WIP e medir entrega e produtividade sem transferir gargalo indevidamente. |
| **P2 — Energia e utilidades** | Consumo por intervalo, produção, mix, temperatura ambiente e estado da linha. | Consumo específico, regressão e monitoramento condicionado à produção. Que variação não é explicada pelo volume? | Consumo por unidade aumenta durante ociosidade prolongada. | Confirmar com medidores e manutenção; piloto de desligamento seguro e comparação ajustada por mix. |

### Exemplo financeiro para o piloto de refugo

Hipótese ilustrativa: 100.000 unidades/mês, taxa de refugo de 4%, custo evitável de R$ 5 por unidade e redução sustentada para 3%. Economia bruta estimada = 100.000 × (0,04 − 0,03) × R$ 5 = **R$ 5.000/mês**. Com custo de implantação de R$ 12.000 e sem custos recorrentes, o payback simples estimado é 2,4 meses. Esses valores não são uma promessa: confirmar volume, mix, custo marginal efetivamente evitável, período de comparação, custos de implantação e recorrentes; finanças aprova o benefício realizado. Evitar somar economias duplicadas entre projetos.

### Entrega local de piloto antes/depois

Disponível no cenário **Verificação de piloto antes e depois**, com plano explícito em Implementar: indicador, definição, unidade, meta/direção, janelas, ação opcional e declarações de desenho/comparabilidade. Calcula Welch para médias independentes ou Wilson/Newcombe para proporções de unidades defeituosas, com IC e diferenças depois − antes. O resultado distingue atendimento pontual, incerteza e revisão humana; não atribui causalidade nem altera o estado da ação. Alterações posteriores do plano preservam parâmetros executados com aviso, inclusive na reabertura e no relatório. O pacote exportado mantém/reproduz esses parâmetros. Ver [método e limites](METODO_PILOTO_ANTES_DEPOIS.md) e [dois exemplos novos](../problemas_exemplos_testes_LSS/COMO_TESTAR_PILOTOS.md).

Estado conferido em 13/11/2026: 14 cenários locais, 15 planilhas fictícias passando por triagem/cálculo e 186 testes aprovados, com 1 ignorado. O arquivo `test_auto_seed.py`, de inicialização da API, ficou fora dessa execução. A comparação entre grupos agora escolhe explicitamente medições ou taxas com denominadores, ICs e parâmetros preservados; ver [método e limites](METODO_COMPARACAO_GRUPOS.md). A integração corporativa, autenticação multiusuário verificada, aprovação independente de fase, desenhos pareados/seriais e validação industrial continuam pendentes. Consulte a [avaliação de completude](AVALIACAO_COMPLETUDE.md).

## 5. Roadmap de entregas

Estimativas são faixas indicativas a partir do início do projeto, não compromissos de prazo. Premissas: dois desenvolvedores com dedicação integral, um Black Belt/dono de produto com disponibilidade regular, apoio parcial de estatístico, especialista do processo, segurança e usuário piloto; acesso a dados anonimizados e decisões rápidas. Uma única pessoa, integrações legadas ou validação de cliente podem ampliar os prazos. O trabalho de interface pode avançar em paralelo após os contratos de dados essenciais.

| Etapa | Janela indicativa | Entregas principais | Critério de saída |
|---|---|---|---|
| **0. Base confiável** | Semanas 1–4 | Inventário executável e matriz de métodos; corrigir segurança prioritária e isolamento; consolidar contratos de análise e erros; confirmar mapeamento manual e qualidade de dados; selecionar linha piloto. | Nenhum acesso cruzado em testes de autorização; entradas e limites exigidos são explícitos; revisão estatística identifica métodos liberados e bloqueados. |
| **1. MVP de refugo** | Semanas 5–12 | Projeto/CTQ, importação CSV/XLSX, dados e denominadores validados, Pareto por custo e quantidade, estratificação, carta p/np, histórico, ações e relatório. Interface para criar e revisar projeto. | Um caso real ou anonimizado percorre importação → análise → hipótese → ação → relatório; Black Belt reproduz os resultados e piloto consegue executá-lo sem suporte técnico contínuo. |
| **2. Medição e capacidade** | Semanas 13–20 | MSA aplicável, cartas de variáveis com subgrupos, estabilidade, especificações, capacidade normal e não normal conforme métodos validados, intervalos e comparação de períodos; plano de controle com reação. | Valores conferidos com exemplos de referência independentes; dados insuficientes ou instabilidade geram ressalva/bloqueio; acompanhamento preserva limites aprovados. |
| **3. Diagnóstico e melhoria** | Semanas 21–30 | Testes de proporções e grupos, regressão com diagnóstico, tamanho de amostra para estudos selecionados, FMEA ligado a ações e controles, planejamento DOE com objetivo e restrições, piloto antes/depois. | Cada análise registra pergunta, pressupostos e limitações; experimento e confirmação são registrados e revisados; hipóteses não são apresentadas como causas provadas. |
| **4. Escala industrial** | Semanas 31–42 | OEE e fluxo, alertas úteis com responsáveis e deduplicação, aprovações e histórico, visão de portfólio, auditoria, integrações em lote priorizadas e operação monitorada. | Duas linhas ou plantas usam o fluxo com dados isolados; recuperação de falhas, rastreabilidade e revisão de acesso demonstradas em ambiente de homologação. |
| **5. Expansão especializada** | Após etapa 4, conforme demanda | Confiabilidade com censura, Monte Carlo, DOE avançado, VSM, conectores de historiadores e séries temporais, previsão e análises multivariadas. | Cada módulo tem cliente e pergunta definidos, dados adequados, referência de cálculo, revisão técnica e piloto antes de ser liberado. |

### Dependências e prioridades

- **P0:** segurança e isolamento; integridade dos dados e contexto; correção e validação de métricas; jornada de refugo; revisão humana; relatório e ações. Sem esses itens, não há piloto com dados industriais reais.
- **P1:** MSA, SPC de variáveis, capacidade com critérios, diagnóstico estatístico, comparação antes/depois e controle sustentado. OEE entra depois de acordar eventos e definições com a fábrica.
- **P2:** DOE avançado, confiabilidade, simulação e integrações contínuas, priorizados por demanda. IA generativa pode futuramente resumir evidências rastreáveis, mas não calcula resultados de forma independente nem aprova mudanças.

## 6. Primeiros dois ciclos de trabalho

**Ciclo 1 — descoberta e proteção (semanas 1–2)**

- Escolher linha piloto, patrocinador, CTQ, critério de sucesso e fonte dos dados. Levantar dicionário de dados e custo evitável com a fábrica.
- Executar inventário das rotas e permissões; corrigir autenticação, papel no cadastro e filtros de empresa/planta. Elaborar testes de acesso entre empresas.
- Criar matriz para cada método: arquivo/função, entrada, saída, pressupostos, caminho de execução, validação independente e estado de liberação.
- Padronizar o resultado: `status` (válido, inconclusivo, falhou), dados usados, método, versão, parâmetros, avisos e erro. Não ocultar falhas tratadas por exceções.

**Ciclo 2 — dados e diagnóstico inicial (semanas 3–4)**

- Criar contrato de importação com amostra, mapeamento confirmado, data, unidade, quantidade produzida/inspecionada e definição de defeito; bloquear denominadores inconsistentes.
- Validar Pareto e cartas por atributos existentes com exemplos independentes, incluindo tamanhos de amostra variáveis e distinção entre unidades defeituosas e número de defeitos.
- Criar registro de projeto, hipótese, evidência e ação; apresentar protótipo de relatório com ressalvas e responsável.
- Decidir o escopo do MVP a partir de uma demonstração com dados do piloto. Aceite: reproduzir cálculo manual de um lote, manter rastreabilidade de entrada e explicar todos os avisos.

## 7. Regras estatísticas e de produto

- Diferenciar **limites de especificação** do cliente de **limites de controle** calculados a partir do processo; nunca inferir especificação dos dados sem identificá-la como tal.
- Verificar sequência temporal, estabilidade, subgrupos, sistema de medição e adequação da distribuição antes de interpretar capacidade. Em processo instável, mostrar desempenho observado com ressalvas e orientar investigação; não declarar capacidade estável. Referência: [NIST, capacidade de processo](https://itl.nist.gov/div898/handbook/pmc/section1/pmc16.htm).
- Para atributos, distinguir unidades defeituosas de número de defeitos, e registrar oportunidades e denominador. Expor incerteza para eventos raros ou amostras pequenas.
- Exibir tamanho da amostra, efeito e intervalo de confiança quando aplicáveis, além de p-valor; validar pressupostos, dependência temporal, seleção de variáveis e comparações múltiplas. Separar análise exploratória de hipótese pré-definida.
- Estimar variação dentro de subgrupo e global com métodos adequados; não apresentar automaticamente Cp/Cpk e Pp/Ppk como medidas independentes quando usam o mesmo estimador.
- Em DOE, definir fatores, resposta, randomização, bloqueios, replicação, restrições e região de aplicação; registrar confundimento e confirmar solução em novas corridas. Referência: [NIST, terminologia de DOE](https://itl.nist.gov/div898/handbook/pri/section7/pri7.htm).
- O usuário confirma a variável de resposta, objetivo, limites e custos. Dados observacionais geram hipóteses; ação de processo exige validação pelo responsável.
- Guardar versão dos dados e método, filtros, configurações, resultados, falhas, autor e aprovação. Testes com dados de referência e comparação com cálculo independente acompanham cada método liberado.

## 8. Indicadores de sucesso e governança

| Indicador | Como medir | Meta inicial proposta para o piloto |
|---|---|---|
| Jornada completa | Projetos com dados, hipótese, ação, validação e plano de controle registrados. | 1 projeto concluído no MVP; meta de expansão definida após piloto. |
| Tempo até diagnóstico | Horas de trabalho desde dados aceitos até diagnóstico revisado; comparar com método atual. | Medir linha de base; buscar redução de 30% sem reduzir qualidade. |
| Qualidade do cálculo | Casos de referência aprovados / casos aplicáveis, incluindo limites e falhas esperadas. | 100% dos casos de referência definidos para métodos liberados; revisão estatística documentada. |
| Adoção | Usuários ativos que concluem a jornada e avaliação de utilidade. | Pelo menos 2 usuários do piloto completam o fluxo; registrar obstáculos. |
| Resultado industrial | Taxa de refugo ou CTQ por período comparável, com volume, mix e eventos. | Meta negociada com a fábrica antes do piloto; apresentar incerteza e contexto. |
| Benefício financeiro | Economia evitável comprovada, custos e responsável pela validação. | Finanças valida fórmula e valores antes de classificá-los como realizados. |
| Segurança | Tentativas de acesso entre empresas e ações sem autorização em homologação. | Nenhum acesso indevido nos cenários de teste definidos; corrigir qualquer falha antes do piloto. |

Revisão quinzenal do backlog com Black Belt e desenvolvimento; revisão mensal com patrocinador e responsável do processo. Encerramento de cada etapa exige demonstração, evidências dos critérios de saída, responsáveis e decisão registrada. Melhorias adicionais são priorizadas por perda potencial, frequência, risco, disponibilidade dos dados e esforço, evitando presumir economia ou causalidade.

## 9. Decisões para iniciar

1. Definir a primeira indústria, linha e problema de maior perda, além do patrocinador e do dono dos dados.
2. Confirmar disponibilidade de histórico, especificações, denominadores, custos e dados de medição; anonimizar dados para desenvolvimento quando necessário.
3. Acordar equipe, dedicação e horizonte; as janelas acima são planejamento inicial.
4. Validar as definições de refugo, retrabalho, custo, turno e produto com operação e finanças.
5. Aprovar o recorte do MVP e manter o roadmap como documento vivo a cada aprendizado do piloto.
