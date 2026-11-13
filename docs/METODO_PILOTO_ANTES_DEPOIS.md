# Verificação local do piloto: antes e depois

Implementação: `sigmaflow/local_pilot.py`. Cenário `piloto` no catálogo local, configurado na seção **Implementar → Verificar piloto**. A comparação organiza evidências para revisar a ação; não aprova automaticamente eficácia, causa, fase DMAIC ou benefício financeiro.

## Dados e plano explícitos

Use uma única planilha com os dois períodos. Revise o mapeamento de data e medição contínua, ou de data, unidades defeituosas e total inspecionado. Defina indicador, definição operacional, unidade, direção desejada, meta, início/fim de cada janela e contexto de comparabilidade. A ligação com uma ação é opcional; quando presente, seu identificador e descrição são congelados na execução.

As janelas seguem `início antes ≤ fim antes < início depois ≤ fim depois`. Os quatro parâmetros usam AAAA-MM-DD; o fim inclui o dia inteiro. A coluna aceita calendários ISO ou DD/MM/AAAA e datas Excel reconhecidas como datas. Não interpreta número de série como data nem aceita fuso horário implícito. Datas inválidas impedem a seleção mesmo que uma medição possa estar fora das janelas. Os registros fora delas, inclusive transição, são contados e excluídos explicitamente. Valores numéricos ausentes/inválidos dentro das janelas bloqueiam o cálculo; não há exclusão silenciosa.

A equipe precisa declarar independência e revisar comparabilidade de população, mix, medição e outras mudanças. Essas declarações não são testes nem comprovam os pressupostos. Dados pareados, unidades repetidas, lotes agrupados, autocorrelação, diferenças de população ou mudanças de definição exigem outra análise/desenho. Uma série diária de produção não se torna independente ao marcar uma caixa.

## Medições contínuas

Exige ao menos duas observações por janela. Resume `n`, média e desvio amostral, com IC95% t de cada média quando o desvio é positivo. A diferença é sempre **depois − antes**:

`Δ = média_depois − média_antes`

`SE² = s_depois² / n_depois + s_antes² / n_antes`

`ν = SE⁴ / [(s_depois²/n_depois)²/(n_depois−1) + (s_antes²/n_antes)²/(n_antes−1)]`

O IC95% é `Δ ± t(0,975; ν) × SE`, acompanhado de p bilateral de Welch. Não presume variâncias iguais nem usa um teste preliminar de normalidade/variância para escolher automaticamente o procedimento. Independência, adequação da aproximação das médias, tamanho amostral, extremos e resolução devem ser revistos. Fórmula e escopo: [NIST, teste t para duas amostras](https://www.itl.nist.gov/div898/handbook/eda/section3/eda353.htm).

Se ambos os desvios forem zero, a diferença permanece descritiva, sem intervalo ou p-valor. O IC de uma média com desvio zero fica indisponível, sem falsa certeza populacional. Se apenas um desvio for zero, Welch continua disponível quando seus termos são finitos, com ressalva sobre medição e representatividade.

## Proporções de unidades defeituosas

Cada linha precisa de contagens inteiras `0 ≤ unidades defeituosas ≤ total`, com total positivo. O numerador conta cada unidade no máximo uma vez. Número de defeitos e oportunidades não substitui esse numerador. As somas usam inteiros Python; a proporção por período é `Σ defeituosas / Σ inspecionadas`, não a média das taxas das linhas.

Cada proporção tem IC95% Wilson. Para a diferença `d = p_depois − p_antes`, use os intervalos `[L_depois, U_depois]` e `[L_antes, U_antes]`:

`inferior = d − √[(p_depois − L_depois)² + (U_antes − p_antes)²]`

`superior = d + √[(U_depois − p_depois)² + (p_antes − L_antes)²]`

É Newcombe, método 10 para **proporções independentes**, sem correção de continuidade. O intervalo é aproximado e a cobertura pode diferir de 95%, sobretudo em situações extremas. Refere-se a unidades Bernoulli independentes, com probabilidade comum em cada período; somar lotes não corrige agrupamento/sobredispersão. Referência primária: [Newcombe (1998), Statistical Medicine 17, 873–890](https://doi.org/10.1002/(SICI)1097-0258(19980430)17:8%3C873::AID-SIM779%3E3.0.CO;2-I).

A tela usa percentuais para as proporções e a meta; **a diferença e seu intervalo estão em pontos percentuais**. Não calcula redução relativa como se fosse a mesma medida. Não foi acrescentado p-valor de outro teste a esse procedimento; o IC da diferença é a medida de incerteza apresentada. Zero ocorrências mantém intervalo não degenerado e não comprova risco zero.

## Meta, interpretação e próxima decisão

O atendimento pontual compara a estimativa pós com a meta: `≤` quando diminuir é desejado e `≥` quando aumentar é desejado. Registra separadamente se o IC do indicador pós fica do lado da meta, cruza a meta, fica fora dela ou não foi estimado. A sobreposição dos IC dos períodos não é usada como teste da diferença.

Comparação observacional, seleção de janelas, sazonalidade, mix, outras ações e regressão à média limitam atribuição causal. Mesmo uma meta atingida não comprova sustentação. Se a estimativa pós não atende à meta, o próximo passo orienta voltar à investigação e planejar nova coleta, preservando esta execução. Repetir cortes/indicadores para obter significância exige considerar multiplicidade.

## Persistência, relatório e reprodução

O plano atual é salvo em `investigation.pilot`; a análise contém os parâmetros efetivamente usados em `piloto.parameters` e `rastreabilidade.parameters`. Alterar o plano não modifica o cálculo anterior: a tela e o relatório mostram aviso de divergência, permitindo reexecutar conscientemente. A comparação não muda o andamento da ação.

O [pacote rastreável](PACOTE_RASTREAVEL_LOCAL.md) preserva o resultado salvo e reexecuta os parâmetros congelados na análise, mesmo que o plano atual tenha outra meta ou janela. O código do método, dados, parâmetros e ambiente acompanham o ZIP. Gráfico com pontos, IC e referência da meta mantém intervalos indisponíveis como ausentes.

## Evidências de conferência

`tests/test_local_pilot.py` cobre Welch contra SciPy, Newcombe combinado com limites Wilson de SciPy, fronteiras 0/N e N/N, ausência de dispersão, janelas inclusivas/transição, entradas inválidas, índices duplicados, sentido/meta e reprodução do pacote sem herdar a meta atual do plano. Uma revisão independente comparou um caso Welch com SciPy e seis pares de proporções com `statsmodels` (Wilson e Newcombe); diferenças dentro do arredondamento flutuante, até cerca de 1,5 × 10⁻¹⁴ pontos percentuais. Essa conferência tem o escopo desses métodos/casos, sem certificar a plataforma inteira ou um desenho industrial real.

Planilhas fictícias 14 e 15: [como preencher e interpretar](../problemas_exemplos_testes_LSS/COMO_TESTAR_PILOTOS.md).
