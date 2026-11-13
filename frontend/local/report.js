const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
const fmt = (value) => typeof value === 'number' ? value.toLocaleString('pt-BR', {maximumFractionDigits:5}) : value == null ? 'Não calculado' : String(value);
let report = null;
try {
  const embedded = document.getElementById('sigmaflow-report-data');
  const stored = embedded ? embedded.textContent : sessionStorage.getItem('sigmaflow-relatorio-local');
  report = stored ? JSON.parse(stored) : null;
} catch (_) { report = null; }

function renderTraceability(trace) {
  if (!trace || typeof trace !== 'object') return '';
  const fields = [
    ['Identificador da execução', trace.run_id], ['Executada em', trace.executed_at],
    ['Cenário', trace.scenario], ['SHA-256 da planilha', trace.dataset_sha256],
    ['SHA-256 do motor de cálculo', trace.engine_sha256], ['Registros de entrada', trace.input_rows],
    ['SHA-256 dos resultados', trace.result_sha256],
  ];
  const pair = ([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value ?? 'Não registrado')}</dd></div>`;
  return `<details class="result-details result-traceability"><summary>Rastreabilidade desta execução</summary><dl>${fields.map(pair).join('')}${pair(['Mapeamento utilizado', JSON.stringify(trace.mapping ?? {}, null, 2)])}${pair(['Parâmetros utilizados', JSON.stringify(trace.parameters ?? {}, null, 2)])}${pair(['Ambiente de execução', JSON.stringify(trace.environment ?? {}, null, 2)])}</dl><p class="analysis-note">Os identificadores relacionam dados, cálculo e resultado. A rastreabilidade não comprova a validade das premissas nem a adequação do método ao processo.</p></details>`;
}

function normalizePilotPlan(plan) {
  if (!plan || typeof plan !== 'object') return null;
  const keys = ['kind','before_start','before_end','after_start','after_end','direction','target','unit','indicator','definition','action_id','action_label','independence_confirmed','comparability_confirmed','comparability_notes'];
  return Object.fromEntries(keys.map((key) => [key, key === 'target' ? (plan[key] === '' || plan[key] == null ? '' : Number(plan[key]))
    : key.endsWith('_confirmed') ? plan[key] === true : String(plan[key] ?? '').trim()]));
}

function renderPilotExecutionWarning(result, data) {
  if (result.rastreabilidade?.scenario !== 'piloto' && !result.piloto) return '';
  const frozen = result.rastreabilidade?.parameters || result.piloto?.parameters;
  const plan = data.projeto?.pilot;
  let message = '';
  if (!frozen) message = 'Esta execução não registra parâmetros verificáveis. O resultado preservado não confirma o plano atual.';
  else if (!plan || JSON.stringify(normalizePilotPlan(plan)) !== JSON.stringify(normalizePilotPlan(frozen))) message = 'O plano atual do piloto difere dos parâmetros desta execução. Os resultados preservados abaixo correspondem aos parâmetros originais registrados na rastreabilidade; não verificam o plano atual.';
  else {
    const signature = (mapping) => JSON.stringify(Object.entries(mapping || {}).filter(([,value]) => value).sort(([a],[b]) => a.localeCompare(b)));
    if (!result.rastreabilidade?.mapping || signature(result.rastreabilidade.mapping) !== signature(data.mapeamento)) message = 'O mapeamento do relatório difere ou não pode ser comparado ao utilizado nesta execução. Consulte os parâmetros e colunas originais na rastreabilidade antes de interpretar os resultados.';
  }
  return `<p class="pilot-report-notice ${message ? '' : 'pilot-report-current'}">${escapeHtml(message || 'A execução utiliza os parâmetros do plano atual. Essa correspondência não aprova a eficácia da ação nem comprova que a ação causou a mudança.')}</p>`;
}

function renderPilotPlan(plan) {
  if (!plan || !['indicator','definition','target','before_start','after_start','action_id','comparability_notes'].some((key) => plan[key] != null && String(plan[key]).trim())) return '';
  const fields = [
    ['Tipo', plan.kind === 'proportion' ? 'Proporção de unidades rejeitadas (%)' : 'Média de medida contínua'],
    ['Indicador',plan.indicator], ['Unidade',plan.unit], ['Definição operacional',plan.definition],
    ['Melhoria desejada',plan.direction === 'increase' ? 'Aumentar o indicador' : 'Reduzir o indicador'],
    ['Meta após o piloto',plan.target], ['Antes (datas inclusivas)',`${plan.before_start || 'Não informado'} a ${plan.before_end || 'Não informado'}`],
    ['Depois (datas inclusivas)',`${plan.after_start || 'Não informado'} a ${plan.after_end || 'Não informado'}`],
    ['Ação relacionada (texto registrado)',plan.action_id ? `${plan.action_label || 'Sem texto registrado'} · ${plan.action_id}` : 'Sem ação relacionada · exploração'],
    ['Independência declarada',plan.independence_confirmed === true ? 'Declarada pela equipe; não verificada automaticamente' : 'Não confirmada'],
    ['Comparabilidade declarada',plan.comparability_confirmed === true ? 'Declarada pela equipe; não verificada automaticamente' : 'Não confirmada'],
    ['Comparabilidade e outras mudanças',plan.comparability_notes],
  ];
  return `<section class="report-section"><div class="report-section-kicker">IMPLEMENTAR · VERIFICAÇÃO DO PILOTO</div><h2>Plano atual: antes e depois</h2><div class="project-fields">${fields.map(([label,value]) => `<div class="project-field"><span>${escapeHtml(label)}</span><p>${escapeHtml(value === '' || value == null ? 'Não informado' : value)}</p></div>`).join('')}</div><p class="report-method">Este é o plano atual registrado no projeto. Cada execução mantém seus próprios parâmetros e pode corresponder a um plano anterior. A comparação exige amostras independentes e comparáveis; dados pareados, repetidos, com dependência temporal ou agrupamento exigem outro método. O resultado não altera o andamento nem aprova a eficácia da ação automaticamente.</p></section>`;
}

const exportInfo = report?.export_info;
if (exportInfo) {
  const box = document.getElementById('report-export-info');
  const kind = exportInfo.kind === 'snapshot' ? 'RELATÓRIO SALVO · RETRATO DA VERSÃO'
    : exportInfo.kind === 'reexecucao' ? 'RELATÓRIO DE NOVA REEXECUÇÃO' : 'ORIGEM DO RELATÓRIO';
  const warnings = Array.isArray(exportInfo.warnings) ? exportInfo.warnings.filter((warning) => typeof warning === 'string' && warning.trim()) : [];
  box.hidden = false;
  box.className = 'report-export-info';
  box.innerHTML = `<strong>${escapeHtml(kind)}</strong><p>${escapeHtml(exportInfo.message || '')}</p>${warnings.length ? `<div class="report-export-warnings"><strong>Alertas sobre a origem e a reprodução dos resultados</strong><ul>${warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join('')}</ul></div>` : ''}<dl><div><dt>Projeto</dt><dd>${escapeHtml(exportInfo.project_id || 'Não registrado')}</dd></div><div><dt>Versão do projeto</dt><dd>${escapeHtml(exportInfo.project_version ?? 'Não registrada')}</dd></div><div><dt>Pacote preparado em</dt><dd>${escapeHtml(exportInfo.exported_at || 'Não registrado')}</dd></div><div><dt>SHA-256 da planilha</dt><dd>${escapeHtml(exportInfo.dataset_sha256 || 'Não registrado')}</dd></div></dl>`;
}

if (!report || !Array.isArray(report.analises)) {
  document.getElementById('report-empty').hidden = false;
  document.getElementById('print-report').disabled = true;
} else {
  if (!report.analises.length) {
    const empty = document.getElementById('report-empty');
    empty.hidden = false;
    empty.textContent = 'Este relatório não contém análises executadas. O contexto do projeto abaixo está disponível para consulta; não há resultados de métodos para interpretar.';
  }
  const generated = new Date(report.gerado_em).toLocaleString('pt-BR');
  document.getElementById('report-meta').innerHTML = `<div><span>PROJETO</span><strong>${escapeHtml(report.projeto?.title || 'Projeto de melhoria')}</strong></div><div><span>PLANILHA</span><strong>${escapeHtml(report.arquivo)}</strong></div><div><span>REGISTROS</span><strong>${escapeHtml(fmt(report.registros))}</strong></div><div><span>ANÁLISES EXECUTADAS</span><strong>${report.analises.length}</strong></div>`;
  document.getElementById('report-objective').innerHTML = `<span>OBJETIVO INFORMADO</span><p>${escapeHtml(report.objetivo?.trim() || 'Não informado.')}</p>`;
  const quality = report.quality_findings || [];
  const detector = report.detector || {};
  document.getElementById('data-quality-report').innerHTML = `<section class="report-section"><div class="report-section-kicker">REVISÃO DOS DADOS</div><h2>Sinais e classificação exploratória</h2><p>${escapeHtml(report.quality_note || 'Verificações descritivas para orientar revisão; não confirmam defeito nem causa.')}</p>${quality.length ? `<ul>${quality.map((item) => `<li><strong>${escapeHtml(item.message)}</strong> ${escapeHtml(item.caveat)}</li>`).join('')}</ul>` : '<p>Nenhum sinal foi marcado pelas verificações básicas usadas nesta triagem.</p>'}<p><strong>Tipos de problema candidatos:</strong> ${escapeHtml((detector.problems || []).join(' · ') || 'nenhum tipo priorizado')}</p>${Object.entries(detector.rationale || {}).map(([key, reasons]) => `<p><strong>${escapeHtml(key)}</strong> · ${escapeHtml((reasons || []).join('; '))} · Pista estrutural (n\u00e3o calibrada)</p>`).join('')}<p class="report-method">Classificações automáticas são heurísticas, e valores fora de 1,5 × IQR são candidatos exploratórios. Revise o contexto; não exclua dados automaticamente.</p></section>`;
  const project = report.projeto || {};
  const charter = project.charter || {};
  const measure = project.measure || {};
  const control = project.control || {};
  const pair = (label, value) => `<div class="project-field"><span>${escapeHtml(label)}</span><p>${escapeHtml(value || 'Não informado')}</p></div>`;
  const causes = project.causes || [];
  const actions = project.actions || [];
  const forces = project.forces || [];
  const decisions = Object.entries(project.decisions || {});
  const gateReviews = project.gate_reviews || {};
  const gateLabels = {definir:'Definir',medir:'Medir',analisar:'Analisar',implementar:'Implementar',controlar:'Controlar'};
  const gateCriterionLabels = {problema:'Problema, local e período delimitados',indicador:'Indicador Y, definição operacional e unidade',meta:'Linha de base e meta',responsaveis:'Responsável e patrocinador',dados:'Dados da linha de base',coleta:'Fonte, amostragem e unidade',medicao:'Sistema de medição',limitacoes:'Observações e limitações',resultados:'Execução analítica',causas:'Causa com evidência e estado',acao:'Ação ligada a causa validada',piloto:'Plano e resultado do piloto',monitoramento:'Indicador, responsável, frequência e fonte',reacao:'Regra de reação e padrão de trabalho'};
  const gateStatusLabels = {pending:'Aguardando revisão',adequate:'Revisado: adequado',inadequate:'Revisado: precisa de correção',not_applicable:'Não aplicável'};
  const decisionLabels = {priorizar:'Priorizar para investigação', adiar:'Adiar', nao_aplicar:'Não aplicar'};
  document.getElementById('project-report').innerHTML = `${decisions.length ? `<section class="report-section"><div class="report-section-kicker">REVISÃO HUMANA</div><h2>Decisões sobre as oportunidades</h2><div class="table-wrap"><table><thead><tr><th>Oportunidade</th><th>Decisão</th><th>Motivo</th><th>Estado do registro</th></tr></thead><tbody>${decisions.map(([id,decision]) => `<tr><td>${escapeHtml(decision.title || id)}</td><td>${escapeHtml(decisionLabels[decision.state] || decision.state || 'Sem decisão')}</td><td>${escapeHtml(decision.reason || 'Não informado')}</td><td>${decision.confirmed ? 'Registrada' : 'Motivo pendente'}</td></tr>`).join('')}</tbody></table></div><p class="report-method">Decisões pertencem à equipe do projeto. Priorizar uma oportunidade não valida hipótese nem aprova uma mudança operacional.</p></section>` : ''}<section class="report-section project-report-section"><div class="report-section-kicker">CONTEXTO DO PROJETO</div><h2>Contrato e medição</h2><div class="project-fields">${pair('Problema',charter.problem)}${pair('Indicador principal (Y)',charter.y)}${pair('Definição operacional',charter.definition)}${pair('Unidade',charter.unit)}${pair('Linha de base',charter.baseline)}${pair('Meta e prazo',charter.target)}${pair('Responsável',charter.owner)}${pair('Patrocinador / dono do processo',charter.sponsor)}${pair('Coleta e desenho dos dados',measure.source)}${pair('Unidade experimental / denominador',measure.unit)}${pair('Revisão do sistema de medição',measure.msa)}${pair('Limitações de medição',measure.notes)}</div></section>${causes.length ? `<section class="report-section"><div class="report-section-kicker">ANALISAR · HIPÓTESES</div><h2>Causas potenciais e evidências</h2><div class="table-wrap"><table><thead><tr><th>Categoria</th><th>Hipótese</th><th>Prioridade qualitativa</th><th>Estado</th><th>Evidência registrada</th></tr></thead><tbody>${causes.map((cause) => `<tr><td>${escapeHtml(cause.category)}</td><td>${escapeHtml(cause.text)}</td><td>${Number(cause.impact||3)*Number(cause.frequency||3)}/25</td><td>${escapeHtml(cause.status)}</td><td>${escapeHtml(cause.evidence||'Não informada')}</td></tr>`).join('')}</tbody></table></div>${causes.map((cause) => `<p class="report-method"><strong>5 porquês · ${escapeHtml(cause.text)}:</strong> ${(cause.whys||[]).filter(Boolean).map((why,index)=>`${index+1}) ${escapeHtml(why)}`).join(' · ') || 'Não registrados.'}</p>`).join('')}<p class="report-method">Estados de causa são registros da equipe. A presença de uma hipótese ou pontuação não constitui validação causal.</p></section>` : ''}${forces.length ? `<section class="report-section"><div class="report-section-kicker">IMPLEMENTAR · CONTEXTO</div><h2>Forças e barreiras</h2><ul>${forces.map((force) => `<li>${escapeHtml(force.kind==='barreira'?'Barreira':'Força de apoio')} (impacto percebido ${Number(force.impact)}): ${escapeHtml(force.text)}</li>`).join('')}</ul><p class="report-method">A escala representa julgamento qualitativo da equipe, não probabilidade de sucesso.</p></section>` : ''}${actions.length ? `<section class="report-section"><div class="report-section-kicker">IMPLEMENTAR · PLANO DE AÇÃO</div><h2>Ações e verificação</h2><div class="table-wrap"><table><thead><tr><th>Ação</th><th>Causa relacionada</th><th>Responsável / prazo</th><th>Critério de verificação</th><th>Estado</th></tr></thead><tbody>${actions.map((action) => {const cause=causes.find((item)=>item.id===action.causeId);return `<tr><td>${escapeHtml(action.action)}</td><td>${escapeHtml(cause?.text||'Não relacionada')}</td><td>${escapeHtml(action.owner||'Não definido')} · ${escapeHtml(action.due||'Sem prazo')}</td><td>${escapeHtml(action.verification||'Não definido')}</td><td>${escapeHtml(action.status||'planejada')}</td></tr>`;}).join('')}</tbody></table></div></section>` : ''}<section class="report-section project-report-section"><div class="report-section-kicker">CONTROLAR · SUSTENTAÇÃO</div><h2>Plano de controle</h2><div class="project-fields">${pair('Indicador',control.metric)}${pair('Responsável',control.owner)}${pair('Frequência e fonte',control.frequency)}${pair('Regra de reação',control.reaction)}${pair('Documento e padronização',control.standard)}</div></section>`;
  document.getElementById('project-report').insertAdjacentHTML('beforeend', renderPilotPlan(project.pilot));
  const gateRows = Object.entries(gateReviews).flatMap(([phase, checks]) => Object.entries(checks || {}).map(([key, review]) => ({
    phase:gateLabels[phase] || phase, key:gateCriterionLabels[key] || key, review:review || {},
  })));
  if (gateRows.length) {
    document.getElementById('project-report').insertAdjacentHTML('beforeend', `<section class="report-section"><div class="report-section-kicker">DMAIC · REVISÃO DE EVIDÊNCIAS</div><h2>Critérios e revisões registradas</h2><div class="table-wrap"><table><thead><tr><th>Fase</th><th>Critério</th><th>Estado</th><th>Revisor declarado</th><th>Evidência</th><th>Justificativa / observação</th><th>Data registrada</th></tr></thead><tbody>${gateRows.map(({phase,key,review}) => `<tr><td>${escapeHtml(phase)}</td><td>${escapeHtml(key)}</td><td>${escapeHtml(gateStatusLabels[review.status] || 'Sem revisão')}</td><td>${escapeHtml(review.reviewer || 'Não informado')}</td><td>${escapeHtml(review.evidence || 'Não informada')}</td><td>${escapeHtml(review.reason || 'Não informada')}</td><td>${escapeHtml(review.reviewed_at || 'Não registrada')}</td></tr>`).join('')}</tbody></table></div><p class="report-method">Os nomes são declarações locais sem autenticação. O relatório preserva o estado registrado, mas não certifica a validade da evidência nem constitui aprovação independente da fase.</p></section>`);
  }
  document.getElementById('report-content').innerHTML = report.analises.map((result, index) => `<section class="report-section"><div class="report-section-kicker">ANÁLISE ${String(index+1).padStart(2,'0')}</div><h2>${escapeHtml(result.titulo)}</h2>${renderPilotExecutionWarning(result, report)}<p class="report-method">Método: ${escapeHtml(result.metodo)}</p><div class="analysis-metrics">${result.indicadores.map(([label,value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(fmt(value))}</strong></div>`).join('')}</div>${renderChart(result.grafico)}${result.grafico_np ? renderChart(result.grafico_np) : ''}${result.grafico_custo ? renderChart(result.grafico_custo) : ''}<div class="result-insight"><strong>O que os dados mostram</strong><p>${escapeHtml(result.insight)}</p>${result.evidencias?.length ? `<strong>Evidências dos cálculos</strong><ul>${result.evidencias.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : ''}<strong>Como isso pode ajudar</strong><p>${escapeHtml(result.proximo_passo)}</p></div><div class="report-notes"><h3>Cuidados na interpretação</h3><ul>${result.observacoes.map((note) => `<li>${escapeHtml(note)}</li>`).join('')}</ul></div><details class="result-details"><summary>Ver tabela de resultados</summary><div class="table-wrap"><table><thead><tr>${result.colunas.map((col) => `<th>${escapeHtml(col)}</th>`).join('')}</tr></thead><tbody>${result.linhas.map((row) => `<tr>${row.map((value) => `<td>${escapeHtml(fmt(value))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>${result.linhas_total > result.linhas.length ? `<p class="analysis-note">Exibidas ${result.linhas.length} de ${result.linhas_total} linhas.</p>` : ''}${result.linhas_np?.length ? `<h4>Carta np para tamanho fixo</h4><div class="table-wrap"><table><thead><tr>${result.colunas_np.map((col) => `<th>${escapeHtml(col)}</th>`).join('')}</tr></thead><tbody>${result.linhas_np.map((row) => `<tr>${row.map((value) => `<td>${escapeHtml(fmt(value))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : ''}${result.linhas_custo?.length ? `<h4>Pareto por custo</h4><div class="table-wrap"><table><thead><tr>${result.colunas_custo.map((col) => `<th>${escapeHtml(col)}</th>`).join('')}</tr></thead><tbody>${result.linhas_custo.map((row) => `<tr>${row.map((value) => `<td>${escapeHtml(fmt(value))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : ''}${result.linhas_estratificacao?.length ? `<h4>Estratifica\u00e7\u00e3o</h4><div class="table-wrap"><table><thead><tr>${result.colunas_estratificacao.map((col) => `<th>${escapeHtml(col)}</th>`).join('')}</tr></thead><tbody>${result.linhas_estratificacao.slice(0,100).map((row) => `<tr>${row.map((value) => `<td>${escapeHtml(fmt(value))}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="analysis-note">Exibidas ${Math.min(result.linhas_estratificacao.length,100)} de ${result.estratificacao_total} linhas estratificadas.</p>` : ''}</details>${renderTraceability(result.rastreabilidade)}</section>`).join('');
}
document.getElementById('print-report').addEventListener('click', () => window.print());
