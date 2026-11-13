# Comparações entre grupos na interface local

O cenário **Diferenças entre grupos** permite escolher a pergunta a responder:

- **Medições:** usa grupo e medida, descrição por grupo e comparação exploratória de médias (Welch para dois grupos) ou Kruskal-Wallis para mais grupos, conforme os dados disponíveis.
- **Proporção de unidades rejeitadas:** usa grupo, unidades rejeitadas e unidades inspecionadas. Cada taxa é `soma(rejeitadas) / soma(inspecionadas)`, sem fazer média simples das taxas das linhas.

Se a planilha contiver medições e contagens, a tela pede a escolha. A proporção exige declarar que cada unidade rejeitada é contada uma vez e que cada linha tem denominador próprio, sem repetir a produção total por categoria. Essa declaração é do analista; o sistema não reconhece automaticamente registros da mesma unidade ou lote.

Exemplo fictício: duas linhas têm 10 rejeições cada. Com 1.000 unidades inspecionadas na A e 100 na B, as taxas são 1% e 10%. A diferença B − A é 9 pontos percentuais. A contagem absoluta isolada não mostra essa diferença.

## Saídas e limites

Para proporções, são aceitos 2 a 50 grupos, com contagens inteiras, não negativas, total positivo e rejeitadas menores ou iguais ao total. A tabela informa os denominadores e os IC95% Wilson por grupo; o gráfico mostra até 20 grupos e identifica quando omite os demais.

O teste global usa qui-quadrado sem correção de continuidade; se alguma frequência esperada for menor que 5 e houver dois grupos, usa Fisher bilateral. Para três ou mais grupos com frequências esperadas pequenas, a versão atual apresenta a descrição e explica por que não calculou o teste. Se toda a amostra tiver o mesmo desfecho, os intervalos continuam disponíveis e não há teste global nessa implementação.

Com exatamente dois grupos, a diferença **B − A**, na ordem de primeira aparição na planilha, inclui IC95% aproximado Newcombe-Wilson sem correção de continuidade. ICs individuais são pontuais; sua sobreposição não substitui o IC da diferença. Com três ou mais grupos, não há contraste pareado nem ajuste de multiplicidade: um teste global não identifica quais pares diferem.

Pressupostos: unidades independentes e probabilidade comparável dentro de cada grupo. Lotes, mix, tempo, medições repetidas, dependência temporal e outros fatores podem afetar a comparação. A análise observacional orienta investigação, sem atribuir causa automaticamente.

## Contrato da análise

```json
{"comparison_kind":"measurement"}
```

ou

```json
{"comparison_kind":"proportion","count_basis":"defective_units","denominators_disjoint":true}
```

Valores ausentes, confirmação numérica `1` no lugar de booleano e chaves adicionais não são aceitos para proporções. Registros antigos permanecem consultáveis; a tela não presume novas confirmações quando os parâmetros não constam na execução salva. Os parâmetros escolhidos são preservados na rastreabilidade e na reprodução exportada.

As referências de cálculo são a [implementação de Newcombe no statsmodels](https://www.statsmodels.org/dev/_modules/statsmodels/stats/proportion.html), o [qui-quadrado](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.contingency.chi2_contingency.html) e [Fisher](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html) do SciPy. Os testes usam ICs Wilson independentes via `scipy.stats.binomtest`, testes de contingência, tamanhos desiguais, contagens inválidas, casos de fronteira e reprodução dos parâmetros.
