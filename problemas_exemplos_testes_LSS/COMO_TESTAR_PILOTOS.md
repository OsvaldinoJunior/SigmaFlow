# Dois pilotos fictícios para testar a comparação antes/depois

Na página local, importe uma das planilhas, confira o mapeamento e abra **Verificação de piloto antes e depois → Configurar comparação**. O formulário fica na área Implementar. A segunda aba da planilha contém os parâmetros do exemplo; eles não são inferidos dos dados.

| Campo | 14 — Refugo | 15 — Tempo de atendimento |
|---|---|---|
| Arquivo | [14_piloto_refugo_antes_depois.xlsx](14_piloto_refugo_antes_depois.xlsx) | [15_piloto_medicao_meta_pendente.xlsx](15_piloto_medicao_meta_pendente.xlsx) |
| Tipo | Proporção de unidades defeituosas | Medição contínua |
| Data | Data da coleta | Data da coleta |
| Resposta | Quantidade rejeitada / Unidades inspecionadas | Medição do processo |
| Unidade | % | min |
| Antes | 01/01/2026 a 10/01/2026 | 01/01/2026 a 10/01/2026 |
| Depois | 21/01/2026 a 30/01/2026 | 21/01/2026 a 30/01/2026 |
| Direção desejada | Diminuir | Diminuir |
| Meta pós | 2,5% | 9,5 min |
| Resultado esperado | Estimativa pontual pós atende à meta | Média pós muda, mas não atende à meta; orienta revisar investigação/ação |

Identifique o indicador e sua definição operacional; registre que são dados fictícios e que independência/comparabilidade são hipóteses para exercitar o formulário. A ação ligada é opcional. Nenhum desses exemplos comprova uma intervenção real. Os dez registros de transição (dias 11 a 20) são excluídos e contados explicitamente.

Confira os IC, o sinal **depois − antes**, os denominadores no refugo e a diferença em **pontos percentuais**, sem confundir com redução relativa. Depois altere apenas a meta: o resultado anterior deve permanecer com aviso de que corresponde ao plano original. Reexecute para obter um novo cálculo e salve/reabra o projeto para conferir a persistência. A exportação conserva os parâmetros originais da execução.

O [método e seus limites](../docs/METODO_PILOTO_ANTES_DEPOIS.md) descrevem fórmulas, pressupostos e casos não cobertos.
