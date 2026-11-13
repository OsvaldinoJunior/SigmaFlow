# Exemplos fictícios e verificação do SigmaFlow

As planilhas são fictícias e a primeira aba contém os dados usados pela interface. Abra uma planilha por vez na tela local. A segunda aba explica o cenário.

A verificação envia cada arquivo aos endpoints de diagnóstico e análise da interface, usa o mapeamento automático e confere a sugestão e a execução do cenário esperado. Os pilotos usam parâmetros explicitamente definidos na segunda aba; não são inferidos da planilha.

| Arquivo | Problema fictício | Caminho esperado | Resultado da triagem |
|---|---|---|---|
| [01_refugo_retrabalho.xlsx](01_refugo_retrabalho.xlsx) | Refugo e retrabalho | Pareto por unidades/ocorrencias | OK — triagem e execução: Pareto de contagem confirmada pelo analista |
| [02_taxa_defeitos_tempo.xlsx](02_taxa_defeitos_tempo.xlsx) | Taxa de defeitos no tempo | Carta p | OK — triagem e execução: Carta p com limites de 3 desvios por tamanho de amostra |
| [03_capacidade_dimensional.xlsx](03_capacidade_dimensional.xlsx) | Capacidade dimensional | Capacidade de processo | OK — triagem e execução: Contagem observada e índices preliminares com desvio global |
| [04_variacao_temporal.xlsx](04_variacao_temporal.xlsx) | Variação no tempo | Carta de controle | OK — triagem e execução: I-MR: desvio dentro estimado por amplitude móvel média / 1,128 |
| [05_comparacao_turnos.xlsx](05_comparacao_turnos.xlsx) | Diferenças entre turnos | Comparação de grupos | OK — triagem e execução: Estatística descritiva estratificada |
| [06_msa_gauge_rr.xlsx](06_msa_gauge_rr.xlsx) | Sistema de medição | Gauge R&R | OK — triagem e execução: ANOVA cruzada balanceada com interação peça × operador |
| [07_fmea_processo.xlsx](07_fmea_processo.xlsx) | FMEA de processo | FMEA | OK — triagem e execução: RPN = severidade × ocorrência × detecção |
| [08_fatores_experimento.xlsx](08_fatores_experimento.xlsx) | Fatores e experimento | Exploração por fator | OK — triagem e execução: ANOVA de Welch exploratória + descrição por nível |
| [09_paradas_oee.xlsx](09_paradas_oee.xlsx) | Paradas e eficiência | OEE | OK — triagem e execução: Disponibilidade × desempenho × qualidade |
| [10_fluxo_lead_time.xlsx](10_fluxo_lead_time.xlsx) | Fluxo e lead time | Distribuição de tempos | OK — triagem e execução: Estatística descritiva estratificada |
| [11_energia_por_producao.xlsx](11_energia_por_producao.xlsx) | Energia por produção | Consumo por unidade | OK — triagem e execução: Consumo total dividido pela produção total |
| [12_falhas_confiabilidade.xlsx](12_falhas_confiabilidade.xlsx) | Falhas e confiabilidade | Contagem de falhas por ativo | OK — triagem e execução: Contagem descritiva por ativo |
| [13_vida_util_censurada.xlsx](13_vida_util_censurada.xlsx) | Vida útil com censura à direita | Kaplan–Meier | OK — triagem e execução: Kaplan–Meier; IC95% pontual log-log de Greenwood; RMST até τ |
| [14_piloto_refugo_antes_depois.xlsx](14_piloto_refugo_antes_depois.xlsx) | Piloto de refugo com meta pontual atingida | Proporções: Wilson e Newcombe | OK — triagem e execução: Newcombe-Wilson sem correção de continuidade, diferença depois − antes, IC95% aproximado |
| [15_piloto_medicao_meta_pendente.xlsx](15_piloto_medicao_meta_pendente.xlsx) | Piloto de medição com meta pendente | Comparação de médias: Welch | OK — triagem e execução: Welch, diferença de médias depois − antes, IC95% bilateral |

## Verificações adicionais

- OK — Taxa sem quantidade inspecionada.
- OK — Linha e turno geram pedido de escolha.
- OK — Escolha manual atualiza comparação de grupos.

## Como interpretar

OK indica leitura, sugestão e execução do caminho esperado; não comprova validade estatística ou adequação ao contexto industrial. A triagem ainda depende do nome das colunas e não comprova causas, adequação das análises ou qualidade dos dados. Confira o mapeamento e os pressupostos na interface.

Para repetir a verificação, execute `python scripts/gerar_exemplos_lss.py` na pasta do projeto. Planilhas já existentes são preservadas; o relatório de resultados é atualizado.
