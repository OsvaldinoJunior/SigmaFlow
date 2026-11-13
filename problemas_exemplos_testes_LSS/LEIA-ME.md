# Exemplos fictícios e verificação do SigmaFlow

As planilhas são fictícias e a primeira aba contém os dados usados pela interface. Abra uma planilha por vez na tela local. A segunda aba explica o cenário.

Para iniciar a interface local, execute `iniciar_interface_local.bat`. Se faltar alguma dependência, instale `requirements-local.txt` no mesmo Python que executa o arquivo BAT.

A verificação envia cada arquivo aos endpoints de diagnóstico e análise da interface, usa o mapeamento automático e confere se o cenário esperado é sugerido e executado. O relatório gerado fica em `RESULTADO_VERIFICACAO.md`; o script preserva este LEIA-ME e as planilhas já existentes.

| Arquivo | Problema fictício | Caminho esperado | Resultado da triagem |
|---|---|---|---|
| [01_refugo_retrabalho.xlsx](01_refugo_retrabalho.xlsx) | Refugo e retrabalho | Pareto de defeitos | OK — identificado para revisão |
| [02_taxa_defeitos_tempo.xlsx](02_taxa_defeitos_tempo.xlsx) | Taxa de defeitos no tempo | Carta p | OK — identificado para revisão |
| [03_capacidade_dimensional.xlsx](03_capacidade_dimensional.xlsx) | Capacidade dimensional | Capacidade de processo | OK — identificado para revisão |
| [04_variacao_temporal.xlsx](04_variacao_temporal.xlsx) | Variação no tempo | Carta de controle | OK — identificado para revisão |
| [05_comparacao_turnos.xlsx](05_comparacao_turnos.xlsx) | Diferenças entre turnos | Comparação de grupos | OK — identificado para revisão |
| [06_msa_gauge_rr.xlsx](06_msa_gauge_rr.xlsx) | Sistema de medição | Gauge R&R | OK — identificado para revisão |
| [07_fmea_processo.xlsx](07_fmea_processo.xlsx) | FMEA de processo | FMEA | OK — identificado para revisão |
| [08_fatores_experimento.xlsx](08_fatores_experimento.xlsx) | Fatores e experimento | Exploração por fator; não é DOE formal | OK — identificado para revisão |
| [09_paradas_oee.xlsx](09_paradas_oee.xlsx) | Paradas e eficiência | OEE | OK — identificado para revisão |
| [10_fluxo_lead_time.xlsx](10_fluxo_lead_time.xlsx) | Fluxo e lead time | Distribuição de tempos | OK — identificado para revisão |
| [11_energia_por_producao.xlsx](11_energia_por_producao.xlsx) | Energia por produção | Consumo por unidade | OK — identificado para revisão |
| [12_falhas_confiabilidade.xlsx](12_falhas_confiabilidade.xlsx) | Histórico de falhas | Contagem de falhas por ativo | OK — identificado para revisão |
| [13_vida_util_censurada.xlsx](13_vida_util_censurada.xlsx) | Vida útil de válvulas com unidades ainda sem falha | Kaplan–Meier com censura à direita | Uma linha por unidade; evento 1 = falha, 0 = censura |
| [14_piloto_refugo_antes_depois.xlsx](14_piloto_refugo_antes_depois.xlsx) | Piloto de refugo | Wilson/Newcombe e meta pontual | Parâmetros explícitos; ver [como testar](COMO_TESTAR_PILOTOS.md) |
| [15_piloto_medicao_meta_pendente.xlsx](15_piloto_medicao_meta_pendente.xlsx) | Piloto de medição com meta pendente | Welch e retorno à investigação | Parâmetros explícitos; ver [como testar](COMO_TESTAR_PILOTOS.md) |

## Verificações adicionais

- OK — Taxa sem quantidade inspecionada.
- OK — Linha e turno geram pedido de escolha.
- OK — Escolha manual atualiza comparação de grupos.

## Como interpretar

## Execução verificada em 13/11/2026

Os 13 arquivos foram abertos pelo mesmo leitor da interface, passaram pela triagem automática e executaram o cenário correspondente. A verificação pelo script usa os endpoints de diagnóstico e análise e grava o resultado em [RESULTADO_VERIFICACAO.md](RESULTADO_VERIFICACAO.md). Os métodos reportados pelo caminho local foram:

| Cenário | Método executado pelo protótipo |
|---|---|
| Refugo | Agrupamento por categoria e Pareto |
| Atributos | Carta p com limites variáveis pelo tamanho da amostra |
| Capacidade | Contagem observada e índices preliminares com desvio global |
| SPC de variáveis | I-MR com estimativa de sigma pela amplitude móvel média / 1,128 |
| Grupos | Estatística descritiva estratificada |
| MSA | ANOVA cruzada balanceada com interação peça × operador |
| FMEA | RPN = severidade × ocorrência × detecção |
| Fatores | ANOVA exploratória de um fator e descrição por nível quando os requisitos mínimos são atendidos; não executa desenho/otimização DOE |
| OEE | Disponibilidade × desempenho × qualidade |
| Fluxo | Estatística descritiva estratificada |
| Energia | Consumo total dividido pela produção total |
| Confiabilidade | Contagem descritiva por ativo |
| Sobrevivência | Kaplan–Meier com censura à direita, IC95% pontual log-log de Greenwood, mediana e RMST até o horizonte observado |

Essa verificação comprova leitura e execução dos exemplos, sem comprovar adequação a um processo real. Vários cenários ainda são resumos descritivos; capacidade, MSA, cartas, OEE e outros cálculos exigem revisão das premissas. O cenário de sobrevivência é limitado a unidades independentes com censura à direita; não inclui Weibull, riscos competitivos ou eventos recorrentes. DOE formal e comparações inferenciais completas permanecem no roadmap. Use as planilhas apenas como dados fictícios.

No exemplo 13 há 12 válvulas, 6 falhas e 6 censuras. A mediana de vida estimada é 330 horas, a sobrevivência estimada em 500 horas é 33%, e a área sob a curva até 500 horas (RMST) é 351,9625 horas. Veja [o método e suas limitações](../docs/METODO_KAPLAN_MEIER_LOCAL.md).

As verificações automatizadas estão em `tests/test_local_examples_smoke.py`. Elas verificam leitura, sugestão e execução sem erro; não comprovam que as colunas tenham o significado operacional correto. Confira mapeamento, unidades e pressupostos na interface.

Para repetir a verificação, execute `python scripts/gerar_exemplos_lss.py` na pasta do projeto. Planilhas já existentes são preservadas; o relatório de resultados é atualizado.
