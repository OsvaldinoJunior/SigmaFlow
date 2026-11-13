# Guia de métodos estudados para o SigmaFlow

Este guia registra procedimentos para orientar a futura implementação. As referências e o estado da revisão estão em `ACOMPANHAMENTO_ESTUDO_BELTS.md`. A seleção do método, suas premissas e a interpretação precisam ser revisadas para cada processo.

Complemento implementado com fontes metodológicas independentes: [Kaplan–Meier para vida útil com censura à direita](METODO_KAPLAN_MEIER_LOCAL.md). A nota registra os dados necessários, cálculo, Greenwood, mediana, RMST, exemplo fictício e limitações. Essa implementação não altera o estado de revisão das aulas.

## Plano de medição e amostragem

**Fonte:** Green Belt 13 e planilha complementar.

1. Descrever objetivo, definição operacional, indicador, unidade e critérios de registro.
2. Definir população, fonte, período, frequência, responsáveis, instrumento e tamanho da amostra; registrar outras variáveis relevantes e como os resultados serão usados.
3. Escolher e documentar o desenho de amostragem, como aleatório, sistemático ou estratificado. Analisar cobertura e possíveis vieses, incluindo ciclos que coincidam com o intervalo sistemático.
4. Testar a coleta e revisar consistência, treinamento e condições do sistema de medição; registrar resolução e limitações.
5. Vincular o plano aos dados carregados e reutilizar os campos no diagnóstico e no relatório. Guardar referência à fonte, sem armazenar senhas no plano.

**Insight possível:** indicar que a planilha contém apenas um turno quando o objetivo menciona a fábrica inteira, orientando o usuário a verificar cobertura antes de comparar turnos ou generalizar resultados.

## Mapeamento de processos e fluxo de valor

**Fonte:** Yellow Belt 6 e apostila Yellow Belt, páginas 95–124.

1. Definir início, fim, cliente, objetivo e participantes; observar o processo real com quem o executa.
2. Registrar etapas, responsáveis, entradas, saídas, decisões, retornos e sistemas usados. Permitir detalhar subetapas e rotas paralelas.
3. Quando o objetivo for fluxo de valor, associar tempos de processamento e espera, demanda, estoques, recursos e fluxo de informação, preservando unidades e períodos de coleta.
4. Apresentar o estado atual e hipóteses de gargalo, retrabalho ou espera para conferência; não concluir gargalo apenas por uma etapa ter tempo alto sem considerar capacidade, demanda e paralelismo.
5. Construir um estado futuro proposto, registrar hipóteses e ações e comparar indicadores após a implementação.

**Insight possível:** uma etapa que exige cruzar quatro fontes pode ser detalhada em subetapas; se dados de filas e capacidade confirmarem acúmulo, a equipe pode investigar automação ou redistribuição de trabalho.

**Complemento de gargalos, apostila Yellow Belt, páginas 186–189:** comparar demanda e capacidade por recurso no mesmo período, considerando recursos paralelos, disponibilidade, paradas, tempos de troca, perdas e lotes. A fórmula `60 / minutos por unidade` representa capacidade teórica por hora para um recurso sob hipóteses simplificadas; maior tempo ou fila é indício a investigar, sem determinar sozinho o gargalo.

## SIPOC

**Fonte:** Yellow Belt 4.1 e apostila, páginas 76–78.

1. Definir o processo, suas fronteiras, início, fim e objetivo.
2. Registrar as principais etapas na ordem observada, sem exigir detalhamento de todas as tarefas.
3. Para cada etapa ou para o processo no nível escolhido, registrar fornecedores, entradas, saídas e clientes; permitir participantes internos e externos.
4. Ligar saídas às entradas correspondentes, identificar requisitos e confirmar os relacionamentos com as pessoas envolvidas.
5. Reutilizar etapas e participantes no mapa detalhado, no plano de medição e no FMEA, mantendo o usuário responsável pela validação.

**Insight possível:** destacar uma saída sem cliente identificado ou uma etapa sem fonte de entrada definida como questão para revisão, sem concluir automaticamente que existe falha.

## MSA: Gauge R&R cruzado por ANOVA

**Fonte:** Green Belt 14.1 e Black Belt 17, transcrições e quadros examinados.

1. Definir a característica, unidade, instrumento, resolução, operadores e condições. Selecionar peças que representem a faixa de variação de interesse.
2. Planejar medições repetidas das mesmas peças por cada operador, com sequência apropriada e sem acesso aos resultados anteriores. Registrar cada peça, operador, repetição e medida.
3. Verificar se o desenho é cruzado e balanceado e se a quantidade de peças, operadores e repetições permite o cálculo pretendido. Registrar exceções e limitações.
4. Ajustar ANOVA com peça, operador e interação; estimar repetibilidade, reprodutibilidade, variação entre peças e R&R total. Informar o modelo, a regra para componentes negativos e se a interação foi mantida ou agrupada.
5. Mostrar separadamente contribuição percentual de variância, percentual de variação do estudo, NDC e, quando aplicável, percentual da tolerância; não somar percentuais sobrepostos de variação do estudo.
6. Interpretar gráficos por peça e operador, médias, amplitudes e interações. Comparar indicadores com critérios definidos para a aplicação e investigar falhas antes de aprovar o uso.

**No código atual:** `crossed_grr` implementa o desenho balanceado e mantém a interação; falta ampliar rastreabilidade e apresentação conforme as anotações.

**Insight possível:** se a repetibilidade estimada for a maior fonte de variação do sistema, sugerir investigar instrumento e método; se houver evidência de diferenças entre operadores, investigar procedimento e condições. Esses padrões direcionam investigação e não identificam a causa sozinhos.

## DPMO

**Fonte:** Green Belt 20, transcrição integral e quadro da fórmula examinados.

1. Definir unidade inspecionada, o que conta como defeito e as oportunidades de defeito por unidade. Registrar período e população observada.
2. Contar os defeitos e calcular as oportunidades efetivamente inspecionadas. Se forem constantes: unidades × oportunidades por unidade. Se variarem, somar as oportunidades reais.
3. Calcular `DPMO = defeitos / oportunidades inspecionadas × 1.000.000`. Exemplo da aula: 36 / (30 × 43) × 1.000.000 ≈ 27.907.
4. Apresentar numerador, denominador e definição de oportunidade, distinguindo defeitos de unidades defeituosas. Qualquer conversão para nível sigma deve indicar a convenção e hipóteses utilizadas.
5. Avaliar representatividade, condições de coleta e incerteza; uma amostra pequena ou um período curto não comprovam estabilidade.

**Insight possível:** comparar DPMO entre linhas ou períodos quando unidade, critérios e oportunidades forem comparáveis, mostrando as contagens e destacando diferenças que merecem investigação.

## Capacidade de processo

**Fonte:** Green Belt 22 e artigo complementar sobre dados não normais consultado.

1. Registrar característica, unidade, limites de especificação, método de medição, sequência temporal e subgrupos.
2. Avaliar a estabilidade com gráfico apropriado e investigar sinais. Estudar a distribuição e verificar se os dados e o modelo são adequados; um teste de normalidade não significativo não comprova normalidade.
3. Distinguir variação dentro dos subgrupos e variação global. Com pressupostos adequados, apresentar Cp/Cpk para o estimador apropriado de curto prazo e Pp/Ppk para a variação global, identificando exatamente o estimador usado.
4. Com limites bilaterais, `Cp = (LSE − LIE) / (6σ)` e `Cpk = min((LSE − média)/(3σ), (média − LIE)/(3σ))`; adaptar o procedimento ao caso unilateral e não calcular um índice que exige limite ausente.
5. Para dados não normais, avaliar modelos e ajuste inclusive nas caudas e declarar o modelo empregado. Reportar contagem observada fora da especificação separadamente das estimativas modeladas.
6. Explicar que estabilidade e normalidade são questões distintas e que um índice isolado não garante zero defeitos. Validar os resultados contra casos de referência antes de uso operacional.

**No código atual:** há Pp/Ppk com desvio global; não renomear esses indicadores para Cp/Cpk sem implementar o estimador correspondente.

**Insight possível:** indicar qual limite está mais próximo da média e separar o efeito do deslocamento do centro e o da dispersão; apresentar contagem observada e condições necessárias para previsões.

## ANOVA de um fator

**Fonte:** Black Belt 20, transcrição e quadro examinados; a aula seguinte aborda a continuação.

1. Identificar resposta numérica, fator, níveis, unidade experimental, desenho e tamanho de cada grupo.
2. Examinar distribuição dos resíduos, variâncias por grupo, independência e características da coleta; registrar limitações.
3. Calcular a ANOVA adequada ao desenho e apresentar médias, diferenças, estatística, graus de liberdade, valor de p e medida de efeito com contexto.
4. Para comparações adicionais, escolher o procedimento adequado e considerar multiplicidade. Um teste não significativo não comprova que os grupos ou suas variâncias são iguais.
5. Interpretar associações com base no desenho; não afirmar causa só porque o teste apresentou significância.

**Insight possível:** mostrar grupos com médias e intervalos diferentes, quando a análise e as comparações forem apropriadas, e indicar quais condições devem ser verificadas antes de uma ação.

### Política do protótipo local (13/11/2026)

Para uma comparação exploratória de um fator, o protótipo usa Welch diretamente, não alterna entre F clássico e Welch conforme um pré-teste de Levene. Pré-testes podem alterar o erro tipo I do procedimento combinado; Levene (centrado na mediana) é exibido como diagnóstico, não como porta automática de decisão. Shapiro-Wilk é aplicado aos resíduos como outro sinal para revisão, sem tratar p>0,05 como prova de normalidade. O teste de Welch ainda exige observações independentes e não corrige dependência, viés de coleta, outliers influentes ou desenho experimental inadequado. O teste calcula comparação de médias por níveis observados; continua não sendo DOE formal nem evidência de causalidade.

Referências da implementação: [SciPy f_oneway — Welch e premissas](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.f_oneway.html), [SciPy Levene](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.levene.html), [SciPy Shapiro-Wilk — limite de interpretação do p-valor acima de N=5.000](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.shapiro.html) e [Zimmerman (2004), testes preliminares de igualdade de variâncias](https://doi.org/10.1348/000711004849222). O cálculo local é conferido contra `scipy.stats.f_oneway(equal_var=False)` quando essa opção existe na versão instalada.

### Pós-teste exploratório entre níveis

Para três ou mais níveis independentes, a versão local calcula cada contraste de médias com teste t de Welch, ajusta os p-valores pela etapa sequencial de Holm e calcula intervalos simultâneos bilaterais de 95% com Bonferroni. O relatório expõe a diferença, o intervalo, o p bruto e o p ajustado; Levene/Shapiro continuam diagnósticos. Este procedimento exploratório não substitui um plano de comparações definido antes da análise e pressupõe grupos independentes; não trata medidas repetidas, estrutura hierárquica, dependência nem confusão de fatores. Não está rotulado como Games-Howell.

Referências: [SciPy ttest_ind / Welch](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html) e [Holm (1979), procedimento sequencial para múltiplos testes](https://doi.org/10.2307/4615733).

## Testes de hipóteses para médias

**Fonte:** Green Belt 32, transcrição e quadro examinados.

1. Formular a pergunta, hipótese nula, alternativa, direção da diferença, nível de significância e tamanho de efeito importante para o negócio antes da análise.
2. Identificar uma amostra, duas amostras independentes ou pares vinculados. Confirmar unidade experimental, estratégia de coleta, dependência, distribuição das diferenças quando pertinente e dados ausentes.
3. Escolher teste e intervalo compatíveis com o desenho e com o conhecimento do desvio populacional; não selecionar Z automaticamente apenas porque a amostra tem 30 ou mais observações.
4. Exibir diferença estimada, unidade, intervalo, estatística, graus de liberdade quando aplicável, valor de p e premissas. Um p não significativo não comprova igualdade; p não é probabilidade de H0 ser verdadeira.
5. Relacionar o resultado à diferença relevante para o negócio, ao desenho e à incerteza. Uma diferença estatística não demonstra por si só causa, equivalência ou relevância prática.

**Insight possível:** se uma comparação de dois turnos independentes estimar diferença de tempo com intervalo que inclua valores relevantes para o processo, explicar a direção e a incerteza e sugerir investigar condições de coleta e fatores operacionais.

## Regressão múltipla

**Fonte:** Black Belt 23, transcrição e quadro examinados.

1. Definir a resposta, objetivo preditivo ou exploratório, unidade de observação, período e variáveis disponíveis no momento da decisão. Registrar como cada dado foi medido.
2. Examinar dados faltantes, relação entre variáveis, possível vazamento de informações futuras e dependência entre observações. Preservar os dados originais e documentar alterações.
3. Ajustar um modelo adequado ao tipo de resposta e ao desenho, verificar resíduos e colinearidade e avaliar o desempenho em dados separados ou novos, respeitando a ordem temporal quando necessário.
4. Apresentar coeficientes com unidades e incerteza, erros de previsão e faixa de aplicação. R² ajustado não é probabilidade de acerto; valor de p não mede sozinho a importância prática.
5. Investigar observações influentes sem excluí-las automaticamente; se houver exclusão justificada, registrar o motivo e comparar os resultados com e sem ela. Correlacionar variáveis não demonstra causalidade.

**Insight possível:** indicar que o tempo estimado de atendimento varia com a carga de pedidos em dados comparáveis e mostrar a faixa de incerteza, evitando afirmar que reduzir uma variável causará a melhoria sem desenho apropriado.

## DOE fatorial de dois níveis

**Fonte:** Black Belt 24, transcrição e quadro de interação examinados.

1. Definir objetivo, resposta e unidade experimental; escolher fatores controláveis, dois níveis viáveis e restrições do processo.
2. Escolher fatorial completo ou fracionado; registrar combinações, repetições, randomização, blocos e, se usados, pontos centrais. Em desenho fracionado, explicitar resolução e efeitos confundidos.
3. Executar e registrar os resultados vinculados à ordem efetiva, níveis reais, desvios e condições, sem substituir resultados ausentes por estimativas silenciosas.
4. Ajustar modelo compatível com o desenho; apresentar efeitos e interações identificáveis, intervalos, diagnóstico de resíduos e gráficos. Interação significa que o efeito de um fator depende do nível de outro.
5. Recomendar configurações dentro do domínio estudado e validar em novas execuções. Não representar o resumo de um fator já existente no protótipo como DOE fatorial completo.

**Insight possível:** quando um efeito de temperatura mudar conforme o nível de velocidade, apresentar o gráfico de interação e propor uma combinação para confirmação experimental.

## FMEA de processo

**Fonte:** Green Belt 41 e apostila Yellow Belt, páginas 207–218.

1. Definir equipe, processo e etapas; associar entradas e saídas já mapeadas.
2. Para cada função, registrar modos de falha, efeitos, severidade, causas e controles de prevenção e detecção. Permitir várias causas e efeitos por modo.
3. Registrar as escalas e atribuir severidade, ocorrência e detecção com justificativa. Na escala apresentada na aula, maior nota de detecção significa maior dificuldade de detectar.
4. Calcular o RPN quando esse método for aplicável; considerar severidade e contexto de risco além do produto.
5. Registrar ação, responsável, prazo e evidência; reavaliar as notas e manter histórico antes/depois. A severidade deve refletir o efeito efetivo; alterações precisam de justificativa.

**Insight possível:** destacar um modo de falha com severidade elevada e controle de detecção fraco, mesmo quando outro modo tiver produto RPN maior, explicando as notas e a justificativa.

## Controle estatístico de processo

**Fonte:** Green Belt 37 e 39, transcrições e quadros examinados.

1. Definir o indicador, unidade, período, frequência, ordem temporal e o tipo de dado; considerar tamanho e formação dos subgrupos.
2. Selecionar carta apropriada e estimar limites com dados de referência adequados. Identificar os limites de controle separadamente dos limites de especificação do cliente.
3. Em cartas X̄-R, examinar a variação dentro dos subgrupos e depois as médias. Exibir linha central, limites e regras de sinal utilizadas; investigar pontos e padrões sinalizados no contexto do processo. Informar janela e critérios de cada regra, sem considerar automaticamente que uma maioria de pontos no terço central seja sinal de instabilidade.
4. Registrar a investigação, responsável e reação. Não recalcular limites para esconder sinais e não interpretar cada flutuação como causa especial.
5. Acompanhar as ações e revisar o plano de controle quando houver mudança sustentada no processo.

**Insight possível:** após uma regra sinalizar um ponto, indicar o horário, a regra e os registros próximos para investigação, evitando afirmar automaticamente qual foi a causa.

## Desperdícios Lean e fluxo

**Fonte:** Yellow Belt 8, transcrição integral e quadro examinados.

1. Mapear etapas, responsáveis, entradas, saídas, tempos de trabalho e espera, filas, retrabalho e demanda, com período e unidade.
2. Sugerir categorias de desperdício conforme evidências; registrar hipóteses e permitir revisão pela equipe. Não presumir que todas as categorias existam.
3. Identificar atividades que agregam valor, as potencialmente desnecessárias e as necessárias ao processo; guardar justificativa, requisitos e riscos antes de propor mudanças.
4. Quando houver dados suficientes, comparar cenários de lote, fluxo unitário ou puxado, declarando capacidades, tempos, estoques e restrições. Os resultados dependem dessas premissas.
5. Definir ação e indicador de acompanhamento, preservando segurança, qualidade e requisitos aplicáveis.

**Insight possível:** destacar a etapa com maior espera medida por pedido e propor observar sua fila e capacidade; não inferir a causa apenas pelo tempo.

## Priorização por impacto e esforço

**Fonte:** apostila Yellow Belt, páginas 201–205 consultadas.

1. Identificar problema, indicadores e oportunidades ou hipóteses; relacionar cada item às evidências e às etapas pertinentes.
2. Definir com a equipe escalas e critérios de impacto, esforço e risco. Registrar participantes, fontes e justificativas de cada pontuação.
3. Exibir matriz e ordenação como apoio à decisão, distinguindo avaliações subjetivas de efeitos medidos. Nenhuma pontuação comprova causalidade.
4. Revisar restrições, dependências e requisitos antes de aprovar prioridades; documentar decisões e reavaliar quando surgirem novos dados.

**Insight possível:** destacar oportunidade avaliada como alto impacto e baixo esforço para análise da equipe, mostrando a justificativa e as incertezas da pontuação.

## Plano de controle e prevenção de erros

**Fonte:** apostila Yellow Belt, páginas 259–270 consultadas.

1. Para cada etapa e característica relevante, registrar requisito, unidade, método de medição, instrumento, amostra, frequência, responsável e fonte de dados.
2. Definir limites e critérios de reação aplicáveis, mantendo separados limites de controle e especificações. Associar cada sinal ou desvio ao procedimento e ao responsável pela investigação.
3. Registrar oportunidades de prevenção, detecção ou aviso para erros conhecidos; detalhar condição, resposta esperada e validação com a equipe antes da implantação.
4. Manter instruções acessíveis, versões, treinamento e evidências de revisão; acompanhar o indicador e investigar desvios e mudanças sustentadas.

**Insight possível:** apontar uma característica crítica sem método de controle ou sem responsável registrado e sugerir que a equipe complete o plano.

## 5S e plano de ação

**Fonte:** apostila Yellow Belt, páginas 222–253 consultadas.

1. Registrar área, equipe, condição observada e evidências; organizar oportunidades por utilização, organização, limpeza, padronização e sustentação, conforme o contexto.
2. Vincular cada ação ao problema e à hipótese ou evidência correspondente. Explicitar o que será feito, resultado esperado, responsável, prazo e condições de execução.
3. Acompanhar situação, impedimentos, mudanças de prazo e evidências de conclusão; manter histórico e participantes informados.
4. Medir o indicador antes e após a ação em períodos comparáveis e acompanhar a sustentação. A conclusão da tarefa ou uma comparação antes/depois, isoladamente, não comprova que a ação causou a mudança.

**Insight possível:** destacar ações vencidas ou concluídas sem evidência e sugerir revisão com o responsável; indicar indicadores sem acompanhamento após a implantação.

## Análise exploratória e boxplot

**Fonte:** apostila Yellow Belt, páginas 156–170 consultadas.

1. Identificar variável, unidade, período, população e dados ausentes; apresentar quantidade de observações e método usado no desvio padrão.
2. Exibir mediana, quartis e dispersão por grupo quando houver observações suficientes. Registrar o método de cálculo de quartis e a convenção dos bigodes do boxplot.
3. Destacar possíveis valores atípicos para investigação sem removê-los automaticamente. A regra de 1,5 vezes o intervalo interquartil é um critério de sinalização, que deve ser informado. Ao comparar grupos, considerar representatividade, períodos, tamanhos de amostra e contexto.
4. Cruzar a visualização com dados temporais e definição dos grupos para formular hipóteses; diferenças visuais não demonstram causalidade. Em dispersão, avaliar também padrões não lineares; correlação linear próxima de zero não descarta toda relação.

**Insight possível:** destacar um turno com maior dispersão observada e sugerir examinar condições e qualidade dos registros antes de concluir o motivo.

## Regressão linear simples

**Fonte:** Green Belt 31, transcrição integral e quadro examinados.

1. Definir preditor X, resposta Y, unidades, período e finalidade; examinar diagrama de dispersão, dados faltantes e condições de coleta.
2. Ajustar modelo apropriado, informar coeficientes, incerteza, faixa observada e diagnósticos de resíduos. Avaliar desempenho em dados separados ou novos quando a finalidade for previsão.
3. Investigar pontos influentes; preservar dados originais e não excluir observações apenas para melhorar R². Se houver exclusão justificada, apresentar análise de sensibilidade.
4. Distinguir estimativa média de previsão individual e seus intervalos. Não interpretar R² como taxa de acerto, associação como causa ou extrapolação como resultado validado.

**Insight possível:** estimar como a resposta muda com o preditor dentro da faixa estudada, mostrando incerteza e outras variáveis que podem ser relevantes.

## Projeto DMAIC com dados reutilizáveis

**Fonte:** Yellow Belt, apresentação do roadmap; transcrição integral e quadro examinados.

1. Manter cadastro único de projeto, problema, escopo, indicador, meta, equipe, etapas e evidências, com histórico e origem.
2. Reutilizar os mesmos dados em contrato, SIPOC, análises, planos e relatório; exibir alterações compartilhadas e preservar decisões anteriores.
3. Sugerir perguntas e ferramentas conforme os dados e o contexto, permitindo não aplicável, revisão e retorno entre fases.
4. Definir cada indicador com numerador, denominador, unidade, período, linha de base e meta; validar compatibilidade antes de comparar. Custo por ligação, por exemplo, usa custo total dividido pelo número de ligações.
5. Acompanhar ações, responsáveis e prazo e diferenciar progresso de preenchimento de melhoria demonstrada no processo.

**Insight possível:** indicar ausência de linha de base ou incompatibilidade entre períodos de meta e indicador e sugerir os dados que faltam para avaliação.

**Ponto de partida no código local:** `frontend/local/app.js` mantém arquivo, diagnóstico e análises em variáveis da página e prepara o relatório em `sessionStorage`; `sigmaflow/local_app.py` expõe as rotas locais de diagnóstico, seleção de planilha e análises. Portanto, para reutilização entre sessões e ferramentas será necessário projetar persistência de projeto e referências compartilhadas, além de incluir identificador de projeto e versão de dados nas operações. Essa é uma proposta, ainda não implementada; antes de escolher a solução de armazenamento, avaliar também os componentes existentes da API principal.

## Cartas de controle por atributos

**Fonte:** Green Belt 40, transcrição integral e quadro examinados.

1. Definir unidade, período, critério de não conformidade e se os dados são unidades não conformes ou número de defeitos; guardar contagem e exposição por amostra.
2. Para unidades não conformes, avaliar carta np com tamanho constante ou p para proporção com tamanho variável; para contagem de não conformidades, avaliar c com oportunidade constante ou u para taxa por unidade.
3. Verificar premissas, tamanho das amostras, independência, exposição e possível sobredispersão. Definir linha de base, limites e regras, e documentar o método.
4. Apresentar a carta e sinais, diferenciando limites de controle de especificações. Variação entre pontos, isoladamente, não prova instabilidade; investigar sinais no contexto antes de intervir.

**Insight possível:** apontar lote com sinal e apresentar número inspecionado, quantidade não conforme, proporção e regra acionada para investigação.

## Complemento de ANOVA: comparações múltiplas

**Fonte: Black Belt 21.** Apresentar tabela de somas de quadrados, graus de liberdade, quadrados médios e F; escolher comparações múltiplas conforme pergunta e desenho. Resultados não significativos ou letras compartilhadas não comprovam igualdade. Um intervalo para diferença de médias que inclua zero não implica variância nula nem demonstra equivalência.

## Complemento de R&R: resolução e discriminação

**Fonte:** Green Belt 14, transcrição integral e quadro examinados.

Registrar identificação de peça, operador, repetição, ordem e valor; avaliar o desenho e mostrar repetibilidade, reprodutibilidade, componente entre peças e NDC com fórmulas e pressupostos. A resolução do instrumento e a quantidade de divisões em uma faixa não equivalem automaticamente ao NDC estimado por R&R. Separar percentual de contribuição de variância e percentual da variação do estudo; a aceitação depende do critério escolhido, da aplicação e do risco.

**Insight possível:** quando o componente de repetibilidade for elevado em relação à variação observada, sugerir investigar instrumento e método de medição, preservando a incerteza e o contexto do estudo.

## DOE com três níveis

**Fonte:** Black Belt 25, transcrição integral e quadro examinados.

1. Definir resposta, objetivo, fatores, três níveis viáveis e limitações. Informar que um fatorial completo com quatro fatores em três níveis exige 81 combinações antes das réplicas.
2. Selecionar desenho e termos estimáveis conforme orçamento e objetivo; registrar réplicas, blocos, aleatorização e ordem real, além de eventuais efeitos confundidos.
3. Coletar resultados associados a cada ensaio e ajustar modelo compatível, incluindo interação ou curvatura quando o desenho as permitir e forem pertinentes.
4. Examinar resíduos e incerteza; R² ajustado alto não valida previsão. Avaliar interações com estimativas e gráficos, sem exigir que linhas se cruzem.
5. Otimizar dentro das condições estudadas e recomendar ensaios de confirmação. Informar limites, incerteza e restrições da sugestão.

**Insight possível:** apresentar configuração candidata próxima ao alvo, com faixa de incerteza e confirmação experimental antes da aplicação.

## Experimento Taguchi e robustez

**Fonte:** Black Belt 26, transcrição integral e quadro examinados.

1. Definir resposta, alvo ou direção desejada, restrições e fatores controláveis e de ruído; identificar se existe fator de sinal e se a resposta é estática ou dinâmica.
2. Planejar um arranjo adequado com níveis, repetições e condições de ruído. Registrar ordem, aleatorização viável, efeitos confundidos e interações identificáveis.
3. Coletar respostas com vínculo aos ensaios e condições reais. Selecionar e documentar a fórmula da razão sinal/ruído adequada ao objetivo e ao domínio dos dados; não assumir que uma fórmula serve para todos os casos.
4. Apresentar efeitos estimados, média, variabilidade, interação e limitações do desenho. Comparar configurações dentro da faixa estudada e confirmar a escolhida em novas execuções.

**Insight possível:** identificar configuração candidata que mantenha resposta próxima ao alvo sob temperaturas estudadas, com sua variabilidade e recomendação de confirmação experimental.

## Comparação de variâncias

**Fonte:** Black Belt 22, transcrição integral e quadro examinados.

1. Definir característica, unidades, grupos e desenho de coleta; verificar independência, dados ausentes e condições.
2. Exibir dados individuais e resumo de dispersão. Escolher comparação compatível com distribuição, desenho e objetivo; registrar premissas e limitações.
3. Apresentar estimativa da diferença ou razão, intervalo e teste pertinente. Um p não significativo ou sobreposição visual não comprovam igualdade.
4. Comparar a incerteza com o efeito relevante para o negócio. Não selecionar método pelo maior p-valor nem exigir automaticamente igualdade de variâncias para toda comparação de médias.

**Insight possível:** se a incerteza da razão de dispersões entre máquinas incluir diferenças relevantes, sugerir coleta adicional e investigar condições de operação.

## Cartas para observações individuais e pequenos lotes

**Fonte:** Black Belt 33, transcrição integral e quadro examinados.

Para observações individuais ordenadas, considerar carta I-AM e analisar a variação móvel junto dos valores individuais. Para pequenos lotes de produtos diferentes, avaliar carta apropriada e documentar padronização, referências e incerteza dos limites. Amplitude positiva não é, por si, sinal de instabilidade; limites de controle não são limites de especificação. Identificar data, produto, regra e valor de cada sinal para investigação contextual.

**Planejamento do CEP, Black Belt 32:** vincular requisito confirmado, característica, etapa, método de medição e frequência à carta adequada; guardar linha de base, regras de sinal, responsáveis, plano de reação, ocorrências e intervenções. Compartilhar a carta com a equipe e registrar a investigação dos sinais. A carta apoia decisões, mas não identifica automaticamente a causa nem garante melhoria.

## Concordância por atributos

**Fonte:** Green Belt 16, transcrição integral e quadro examinados.

1. Definir o uso da inspeção e as categorias nominais ou ordinais. Selecionar amostras representativas e registrar o padrão de referência quando existir e for confiável.
2. Planejar avaliações repetidas, preferencialmente aleatórias e cegas quando adequadas, registrando amostra, avaliador, repetição, resultado e referência.
3. Calcular separadamente concordância dentro de cada avaliador, entre avaliadores e com a referência. Escolher estatísticas adequadas ao desenho e às categorias; documentar o tratamento de avaliações ausentes e categorias raras.
4. Apresentar percentuais, matrizes de confusão, coeficientes aplicáveis e incerteza; comparar com critérios definidos para o uso. Um valor de p pequeno não demonstra concordância suficiente e consistência sem referência não demonstra exatidão.
5. Investigar divergências com a equipe e revisar critérios, instrumentos ou treinamento; repetir a avaliação para acompanhar mudanças.

**Insight possível:** mostrar quais classes foram mais confundidas com o padrão e sugerir revisar exemplos e critérios dessas classes.

## Qui-quadrado de independência

**Fonte:** Black Belt 28, transcrição integral e quadro examinados.

1. Definir pergunta, unidade de observação, categorias e população; verificar independência das observações e tratamento de registros ausentes.
2. Construir tabela de contingência com contagens observadas e esperadas sob independência. Avaliar se a aproximação do teste é adequada; para dados esparsos, selecionar método apropriado ao desenho.
3. Apresentar estatística, graus de liberdade, valor de p, tamanho de efeito adequado e frequências; registrar nível de significância e múltiplas comparações quando houver.
4. P pequeno indica evidência contra independência sob as hipóteses do teste; p alto não comprova independência. Não interpretar associação como causa ou previsão certa de resultado individual.

**Insight possível:** se houver evidência adequada de associação entre turno e tipo de defeito, mostrar as frequências por turno e sugerir investigar diferenças operacionais, mantendo outras explicações em aberto.

## Pareto

**Fonte:** Green Belt 28, transcrição integral e quadro examinados.

1. Definir população, período, categoria e medida: contagem, custo ou tempo perdido, com unidade e denominador quando necessário.
2. Somar por categoria, ordenar de forma decrescente e calcular participação e percentual acumulado. Exibir barras e linha acumulada, com tabela acessível e indicação de dados faltantes.
3. Permitir configurar e expandir o agrupamento outros; mostrar os critérios de agrupamento. Aplicar desdobramento apenas quando existirem dados da categoria selecionada.
4. Comparar períodos com exposição, categorias, unidades e escalas comparáveis. Informar mudanças na coleta e não atribuir melhora a uma ação somente pela comparação antes/depois.
5. Apresentar concentração real, sem presumir 80/20, e evitar chamar categorias de causas comprovadas. Priorizar também considerando impacto, risco e viabilidade.

**Insight possível:** informar que duas categorias representam determinada parcela das horas de parada registradas e sugerir detalhá-las por máquina e turno, se os dados existirem.

## Ishikawa e cinco porquês

**Fontes:** Green Belt 26 e 27, transcrições integrais e quadros examinados.

1. Definir um problema observável, com indicador, período e etapa do processo. Registrar a equipe que participa da investigação.
2. Organizar hipóteses de causa em categorias pertinentes e permitir subcausas; sugerir os 6 Ms quando fizerem sentido, sem obrigá-los em todos os processos.
3. Aprofundar cada hipótese com perguntas sucessivas, permitindo ramificações e diferentes quantidades de perguntas. Registrar como cada elo foi estabelecido.
4. Para cada hipótese, registrar evidências a favor e contra, fonte, data, responsável, fatores alternativos e lacunas; oferecer sugestões de dados e análises adequadas.
5. Acompanhar validação e ações e preservar histórico. Uma resposta, correlação ou sequência de perguntas não demonstra por si só causalidade nem identifica necessariamente a causa principal.

**Insight possível:** se faltarem registros de manutenção em períodos com paradas frequentes, sugerir cruzar eventos e condições operacionais e verificar outras causas antes de atribuir o problema à manutenção.

## Referências técnicas para conferir a implementação

### Nível sigma para tempo de espera e dados não normais

**Fontes:** Green Belt 21 e 21.1, transcrições integrais e quadros dos relatórios examinados.

- Pedir a meta definida pelo cliente e sua unidade. Um limite físico, como zero minuto de espera, não é automaticamente um limite inferior de especificação; confirmar se existe um requisito inferior antes de incluí-lo nos cálculos.
- Mostrar a contagem e o percentual observados acima da meta separados de PPM e níveis sigma estimados a partir de um modelo. Identificar claramente a distribuição, o estimador de dispersão e qualquer convenção de deslocamento sigma.
- Não concluir que os dados seguem distribuição normal somente porque o teste de normalidade não rejeitou a hipótese. Considerar gráfico, tamanho da amostra e adequação nas caudas.
- Solicitar como os subgrupos foram formados e verificar estabilidade: a existência de subgrupos, por si só, não assegura ausência de causas especiais. Diferenças entre dispersões global e dentro dos subgrupos sugerem investigação, sem identificar a causa automaticamente.
- **Insight possível:** informar quantos atendimentos ultrapassaram a meta e em quais períodos se concentram; propor investigação da carga e das condições nesses períodos, sem atribuir causalidade apenas pela coincidência.
- Para distribuições não normais, comparar modelos plausíveis considerando suporte, gráficos e ajuste nas caudas; não selecionar automaticamente aquele com maior p-valor. Apresentar sensibilidade e incerteza das estimativas. A não normalidade não demonstra instabilidade e o teorema central do limite não normaliza as medições individuais.

- [NIST — limites de controle e de especificação](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc32.htm).
- [NIST — avaliação de estabilidade do processo](https://www.itl.nist.gov/div898/handbook/ppc/section4/ppc45.htm).
- [NIST — inspeção de resíduos em modelos de experimento](https://www.itl.nist.gov/div898/handbook/pri/section2/pri24.htm).
- [NIST — terminologia de DOE e efeitos confundidos](https://www.itl.nist.gov/div898/handbook/pri/section7/pri7.htm).
- [NIST — análise de repetibilidade de medição](https://www.itl.nist.gov/div898/handbook/mpc/section4/mpc441.htm).

## Roadmap DMAIC para o SigmaFlow

**Base estudada:** aula Green Belt 0.1 e arquivo complementar Roadmap_LSS_X1.xlsm. A planilha organiza métodos por fase, distingue obrigatório e opcional, registra perguntas-chave Sim/Não, atividades com datas e evidências, e calcula estado no dashboard.

- Tratar Definir, Medir, Analisar, Melhorar e Controlar como marcos com objetivo e critérios de saída, não como etapas de interface imutáveis. Ex.: Medir estabiliza definições, sistema de medição e baseline antes de interpretar; Analisar transforma causas potenciais em hipóteses validadas; Melhorar liga ações a causas; Controlar monitora resultado e sustenta a mudança.
- Representar requisitos por fase de modo explícito: ferramenta obrigatória concluída, pergunta-chave obrigatória respondida/atendida, percentual de atividades e evidência. “Ferramenta utilizada” registra execução, não a validade dos resultados. Opcional pode ser recomendada automaticamente quando os dados/caso justificarem; exibir justificativa e permitir decisão do Belt.
- Fazer sugestões adaptativas a partir do problema, indicador, unidade, tipo de coluna e qualidade dos dados. Cada sugestão inclui para que serve, pré-requisitos, evidência usada na recomendação e limitações; aceitar/dispensar com motivo é decisão registrada pelo usuário.
- Anexar artefatos versionados (dados, gráficos, mapas, aprovações e notas) à análise, método, atividade e fase. Compartilhar os dados mestre do projeto entre telas, evitando recadastro. Cronograma permite novas atividades, datas planejadas/reais e status; tarefas futuras ficam distintas de análises concluídas.
- Permitir iterações e retorno controlado. Se a meta não for atingida, reabrir investigação/Analisar, preservar a análise anterior e registrar razão, aprendizado e nova hipótese. Fluxo mostra fase atual como estado derivado dos critérios, com eventual override documentado, e não como sequência automática irreversível.
- Não deixar que dashboard ou percentual substitua revisão metodológica, validação do indicador, análise estatística e aprovação do responsável. A interface deve explicar exatamente o que falta para um gate e a fonte de cada requisito.

### Dados compartilhados e fase Definir

**Base adicional:** Green Belt 11.1, com transcrição integral e quadros revisados.

- O contrato nasce como rascunho e recebe dados do SIPOC, equipe, VOC/VOB e indicador. Armazenar uma referência comum para cada informação; uma alteração deve atualizar as telas que a consultam, preservando as versões usadas em relatórios anteriores.
- Manter nome, definição operacional, fórmula, unidade, direção desejada, população/denominador, fonte, período, baseline e meta como partes explícitas do indicador. Custos e cumprimento de prazo podem estar relacionados, mas não são intercambiáveis.
- Sugerir requisitos e representantes com origem identificada, permitindo confirmação e edição. Nomes de colunas não bastam para comprovar CTQ, construir SIPOC ou decidir envolvimento de pessoas.
- Expor os campos existentes de `Project` antes de criar cadastros paralelos; registrar separadamente execução, evidências, revisão e aprovação.

### Da hipótese à ação

**Base adicional:** Green Belt 32.6, com revisão integral, quadros e notas do subagente conferidas.

- Encadear observação estratificada, causa potencial, cadeia de porquês, hipótese consolidada, prioridade, análise e ação. Preservar ramificações e convergências; deduplicar sem apagar a origem.
- Distinguir hipótese candidata, decisão de priorizar/adiar e resultado validado/refutado/inconclusivo. A nota de relação atribuída pela equipe não é correlação estatística; total ponderado não comprova causalidade.
- Diferenciar zero avaliado de relação não avaliada. Guardar escala, pesos, justificativa e autor. A fração de causas priorizadas não representa a fração do impacto real do projeto.
- Manter causas e ações adiadas no histórico para nova iteração se a meta não for atingida. Um método sugerido só gera resultado após sua execução com dados e pressupostos apropriados.

### Indicador operacional e benefício econômico

**Base adicional:** Green Belt 32.7; divergências e fontes externas estão registradas no acompanhamento do estudo.

- Separar referência, projeção e realizado, com unidades, exposição/volume, calendário, custos unitários, investimento e custos recorrentes. Mostrar a memória de cálculo e a origem de cada premissa.
- Separar capacidade liberada, custo evitado, economia contábil/caixa e receita incremental. Categoria do benefício e confiança na atribuição são dimensões diferentes; impedir dupla contagem entre iniciativas.
- Guardar realização informada, evidência e validação de Finanças em campos distintos. Anualização permanece uma projeção até haver observação e conciliação do período.
- Validar coerência algébrica: numerador/denominador, direção, unidade, pontos percentuais e variação relativa. Não transportar o mesmo percentual de mudança de eficiência para a redução de paradas sem derivar a fórmula.
- EBITDA e margem EBITDA são métricas diferentes; classificação de gastos depende da política aplicável e de revisão contábil. Referências: [CVM 156](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/100/resol156.pdf) e [CPC 27 consolidado na CVM 73](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/001/resol073.pdf).

### Planejar, implantar e verificar ações

**Base adicional:** Green Belt 36.1, transcrição integral, 18 quadros e estrutura do workbook.

- Compartilhar as mesmas ações entre tabela, matriz esforço/impacto/risco, cronograma, evidências e relatório. As quatro ferramentas da aula podem avançar conforme suas dependências; não há sequência única de telas.
- Reusar `ActionItem` em `sigmaflow/core/models.py`: já possui vínculos a projeto, execução e insight, responsável, datas, evidências e verificação. Ampliar a ligação com hipótese/causa, critérios de risco e plano de validação; revisar os campos expostos na API.
- Separar planejamento aprovado, implantação executada e eficácia verificada. Um responsável final pode ter vários colaboradores; data final da implantação não encerra a rotina recorrente que ela criou.
- Escores de esforço e impacto e categorias de risco são julgamentos com critérios explícitos. A sugestão de três alternativas por causa e os cortes da matriz são heurísticas do curso; não impor números universais. Conservar ações canceladas/adiadas e seus motivos sem contá-las como entrega.
- Comparar mapa atual/futuro e planejar a medição antes do piloto. Um boxplot ilustrativo, uma foto ou aprovação apoiam a documentação, mas não substituem verificação quantitativa reproduzível quando cabível.
- Revisar recomendações observacionais em `sigmaflow/dmaic/improve/phase.py`: associação ou melhor quintil não comprova que controlar um fator produzirá o resultado. Confirmar objetivo e restrições e levar a hipótese para validação.

### Sustentação e comparação em Controlar

**Base adicional:** Green Belt 43.1, com revisão integral, quadros e workbook.

- Conectar controle a processo, causa/hipótese, ação, indicador, fonte, desenho de amostragem, frequência, responsável e plano de reação. O encerramento formal não encerra necessariamente o acompanhamento.
- Separar limites de especificação, parâmetros de reação/negócio e limites estatísticos de controle; registrar tipo, origem e versão de cada faixa.
- Antes de comparar capacidade, conferir versões dos requisitos, população, medição, unidades, períodos e estabilidade. Se os limites mudarem, explicar a diferença e produzir comparação sob critérios consistentes. O exemplo do curso apresenta média e desvios iguais nos dois painéis, mas amplia as especificações; não demonstra melhoria da distribuição.
- Guardar lições aprendidas e reabrir a investigação quando a ação não produzir o resultado esperado, conservando a análise anterior e a justificativa da nova iteração.

### SWOT como diagnóstico estratégico contextual

**Base adicional:** Black Belt 2 e 2.1, transcrições integrais e inspeção de quadros.

- Começar pelo objetivo/indicador estratégico e selecionar fontes de informação adequadas ao tema. Clientes ajudam a entender vendas/aceitação; equipe e donos de processo informam capacidade, restrições e custos; stakeholders ampliam o contexto.
- Distinguir fatores internos (forças/fraquezas) e externos (oportunidades/ameaças). Perguntas de aplicação podem explorar alinhamento à estratégia, perspectiva do cliente, capacidade, custo/prazo, concorrência e tempo de resposta.
- Tratar fatores como evidência qualitativa discutível. Registrar fonte, contexto, data, responsável e divergências; compartilhar e revisar com equipe/liderança. Ausência de registro não prova ausência do fator.
- Usar cruzamentos da matriz para gerar opções e hipóteses, sem convertê-los em causa-raiz, previsão validada, prioridade estatística ou saving. Medir depois efeitos de cliente/processo e validar relações com métodos DMAIC apropriados.
- No SigmaFlow, SWOT é uma ferramenta optativa de enquadramento estratégico. Deve ligar fatores a objetivos, riscos, stakeholders e ações, preservando a origem e o estado da evidência. Não deve ser etapa mandatória de todo diagnóstico operacional.

### Planejamento por gerações (MGPP)

**Base adicional:** Black Belt 4, transcrição integral e três quadros.

- Usar quando escopo, investimentos ou ideias concorrentes tornam o projeto grande demais para um primeiro ciclo gerenciável. Particionar por gerações mantém uma visão macro enquanto explicita o que será feito agora e o que fica para depois.
- Registrar visão/objetivo, gerações de processo, plataformas/tecnologias, dependências, horizonte, capacidade e pressupostos. Construir com equipe e revisar à medida que o projeto evolui.
- Versionar alterações e preservar backlog futuro. Gerenciar cada geração com limites claros; não misturar geração com fase DMAIC. Separar metas e benefícios planejados de resultados medidos e validados.
- No SigmaFlow, oferecer essa estrutura quando útil ao contexto, preservando histórico e comparação previsto/realizado sem somar benefícios futuros como ganhos realizados.

### Balanced Scorecard e ligação com projetos DMAIC

**Base adicional:** Black Belt 3, transcrição integral, 51 segmentos e quadros das perspectivas.

- Usar BSC para comunicar como objetivos e indicadores conectam estratégia e atividades. As perspectivas apresentadas são Financeira, Clientes, Processos Internos e Aprendizado & Crescimento; exemplos devem se adaptar à estratégia e ao ciclo de vida da organização.
- Relacionar objetivos, indicadores, metas, donos e fonte de dados. Preservar o mapa estratégico/scorecard separado do projeto DMAIC, conectando-os por vínculos explícitos.
- Tratar relações entre perspectivas como hipóteses estratégicas, não prova causal. Acompanhar indicadores de equilíbrio para evitar que uma meta local (por exemplo, cortar custo) prejudique qualidade, prazo, segurança ou cliente.
- O curso não define fórmulas, pesos, cadências universais ou testes causais do BSC. Não inventar esses critérios no produto; tornar configurações visíveis e pedir confirmação.

### Gestão de stakeholders

**Base adicional:** Black Belt 5, transcrição integral e quadros de avaliação e comunicação.

- Identificar quem influencia ou é afetado pelo escopo; distinguir impacto do stakeholder no projeto, impacto do projeto na pessoa/grupo e posição declarada sobre a iniciativa.
- Usar estratégias de comunicação, participação, visibilidade, aliados e conversa sincera. O plano de aula guarda audiência, mídia/canal, propósito, tópicos, frequência e notas/status.
- A pontuação multiplicativa mostrada é heurística, não probabilidade ou avaliação objetiva de caráter. No produto, deixar critério, fonte e autor visíveis; manter notas individuais restritas e revisáveis; ausência de resposta não prova oposição.
- Relacionar stakeholders a VOC, requisitos, riscos, decisões e ações, sem transformar opinião em causa-raiz ou conclusão automática.

### Matriz RACI

**Base adicional:** Black Belt 6, transcrição integral e três quadros.

- Por atividade, atribuir R (executa), A (Avalista/aprova e verifica, na terminologia do curso), C (consultado antes, com troca bidirecional) e I (informado depois). O slide pede um A por tarefa e admite R múltiplos; clarificar a divisão.
- Configurar atividades e papéis para o projeto; sinalizar ausências/duplicidades para revisão. Papéis devem estar ligados a pessoas/funções e decisões conforme contexto, não a colunas fixas.
- Separar responsabilidade atribuída de estado, aprovação formal e evidência de execução. RACI reduz confusão, mas não demonstra trabalho executado ou qualidade.

### Gerenciamento do projeto e desenvolvimento de equipes

**Base adicional:** Black Belt 7, transcrição integral e quadros.

- Tratar o Black Belt como integrador do projeto: coordenar áreas, delegar, acompanhar dependências e recursos e obter decisões das autoridades adequadas. Não centralizar todo o conhecimento ou execução no líder.
- Registrar dedicação estimada, papéis e disponibilidade em contexto; pessoas podem participar de vários projetos. As cargas full-time/part-time citadas são exemplo didático, não padrão obrigatório.
- Acompanhar as cinco etapas mostradas (formação, confusão, normalização, performance, realização) como linguagem de facilitação e reflexão da equipe, não como avaliação psicológica ou sequência garantida.

### Liderança e aprendizagem da equipe

**Base adicional:** Black Belt 10, transcrição integral e quadro Saber/Fazer.

- Tratar liderança como comportamento situado e desenvolvimento contínuo, não título de cargo. Facilitar, comunicar, compartilhar conhecimento e combinar responsabilidades com a equipe.
- A matriz Saber/Fazer da aula é uma reflexão conceitual, sem escala validada. No produto, se usada, manter como autoavaliação opcional para orientar aprendizagem, sem ranking de pessoas.
- Registrar combinados, decisões e necessidades de apoio com acesso controlado. Privacidade de equipe não elimina encaminhamentos obrigatórios de segurança/compliance.

### Janela de Johari e coaching

**Base adicional:** Black Belt 11, transcrição integral e seis quadros.

- Usar os quadrantes aberto, cego, oculto e desconhecido como linguagem de reflexão sobre percepção/comunicação. Confirmar os eixos pelo material visual quando a transcrição estiver inconsistente.
- Feedback pode ser estruturado por pergunta específica, exemplo observável, resposta voluntária e ação combinada. Não tratar percepção de colegas como fato objetivo.
- Manter privacidade e consentimento para autorrevelação; questionários e quadrantes da aula não são escalas psicológicas validadas. Não inferir potencial, emoção ou desempenho por algoritmo.

### Plano de Comunicação

**Base adicional:** Black Belt 8 (conteúdo do arquivo nomeado Plano de Ação), transcrição integral e quadros.

- Separar plano de comunicação de plano de ação de melhoria. Por público ou marco, registrar audiência, canal, propósito, mensagem, ação/feedback esperado, responsável, frequência e status.
- Usar comunicação clara, atualizada, formal o suficiente ao contexto e com ciclo de feedback. Acompanhar se funcionou; mensagem enviada não prova compreensão ou eficácia.
- Deixar canal e cadência configuráveis. O curso não fornece fórmula universal de frequência, escala de eficácia ou limiar de sucesso.

### Formação da equipe do projeto

**Base adicional:** Black Belt 9, transcrição integral e sete quadros.

- Selecionar participantes pelas necessidades do problema/processo e pelo conhecimento/competências requeridos; permitir núcleo, especialistas por etapa e participação parcial. A referência de 4–8 pessoas varia conforme escopo.
- Tratar os papéis Belbin como roteiro opcional para discutir contribuições que faltam e tensões possíveis; não inferir personalidade nem selecionar pessoas automaticamente.
- Separar qualidade técnica da solução de aceitação e viabilidade de implementação. Não usar métricas de atividade como ranking individual sem avaliar incentivos perversos.


## Lideran?a situacional e estilos E1?E4

A aula Black Belt 12 apresenta estilos como combina??o de dire??o da tarefa e apoio: E1 dire??o, E2 treinamento, E3 apoio, E4 delega??o. Use como roteiro de conversa ajustado ? tarefa e ? situa??o, acompanhando mudan?as de capacidade e seguran?a. O conte?do n?o valida uma escala psicom?trica. No SigmaFlow, qualquer sugest?o deve ser revis?vel pelo l?der, baseada em evid?ncias observ?veis e separada de avalia??o de desempenho. Ver [nota da aula 12](../aulas_local/Black%20Belt%20-%20Aula%2012%20-%20Estilo%20de%20Lideranca%20-%20Revisao%20SigmaFlow.md).


## Viabilidade econ?mica e indicadores financeiros

A aula Black Belt 14 aborda ROI, ROIC, payback, VPL e TIR. Para qualquer c?lculo, guardar defini??o/f?rmula, fluxo, moeda, per?odo, TMA, conven??o de taxa, premissas e respons?vel financeiro. A aula cont?m uma diverg?ncia entre a f?rmula ROI no slide e o exemplo falado, portanto o SigmaFlow deve exigir uma defini??o revisada por Finan?as. Exibir cen?rio previsto, benef?cio aprovado e realizado separadamente; indicadores n?o provam causalidade. Ver [nota da aula 14](../aulas_local/Black%20Belt%20-%20Aula%2014%20-%20Gerenciamento%20de%20Custos%20-%20Revisao%20SigmaFlow.md).


## Custo de estoque, oportunidade e an?lise de valor

A aula Black Belt 15 decomp?e custo de estoque em pedido/aquisi??o, manuten??o/armazenagem e falta; o alvo ? equilibrar estoque com demanda e n?vel de servi?o. Custo de oportunidade compara a melhor alternativa abandonada. An?lise de valor examina fun??es e custos sem comprometer seguran?a, qualidade ou conformidade. Os exemplos de taxa da aula s?o hist?ricos e uma composi??o fica amb?gua; documentar fonte, per?odo e premissas financeiras. Ver [nota da aula 15](../aulas_local/Black%20Belt%20-%20Aula%2015%20-%20Estudo%20de%20Viabilidade%20-%20Revisao%20SigmaFlow.md).


## Prepara??o de dados e escolha assistida de an?lise

A aula Black Belt 16 demonstra Minitab 19: worksheet, tipos num?rico/texto/data, histograma e um Assistente que conduz op??es conforme objetivo e tipo de dado. A ferramenta pode orientar a busca, mas n?o substitui requisitos de amostragem, MSA, pressupostos e defini??o de especifica??es. A aula s? anuncia capacidade, controle, regress?o e experimentos; cada m?todo exige estudo e revis?o espec?ficos. Ver [nota da aula 16](../aulas_local/Black%20Belt%20-%20Aula%2016%20-%20Minitab%20-%20Revisao%20SigmaFlow.md).


## Desenho de base para estudos de medi??o

A aula Black Belt 17.2 cria uma worksheet 5 amostras ? 3 operadores ? 3 r?plicas no Minitab e registra dist?ncia da catapulta. Por?m, o menu demonstrado ? para concord?ncia de atributos, incompat?vel em princ?pio com resposta cont?nua; confirmar o objetivo e selecionar o desenho correto. A sequ?ncia sem aleatoriza??o ? espec?fica ao simulador e pode confundir ordem/tempo em estudos reais. Ver [nota da aula 17.2](../aulas_local/Black%20Belt%20-%20Aula%2017.2%20-%20Construcao%20de%20Base%20Minitab%20-%20Revisao%20SigmaFlow.md).

## Dados não normais: investigação, distribuição e transformação

**Base adicional:** Black Belt 18, transcrição integral e oito quadros. Ver [nota da aula 18](../aulas_local/Black%20Belt%20-%20Aula%2018%20-%20Revisao%20Dados%20Nao%20Normais%20SigmaFlow.md).

- Antes de transformar, conferir definições, plano/tamanho amostral, ordem temporal, causas especiais e sistema de medição. Não apagar observações; documentar qualquer análise separada e preservar a série original.
- Escolher com conhecimento do processo entre modelo não normal, transformação validada e método não paramétrico. Box-Cox (potência λ) exige valores positivos; Johnson é mais flexível. λ não tem relação com parâmetro de Poisson. Comparar ajuste, premissas e interpretabilidade; não escolher só pelo maior p-valor.
- Capacidade depende de processo estável, especificações e distribuição apropriada. A transformação apenas muda escala/modelo e não melhora qualidade/estabilidade automaticamente. Interpretar resultados na escala transformada e registrar retorno para unidades originais.
- No SigmaFlow, manter originais imutáveis, salvar colunas derivadas e parâmetros, mostrar opções com limitações e pedir revisão técnica antes de conclusão de capacidade.


## Box-Cox: exerc?cio referenciado pela aula 19

A p?gina BB 19 remete ao Quiz 4 do Green Belt e ao Arquivo 29 Controle de Pigmento para um exerc?cio Box-Cox, sem instru??es t?cnicas detalhadas. Vincular dados originais, ?/f?rmula, diagn?sticos e interpreta??o ? escala original; consultar a nota da aula 18 para limites de transforma??o. A m?dia local desta entrada tem apenas 6s com quadro preto. Ver [registro da p?gina 19](../aulas_local/Black%20Belt%20-%20Aula%2019%20-%20Registro%20da%20Pagina%20e%20Exercicio%20Box%20Cox.md).

## Transformações Box-Cox e Johnson: uso e limites

**Base adicional:** Black Belt 18 e 18.1, transcrições integrais e quadros. Ver [nota de transformação da aula 18.1](../aulas_local/Black%20Belt%20-%20Aula%2018.1%20-%20Revisao%20Transformacoes%20Minitab%20SigmaFlow.md).

- Primeiro investigar causas especiais, estabilidade, plano amostral e sistema de medição; não eliminar pontos automaticamente. Uma transformação não corrige mudança, mistura ou instabilidade do processo.
- Box-Cox aplica uma transformação de potência controlada por λ; λ não é o parâmetro da distribuição de Poisson. Box-Cox exige dados positivos nos procedimentos Minitab descritos. Johnson é alternativa mais flexível. Registrar método, parâmetros e dados derivados sem sobrescrever originais.
- Avaliar ajuste e contexto do processo. Não escolher apenas pelo maior p-valor e não apresentar transformação como normalização/comprovação de melhoria. Para capacidade, considerar distribuição não normal ou método não paramétrico e verificar estabilidade/especificações.
- O SigmaFlow deve mostrar métodos candidatos, estatísticas de ajuste e limites, em escalas original e transformada; a seleção e conclusão requerem julgamento técnico.

## Exercício de transformação e CEP: divergência de subgrupos

A aula Black Belt 19.1 aplica Box-Cox/Johnson ao exemplo de pigmento e depois mostra capacidade e cartas Xbarra-R. A identificação de distribuição usa subgrupos de 5, mas os diálogos de capacidade/CEP exibem tamanho 2; o gráfico ainda informa tamanhos amostrais desiguais. Confirmar o plano de coleta e o subgrupo racional antes de aceitar a carta ou capacidade. Um sinal na carta R é em relação aos limites de controle, não às especificações. Transformar não elimina instabilidade nem prova melhoria. A fala confunde λ Box-Cox com Poisson; λ é parâmetro de potência. Ver [nota da aula 19.1](../aulas_local/Black%20Belt%20-%20Aula%2019.1%20-%20Exercicio%20Transformacao%20Minitab%20SigmaFlow.md).

## Teste de igualdade de variâncias: interpretação e sequência analítica

Black Belt 20.1 compara as variâncias de duas amostras Antiga/Nova. Com p>α, a conclusão é falhar em rejeitar H0, não provar igualdade. Avalie método, distribuição, amostragem e potência; não transformar boxplots/intervalos sobrepostos em prova. Igualdade de variâncias é uma premissa de alguns procedimentos, não um teste de médias, estabilidade ou desempenho. Escolher t/ANOVA apropriado ao desenho e considerar Welch quando as variâncias diferem. Ver [Understanding test for equal variances — Minitab Support](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/anova/supporting-topics/basics/understanding-test-for-equal-variances/) e [nota detalhada da aula 20.1](../aulas_local/Black%20Belt%20-%20Aula%2020.1%20-%20ANOVA%20Teste%20de%20Variancia%20Minitab%20SigmaFlow.md).

## DFSS e DOE de mistura

Black Belt 27 apresenta DOE de mistura como ferramenta para formular respostas com proporções cuja soma é fixa e mostra restrições, simplex-centroid/lattice, regressão e otimizador. A solução prevista do exercício não é resultado confirmado; a desejabilidade composta (D=0,701950) é uma pontuação, não probabilidade de sucesso. Validar desenho, modelo, resíduos, faixa de previsão e fazer corridas confirmatórias. Separar o uso de DMAIC para melhorar processo existente do DFSS para projetar/redesenhar, sem inferir que a aula cobriu um roadmap DFSS completo. Ver [nota da aula 27](../aulas_local/Black%20Belt%20-%20Aula%2027%20-%20DFSS%20SigmaFlow.md), [NIST sobre misturas](https://itl.nist.gov/div898/handbook/pri/section5/pri54.htm) e [Minitab sobre otimizador de respostas](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/using-fitted-models/supporting-topics/response-optimization/what-is-response-optimization/).

## Priorização qualitativa por tabela de pares

Na Black Belt 30, a equipe compara alternativas duas a duas e soma preferências ponderadas. Isso documenta consenso sob uma regra definida, mas não mede impacto, risco, custo ou viabilidade. Guardar votos, critérios, participantes e dissenso; tratar multivotação para listas grandes como heurística. Validar a shortlist com dados e critérios explícitos antes de selecionar ação. Ver [nota da aula 30](../aulas_local/Black%20Belt%20-%20Aula%2030%20-%20Priorizacoes%20SigmaFlow.md).

## Campos de força e criatividade na implementação

Black Belt 29 apresenta forças motrizes/restritivas como mapa qualitativo para conversa de mudança; pesos não são medida objetiva de causa ou chance de sucesso. Trate resistência como hipótese/barreira que pode conter risco ou informação válida. Facilite criatividade e processo de geração/teste de ideias sem classificar pessoas por “lado do cérebro”: a dicotomia esquerda analítica/direita criativa e suas generalizações de gênero não têm suporte como perfis individuais. Vincule ideia selecionada a hipótese, piloto, métrica e decisão. Ver [nota da aula 29](../aulas_local/Black%20Belt%20-%20Aula%2029%20-%20Campos%20de%20Forca%20e%20Criatividade%20SigmaFlow.md), [Nielsen et al. (2013)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0071275) e [Hines (1987)](https://pmc.ncbi.nlm.nih.gov/articles/PMC3897366/).

## Marketing pessoal no papel do Black Belt

Black Belt 31 propõe autorreflexão, feedback, competências, comunicação coerente, formação e rede de contatos; esses são tópicos de desenvolvimento profissional, não métricas de processo. Não converter os arquétipos animais da aula em teste ou rótulo de equipe, nem aparência em critério de mérito. No SigmaFlow, apoiar comunicação rastreável de evidências, decisões e compromissos com stakeholders; separar percepção de resultado mensurado. Ver [nota da aula 31](../aulas_local/Black%20Belt%20-%20Aula%2031%20-%20Marketing%20Pessoal%20SigmaFlow.md).

## Cartas Xbarra-R, Xbarra-S e pré-controle

Na Black Belt 34, usar R para subgrupos pequenos (até 8 na orientação Minitab) e S para 9 ou mais; R é amplitude e S é desvio-padrão intrassubgrupo. Desenhar subgrupos racionalmente e distinguir limites estatísticos de controle dos limites de especificação. Amplitude não é um alvo de zero. Pré-controle opera com zonas baseadas em especificações e não substitui cartas estatísticas para estabilidade; sua simplicidade pode dar falsa segurança ou incentivar ajuste excessivo se usado indiscriminadamente. Ver [Minitab — Xbar-R](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/control-charts/how-to/variables-charts-for-subgroups/xbar-r-chart/before-you-start/data-considerations/), [NIST — Stability](https://itl.nist.gov/div898/handbook/ppc/section4/ppc45.htm) e [nota da aula 34](../aulas_local/Black%20Belt%20-%20Aula%2034%20-%20CEP%20Avancado%203%20SigmaFlow.md).

## Cartas por atributo e CEP multivariado

Na Black Belt 35, selecionar P/NP para proporção/contagem de unidades defeituosas e C/U para número de defeitos; NP exige tamanho de subgrupo constante. Diagnosticar sobredispersão/subdispersão antes de considerar Laney P′, que ajusta a dispersão mas não explica sua causa. Limites de controle não são especificações. T²/variância generalizada acompanha variáveis relacionadas em conjunto, sem apontar qual variável causou o sinal; não condicionar a carta a um corte simples de Pearson. Ver [Minitab — diagnóstico P](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/control-charts/how-to/attributes-charts/p-chart-diagnostic/interpret-the-results/key-results/), [Minitab — Laney P′](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/control-charts/how-to/attributes-charts/laney-p-chart/interpret-the-results/key-results/) e [nota da aula 35](../aulas_local/Black%20Belt%20-%20Aula%2035%20-%20CEP%20Avancado%204%20SigmaFlow.md).

## EWMA — carta ponderada pelo tempo

Black Belt 36 apresenta EWMA para dados contínuos em ordem temporal e a compara com I/Xbarra. Cada ponto resume a observação atual e o histórico com peso exponencial; essa memória pode revelar pequenas mudanças sustentadas. Não é previsão futura, normalização ou correção de processo. Ajuste peso/limites ao padrão de mudança e ao custo de falso alarme/atraso; verificar medição, subgrupos e autocorrelação. Separar limites de controle das especificações. Um sinal inicia investigação e não comanda automaticamente equipamento. Ver [Minitab — EWMA overview](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/control-charts/how-to/time-weighted-charts/ewma-chart/before-you-start/overview/), [data considerations](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/control-charts/how-to/time-weighted-charts/ewma-chart/before-you-start/data-considerations/) e [nota da aula 36](../aulas_local/Black%20Belt%20-%20Aula%2036%20-%20CEP%20Avancado%205%20SigmaFlow.md).

## Programa de implantação e gestão do CEP

Black Belt 37 estrutura governança, política, papéis, treinamento e comunicação, fornecedores, escolha de características críticas, MSA, coleta/subgrupos, cartas, reação a causas especiais, melhoria e monitoramento recorrente. Adaptar as doze etapas à escala/risco e preservar fonte do requisito e evidências. Não aplicar automaticamente os cortes Pp≥1,5/Ppk≥1,33 do slide para diminuir amostragem; não excluir sinais nem recalcular limites sem investigar e documentar causa atribuível. Capacidade exige estabilidade e premissas válidas. O critério 1,5×IQR não substitui limites/regras de CEP; usar plano de reação com registro e análise. Ver [NIST — Stability](https://itl.nist.gov/div898/handbook/ppc/section4/ppc45.htm), [NIST — out of control](https://www.itl.nist.gov/div898/handbook/pmc/section1/pmc14.htm), [Minitab — capability analysis](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/capability-analysis/supporting-topics/basics/uses-of-capability-analysis/) e [nota da aula 37](../aulas_local/Black%20Belt%20-%20Aula%2037%20-%20Gestao%20e%20Implementacao%20de%20CEP%20SigmaFlow.md).

## MSA da catapulta — exercício de reavaliação

Black Belt 17.1 é um exercício, não demonstração estatística: usar o roteiro/formulário da 3ª dinâmica para avaliar R&R, definir melhorias se necessárias e repetir lançamentos/estudo. Não inferir critérios nem resultados. Projeto do estudo deve explicitar partes, avaliadores, repetições, randomização, cruzado/aninhado, condição de uso e método; especificação do produto não é critério de aceitação do MSA. Comparar antes/depois apenas com desenho e condições registrados. Ver [nota da aula 17.1](../aulas_local/Black%20Belt%20-%20Aula%2017.1%20-%20Exercicio%20MSA%20SigmaFlow.md).
