# Interface local de diagnóstico

Execute `iniciar_interface_local.bat` ou `python sigmaflow/local_app.py`. Abra `http://127.0.0.1:8765` e mantenha o terminal aberto. Encerre com Ctrl+C.

A interface usa Python com pandas, numpy, scipy e openpyxl; para `.xls`, instale também `xlrd`. A primeira aba do Excel é lida. Arquivos têm limite de 10 MB. O processamento ocorre no computador local.

Selecione CSV, XLSX ou XLS, confira o mapeamento e execute uma análise sugerida. O católogo usa campos e nomes para sugerir métodos; colunas disponóveis não comprovam pressupostos, causalidade ou validade operacional. Revise dados e ressalvas com especialista.

Depois das análises, abra o relatório na página. **Salvar projeto** persiste o caso. A lista retoma projetos locais. **Histórico** mostra revisóes; relatório e exportação estão vinculados à versão selecionada. Restaurar cria nova revisão; copiar cria outro projeto. Em conflito entre abas, o autosave para e preserva a edição para recarga ou cópia.

Esta é uma prévia local. Não há autenticação nem coordenação entre processos/servidores. Leia `HISTORICO_PROJETOS_LOCAIS.md` e `CRITERIOS_CONCLUSAO_LOCAL.md` antes de uso industrial.

Na comparação entre grupos, escolha medições ou proporção de unidades rejeitadas. Para proporções, confirme unidades distintas e denominadores próprios por linha. Consulte o [método de comparação](METODO_COMPARACAO_GRUPOS.md) e a [avaliação de completude](AVALIACAO_COMPLETUDE.md).
