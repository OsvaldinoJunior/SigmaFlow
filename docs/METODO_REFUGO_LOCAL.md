# Refugo, custo e cartas de atributos no prototipo local

## Definicoes informadas pelo analista

Na oportunidade de refugo, escolha se a contagem representa unidades defeituosas ou ocorrencias de defeitos. O sistema nao deduz essa semantica pelo nome da coluna. Ocorrencias multiplas em uma unidade nao podem ser interpretadas como unidades rejeitadas.

O Pareto principal soma a contagem por categoria, ordena do maior para o menor e calcula participacao e acumulado. Se houver uma coluna de custo, um Pareto separado e calculado por custo:

Os graficos mostram barras ordenadas e a linha do percentual acumulado. A marca de 80% e uma referencia heuristica de concentracao, nao uma regra universal de priorizacao. A sugestao informa se custo e grupo foram mapeados; se custo unitario e custo total estiverem ambos selecionados, a execucao e bloqueada ate que uma unica base seja definida.

- **Custo por unidade rejeitada:** quantidade de unidades defeituosas multiplicada pelo custo unitario. Bloqueado quando a contagem foi declarada como ocorrencias.
- **Custo total por registro:** soma os valores de custo total informados em cada linha; nao multiplica pela quantidade.

A moeda, periodo, inclusao de retrabalho, custos indiretos, duplicidades e politica contabil devem ser confirmados. O valor calculado e apenas o custo registrado nos dados. Para multiplicar custo unitario, confirme que cada unidade rejeitada entra uma vez na contagem; registros repetidos por unidade podem duplicar o valor.

Quando o papel `grupo` esta mapeado (por exemplo, linha ou turno), a tabela estratifica categoria e contagem dentro de cada grupo. Percentuais descrevem a composicao da contagem rejeitada naquele grupo, sem denominador de producao. Nao sao taxas de defeito nem comparacao de desempenho entre grupos com volumes diferentes. Diferencas orientam perguntas de investigacao e nao atribuem causa ao grupo.

## Carta p e carta np

O fluxo exige confirmacao de que a contagem sao unidades nao conformes. A carta p acompanha proporcao e aceita tamanhos de amostra variaveis. A carta np acompanha contagem e so aparece quando o tamanho de todos os subgrupos e igual. Para `n` constante e `p_bar` estimado:

- Linha central np: `n * p_bar`
- Limites exploratorios: `n * p_bar +/- 3 * sqrt(n * p_bar * (1 - p_bar))`, truncados ao intervalo `[0, n]`.

A referencia independente do NIST descreve p para fracao de itens nao conformes e np para numero de itens nao conformes, com tamanho de subgrupo fixo para np: [NIST/SEMATECH e-Handbook, proporcoes](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc332.htm), [referencia da carta np](https://www.itl.nist.gov/div898/software/dataplot/refman1/ch2/np_cont.pdf).

## Limites da versao local

As cartas calculam limites iniciais com os dados enviados e sinalizam pontos alem de 3 desvios. A interface nao aplica regras suplementares de corridas, nao identifica automaticamente fases/processos misturados e nao valida subgrupos racionais, independencia, estabilidade da linha de base ou adequacao de distribuicao para cada contexto. Revise esses pontos antes de definir limites operacionais. Benchmark manual automatizado confirma alguns casos simples; revisao independente e de especialista ainda e necessaria.
