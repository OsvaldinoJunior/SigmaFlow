# Critérios para concluir o protótipo local

Auditoria de escopo de 13/11/2026. Apresentar a ferramenta como assistente de análise local, não como sistema que aprova métodos ou comprova causa e saving automaticamente.

| Frente | Evidência atual | Critório pendente |
|---|---|---|
| Histórico local | Snapshots por versão, CAS, relatório sem recálculo, exportação por versão, cópia/restauraóão com motivo; API e navegador verificados | Evento imutável por rodada de cálculo; banco transacional antes de compartilhar entre processos/usuórios |
| Refugo (P0) | Sugestão e Pareto por quantidade; carta p em contexto apropriado | Semântica explícita para unidades defeituosas versus ocorrências; Pareto de quantidade e custo unitário/total; estratificação pelo grupo selecionado; cartas p/np com confirmação de unidade defeituosa e np somente para tamanho fixo. Pendente: benchmarks independentes para limites, subgrupos pequenos/zeros e desenho de linha de base. |
| Validade de cálculos | Regressão automatizada e rastreabilidade de código/parómetros | Benchmarks independentes por método e revisão de especialista antes de conclusão industrial |
| DMAIC | Charter, medição, Ishikawa/6M, 5 Porquês, decisões, ações e piloto antes/depois | Evidência/responsóvel por requisito; separar execuóão, revisão e aprovaóão com exceóães justificadas |
| Estudo das aulas | `fila_estudos.json`: 160 itens, 144 estudados e 16 pendentes | `PROGRESSO_ESTUDO_BELTS.md` declara 135/135. Corrigir e revisar os 16 pendentes antes de declarar estudo completo |
| Produto corporativo | Backlog de integração, permissões, multiusuário e governança | Fora do protótipo local; bloqueio antes de clientes/dados reais compartilhados |

## Próxima sequência

1. Fechar refugo ponta a ponta: semântica do indicador, validação, Pareto de custo/quantidade, estratificação, cartas p/np, hipóteses, aóão, piloto e controle.
2. Comparar cada cálculo com caso independente/manual revisado e documentar limites.
3. Persistir cada reexecução sem sobrescrever evidência anterior.
4. Criar gates DMAIC com requisitos, evidências, responsóveis e estados separados para execuóão/revisóo/aprovaóão.
5. Reconciliar fila de estudo e documento de progresso.
