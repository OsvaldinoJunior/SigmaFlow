# Exportação e reprodução do projeto local

Na área **Projeto DMAIC**, use **Baixar pacote do projeto**. A interface salva o estado atual e baixa um ZIP daquela versão. Se o salvamento falhar, o mapeamento estiver pendente ou houver alterações durante a preparação, o download é interrompido com uma explicação. O pacote contém a planilha original e as anotações; distribuí-lo compartilha esses dados.

## Registro salvo e nova execução

O pacote preserva `projeto.json` e `analises_salvas/*.json` sem recalcular seu conteúdo. `relatorio_salvo.html` representa esse registro, inclusive a prévia de tabela que havia sido salva. A triagem original é armazenada nos projetos novos; nos projetos antigos sua ausência fica explícita.

Separadamente, a exportação faz novos cálculos e grava `reexecucoes/*.json`, `reexecucoes/*.csv` e `relatorio_reexecutado.html`. As tabelas JSON/CSV dessa reexecução contêm todas as linhas calculadas; as tabelas HTML continuam como prévias de até 100 linhas, e os gráficos mantêm os limites indicados em suas legendas. A exportação não substitui as análises salvas nem registra aprovação metodológica ou de passagem de fase.

Cada análise nova registra cenário, identificador de execução, horário UTC, SHA-256 da planilha, mapeamento e parâmetros efetivamente usados, número de linhas de entrada, hash do resultado, identidade do código e versões relevantes do ambiente. Outro hash vincula esses parâmetros ao registro da execução. A reexecução usa o mapeamento e os parâmetros desse registro, mesmo que o mapeamento atual do projeto ou o plano do piloto tenha mudado. A rotina de reprodução também recebe esses parâmetros congelados.

O esquema de rastreabilidade 2 normaliza apenas grafias numericamente equivalentes de inteiros (`180.0`/`180`, `-0.0`/`0`) antes do hash, preservando os demais valores sem arredondá-los. Assim o ciclo JSON do navegador não invalida uma análise. Registros do esquema 1 são conferidos com o algoritmo original. Resultados numéricos acima de 2⁵³−1 em módulo são recusados na atribuição da rastreabilidade, com orientação para rever escala/unidade; não se arredondam contagens grandes para fazê-las passar na conferência.

Se a análise antiga não registrar a origem, a reexecução usa o mapeamento salvo do projeto e o identifica como base legada **não verificada**. Se origem, resultado ou parâmetros não corresponderem aos hashes registrados, a reexecução é recusada. Os JSON originais são preservados, e os motivos aparecem nos relatórios e no manifesto. Diferenças entre a prévia antiga e a nova também são destacadas.

## Arquivos do ZIP

| Arquivo ou pasta | Finalidade |
|---|---|
| `dados/original.*` | Os bytes da planilha validada pelo hash do projeto. |
| `projeto.json`, `analises_salvas/` | Estado registrado e resultados originais. |
| `reexecucoes/` | Novos resultados integrais e tabelas CSV. |
| `relatorio_salvo.html`, `relatorio_reexecutado.html` | Relatórios autocontidos com dados, estilos e gráficos; abrem sem servidor, internet ou sessão anterior. |
| `manifesto.json` | Versão do projeto, execuções, diferenças/recusas e hashes de todos os demais arquivos. |
| `codigo/` | Cópia do código de cálculo usado na reexecução. |
| `ambiente.json`, `requirements-congelados.txt` | Python, plataforma e versões dos pacotes relevantes instalados. |
| `reproduzir.json` | Dados e parâmetros necessários para reproduzir os novos cálculos. |
| `verificar_pacote.py` | Confere os hashes com a biblioteca padrão do Python. |
| `reproduzir_analises.py` | Recalcula com o código arquivado e compara com os novos resultados exportados. |

Para verificar os arquivos após extrair o ZIP:

```powershell
python verificar_pacote.py
```

Hashes permitem detectar alteração em relação ao manifesto preservado. Eles não são uma assinatura de autoria, uma trilha inviolável ou prova de validade estatística.

Para reproduzir, use a versão Python de `ambiente.json` e um ambiente separado:

```powershell
python -m pip install -r requirements-congelados.txt
python reproduzir_analises.py
```

A rotina escreve somente em `reproduzidos/`, preservando os registros exportados. Python/pacotes diferentes interrompem a execução por padrão. O argumento `--permitir-ambiente-diferente` autoriza uma comparação explícita nesse ambiente e registra a diferença. Plataformas distintas podem produzir pequenas diferenças numéricas, mesmo com versões iguais. O resultado da comparação está em `reproduzidos/comparacao.json`.

O CSV usa UTF-8 com BOM e separador ponto e vírgula. Textos que poderiam virar fórmulas recebem apóstrofo protetor; o JSON preserva o texto original. Os caminhos internos do ZIP são controlados pelo exportador e não derivam de nomes de cenário ou caminhos enviados pelo usuário.

## Limites atuais

- O pacote representa a versão atual salva; seleção de revisões antigas e importação do ZIP como projeto ainda não estão implementadas.
- A reprodução refere-se aos novos cálculos exportados. Sem origem/código/ambiente registrados na análise antiga, não se afirma que ela foi reproduzida.
- Código alterado após iniciar o servidor exige reinício antes de nova análise/exportação, para evitar atribuir uma execução a arquivos que não correspondam aos módulos carregados.
- O limite do conteúdo não comprimido do pacote é 64 MB. Mantêm-se os limites de arquivo e metadados do armazenamento local.
- Este recurso não acrescenta autenticação multiusuário, assinatura eletrônica ou revisão estatística independente.
