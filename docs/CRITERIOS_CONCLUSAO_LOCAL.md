# Critérios para concluir o protótipo local

Revisão de escopo em 13/11/2026. O SigmaFlow é um assistente local de análise e investigação. A avaliação completa, incluindo a diferença entre o protótipo e o produto corporativo, está em [AVALIACAO_COMPLETUDE.md](AVALIACAO_COMPLETUDE.md).

| Frente | Evidência atual | Critério pendente |
|---|---|---|
| Histórico local | Snapshots por versão, CAS, execuções preservadas por rodada, relatório sem recálculo e pacote reproduzível | Coordenação transacional antes de compartilhar entre processos/usuários; validar backup e recuperação na arquitetura compartilhada |
| Refugo | Pareto por contagem/custo com acumulado; estrato simples; bases de custo explícitas; cartas p/np; comparação de taxas com denominadores, Wilson e Newcombe para dois grupos | Identificar unidades/subgrupos para detectar denominadores repetidos, estratificação multidimensional, mais referências independentes e regras de sinal |
| Validade dos cálculos | Testes de regressão e casos de referência; rastreabilidade de código, dados e parâmetros | Matriz de liberação por método, revisão estatística independente e caso industrial representativo |
| DMAIC | Charter, medição, 6M, 5 Porquês, hipóteses, ações, piloto, controle e revisão por requisito no relatório | Revisores autenticados, aprovação independente, auditoria de alterações e avaliação humana do conteúdo das evidências |
| Estudos | Green Belt 84/84 e Black Belt 51/51 constam como estudados: 135/135 no escopo desses dois cursos | A fila ampliada tem White Belt 4/5 e Yellow Belt 5/20: 16 pendências fora do escopo Green/Black; estudo registrado não valida implementação |
| Produto corporativo | Há código de API, modelos e uma interface corporativa separada | Integrar a jornada, verificar autorização/isolamento, concorrência, operação e governança antes de liberar uso compartilhado |

## Critérios para a próxima entrega local

1. Concluir um projeto de refugo representativo com dados, hipótese, evidência, ação, piloto e controle, revisado pelo usuário Black Belt.
2. Conferir cada método liberado com referências independentes e registrar seus pressupostos, casos de borda e limitações.
3. Verificar a jornada de upload, parâmetros, erros, persistência, reabertura e exportação com os mesmos resultados e contexto.
4. Publicar o escopo suportado e os itens ainda parciais, sem equiparar testes de regressão a validação industrial.
