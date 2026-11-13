# Histórico de projetos locais

## Comportamento entregue

- Cada projeto tem versões numeradas. Os dados de cada revisão são identificados por SHA-256 e mantidos junto ao projeto local.
- O salvamento envia `base_version`. Se outra aba salvar primeiro, a API retorna HTTP 409 com a versóo atual. A interface interrompe o autosave e preserva a edição na tela.
- O painel **Histórico** lista revisóes em ordem decrescente. Abre o relatório salvo na mesma página e exporta a revisão escolhida.
- **Restaurar** cria uma nova revisão com motivo obrigatório. Revisóes intermediórias continuam no histórico. O relatório de uma revisão salva não recalcula métodos.
- **Copiar** cria outro projeto com novo identificador, relação `derived_from`, data, hash e motivo.
- Em um conflito, **Salvar como novo projeto** preserva o rascunho local. Essa cópia não afirma linhagem auditada no histórico da origem.

## API local

- `GET /api/projetos/{id}/historico?limit=50&before={versao}` lista metadados paginados; cursor exclusivo e ordem decrescente.
- `GET /api/projetos/{id}/versoes/{versao}` abre uma revisão e valida o hash dos dados.
- `GET /api/projetos/{id}/versoes/{versao}/relatorio` renderiza somente resultados registrados; não executa métodos.
- `GET /api/projetos/{id}/exportar?version={versao}` exporta a revisão exata.
- `POST /api/projetos/{id}/versoes/{versao}/copiar` recebe `title` opcional e `reason` obrigatório.
- `POST /api/projetos/{id}/versoes/{versao}/restaurar` recebe `base_version` atual e `reason` obrigatório.
- `PUT /api/projetos/{id}` exige `base_version`; conflitos retornam `code: version_conflict` e `current_version`.

## Limites

O bloqueio usa `RLock` no processo Python atual. Ele serializa threads, mas não coordena processos independentes gravando na mesma pasta. Para uso multiusuório, migrar para banco transacional e autenticação/autoria. Hashes detectam alteraóão em relação ao registro; não são assinatura de autor nem aprovação metodológica.

A listagem confere a integridade dos metadados. O hash da planilha é validado quando a revisão é aberta ou exportada. Metadados corrompidos em revisóes antigas aparecem como não legíveis.

`currentAnalyses[scenario]` still displays the latest result for each method. Each successful run is also queued in the browser until the next successful project save, then written as a separate immutable file with run ID, parameters, result, and source hashes. The screen can reopen each run result.
Execution IDs are linked to each project revision. Opening an older revision loads that revision's execution set; a new revision preserves prior runs and adds new ones. ZIP exports include the records in `execucoes/`.
Save and load validate the result hash, parameter hash, and dataset identity. These checks detect changes from the record; they do not prove authorship or method validity.
Local limits: 100 new runs and 8 MB total per save, 2 MB per result, and 10,000 runs per project. Runs not yet saved remain only in the current browser tab until saving succeeds.
