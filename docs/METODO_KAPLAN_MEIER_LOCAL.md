# Vida útil com censura à direita no SigmaFlow local

O cenário **Vida útil e dados censurados** calcula Kaplan–Meier para uma coorte de unidades independentes. Ele considera tanto falhas observadas quanto unidades que chegaram ao fim do acompanhamento sem falhar. O cenário **Histórico de falhas por ativo** continua descritivo e exclui registros com evento 0 quando essa coluna estiver mapeada.

## Dados necessários

Uma linha por unidade, com identificador único, tempo observado na mesma unidade e evento explícito:

| Coluna de exemplo | Significado |
|---|---|
| `Ativo` | Identificador da unidade acompanhada; não repetir para eventos recorrentes. |
| `Tempo observado (horas)` | Tempo desde a origem definida até a falha ou a última observação sem falha. Valores finitos e não negativos; ao menos um tempo positivo. |
| `Evento` | `1` = falha observada; `0` = censura à direita. Uma coluna chamada `Censurado` não é mapeada automaticamente porque pode usar codificação inversa. |

Identificadores únicos não comprovam independência. Revise a definição de falha, origem do tempo, população, unidade, forma de coleta e motivo das retiradas. O modelo pressupõe censura não informativa. Entrada tardia, censura à esquerda/intervalar, falhas recorrentes e riscos competitivos precisam de outro tratamento.

## Cálculo e apresentação

Para cada tempo distinto `t`, o conjunto em risco contém todas as unidades ainda acompanhadas imediatamente antes daquele tempo. Se falhas e censuras empatam, as censuradas participam do risco dessa falha e são retiradas depois. A tabela mostra risco, falhas, censuras e sobrevivência.

`S(t) = S(anterior) × (1 − d/n)`, em que `d` é o número de falhas e `n` o número em risco. A curva usa degraus posteriores no tempo numérico real e indica censuras por `+`.

O IC95% é pontual e usa Greenwood com transformação log-log: `g = Σ d/[n(n−d)]`, `SE = √g/|log S|` e centro `log(−log S)`. A transformação inversa fornece os limites. Nas fronteiras `S=0` ou `S=1`, esse intervalo fica como **não estimado**, sem substituição por intervalos de certeza. Uma curva sem falhas observadas permanece em 100% como estimativa, mas não comprova confiabilidade de 100%.

A mediana é definida como o primeiro tempo com `S(t)≤0,5`, com tolerância numérica de `10⁻¹²` no platô de 50%. Se a curva não o atinge, a mediana é **não alcançada**. Essa escolha é o quantil inferior; outras bibliotecas podem usar outra convenção no platô.

O tempo médio restrito (**RMST**) é a integral da curva de zero até `τ`, o maior tempo observado. O resultado registra esse horizonte; não extrapola a vida além dele. Não é MTBF e não inclui IC de RMST nesta versão. Para comparar coortes, é necessário definir um horizonte comum e um método apropriado à comparação.

O gráfico exibe até os primeiros 1.000 pontos, com aviso quando limitado; a tabela em tela exibe até 100 linhas. Os indicadores usam a coorte completa. O [pacote do projeto](PACOTE_RASTREAVEL_LOCAL.md) exporta a tabela integral em uma nova reexecução JSON/CSV, preservando separadamente o registro salvo. Coortes estratificadas, log-rank, Weibull e modelos com covariáveis permanecem no roadmap.

## Evidências e exemplo local

- `sigmaflow/local_survival.py`: estimador, Greenwood, mediana e RMST.
- `tests/test_local_survival.py`: empates, fronteiras, censura completa, eventos em zero, validação e comparação com o `ecdf` independente da SciPy quando disponível.
- [13_vida_util_censurada.xlsx](../problemas_exemplos_testes_LSS/13_vida_util_censurada.xlsx): 12 válvulas fictícias, 6 falhas e 6 censuras. Mediana pelo critério adotado: 330 horas; sobrevivência em 500 horas: 33%; RMST até 500 horas: 351,9625 horas.

Um caso de referência com tempos `[2,2,3,4]` e eventos `[1,0,1,0]` tem riscos `[4,2,1]`, sobrevivência `[0,75;0,375;0,375]`, mediana 3 e RMST até 4 igual a 3,125. O teste compara os limites log-log com valores independentes e o exemplo das correias publicado pela SciPy.

Fontes metodológicas: [NIST — Kaplan–Meier](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/kaplan.htm), [SciPy — ECDF e dados censurados](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ecdf.html), [Greenwood e Greenwood exponencial — Sawyer](https://www.math.wustl.edu/~sawyer/handouts/greenwood.pdf) e [R survival — convenções de quantis e platôs](https://www.stat.ethz.ch/R-manual/R-devel/library/survival/html/quantile.survfit.html).
