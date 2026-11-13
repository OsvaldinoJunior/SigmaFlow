# Avaliação de completude do SigmaFlow

Auditoria do repositório em **13/11/2026**, com três subagentes revisando diagnóstico, interface e escopo/metodologia, e integração pelo agente principal.

**O projeto oferece uma prévia local funcional; ainda não está concluído como produto industrial compartilhado.** A existência de um módulo, uma aula estudada ou um teste aprovado comprova aquele item no escopo verificado. Não há base para atribuir uma porcentagem global de conclusão sem definir uma versão e seus critérios de aceite.

## Escopo encontrado

| Área | Situação | Evidência e limite prático |
|---|---|---|
| Importação e triagem | Disponível localmente | CSV/XLSX/XLS até 10 MB; mapeamento revisável e sugestões para 14 cenários. A identificação é heurística e não verifica os pressupostos do processo. |
| Cálculos e insights | Parcial | Há análises locais, testes de hipótese selecionados, intervalos e gráficos. As implementações avançadas da biblioteca não estão todas conectadas à tela ou validadas para liberação industrial. |
| Refugo e grupos | Disponível com limites | Pareto por quantidade/custo, acumulado, estrato simples e p/np. Comparações entre grupos escolhem medição ou proporção; taxas usam os denominadores, Wilson por grupo e Newcombe para dois grupos. Denominadores distintos são declarados pelo analista; não há identificador de unidade/subgrupo para detectar duplicação. |
| Investigação DMAIC | Parcial | Charter, medição, Ishikawa/6M, 5 Porquês, estados de causa, ações, piloto e controle. Revisões e evidências são registradas, mas a identidade do revisor é autodeclarada. Não há aprovação independente autenticada. |
| Piloto antes/depois | Disponível com limites | Welch para médias independentes e Wilson/Newcombe para proporções em janelas explícitas. Desenhos pareados, séries dependentes e atribuição causal não estão resolvidos por esse fluxo. |
| Persistência e histórico | Disponível para uso local | Projetos versionados, proteção contra sobrescrita de revisão, execuções preservadas e reabertura. A arquitetura local não coordena múltiplos processos ou usuários. |
| Relatórios e reprodução | Disponível localmente | HTML, impressão em PDF e pacote com planilha, resultados, fontes, ambiente e hashes. Reprodução relaciona entrada e saída; não certifica adequação estatística. |
| Plataforma corporativa | Incompleta | A API e a interface em `frontend/src` são uma base separada da jornada local. Integração, autorização/isolamento, concorrência e recuperação precisam de verificação integrada. Esta avaliação não equivale a uma auditoria de segurança completa. |
| Benefícios e sustentação | Parcial | Há planejamento no roadmap e campos de controle. Falta demonstrar um fluxo integrado de benefício realizado, revisão de Finanças, prevenção de dupla contagem e monitoramento sustentado com plano de reação. |

## Cinco frentes para uma versão industrial

1. **Aceite do protótipo:** um caso representativo concluído do problema ao controle, revisado pelo usuário Black Belt, com comportamento e limites documentados.
2. **Liberação dos métodos:** matriz de entradas, pressupostos, referências independentes, casos de borda e aprovação estatística por método; cobrir os desenhos que a versão decidir suportar.
3. **Uso por empresas:** integrar a jornada à aplicação corporativa e verificar permissões, isolamento entre empresas/plantas, armazenamento, concorrência e recuperação.
4. **Governança e controle:** revisores autenticados, decisões independentes, trilha auditável, linha de base e plano de reação com responsáveis.
5. **Piloto industrial e operação:** casos anonimizados reais, benefício financeiro revisado, implantação/backup/monitoramento e aceite dos usuários.

Essas frentes são critérios de entrega, não cinco tarefas de programação. Integrações e métodos adicionais dependem da versão definida no roadmap.

## Conferência dos estudos

A fila local `aulas_local/fila_estudos.json` contém 160 itens:

| Curso | Marcados como estudados | Pendentes |
|---|---:|---:|
| Green Belt | 84 de 84 | 0 |
| Black Belt | 51 de 51 | 0 |
| Yellow Belt | 5 de 20 | 15 |
| White Belt | 4 de 5 | 1 |

O registro de **135/135 em Green + Black Belt** é coerente com seu escopo. As 16 pendências pertencem aos outros dois cursos. A auditoria conferiu os registros da fila e as notas existentes; não reassistiu a todas as aulas nem usa a contagem de estudo como validação do software.

## Evidências e referências

Nesta revisão, `python -m pytest tests -q --ignore=tests/test_auto_seed.py` aprovou **186 testes**, com **1 ignorado** por indisponibilidade de symlinks no ambiente e 18 avisos. O arquivo de testes de inicialização da API `test_auto_seed.py` ficou fora dessa execução; a suíte não demonstra prontidão corporativa.

No navegador foram verificados: escolha explícita quando as duas bases existem, confirmações obrigatórias, bloqueios de custo e mapeamento pendente, trava durante a requisição, cálculo de taxas com volumes diferentes, relatório e salvamento/reabertura com parâmetros. O projeto temporário criado para essa verificação foi excluído.

- Diagnóstico: `sigmaflow/local_diagnosis.py` e testes de opções de medição/proporção e bloqueios de custo.
- Métodos: `local_analysis.py`, `local_statistics.py`, `local_visuals.py`, `local_pilot.py` e testes dos fluxos locais.
- Jornada e registros: `frontend/local`, `local_project_store.py`, `local_export.py` e testes de versões/exportação.
- Plano: [critérios locais](CRITERIOS_CONCLUSAO_LOCAL.md), [roadmap](ROADMAP_BLACK_BELT.md) e [limites da interface](INTERFACE_LOCAL.md).

Para taxas, foram consultadas a [implementação de Newcombe no statsmodels](https://www.statsmodels.org/dev/_modules/statsmodels/stats/proportion.html), o [qui-quadrado do SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.contingency.chi2_contingency.html) e o [teste exato de Fisher](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html). As verificações numéricas usam referências independentes do SciPy; falta complementá-las com a revisão do desenho industrial.
