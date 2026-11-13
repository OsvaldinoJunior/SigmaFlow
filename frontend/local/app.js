const $ = (id) => document.getElementById(id);
let currentFile = null;
let currentResult = null;
let mappingDirty = false;
let currentAnalyses = {};
let currentSuggestions = new Map();
const analysesInFlight = new Set();
let executionHistory = [];
let pendingExecutions = [];
let analysisVersion = 0;
let diagnosticScroll = 0;
let currentCaseId = null;
let currentCaseVersion = 0;
let workspaceEpoch = 0;
let workspaceEditVersion = 0;
let savedEditVersion = 0;
let autosaveSuspended = false;
let workspaceConflictVersion = null;
let workspaceSwitchPending = false;
let workspaceSwitchRequest = 0;
let projectListRequest = 0;
let reportObjectUrl = null;
let historyState = {id:null, generation:0, headVersion:null, versions:[], nextBefore:null, busy:false, recovery:null, createdId:null};
let currentFileData = null;
let currentPhase = 'definir';
let restoringProject = false;
let autosaveTimer = null;
let projectSaveQueue = Promise.resolve();
let exportingProject = false;
let exportSavePending = false;
let projectSavesPending = 0;
let pilotRequestPending = false;
let pilotRequestController = null;
let pilotSavePending = false;
let pilotRenderedResult = null;
let projectState = emptyProjectState();

function emptyProjectState() {
  return {charter:{}, measure:{}, causes:[], forces:[], actions:[], control:{}, decisions:{}, gateReviews:{}, pilot:emptyPilotPlan()};
}

function emptyPilotPlan() {
  return {kind:'continuous', before_start:'', before_end:'', after_start:'', after_end:'',
    direction:'decrease', target:'', unit:'', indicator:'', definition:'', action_id:'', action_label:'',
    independence_confirmed:false, comparability_confirmed:false, comparability_notes:''};
}

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));

function renderAnalysisTraceability(trace) {
  if (!trace || typeof trace !== 'object') return '';
  const fields = [
    ['Identificador da execução', trace.run_id], ['Executada em', trace.executed_at],
    ['Cenário', trace.scenario], ['SHA-256 da planilha', trace.dataset_sha256],
    ['SHA-256 do motor de cálculo', trace.engine_sha256], ['Registros de entrada', trace.input_rows],
    ['SHA-256 dos resultados', trace.result_sha256],
    ['Mapeamento utilizado', JSON.stringify(trace.mapping ?? {}, null, 2)],
    ['Parâmetros utilizados', JSON.stringify(trace.parameters ?? {}, null, 2)],
    ['Ambiente de execução', JSON.stringify(trace.environment ?? {}, null, 2)],
  ];
  return `<details class="result-details result-traceability"><summary>Rastreabilidade desta execução</summary><dl>${fields.map(([label,value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value ?? 'Não registrado')}</dd></div>`).join('')}</dl><p class="analysis-note">Os identificadores relacionam dados, cálculo e resultado; revise as premissas e a adequação do método ao processo.</p></details>`;
}

function renderExecutionHistory() {
  const panel = $('execution-history-panel');
  if (!panel) return;
  panel.hidden = executionHistory.length === 0;
  $('execution-history-count').textContent = `${executionHistory.length} execução(ões)`;
  $('execution-history-list').innerHTML = [...executionHistory].reverse().map((result) => {
    const trace = result.rastreabilidade || {};
    return `<article class="history-version"><div><strong>${escapeHtml(result.titulo || trace.scenario || 'Análise')} · ${escapeHtml(trace.executed_at || 'data não registrada')}</strong><p>ID ${escapeHtml(trace.run_id || 'indisponível')} · dados ${escapeHtml((trace.dataset_sha256 || '').slice(0,16))} · motor ${escapeHtml((trace.engine_sha256 || '').slice(0,16))}</p><small>Resultado preservado com seus parâmetros originais.</small></div><button type="button" class="outline-button" data-execution-view="${escapeHtml(trace.run_id || '')}">Ver resultado</button></article>`;
  }).join('');
}

function decisionLabel(state) {
  return ({priorizar:'Priorizar para investigação', adiar:'Adiar', nao_aplicar:'Não aplicar'})[state] || '';
}

function refreshOpportunityDecisions() {
  document.querySelectorAll('.suggestion-card[data-scenario]').forEach((card) => {
    const decision = projectState.decisions?.[card.dataset.scenario] || {};
    const select = card.querySelector('[data-decision-field="state"]');
    const reason = card.querySelector('[data-decision-field="reason"]');
    select.value = decision.state || '';
    reason.value = decision.reason || '';
    const summary = decision.state ? ` · ${decisionLabel(decision.state)}${decision.confirmed ? '' : ' (motivo pendente)'}` : '';
    card.querySelector('.analyst-decision summary').textContent = `Decisão do analista${summary}`;
    card.querySelector('.decision-status').textContent = !decision.state ? 'A recomendação automática aguarda sua decisão.'
      : decision.confirmed ? `Decisão registrada: ${decisionLabel(decision.state)}.`
      : 'Informe o motivo para registrar esta decisão.';
  });
}

function setStep(step) {
  document.querySelectorAll('[data-step]').forEach((element) => {
    const number = Number(element.dataset.step);
    element.classList.toggle('active', number === step);
    element.classList.toggle('completed', number < step);
  });
}

function goTo(element) {
  element.scrollIntoView({behavior:'smooth', block:'start'});
}

function clearReport(preservePilot = false) {
  const pilot = preservePilot ? currentAnalyses.piloto : null;
  currentAnalyses = pilot ? {piloto:pilot} : {};
  sessionStorage.removeItem('sigmaflow-relatorio-local');
  $('report-link').hidden = true;
}

function openReport() {
  const mapping = {};
  document.querySelectorAll('[data-role]').forEach((select) => { mapping[select.dataset.role] = select.value; });
  try { saveReport(mapping); } catch (_) { showError('Não foi possível preparar o relatório nesta aba.'); return; }
  showInlineReport('/relatorio', 'Relatório das análises');
}

function showInlineReport(url, label) {
  if (reportObjectUrl && reportObjectUrl !== url) URL.revokeObjectURL(reportObjectUrl);
  reportObjectUrl = url.startsWith('blob:') ? url : null;
  diagnosticScroll = window.scrollY;
  const view = $('inline-report');
  $('inline-report-label').textContent = label;
  $('report-frame').src = url;
  document.querySelector('.app-shell').hidden = true;
  view.hidden = false;
  window.scrollTo(0, 0);
  requestAnimationFrame(() => view.classList.add('visible'));
}

$('back-to-diagnosis').addEventListener('click', () => {
  const view = $('inline-report');
  view.classList.remove('visible');
  view.hidden = true;
  document.querySelector('.app-shell').hidden = false;
  $('report-frame').src = 'about:blank';
  if (reportObjectUrl) { URL.revokeObjectURL(reportObjectUrl); reportObjectUrl = null; }
  window.scrollTo({top:diagnosticScroll, behavior:'smooth'});
});

function saveReport(mapping) {
  const data = {arquivo:currentFile.name, objetivo:$('objective').value, registros:currentResult.rows,
    colunas:currentResult.columns, gerado_em:new Date().toISOString(), mapeamento:mapping,
    analises:Object.values(currentAnalyses), projeto:collectProjectFields(),
    quality_note:currentResult.quality_note, quality_findings:currentResult.quality_findings || [],
    detector:currentResult.legacy_problems || {}};
  sessionStorage.setItem('sigmaflow-relatorio-local', JSON.stringify(data));
  $('report-link').hidden = false;
}

function applyFile(file) {
  if (!file) return;
  if (!/\.(csv|xlsx|xls)$/i.test(file.name)) {
    showError('Formato não suportado. Selecione um arquivo CSV, XLSX ou XLS.');
    return;
  }
  currentFile = file;
  workspaceEpoch++;
  workspaceEditVersion = 0;
  savedEditVersion = 0;
  autosaveSuspended = false;
  workspaceConflictVersion = null;
  currentCaseId = null;
  currentCaseVersion = 0;
  $('workspace-copy-panel').hidden = true;
  renderWorkspaceConflict();
  if (pilotRequestController) pilotRequestController.abort();
  pilotRequestController = null;
  pilotRequestPending = false;
  pilotSavePending = false;
  if ($('pilot-status')) $('pilot-status').textContent = '';
  currentFileData = null;
  analysisVersion++;
  clearReport();
  setStep(1);
  currentResult = null;
  if (!restoringProject) {
    executionHistory = [];
    pendingExecutions = [];
    currentCaseId = null;
    currentPhase = 'definir';
    projectState = emptyProjectState();
    resetProjectFields();
    if ($('project-title')) $('project-title').value = 'Projeto de melhoria';
    if ($('case-workspace')) $('case-workspace').hidden = true;
  }
  $('results').hidden = true;
  $('file-label').textContent = file.name;
  $('dropzone').classList.add('has-file');
  $('error').hidden = true;
  return true;
}

function workspaceHasUnsavedChanges() {
  return Boolean(currentFile && (!currentCaseId || workspaceEditVersion !== savedEditVersion || autosaveSuspended || mappingDirty));
}

async function prepareWorkspaceSwitch() {
  const request = ++workspaceSwitchRequest;
  workspaceSwitchPending = true;
  clearTimeout(autosaveTimer);
  autosaveTimer = null;
  analysisVersion++;
  if (pilotRequestController) pilotRequestController.abort();
  pilotRequestController = null;
  pilotRequestPending = false;
  pilotSavePending = false;
  renderWorkspaceControls();
  await projectSaveQueue;
  if (request !== workspaceSwitchRequest) return null;
  if (workspaceHasUnsavedChanges() && !confirm('Há alterações locais que podem não estar salvas. Abrir outra planilha ou projeto substituirá esta edição. Para preservá-la, cancele e use “Salvar como novo projeto”. Deseja continuar?')) {
    finishWorkspaceSwitch(request);
    return null;
  }
  return request;
}

function finishWorkspaceSwitch(request) {
  if (request !== workspaceSwitchRequest) return;
  workspaceSwitchPending = false;
  renderWorkspaceControls();
}

async function setFile(file) {
  if (!file) return false;
  if (!/\.(csv|xlsx|xls)$/i.test(file.name)) { showError('Formato não suportado. Selecione um arquivo CSV, XLSX ou XLS.'); return false; }
  const request = await prepareWorkspaceSwitch();
  if (request == null) return false;
  try { return applyFile(file); }
  finally { finishWorkspaceSwitch(request); }
}

$('file').addEventListener('change', (event) => setFile(event.target.files[0]));
$('choose-computer').addEventListener('click', async () => {
  const button = $('choose-computer');
  button.disabled = true;
  button.textContent = 'Aguardando seleção no computador...';
  $('error').hidden = true;
  try {
    const response = await fetch('/api/selecionar-planilha', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const result = await response.json();
    if (!response.ok || result.error) throw new Error(result.error || 'Não foi possível abrir a seleção.');
    if (!result.cancelled) {
      const binary = atob(result.content);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      await setFile(new File([bytes], result.name));
    }
  } catch (error) {
    showError(error instanceof TypeError ? 'Não foi possível acessar o servidor. Reinicie a interface local e atualize a página.' : error.message);
  } finally {
    button.disabled = false;
    button.textContent = 'Selecionar planilha no computador';
  }
});
['dragenter', 'dragover'].forEach((eventName) => $('dropzone').addEventListener(eventName, (event) => { event.preventDefault(); $('dropzone').classList.add('dragging'); }));
['dragleave', 'drop'].forEach((eventName) => $('dropzone').addEventListener(eventName, (event) => { event.preventDefault(); $('dropzone').classList.remove('dragging'); }));
$('dropzone').addEventListener('drop', (event) => setFile(event.dataTransfer.files[0]));

$('example').addEventListener('click', async () => {
  const rows = ['data;linha;turno;tipo de defeito;produzido;rejeitados'];
  const defects = ['Vedação', 'Rótulo', 'Enchimento'];
  for (let i = 0; i < 30; i++) {
    rows.push(`2026-10-${String(i + 1).padStart(2, '0')};Linha ${i % 2 + 1};${i % 2 ? 'Noite' : 'Dia'};${defects[i % 3]};${960 + (i % 6) * 20};${18 + (i % 5) * 3}`);
  }
  if (!await setFile(new File([rows.join('\n')], 'exemplo_refugo.csv', {type:'text/csv'}))) return;
  $('objective').value = 'Reduzir o refugo e entender as diferenças entre linhas e turnos.';
  runDiagnosis(false);
});

function readBase64(file) {
  if (file === currentFile && currentFileData) return Promise.resolve(currentFileData);
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const data = String(reader.result).split(',')[1];
      if (file === currentFile) currentFileData = data;
      resolve(data);
    };
    reader.onerror = () => reject(new Error('Não foi possível ler o arquivo selecionado.'));
    reader.readAsDataURL(file);
  });
}

async function runDiagnosis(useMapping, savedProject = null) {
  if (workspaceSwitchPending && !savedProject) return false;
  $('error').hidden = true;
  if (!currentFile) return showError('Selecione uma planilha ou use os dados de exemplo.');
  if (currentFile.size > 10 * 1024 * 1024) return showError('O arquivo deve ter no máximo 10 MB.');
  const mapping = {};
  if (savedProject?.mapping) Object.assign(mapping, savedProject.mapping);
  else if (useMapping && currentResult) document.querySelectorAll('[data-role]').forEach((select) => { mapping[select.dataset.role] = select.value; });
  const requestVersion = analysisVersion;
  $('analyze').disabled = true;
  $('reanalyze').disabled = true;
  $('reanalyze-bottom').disabled = true;
  const original = $('analyze').innerHTML;
  $('analyze').textContent = 'Lendo os dados...';
  try {
    const response = await fetch('/api/diagnostico', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({filename: currentFile.name, content: await readBase64(currentFile), objective: $('objective').value, mapping})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível ler os dados.');
    if (requestVersion !== analysisVersion) return;
    currentResult = data;
    render(data);
    if (savedProject) {
      currentCaseId = savedProject.id;
      currentCaseVersion = savedProject.version;
      currentPhase = savedProject.phase || 'definir';
      projectState = {
        ...emptyProjectState(), ...(savedProject.investigation || {}),
        actions:Array.isArray(savedProject.actions) ? savedProject.actions : [],
        control:savedProject.control || {},
        decisions:savedProject.investigation?.decisions || {},
        gateReviews:savedProject.investigation?.gate_reviews || {},
      };
      currentAnalyses = savedProject.analyses && typeof savedProject.analyses === 'object' ? savedProject.analyses : {};
      executionHistory = Array.isArray(savedProject.execution_history) ? savedProject.execution_history : [];
      pendingExecutions = [];
      renderExecutionHistory();
      fillProjectFields();
      renderProjectWorkspace();
      refreshOpportunityDecisions();
      renderSavedAnalyses(mapping);
    }
    $('results').hidden = false;
    setStep(useMapping ? 3 : 2);
    goTo(useMapping ? $('resultados') : $('results'));
    return true;
  } catch (error) { showError(error instanceof TypeError ? 'Não foi possível conectar ao servidor local. Abra iniciar_interface_local.bat e acesse http://127.0.0.1:8765.' : (error.message || 'Erro ao processar o arquivo.')); return false; }
  finally { $('analyze').disabled = false; $('reanalyze').disabled = false; $('reanalyze-bottom').disabled = false; $('analyze').innerHTML = original; }
}

function showError(message) { $('error').textContent = message; $('error').hidden = false; }
$('analyze').addEventListener('click', () => runDiagnosis(false));
$('reanalyze').addEventListener('click', () => runDiagnosis(true));
$('reanalyze-bottom').addEventListener('click', () => runDiagnosis(true));
$('show-opportunities').addEventListener('click', () => { setStep(3); goTo($('resultados')); });
$('report-link').addEventListener('click', openReport);

function analysisMarkup(result) {
  const fmt = (value) => typeof value === 'number' ? value.toLocaleString('pt-BR', {maximumFractionDigits:5}) : value == null ? 'Não calculado' : String(value);
  return `<h4>${escapeHtml(result.titulo)}</h4><p class="analysis-method">${escapeHtml(result.metodo)}</p><div class="analysis-metrics">${result.indicadores.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(fmt(value))}</strong></div>`).join('')}</div>${renderChart(result.grafico)}${result.grafico_np ? renderChart(result.grafico_np) : ''}${result.grafico_custo ? renderChart(result.grafico_custo) : ''}<div class="result-insight"><strong>O que os dados mostram</strong><p>${escapeHtml(result.insight)}</p>${result.evidencias?.length ? `<strong>Evidências dos cálculos</strong><ul>${result.evidencias.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : ''}<strong>Como isso pode ajudar</strong><p>${escapeHtml(result.proximo_passo)}</p></div><details class="result-details"><summary>Ver tabela e cuidados da análise</summary><div class="table-wrap"><table><thead><tr>${result.colunas.map((col) => `<th>${escapeHtml(col)}</th>`).join('')}</tr></thead><tbody>${result.linhas.map((row) => `<tr>${row.map((value) => `<td>${escapeHtml(fmt(value))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>${result.linhas_total > result.linhas.length ? `<p class="analysis-note">Exibidas ${result.linhas.length} de ${result.linhas_total} linhas.</p>` : ''}${result.linhas_np?.length ? `<h4>Carta np para tamanho fixo</h4><div class="table-wrap"><table><thead><tr>${result.colunas_np.map((col) => `<th>${escapeHtml(col)}</th>`).join('')}</tr></thead><tbody>${result.linhas_np.map((row) => `<tr>${row.map((value) => `<td>${escapeHtml(fmt(value))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>${result.linhas_np_total > result.linhas_np.length ? `<p class="analysis-note">Exibidas ${result.linhas_np.length} de ${result.linhas_np_total} linhas.</p>` : ''}` : ''}${result.linhas_custo?.length ? `<h4>Pareto por custo</h4><div class="table-wrap"><table><thead><tr>${result.colunas_custo.map((col) => `<th>${escapeHtml(col)}</th>`).join('')}</tr></thead><tbody>${result.linhas_custo.map((row) => `<tr>${row.map((value) => `<td>${escapeHtml(fmt(value))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : ''}${result.linhas_estratificacao?.length ? `<h4>Estratifica\u00e7\u00e3o por ${escapeHtml(currentMapping().grupo || 'grupo')}</h4><div class="table-wrap"><table><thead><tr>${result.colunas_estratificacao.map((col) => `<th>${escapeHtml(col)}</th>`).join('')}</tr></thead><tbody>${result.linhas_estratificacao.slice(0,100).map((row) => `<tr>${row.map((value) => `<td>${escapeHtml(fmt(value))}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="analysis-note">Exibidas ${Math.min(result.linhas_estratificacao.length,100)} de ${result.estratificacao_total} linhas estratificadas.</p>` : ''}${result.observacoes.map((note) => `<p class="analysis-note">${escapeHtml(note)}</p>`).join('')}</details>${renderAnalysisTraceability(result.rastreabilidade)}<button type="button" class="report-open">Ver relatório das análises →</button>`;
}

function renderSavedAnalyses(mapping) {
  for (const [scenario, result] of Object.entries(currentAnalyses)) {
    if (scenario === 'piloto') continue;
    const card = document.querySelector(`[data-scenario="${CSS.escape(scenario)}"]`);
    if (!card) continue;
    const output = card.querySelector('.analysis-output');
    const savedParameters = result.rastreabilidade?.parameters || result.parameters || {};
    const kindSelect = card.querySelector('[data-analysis-param="comparison_kind"]');
    const basisSelect = card.querySelector('[data-analysis-param="count_basis"]');
    const disjointCheck = card.querySelector('[data-analysis-param="denominators_disjoint"]');
    const legacyGroupWithoutParameters = scenario === 'grupos' && !savedParameters.comparison_kind;
    card.dataset.legacySnapshotParametersMissing = legacyGroupWithoutParameters ? 'true' : 'false';
    if (kindSelect && legacyGroupWithoutParameters) kindSelect.value = '';
    if (kindSelect && !legacyGroupWithoutParameters && savedParameters.comparison_kind) kindSelect.value = savedParameters.comparison_kind;
    if (basisSelect && !legacyGroupWithoutParameters && savedParameters.count_basis) basisSelect.value = savedParameters.count_basis;
    if (disjointCheck && !legacyGroupWithoutParameters && savedParameters.denominators_disjoint === true) disjointCheck.checked = true;
    syncScenarioParameterFields(card);
    output.innerHTML = analysisMarkup(result);
    output.hidden = false;
    card.classList.add('has-result');
    const button = card.querySelector('.run-analysis');
    button.textContent = 'Executar análise novamente ↻';
    refreshAnalysisEligibility(card);
  }
  renderPilotResult();
  if (Object.keys(currentAnalyses).length) saveReport(mapping);
}

function analysisParametersForCard(card) {
  const scenario = card?.dataset.scenario;
  const value = (name) => card.querySelector(`[data-analysis-param="${name}"]`)?.value || '';
  const checked = (name) => card.querySelector(`[data-analysis-param="${name}"]`)?.checked === true;
  if (scenario === 'refugo') {
    const countBasis = value('count_basis');
    return ['defective_units', 'defect_occurrences'].includes(countBasis) ? {count_basis:countBasis} : null;
  }
  if (scenario === 'atributos') return value('count_basis') === 'defective_units' ? {count_basis:'defective_units'} : null;
  if (scenario === 'grupos') {
    const item = currentSuggestions.get(scenario);
    const kind = value('comparison_kind');
    const option = item?.comparison_options?.find((candidate) => candidate.value === kind && candidate.available);
    if (!option || card.dataset.legacySnapshotParametersMissing === 'true') return null;
    if (kind === 'measurement') return {comparison_kind:'measurement'};
    if (kind === 'proportion' && value('count_basis') === 'defective_units' && checked('denominators_disjoint')) {
      return {comparison_kind:'proportion', count_basis:'defective_units', denominators_disjoint:true};
    }
    return null;
  }
  return {};
}

function analysisEligibility(card) {
  const scenario = card?.dataset.scenario;
  const suggestion = currentSuggestions.get(scenario);
  const parameters = analysisParametersForCard(card);
  const eligible = Boolean(currentFile && card?.isConnected && suggestion
    && suggestion.status === 'revisar'
    && !(suggestion.blockers || []).length
    && !mappingDirty
    && !analysesInFlight.has(scenario)
    && parameters !== null);
  return {eligible, parameters, suggestion};
}

function syncScenarioParameterFields(card) {
  if (!card) return;
  const kind = card.querySelector('[data-analysis-param="comparison_kind"]')?.value || '';
  const proportion = kind === 'proportion';
  const basisField = card.querySelector('[data-analysis-param="count_basis"]')?.closest('label');
  const denominatorField = card.querySelector('[data-analysis-param="denominators_disjoint"]')?.closest('label');
  if (card.dataset.scenario === 'grupos') {
    if (basisField) basisField.hidden = !proportion;
    if (denominatorField) denominatorField.hidden = !proportion;
  }
  const busy = analysesInFlight.has(card.dataset.scenario);
  card.querySelectorAll('[data-analysis-param]').forEach((field) => { field.disabled = busy; });
}

function refreshAnalysisEligibility(card) {
  if (!card) return;
  const button = card.querySelector('.run-analysis');
  if (!button || card.dataset.scenario === 'piloto') return;
  syncScenarioParameterFields(card);
  const {eligible, suggestion} = analysisEligibility(card);
  button.disabled = !eligible;
  if (analysesInFlight.has(card.dataset.scenario)) button.textContent = 'Calculando...';
  else if (card.classList.contains('has-result')) button.textContent = 'Executar análise novamente ↻';
  else if (suggestion?.blockers?.length) button.textContent = 'Revise os bloqueios acima';
  else if (suggestion?.status !== 'revisar') button.textContent = 'Preencha os dados necessários';
  else if (!eligible) button.textContent = 'Confirme os parâmetros da análise';
  else button.textContent = 'Executar análise →';
}

function render(data) {
  analysisVersion++;
  currentSuggestions = new Map((data.suggestions || []).map((item) => [item.id, item]));
  clearReport(true);
  mappingDirty = false;
  $('mapping-notice').hidden = true;
  $('result-file').textContent = `Arquivo analisado: ${currentFile.name}`;
  $('row-count').textContent = data.rows.toLocaleString('pt-BR');
  $('col-count').textContent = data.columns.length.toLocaleString('pt-BR');
  $('numeric-count').textContent = data.numeric_count.toLocaleString('pt-BR');
  $('missing-count').textContent = data.missing_cells.toLocaleString('pt-BR');
  $('mapping-fields').innerHTML = data.roles.map((role) => `<label>${escapeHtml(role.label)}<select data-role="${escapeHtml(role.id)}"><option value="">Não informada</option>${data.columns.map((col) => `<option value="${escapeHtml(col)}" ${role.selected === col ? 'selected' : ''}>${escapeHtml(col)}</option>`).join('')}</select>${role.candidates.length > 1 && !role.selected ? '<small>Mais de uma coluna possível: selecione.</small>' : ''}</label>`).join('');
  $('preview').innerHTML = `<thead><tr>${data.columns.map((col) => `<th>${escapeHtml(col)}</th>`).join('')}</tr></thead><tbody>${data.preview.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join('')}</tr>`).join('')}</tbody>`;
  const numbers = data.numeric_summary || [];
  const formatNumber = (value) => Number(value).toLocaleString('pt-BR', {maximumFractionDigits: 3});
  $('numeric-section').hidden = !numbers.length;
  $('numeric-summary').innerHTML = `<thead><tr><th>Coluna</th><th>Valores válidos</th><th>Mínimo</th><th>Média</th><th>Máximo</th></tr></thead><tbody>${numbers.map((item) => `<tr><td>${escapeHtml(item.column)}</td><td>${formatNumber(item.count)}</td><td>${formatNumber(item.min)}</td><td>${formatNumber(item.mean)}</td><td>${formatNumber(item.max)}</td></tr>`).join('')}</tbody>`;
  const ready = data.suggestions.filter((item) => item.status === 'revisar').length;
  $('suggestion-count').textContent = `${ready} para revisar · ${data.suggestions.length} cenários`;
  $('warning').hidden = !data.warning;
  $('warning').textContent = data.warning || '';
  const quality = data.quality_findings || [];
  $('data-findings').hidden = !quality.length && !(data.legacy_problems?.problems || []).length;
  $('quality-note').textContent = data.quality_note || '';
  $('quality-findings').innerHTML = quality.length ? quality.map((item) => `<article class="quality-card"><strong>${escapeHtml(item.message)}</strong><p>${escapeHtml(item.caveat)}</p></article>`).join('') : '<p class="analysis-note">Nenhum sinal descritivo foi marcado por estas verificações básicas.</p>';
  const detector = data.legacy_problems || {};
  const detected = detector.problems || [];
  $('detector-findings').innerHTML = detected.length ? `<p><strong>Tipos candidatos:</strong> ${detected.map((item) => escapeHtml(item)).join(' · ')}</p>${Object.entries(detector.rationale || {}).map(([key, reasons]) => `<p><strong>${escapeHtml(key)}</strong> · ${escapeHtml((reasons || []).join('; '))} <span>Pista estrutural (n\u00e3o calibrada)</span></p>`).join('')}` : '<p>Nenhuma classe heurística foi priorizada; explore as sugestões abaixo e confirme o objetivo.</p>';
function scenarioParameterMarkup(item) {
  if (['refugo', 'atributos'].includes(item.id)) {
    return `<label class="analysis-parameter">${item.id === 'atributos' ? 'Confirme a sem\u00e2ntica exigida pela carta p/np:' : 'O que a coluna de contagem representa?'}<select data-analysis-param="count_basis"><option value="">Selecione antes de calcular</option><option value="defective_units">Contagem de unidades defeituosas</option>${item.id === 'refugo' ? '<option value="defect_occurrences">Ocorr\u00eancias de defeitos</option>' : ''}</select></label>`;
  }
  if (item.id !== 'grupos') return '';
  const options = Array.isArray(item.comparison_options) ? item.comparison_options : [];
  const available = options.filter((option) => option.available);
  const initial = available.length === 1 ? available[0].value : '';
  const optionMarkup = options.map((option) => {
    const unavailableReason = option.missing?.length ? ` — faltam: ${option.missing.join(', ')}` : '';
    return `<option value="${escapeHtml(option.value)}" ${option.available ? '' : 'disabled'} ${option.value === initial ? 'selected' : ''}>${escapeHtml(option.label)}${escapeHtml(unavailableReason)}</option>`;
  }).join('');
  return `<label class="analysis-parameter">Tipo de compara\u00e7\u00e3o<select data-analysis-param="comparison_kind"><option value="" ${initial ? '' : 'selected'}>Selecione o tipo</option>${optionMarkup}</select></label><label class="analysis-parameter" hidden>Confirma\u00e7\u00e3o da contagem para propor\u00e7\u00f5es<select data-analysis-param="count_basis"><option value="">Confirme o significado da contagem</option><option value="defective_units">Unidades defeituosas: cada unidade aparece uma vez</option></select></label><label class="analysis-parameter" hidden><input type="checkbox" data-analysis-param="denominators_disjoint"> Cada linha representa unidades distintas e o total n\u00e3o se repete entre tipos de defeito.</label><p class="analysis-note">A op\u00e7\u00e3o de propor\u00e7\u00e3o s\u00f3 serve quando os grupos t\u00eam denominadores sem sobreposi\u00e7\u00e3o. N\u00e3o repita a produ\u00e7\u00e3o total para cada categoria de defeito.</p>`;
}

function renderSuggestionCard(item, index) {
  const decision = projectState.decisions?.[item.id] || {};
  const summary = decision.state ? ` · ${escapeHtml(decisionLabel(decision.state))}${decision.confirmed ? '' : ' (motivo pendente)'}` : '';
  const status = !decision.state ? 'A recomendação automática aguarda sua decisão.'
    : decision.confirmed ? `Decisão registrada: ${decisionLabel(decision.state)}.`
    : 'Informe o motivo para registrar esta decisão.';
  return `<article class="suggestion-card" data-scenario="${escapeHtml(item.id)}"><div class="card-top"><span class="card-index">${String(index + 1).padStart(2,'0')} / CENÁRIO</span><span class="status ${item.status === 'revisar' ? 'ready' : 'incomplete'}">${item.status === 'revisar' ? '●  REVISAR DADOS' : '○  FALTAM DADOS'}</span></div><h3>${escapeHtml(item.title)}</h3><p class="question">${escapeHtml(item.question)}</p><div class="method-list">${item.methods.map((method) => `<span>${escapeHtml(method)}</span>`).join('')}</div><div class="card-detail">${item.found.length ? `<p><strong>Encontrado</strong> ${item.found.map((entry) => `${escapeHtml(entry.role)}: <b>${escapeHtml(entry.column)}</b>`).join(' · ')}</p>` : '<p><strong>Encontrado</strong> Nenhuma coluna associada ainda.</p>'}${item.missing.length ? `<p><strong>Falta informar</strong> ${item.missing.map(escapeHtml).join(' \u00b7 ')}</p>` : ''}${item.optional_found?.length ? `<p><strong>Colunas opcionais reconhecidas</strong> ${item.optional_found.map((entry) => `${escapeHtml(entry.role)}: <b>${escapeHtml(entry.column)}</b>`).join(' \u00b7 ')}</p>` : ''}${item.blockers?.length ? `<p class="analysis-blocker"><strong>Revise o mapeamento</strong> ${item.blockers.map(escapeHtml).join(' ')}</p>` : ''}</div><p class="caveat">${escapeHtml(item.caveat)}</p>${item.id === 'refugo' ? '<p class="analysis-note refugo-guidance">Unidade defeituosa = pe\u00e7a \u00fanica rejeitada; ocorr\u00eancia = cada defeito, que pode se repetir na mesma pe\u00e7a. Custo unit\u00e1rio \u00e9 multiplicado pelas unidades rejeitadas; custo total por registro \u00e9 somado. Use apenas uma base de custo e confirme moeda e per\u00edodo. Grupo habilita estratifica\u00e7\u00e3o; a contagem n\u00e3o ajusta diferen\u00e7as de volume produzido.</p>' : ''}${scenarioParameterMarkup(item)}<details class="analyst-decision"><summary>Decisão do analista${summary}</summary><label>Como tratar esta oportunidade?<select data-decision-field="state"><option value="" ${!decision.state?'selected':''}>Ainda sem decisão</option><option value="priorizar" ${decision.state==='priorizar'?'selected':''}>Priorizar para investigação</option><option value="adiar" ${decision.state==='adiar'?'selected':''}>Adiar</option><option value="nao_aplicar" ${decision.state==='nao_aplicar'?'selected':''}>Não aplicar</option></select></label><label>Motivo da decisão<textarea data-decision-field="reason" rows="2" placeholder="Obrigatório ao adiar ou não aplicar">${escapeHtml(decision.reason || '')}</textarea></label><p class="decision-status" aria-live="polite">${escapeHtml(status)}</p></details><button type="button" class="run-analysis" ${item.status !== 'revisar' || item.blockers?.length || ['refugo','atributos'].includes(item.id) ? 'disabled' : ''}>${item.blockers?.length ? 'Revise o mapeamento de custo' : item.status === 'revisar' ? 'Executar an\u00e1lise \u2192' : 'Preencha os dados necess\u00e1rios'}</button><div class="analysis-output" aria-live="polite" hidden></div></article>`;
}

  $('suggestions').innerHTML = data.suggestions.map(renderSuggestionCard).join('');
  document.querySelectorAll('#suggestions [data-scenario]').forEach(refreshAnalysisEligibility);
  const pilotButton = document.querySelector('[data-scenario="piloto"] .run-analysis');
  if (pilotButton) { pilotButton.disabled = false; pilotButton.textContent = 'Configurar comparação do piloto →'; }
  $('case-workspace').hidden = false;
  renderProjectWorkspace();
  if (currentAnalyses.piloto) saveReport(currentMapping());
}

$('mapping-fields').addEventListener('change', () => {
  analysisVersion++;
  clearReport(true);
  setStep(2);
  mappingDirty = true;
  $('mapping-notice').hidden = false;
  document.querySelectorAll('.run-analysis').forEach((button) => { button.disabled = true; });
  document.querySelectorAll('.analysis-output').forEach((output) => { output.hidden = true; });
  renderPilotAvailability();
  renderPilotResult();
  if (currentAnalyses.piloto) saveReport(currentMapping());
});

$('suggestions').addEventListener('input', (event) => {
  if (event.target.dataset.decisionField === 'reason') updateOpportunityDecision(event.target.closest('[data-scenario]'));
});
$('suggestions').addEventListener('change', (event) => {
  if (event.target.dataset.decisionField === 'state') updateOpportunityDecision(event.target.closest('[data-scenario]'));
  if (event.target.dataset.analysisParam) {
    const card = event.target.closest('[data-scenario]');
    if (card.dataset.scenario === 'grupos') card.dataset.legacySnapshotParametersMissing = 'false';
    syncScenarioParameterFields(card);
    refreshAnalysisEligibility(card);
  }
});

function updateOpportunityDecision(card) {
  if (!card) return;
  const scenario = card.dataset.scenario;
  const state = card.querySelector('[data-decision-field="state"]').value;
  const reason = card.querySelector('[data-decision-field="reason"]').value.trim();
  if (!state) {
    delete projectState.decisions[scenario];
    card.querySelector('[data-decision-field="reason"]').value = '';
  }
  else projectState.decisions[scenario] = {
    title:card.querySelector('h3').textContent,
    state, reason, confirmed:state === 'priorizar' || Boolean(reason), updated_at:new Date().toISOString(),
  };
  const decision = projectState.decisions[scenario];
  card.querySelector('.decision-status').textContent = !decision ? 'A recomendação automática aguarda sua decisão.'
    : decision.confirmed ? `Decisão registrada: ${decisionLabel(decision.state)}.`
    : 'Informe o motivo para registrar esta decisão.';
  const suffix = decision ? ` · ${decisionLabel(decision.state)}${decision.confirmed ? '' : ' (motivo pendente)'}` : '';
  card.querySelector('.analyst-decision summary').textContent = `Decisão do analista${suffix}`;
  queueProjectSave();
  if (Object.keys(currentAnalyses).length) {
    const mapping = Object.fromEntries([...document.querySelectorAll('[data-role]')].map((select) => [select.dataset.role, select.value]));
    saveReport(mapping);
  }
}

$('suggestions').addEventListener('click', async (event) => {
  if (event.target.closest('.report-open')) { openReport(); return; }
  const button = event.target.closest('.run-analysis');
  if (!button || !currentFile) return;
  const card = button.closest('[data-scenario]');
  if (card.dataset.scenario === 'piloto') { openPilotPlan(); return; }
  const eligibility = analysisEligibility(card);
  if (!eligibility.eligible) { refreshAnalysisEligibility(card); return; }
  const parameters = structuredClone(eligibility.parameters);
  const scenario = card.dataset.scenario;
  const sourceFile = currentFile;
  const output = card.querySelector('.analysis-output');
  output.classList.remove('analysis-error');
  const mapping = {};
  document.querySelectorAll('[data-role]').forEach((select) => { mapping[select.dataset.role] = select.value; });
  const requestVersion = analysisVersion;
  analysesInFlight.add(scenario);
  refreshAnalysisEligibility(card);
  output.hidden = true;
  card.classList.remove('has-result');
  try {
    const requestBody = {filename:sourceFile.name, content:await readBase64(sourceFile), mapping, scenario, parameters};
    const response = await fetch('/api/analises', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(requestBody)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'N\u00e3o foi poss\u00edvel executar esta an\u00e1lise.');
    if (requestVersion !== analysisVersion) return;
    output.innerHTML = analysisMarkup(result);
    currentAnalyses[scenario] = result;
    executionHistory.push(result);
    pendingExecutions.push(result);
    renderExecutionHistory();
    saveReport(mapping);
    queueProjectSave();
    card.classList.add('has-result');
    output.hidden = false;
    setStep(4);
    requestAnimationFrame(() => goTo(output));
  } catch (error) {
    if (requestVersion === analysisVersion) {
      output.textContent = error instanceof TypeError ? 'N\u00e3o foi poss\u00edvel conectar ao servidor local. Reinicie a interface e tente novamente.' : error.message;
      output.classList.add('analysis-error');
      output.hidden = false;
    }
  } finally {
    analysesInFlight.delete(scenario);
    if (card.isConnected) refreshAnalysisEligibility(card);
    const currentCard = document.querySelector(`#suggestions [data-scenario="${CSS.escape(scenario)}"]`);
    if (currentCard && currentCard !== card) refreshAnalysisEligibility(currentCard);
  }
});

const PHASES = ['definir', 'medir', 'analisar', 'implementar', 'controlar'];
const CHARTER_FIELDS = ['problem', 'y', 'definition', 'unit', 'baseline', 'target', 'owner', 'sponsor'];
const MEASURE_FIELDS = ['source', 'unit', 'msa', 'notes'];
const CONTROL_FIELDS = ['metric', 'owner', 'frequency', 'reaction', 'standard'];

function readFields(prefix, keys) {
  return Object.fromEntries(keys.map((key) => [key, $(`${prefix}-${key}`).value]));
}

function collectProjectFields() {
  if ($('charter-problem')) {
    projectState.charter = readFields('charter', CHARTER_FIELDS);
    projectState.measure = readFields('measure', MEASURE_FIELDS);
    projectState.control = readFields('control', CONTROL_FIELDS);
    projectState.pilot = readPilotPlan();
  }
  return {
    title:$('project-title')?.value || 'Projeto de melhoria',
    objective:$('objective')?.value || '', phase:currentPhase,
    charter:projectState.charter, measure:projectState.measure,
    causes:projectState.causes, forces:projectState.forces,
    actions:projectState.actions, control:projectState.control, decisions:projectState.decisions, gateReviews:projectState.gateReviews, pilot:projectState.pilot,
  };
}

function fillProjectFields() {
  const context = projectState.charter || {};
  for (const key of CHARTER_FIELDS) if ($(`charter-${key}`)) $(`charter-${key}`).value = context[key] || '';
  const measure = projectState.measure || {};
  for (const key of MEASURE_FIELDS) if ($(`measure-${key}`)) $(`measure-${key}`).value = measure[key] || (key === 'msa' ? 'pendente' : '');
  const control = projectState.control || {};
  for (const key of CONTROL_FIELDS) if ($(`control-${key}`)) $(`control-${key}`).value = control[key] || '';
  fillPilotForm();
}

function resetProjectFields() {
  [...CHARTER_FIELDS.map((key) => `charter-${key}`), ...MEASURE_FIELDS.map((key) => `measure-${key}`),
    ...CONTROL_FIELDS.map((key) => `control-${key}`)].forEach((id) => { if ($(id)) $(id).value = ''; });
  if ($('measure-msa')) $('measure-msa').value = 'pendente';
  if ($('cause-list')) $('cause-list').innerHTML = '<p class="empty-state">Nenhuma causa potencial registrada.</p>';
  if ($('action-list')) $('action-list').innerHTML = '<p class="empty-state">Nenhuma ação registrada.</p>';
  if ($('force-list')) $('force-list').innerHTML = '';
  fillPilotForm();
  pilotRenderedResult = null;
  if ($('pilot-output')) { $('pilot-output').innerHTML = ''; $('pilot-output').hidden = true; }
  if ($('pilot-status')) $('pilot-status').textContent = '';
  if ($('pilot-result-notice')) $('pilot-result-notice').hidden = true;
}

function currentMapping() {
  return Object.fromEntries([...document.querySelectorAll('[data-role]')].map((select) => [select.dataset.role, select.value]));
}

function readPilotPlan() {
  const plan = {...emptyPilotPlan(), ...(projectState.pilot || {})};
  document.querySelectorAll('[data-pilot-field]').forEach((input) => {
    plan[input.dataset.pilotField] = input.type === 'checkbox' ? input.checked : input.value;
  });
  if (plan.kind === 'proportion') plan.unit = '%';
  return plan;
}

function fillPilotForm() {
  const plan = {...emptyPilotPlan(), ...(projectState.pilot || {})};
  projectState.pilot = plan;
  document.querySelectorAll('[data-pilot-field]').forEach((input) => {
    if (input.dataset.pilotField === 'action_id') return;
    if (input.type === 'checkbox') input.checked = plan[input.dataset.pilotField] === true;
    else input.value = plan[input.dataset.pilotField] ?? '';
  });
  renderPilotActions();
  renderPilotAvailability();
}

function renderPilotActions() {
  const select = $('pilot-action');
  if (!select) return;
  const plan = projectState.pilot || emptyPilotPlan();
  const actions = projectState.actions || [];
  const missingAction = plan.action_id && !actions.some((action) => action.id === plan.action_id);
  select.innerHTML = `<option value="">Sem ação relacionada · exploração</option>${actions.map((action) => `<option value="${escapeHtml(action.id)}">${escapeHtml(action.action)}</option>`).join('')}${missingAction ? `<option value="${escapeHtml(plan.action_id)}">Ação não disponível no plano atual · ${escapeHtml(plan.action_label || plan.action_id)}</option>` : ''}`;
  select.value = plan.action_id || '';
}

function normalizedPilotParameters(plan) {
  if (!plan || typeof plan !== 'object') return null;
  const result = {};
  Object.keys(emptyPilotPlan()).forEach((key) => {
    if (key === 'target') result[key] = plan[key] === '' || plan[key] == null ? '' : Number(plan[key]);
    else if (key.endsWith('_confirmed')) result[key] = plan[key] === true;
    else result[key] = String(plan[key] ?? '').trim();
  });
  return result;
}

function pilotExecutionParameters(result) {
  return result?.rastreabilidade?.parameters || result?.piloto?.parameters || null;
}

function mappingSignature(mapping) {
  return JSON.stringify(Object.entries(mapping || {}).filter(([,value]) => value).sort(([a],[b]) => a.localeCompare(b)));
}

function pilotResultWarning(result) {
  if (!result) return '';
  const frozen = pilotExecutionParameters(result);
  if (!frozen) return 'A execução preservada não registra parâmetros verificáveis. Ela não confirma o plano atual; configure e execute novamente para produzir um registro rastreável.';
  if (JSON.stringify(normalizedPilotParameters(frozen)) !== JSON.stringify(normalizedPilotParameters(projectState.pilot))) return 'O plano atual foi alterado após esta execução. O resultado abaixo permanece vinculado aos parâmetros originais registrados na rastreabilidade e não verifica o plano atual. Execute novamente para comparar o novo plano.';
  if (mappingDirty || !result.rastreabilidade?.mapping || mappingSignature(result.rastreabilidade.mapping) !== mappingSignature(currentMapping())) return 'O mapeamento atual está pendente ou difere do utilizado nesta execução. O resultado original foi preservado; atualize as sugestões e execute novamente antes de interpretar a comparação atual.';
  return '';
}

function renderPilotResult() {
  if (!$('pilot-output')) return;
  const result = currentAnalyses.piloto;
  const output = $('pilot-output');
  const notice = $('pilot-result-notice');
  if (!result) {
    output.hidden = true;
    notice.hidden = true;
    pilotRenderedResult = null;
    return;
  }
  if (pilotRenderedResult !== result) {
    output.innerHTML = analysisMarkup(result);
    pilotRenderedResult = result;
  }
  output.hidden = false;
  const warning = pilotResultWarning(result);
  notice.hidden = false;
  notice.classList.toggle('pilot-result-current', !warning);
  notice.textContent = warning || 'A execução abaixo utiliza os parâmetros do plano atual. Essa correspondência registra o cálculo realizado e não representa aprovação da eficácia da ação ou comprovação de causalidade.';
}

function renderPilotAvailability() {
  const button = $('pilot-run');
  if (!button) return;
  const plan = projectState.pilot || emptyPilotPlan();
  const mapping = currentMapping();
  const required = plan.kind === 'proportion' ? ['data','defeitos','total'] : ['data','medida'];
  const missing = required.filter((role) => !mapping[role]);
  $('pilot-mapping').textContent = mappingDirty ? 'Mapeamento alterado: clique em Atualizar sugestões antes de calcular.'
    : missing.length ? `Revise o mapeamento global: faltam ${missing.join(', ')} para este tipo de piloto.`
    : `Colunas utilizadas: ${required.map((role) => `${role} = ${mapping[role]}`).join(' · ')}. As datas devem representar o período real de cada observação.`;
  $('pilot-unit').readOnly = plan.kind === 'proportion';
  if (plan.kind === 'proportion') $('pilot-unit').value = '%';
  $('pilot-target').min = plan.kind === 'proportion' ? '0' : '';
  $('pilot-target').max = plan.kind === 'proportion' ? '100' : '';
  button.disabled = pilotRequestPending || exportingProject || workspaceSwitchPending || projectSavesPending > 0 || mappingDirty || !currentResult || missing.length > 0;
  button.textContent = pilotRequestPending ? 'Calculando comparação…' : 'Calcular comparação do piloto';
  $('save-project').disabled = pilotRequestPending || workspaceSwitchPending || autosaveSuspended;
  $('export-project').disabled = pilotRequestPending || exportingProject || workspaceSwitchPending || autosaveSuspended;
}

function openPilotPlan() {
  collectProjectFields();
  const plan = projectState.pilot;
  if (!plan.indicator) plan.indicator = projectState.charter.y || '';
  if (!plan.definition) plan.definition = projectState.charter.definition || '';
  if (!plan.unit) plan.unit = projectState.charter.unit || '';
  fillPilotForm();
  renderPilotResult();
  setPhase('implementar');
  goTo($('pilot-section'));
  $('pilot-section').focus({preventScroll:true});
}

function updatePilotPlan(event) {
  const previous = projectState.pilot || emptyPilotPlan();
  projectState.pilot = readPilotPlan();
  if (event?.target?.dataset.pilotField === 'action_id') {
    projectState.pilot.action_label = projectState.actions.find((action) => action.id === projectState.pilot.action_id)?.action || '';
  }
  if (previous.kind === 'proportion' && projectState.pilot.kind === 'continuous' && projectState.pilot.unit === '%') {
    projectState.pilot.unit = '';
    $('pilot-unit').value = '';
  }
  renderPilotAvailability();
  renderPilotResult();
  $('pilot-status').textContent = pilotRequestPending ? 'O plano foi editado durante o cálculo. O resultado retornará com os parâmetros originais e será identificado como anterior ao plano atual.' : '';
  queueProjectSave();
  if (currentResult && Object.keys(currentAnalyses).length) saveReport(currentMapping());
}

async function runPilot(event) {
  event.preventDefault();
  if (pilotRequestPending || exportingProject || workspaceSwitchPending || projectSavesPending > 0) return;
  const form = $('pilot-form');
  if (!form.reportValidity()) return;
  projectState.pilot = readPilotPlan();
  const parameters = normalizedPilotParameters(projectState.pilot);
  const status = $('pilot-status');
  const mapping = currentMapping();
  if (!currentFile || !currentResult || mappingDirty) { status.textContent = 'Analise a planilha e confirme o mapeamento antes de calcular o piloto.'; return; }
  if (parameters.before_start > parameters.before_end || parameters.after_start > parameters.after_end || parameters.before_end >= parameters.after_start) {
    status.textContent = 'Revise as janelas: início até fim em cada período, e o fim do antes deve ocorrer antes do início do depois. As datas são inclusivas e não podem se sobrepor.';
    return;
  }
  if (!Number.isFinite(parameters.target)) { status.textContent = 'Informe uma meta numérica finita na unidade do indicador.'; return; }
  if (!parameters.indicator || !parameters.definition || !parameters.unit || !parameters.comparability_notes || !parameters.independence_confirmed || !parameters.comparability_confirmed) {
    status.textContent = 'Preencha indicador, definição, unidade e nota de comparabilidade; revise e confirme as duas declarações.';
    return;
  }
  const sourceFile = currentFile;
  const requestVersion = analysisVersion;
  const controller = new AbortController();
  pilotRequestController = controller;
  pilotRequestPending = true;
  pilotSavePending = false;
  clearTimeout(autosaveTimer);
  autosaveTimer = null;
  renderPilotAvailability();
  status.textContent = 'Calculando com os parâmetros congelados desta solicitação…';
  try {
    const content = await readBase64(sourceFile);
    if (sourceFile !== currentFile || controller.signal.aborted) return;
    const response = await fetch('/api/analises', {method:'POST', headers:{'Content-Type':'application/json'}, signal:controller.signal,
      body:JSON.stringify({filename:sourceFile.name, content, mapping, scenario:'piloto', parameters})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Não foi possível comparar os períodos do piloto.');
    if (sourceFile !== currentFile || controller.signal.aborted) return;
    currentAnalyses.piloto = result;
    executionHistory.push(result);
    pendingExecutions.push(result);
    renderExecutionHistory();
    renderPilotResult();
    try { saveReport(currentMapping()); } catch (_) { /* O resultado permanece disponível na página. */ }
    status.textContent = requestVersion !== analysisVersion || pilotResultWarning(result)
      ? 'Comparação concluída e preservada com os parâmetros originais. Revise o aviso antes dos resultados.'
      : 'Comparação concluída. Revise a incerteza, a meta, as limitações e as demais mudanças no processo antes de avaliar a ação.';
    pilotSavePending = true;
    setStep(4);
    goTo($('pilot-result-notice'));
  } catch (error) {
    if (sourceFile === currentFile && !controller.signal.aborted) status.textContent = `Não foi possível calcular o piloto. ${error.message || 'Tente novamente.'} O resultado anterior, quando existente, foi preservado.`;
  } finally {
    if (pilotRequestController === controller) {
      pilotRequestController = null;
      pilotRequestPending = false;
      renderPilotAvailability();
      if (pilotSavePending) { pilotSavePending = false; queueProjectSave(); }
    }
  }
}

function setPhase(phase) {
  if (!PHASES.includes(phase)) return;
  currentPhase = phase;
  document.querySelectorAll('.dmaic-tabs [data-phase]').forEach((button) => {
    const active = button.dataset.phase === phase;
    button.setAttribute('aria-selected', String(active));
    button.tabIndex = active ? 0 : -1;
  });
  document.querySelectorAll('.phase-panel').forEach((panel) => { panel.hidden = panel.id !== `phase-${phase}`; });
  renderPhaseChecks();
  queueProjectSave();
}

function phaseGates() {
  const c = projectState.charter || {};
  const m = projectState.measure || {};
  const control = projectState.control || {};
  const causes = projectState.causes || [];
  const actions = projectState.actions || [];
  const hasData = Boolean(currentFile && currentResult);
  const validCauseIds = new Set(causes.filter((cause) => cause.status === 'validada').map((cause) => cause.id));
  const requirements = {
    definir: [
      ['problema', 'Problema, local e período delimitados', Boolean(c.problem?.trim())],
      ['indicador', 'Indicador Y, definição operacional e unidade', Boolean(c.y?.trim() && c.definition?.trim() && c.unit?.trim())],
      ['meta', 'Linha de base e meta registradas', Boolean(c.baseline?.trim() && c.target?.trim())],
      ['responsaveis', 'Responsável e patrocinador/dono do processo', Boolean(c.owner?.trim() && c.sponsor?.trim())],
    ],
    medir: [
      ['dados', 'Dados da linha de base analisados', hasData],
      ['coleta', 'Fonte, amostragem e unidade experimental descritas', Boolean(m.source?.trim() && m.unit?.trim())],
      ['medicao', 'Sistema de medição avaliado ou não aplicabilidade justificada', Boolean(m.msa && m.msa !== 'pendente')],
      ['limitacoes', 'Observações e limitações registradas', Boolean(m.notes?.trim())],
    ],
    analisar: [
      ['resultados', 'Ao menos uma execução analítica registrada', Object.keys(currentAnalyses).some((key) => key !== 'piloto')],
      ['causas', 'Causa investigada com evidência e estado explícito', causes.some((cause) => cause.evidence?.trim() && ['validada','refutada','inconclusiva'].includes(cause.status))],
    ],
    implementar: [
      ['acao', 'Ação ligada a causa validada, com responsável e verificação', actions.some((action) => validCauseIds.has(action.causeId) && action.action?.trim() && action.owner?.trim() && action.verification?.trim())],
      ['piloto', 'Plano e resultado de piloto registrados', Boolean(currentAnalyses.piloto && projectState.pilot?.indicator?.trim() && projectState.pilot?.comparability_notes?.trim())],
    ],
    controlar: [
      ['monitoramento', 'Indicador, responsável, frequência e fonte definidos', Boolean(control.metric?.trim() && control.owner?.trim() && control.frequency?.trim())],
      ['reacao', 'Regra de reação e padrão de trabalho definidos', Boolean(control.reaction?.trim() && control.standard?.trim())],
    ],
  };
  const labels = {definir:'Definir',medir:'Medir',analisar:'Analisar',implementar:'Implementar',controlar:'Controlar'};
  return Object.fromEntries(Object.entries(requirements).map(([phase, items]) => {
    const reviews = projectState.gateReviews?.[phase] || {};
    const checks = items.map(([key, label, ready]) => {
      const review = reviews[key] || {};
      const reviewer = Boolean(review.reviewer?.trim());
      const accepted = review.status === 'adequate' && ready && reviewer && Boolean(review.evidence?.trim());
      const exception = review.status === 'not_applicable' && reviewer && Boolean(review.reason?.trim());
      const resolved = accepted || exception;
      const status = accepted ? 'Revisado como adequado' : exception ? 'Exceção local justificada'
        : review.status === 'inadequate' ? 'Correção necessária' : !ready ? 'Informação pendente' : 'Aguardando revisão';
      return {phase, key, label, ready, review, resolved, exception, status};
    });
    const ok = checks.every((item) => item.resolved);
    const pending = !ok && checks.every((item) => (item.ready && item.review.status !== 'inadequate') || item.exception);
    const exceptionCount = checks.filter((item) => item.exception).length;
    const text = ok ? `${checks.length} requisito(s) revisado(s); ${exceptionCount} exceção(ões) justificada(s).`
      : checks.filter((item) => !item.resolved).map((item) => `${item.label}: ${item.status.toLowerCase()}.`).join(' ');
    return [phase, {ok, pending, exceptionCount, text, label:labels[phase], checks}];
  }));
}

function renderPhaseChecks() {
  const gates = phaseGates();
  const guidance = $('phase-guidance');
  const reviewPanelOpen = guidance.querySelector('.gate-review-panel')?.open || false;
  const activeField = document.activeElement?.matches('[data-gate-phase][data-gate-key][data-gate-field]')
    ? {...document.activeElement.dataset} : null;
  document.querySelectorAll('.dmaic-tabs [data-phase]').forEach((button) => {
    const gate = gates[button.dataset.phase];
    const mark = button.querySelector('small');
    if (mark) mark.textContent = gate.ok ? '\u2713' : gate.pending ? '\u2026' : '\u2022';
    button.classList.toggle('gate-met', gate.ok);
    button.classList.toggle('gate-pending-review', gate.pending);
  });
  const gate = gates[currentPhase];
  const summary = gate.ok ? `Revisão registrada \u00b7 ${gate.label}` : gate.pending ? `Aguardando revisão \u00b7 ${gate.label}` : `Pendências da fase \u00b7 ${gate.label}`;
  const cards = gate.checks.map((item) => {
    const review = item.review;
    return `<article class="gate-review-card"><div class="gate-review-heading"><strong>${escapeHtml(item.label)}</strong><span class="gate-review-status ${item.resolved ? 'is-resolved' : item.review.status === 'inadequate' ? 'needs-correction' : ''}">${escapeHtml(item.status)}</span></div><p class="gate-prerequisite">${item.ready ? 'Informação registrada no projeto.' : 'Complete a informação correspondente na fase antes de marcar como adequada.'}</p><div class="gate-review-fields"><label>Estado da revisão<select data-gate-phase="${item.phase}" data-gate-key="${item.key}" data-gate-field="status"><option value="pending" ${(!review.status || review.status==='pending')?'selected':''}>Aguardando revisão</option><option value="adequate" ${review.status==='adequate'?'selected':''}>Revisado: adequado</option><option value="inadequate" ${review.status==='inadequate'?'selected':''}>Revisado: precisa de correção</option><option value="not_applicable" ${review.status==='not_applicable'?'selected':''}>Não aplicável: justificar exceção</option></select></label><label>Revisor (nome/função)<input maxlength="120" data-gate-phase="${item.phase}" data-gate-key="${item.key}" data-gate-field="reviewer" value="${escapeHtml(review.reviewer || '')}" placeholder="Identificação declarada"></label><label>Referência da evidência<input maxlength="500" data-gate-phase="${item.phase}" data-gate-key="${item.key}" data-gate-field="evidence" value="${escapeHtml(review.evidence || '')}" placeholder="Arquivo, registro, análise, ata ou local da evidência"></label><label>Justificativa / observação<textarea rows="2" maxlength="1200" data-gate-phase="${item.phase}" data-gate-key="${item.key}" data-gate-field="reason" placeholder="Obrigatória para correção necessária ou exceção">${escapeHtml(review.reason || '')}</textarea></label></div>${review.reviewed_at ? `<small>Revisão registrada em ${escapeHtml(review.reviewed_at)}</small>` : ''}</article>`;
  }).join('');
  guidance.innerHTML = `<strong>${summary}</strong><span>${escapeHtml(gate.text)} Uma revisão registrada não certifica validade estatística nem aprova automaticamente uma passagem DMAIC.</span><details class="gate-review-panel"><summary>Revisar evidências e critérios (${gate.checks.filter((item) => item.resolved).length}/${gate.checks.length})</summary><p class="gate-local-limit">O SigmaFlow local não autentica revisores. O nome informado é uma declaração no registro, não uma identidade verificada.</p><div class="gate-review-list">${cards}</div></details>`;
  const reviewPanel = guidance.querySelector('.gate-review-panel');
  if (reviewPanel) reviewPanel.open = reviewPanelOpen;
  if (activeField) {
    const selector = `[data-gate-phase="${activeField.gatePhase}"][data-gate-key="${activeField.gateKey}"][data-gate-field="${activeField.gateField}"]`;
    guidance.querySelector(selector)?.focus();
  }
  const checkIds = {medir:'measure-check',analisar:'analyze-check',implementar:'improve-check',controlar:'control-check'};
  for (const [phase,id] of Object.entries(checkIds)) {
    if ($(id)) $(id).textContent = `${gates[phase].ok ? '\u2713' : gates[phase].pending ? '\u2026' : '\u2022'} ${gates[phase].text}`;
  }
}

$('phase-guidance').addEventListener('input', (event) => {
  const field = event.target.closest('[data-gate-phase][data-gate-key][data-gate-field]');
  if (!field) return;
  const {gatePhase, gateKey, gateField} = field.dataset;
  projectState.gateReviews ||= {};
  projectState.gateReviews[gatePhase] ||= {};
  const review = projectState.gateReviews[gatePhase][gateKey] ||= {status:'pending', reviewer:'', evidence:'', reason:'', reviewed_at:''};
  review[gateField] = field.value;
  if (gateField === 'status') review.reviewed_at = field.value === 'pending' ? '' : new Date().toISOString();
  queueProjectSave();
});
$('phase-guidance').addEventListener('change', (event) => {
  if (event.target.matches('[data-gate-phase][data-gate-key][data-gate-field]')) renderPhaseChecks();
});

function renderCauses() {
  const list = $('cause-list');
  if (!projectState.causes.length) list.innerHTML = '<p class="empty-state">Nenhuma causa potencial registrada.</p>';
  else list.innerHTML = projectState.causes.map((cause, index) => {
    const priority = Number(cause.impact || 3) * Number(cause.frequency || 3);
    return `<article class="cause-card" data-cause-index="${index}"><div class="cause-card-top"><div><span class="cause-category">${escapeHtml(cause.category)}</span><h4>${escapeHtml(cause.text)}</h4></div><button type="button" class="text-button danger-text" data-remove-cause="${index}">Remover</button></div><div class="cause-rating"><label>Impacto<select data-cause-field="impact">${[1,2,3,4,5].map((n) => `<option value="${n}" ${Number(cause.impact || 3)===n?'selected':''}>${n}</option>`).join('')}</select></label><label>Frequência percebida<select data-cause-field="frequency">${[1,2,3,4,5].map((n) => `<option value="${n}" ${Number(cause.frequency || 3)===n?'selected':''}>${n}</option>`).join('')}</select></label><label>Estado<select data-cause-field="status"><option value="hipotese" ${cause.status==='hipotese'?'selected':''}>Hipótese</option><option value="priorizada" ${cause.status==='priorizada'?'selected':''}>Priorizada para investigar</option><option value="validada" ${cause.status==='validada'?'selected':''}>Validada pela equipe</option><option value="refutada" ${cause.status==='refutada'?'selected':''}>Refutada</option><option value="inconclusiva" ${cause.status==='inconclusiva'?'selected':''}>Inconclusiva</option></select></label><strong>Prioridade qualitativa: ${priority}/25</strong></div><details><summary>Registrar evidências e 5 porquês</summary><label>Evidência observada<textarea rows="3" data-cause-field="evidence" placeholder="Fonte, período, observação ou teste que sustenta ou contradiz a hipótese">${escapeHtml(cause.evidence || '')}</textarea></label><div class="why-grid">${[0,1,2,3,4].map((n) => `<label>${n+1}º por quê<textarea rows="2" data-why-index="${n}" placeholder="${n===0?'Por que o problema ocorre?':'Por que a resposta anterior acontece?'}">${escapeHtml(cause.whys?.[n] || '')}</textarea></label>`).join('')}</div><p class="analysis-note">A cadeia pode ramificar ou parar antes de cinco perguntas. Verifique cada resposta com evidência; cinco respostas não garantem uma causa raiz.</p></details></article>`;
  }).join('');
  const options = projectState.causes.map((cause) => `<option value="${escapeHtml(cause.id)}">${escapeHtml(cause.category)} · ${escapeHtml(cause.text)}</option>`).join('');
  $('action-cause').innerHTML = `<option value="">Selecione uma causa</option>${options}`;
  renderPhaseChecks();
}

function renderForces() {
  $('force-list').innerHTML = projectState.forces.map((force,index) => `<div class="force-row ${force.kind==='barreira'?'force-barrier':''}"><span>${force.kind==='barreira'?'Barreira':'Apoio'} · impacto ${Number(force.impact)}</span><strong>${escapeHtml(force.text)}</strong><button type="button" class="text-button danger-text" data-remove-force="${index}">Remover</button></div>`).join('');
}

function renderActions() {
  const list = $('action-list');
  if (!projectState.actions.length) list.innerHTML = '<p class="empty-state">Nenhuma ação registrada.</p>';
  else list.innerHTML = projectState.actions.map((action,index) => {
    const cause = projectState.causes.find((item) => item.id === action.causeId);
    const score = (Number(action.impact)||1) / Math.max(1,Number(action.effort)||1);
    return `<article class="action-card" data-action-index="${index}"><div><span class="cause-category">${escapeHtml(action.status || 'planejada')} · prioridade impacto/esforço ${score.toFixed(2)}</span><h4>${escapeHtml(action.action)}</h4><p>${cause ? `Causa: ${escapeHtml(cause.text)}` : 'Sem causa relacionada'} · Responsável: ${escapeHtml(action.owner || 'não definido')} · Prazo: ${escapeHtml(action.due || 'não definido')}</p><p><strong>Verificação:</strong> ${escapeHtml(action.verification || 'não definida')}</p></div><label>Andamento<select data-action-field="status"><option ${action.status==='planejada'?'selected':''}>planejada</option><option ${action.status==='em andamento'?'selected':''}>em andamento</option><option ${action.status==='implantada'?'selected':''}>implantada</option><option ${action.status==='cancelada'?'selected':''}>cancelada</option></select></label><button type="button" class="text-button danger-text" data-remove-action="${index}">Remover</button></article>`;
  }).join('');
  renderPilotActions();
  renderPhaseChecks();
}

function renderProjectWorkspace() {
  if (!$('case-workspace')) return;
  if (!$('case-workspace').hidden) {
    renderCauses(); renderForces(); renderActions(); setPhase(currentPhase); renderPilotAvailability(); renderPilotResult();
  }
}

function projectPayload(id, baseVersion) {
  const form = collectProjectFields();
  const file = currentFile;
  const mapping = {};
  document.querySelectorAll('[data-role]').forEach((select) => { mapping[select.dataset.role] = select.value; });
  const payload = JSON.parse(JSON.stringify({
    id, base_version:baseVersion, title:form.title, objective:form.objective, phase:form.phase, mapping,
    analyses:currentAnalyses, diagnosis:currentResult, investigation:{charter:form.charter,measure:form.measure,causes:form.causes,forces:form.forces,decisions:form.decisions,gate_reviews:form.gateReviews,pilot:form.pilot},
    new_executions:pendingExecutions,
    actions:form.actions, control:form.control, filename:file.name,
  }));
  return readBase64(file).then((file_base64) => ({...payload, file_base64}));
}

function renderWorkspaceConflict(message = '') {
  const box = $('workspace-concurrency');
  if (!box) return;
  box.hidden = !autosaveSuspended;
  if (message) $('workspace-conflict-message').textContent = message;
  else if (autosaveSuspended) $('workspace-conflict-message').textContent = `A versão em edição é ${currentCaseVersion || 'nova'}, mas outra operação confirmou a versão ${workspaceConflictVersion ?? 'mais recente'}. Sua planilha, resultados e anotações continuam nesta tela. Reabra a versão atual salva ou preserve esta edição em um novo projeto.`;
}

function suspendWorkspaceAutosave(currentVersion, message = '') {
  autosaveSuspended = true;
  workspaceConflictVersion = currentVersion;
  clearTimeout(autosaveTimer);
  autosaveTimer = null;
  $('save-status').textContent = 'Conflito de versão: edição preservada; salvamento automático suspenso.';
  renderWorkspaceConflict(message);
  renderWorkspaceControls();
}

function renderWorkspaceControls() {
  renderPilotAvailability();
  if ($('load-project')) $('load-project').disabled = workspaceSwitchPending || !$('saved-project-list').value;
  if ($('delete-project')) $('delete-project').disabled = workspaceSwitchPending || !$('saved-project-list').value;
  if ($('history-project')) $('history-project').disabled = !$('saved-project-list').value;
  if ($('reload-current-project')) $('reload-current-project').disabled = !currentCaseId || workspaceSwitchPending || projectSavesPending > 0;
  if ($('show-save-copy')) $('show-save-copy').disabled = !currentResult || pilotRequestPending || workspaceSwitchPending || exportingProject;
  if ($('save-project-copy')) $('save-project-copy').disabled = pilotRequestPending || workspaceSwitchPending || projectSavesPending > 0 || exportingProject;
  ['analyze','reanalyze','reanalyze-bottom'].forEach((id) => { $(id).disabled = workspaceSwitchPending; });
  document.querySelector('.input-grid').inert = workspaceSwitchPending;
  $('results').inert = workspaceSwitchPending;
}

function showWorkspaceCopy() {
  const title = $('project-title').value.trim() || 'Projeto de melhoria';
  $('workspace-copy-title').value = `${title.slice(0, 135)} (cópia da edição)`;
  $('workspace-copy-status').textContent = '';
  $('workspace-copy-panel').hidden = false;
  goTo($('workspace-copy-panel'));
  $('workspace-copy-title').focus();
}

async function persistProject(showMessage = false, {asNew = false, title = null} = {}) {
  if (workspaceSwitchPending) return null;
  if (autosaveSuspended && !asNew) {
    renderWorkspaceConflict();
    if (showMessage) $('save-status').textContent = 'O salvamento está suspenso por conflito. Reabra a versão salva ou use Salvar como novo projeto.';
    return null;
  }
  if (pilotRequestPending) {
    pilotSavePending = true;
    $('save-status').textContent = 'Aguarde o cálculo do piloto; o salvamento será retomado após a conclusão.';
    return null;
  }
  if (!currentFile || !currentResult) {
    if (showMessage) showError('Analise uma planilha antes de salvar o projeto.');
    return null;
  }
  if (!$('project-title').value.trim()) {
    $('save-status').textContent = 'Informe o nome do projeto.';
    return null;
  }
  clearTimeout(autosaveTimer);
  autosaveTimer = null;
  const sourceFile = currentFile;
  const sourceEpoch = workspaceEpoch;
  projectSavesPending++;
  renderWorkspaceControls();
  const saveOperation = projectSaveQueue.then(async () => {
    if (currentFile !== sourceFile || workspaceEpoch !== sourceEpoch) throw new Error('O projeto em edição mudou durante o salvamento. Nenhuma edição de outro projeto será enviada.');
    if (autosaveSuspended && !asNew) throw new Error('O salvamento foi suspenso após um conflito; preserve a edição em um novo projeto ou reabra a versão salva.');
    const id = asNew ? crypto.randomUUID() : currentCaseId || crypto.randomUUID();
    const baseVersion = asNew || !currentCaseId ? 0 : currentCaseVersion;
    const capturedEdits = workspaceEditVersion;
    const payload = await projectPayload(id, baseVersion);
    if (asNew) payload.new_executions = executionHistory;
    const submittedRunIds = payload.new_executions.map((run) => run.rastreabilidade?.run_id).filter(Boolean);
    if (asNew) payload.title = title;
    if (currentFile !== sourceFile || workspaceEpoch !== sourceEpoch) throw new Error('O projeto em edição mudou durante o salvamento. Nenhuma edição de outro projeto será enviada.');
    const result = await window.SigmaFlowCases.save(payload);
    const submittedIds = new Set(submittedRunIds);
    pendingExecutions = pendingExecutions.filter((run) => !submittedIds.has(run.rastreabilidade?.run_id));
    if (result?.id !== id || !Number.isInteger(result.version) || result.version < 1) throw new Error('O servidor não confirmou o projeto e a versão salvos.');
    if (currentFile === sourceFile && workspaceEpoch === sourceEpoch) {
      currentCaseId = result.id;
      currentCaseVersion = result.version;
      savedEditVersion = capturedEdits;
      if (asNew) {
        $('project-title').value = title;
        autosaveSuspended = false;
        workspaceConflictVersion = null;
        renderWorkspaceConflict();
      }
      $('save-status').textContent = workspaceEditVersion === capturedEdits
        ? `Salvo neste computador · versão ${result.version} · ${new Date(result.updated_at).toLocaleString('pt-BR')}`
        : `Versão ${result.version} salva; alterações locais posteriores ainda aguardam salvamento.`;
      await refreshProjectList(result.id);
    }
    return result;
  });
  projectSaveQueue = saveOperation.catch(() => null);
  try {
    return await saveOperation;
  } catch (error) {
    if (currentFile === sourceFile && workspaceEpoch === sourceEpoch) {
      if (error.code === 'version_conflict') suspendWorkspaceAutosave(error.current_version);
      else if (!autosaveSuspended) $('save-status').textContent = 'Não foi possível salvar. A edição permanece nesta tela.';
    }
    if (showMessage) showError(error.message);
    return null;
  } finally {
    projectSavesPending--;
    renderWorkspaceControls();
  }
}

function queueProjectSave() {
  if (restoringProject) return;
  workspaceEditVersion++;
  if (autosaveSuspended) { clearTimeout(autosaveTimer); renderWorkspaceConflict(); return; }
  if (workspaceSwitchPending) { clearTimeout(autosaveTimer); return; }
  if (pilotRequestPending) {
    clearTimeout(autosaveTimer);
    pilotSavePending = true;
    $('save-status').textContent = 'Alterações serão salvas após o cálculo do piloto…';
    return;
  }
  if (exportingProject) {
    $('save-status').textContent = 'Alterações ainda não salvas…';
    clearTimeout(autosaveTimer);
    exportSavePending = true;
    return;
  }
  if (!currentCaseId) return;
  $('save-status').textContent = 'Alterações ainda não salvas…';
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(() => persistProject(false), 1500);
}

async function exportProject() {
  if (exportingProject || workspaceSwitchPending || autosaveSuspended) return;
  const button = $('export-project');
  const status = $('export-status');
  const sourceFile = currentFile;
  const sourceAnalysisVersion = analysisVersion;
  if (pilotRequestPending) { status.textContent = 'Aguarde o cálculo do piloto antes de baixar o pacote.'; return; }
  if (mappingDirty) {
    status.textContent = 'Atualize as sugestões para confirmar o mapeamento antes de baixar o pacote.';
    goTo($('mapeamento'));
    return;
  }
  exportingProject = true;
  renderPilotAvailability();
  exportSavePending = false;
  clearTimeout(autosaveTimer);
  autosaveTimer = null;
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  button.textContent = 'Preparando pacote…';
  status.textContent = 'Salvando o estado atual antes de preparar o pacote…';
  let objectUrl = null;
  try {
    const saved = await persistProject(true);
    if (!saved) throw new Error('O pacote não foi baixado porque o estado atual não pôde ser salvo. Verifique a planilha e o nome do projeto.');
    if (currentFile !== sourceFile || mappingDirty || sourceAnalysisVersion !== analysisVersion) throw new Error('A planilha ou o mapeamento mudou durante o salvamento. Atualize as sugestões e baixe o pacote novamente.');
    if (exportSavePending) throw new Error('O projeto recebeu alterações durante o salvamento. Aguarde o salvamento automático e baixe o pacote novamente.');
    const {id, version} = saved;
    status.textContent = `Preparando o pacote da versão ${version}…`;
    const {blob, filename} = await window.SigmaFlowCases.export(id, version);
    if (currentFile !== sourceFile || mappingDirty || sourceAnalysisVersion !== analysisVersion || exportSavePending) throw new Error('O projeto recebeu alterações durante a preparação do pacote. Aguarde o salvamento e baixe novamente para incluir o estado atual.');
    objectUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = filename;
    link.hidden = true;
    document.body.appendChild(link);
    link.click();
    link.remove();
    status.textContent = `Pacote da versão ${version} preparado. Download solicitado ao navegador.`;
  } catch (error) {
    status.textContent = `Não foi possível baixar o pacote. ${error.message || 'Tente novamente.'}`;
  } finally {
    if (objectUrl) setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    exportingProject = false;
    button.disabled = false;
    button.removeAttribute('aria-busy');
    button.textContent = 'Baixar pacote do projeto';
    renderPilotAvailability();
    if (exportSavePending) { exportSavePending = false; queueProjectSave(); }
  }
}

async function refreshProjectList(preferredId = null) {
  const select = $('saved-project-list');
  if (!select || !window.SigmaFlowCases) return;
  const request = ++projectListRequest;
  try {
    const {projects} = await window.SigmaFlowCases.list();
    if (request !== projectListRequest) return;
    const desiredId = preferredId || select.value || currentCaseId || '';
    select.innerHTML = projects.length ? `<option value="">Selecione um projeto salvo</option>${projects.map((p) => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.title)} · v${Number(p.version)} · ${escapeHtml(new Date(p.updated_at).toLocaleDateString('pt-BR'))}</option>`).join('')}` : '<option value="">Nenhum projeto salvo</option>';
    select.value = desiredId;
    renderWorkspaceControls();
  } catch (_) {
    if (request !== projectListRequest) return;
    select.innerHTML = '<option value="">Armazenamento local indisponível</option>';
    renderWorkspaceControls();
  }
}

function renderHistoryVersions() {
  const container = $('history-list');
  if (!container) return;
  container.innerHTML = historyState.versions.map((item) => {
    const integrity = item.readable ? (item.metadata_integrity === 'hash_checked' ? 'Metadados conferidos por hash' : 'Revis\u00e3o legada sem hash dos metadados') : `Indispon\u00edvel: ${item.error || 'registro inv\u00e1lido'}`;
    const event = item.revision_event?.type || 'revis\u00e3o salva';
    return `<article class="history-version"><div><strong>v${Number(item.version)} ? ${escapeHtml(item.title || 'Projeto sem t\u00edtulo')}</strong><p>${escapeHtml(event)} ? ${escapeHtml(item.phase || 'fase n\u00e3o registrada')} ? ${escapeHtml(item.updated_at ? new Date(item.updated_at).toLocaleString('pt-BR') : 'data indispon\u00edvel')}</p><small>${escapeHtml(integrity)}</small></div><div class="history-buttons"><button type="button" class="outline-button" data-history-report="${Number(item.version)}" ${item.readable ? '' : 'disabled'}>Ver relat\u00f3rio</button><button type="button" class="outline-button" data-history-export="${Number(item.version)}" ${item.readable ? '' : 'disabled'}>Baixar pacote</button><button type="button" class="outline-button" data-history-copy="${Number(item.version)}" ${item.readable ? '' : 'disabled'}>Copiar</button><button type="button" class="outline-button" data-history-restore="${Number(item.version)}" ${item.readable && !item.is_current ? '' : 'disabled'}>Restaurar como nova vers\u00e3o</button></div></article>`;
  }).join('') || '<p>Nenhuma vers\u00e3o salva.</p>';
  $('history-older').hidden = !historyState.nextBefore;
}

async function loadHistoryPage(reset = false) {
  if (!historyState.id || historyState.busy) return;
  const id = historyState.id, generation = historyState.generation;
  historyState.busy = true;
  $('history-status').textContent = 'Carregando vers\u00f5es salvas';
  try {
    const page = await window.SigmaFlowCases.history(id, {limit:25, before:reset ? null : historyState.nextBefore});
    if (generation !== historyState.generation || id !== historyState.id) return;
    historyState.headVersion = page.current_version;
    historyState.nextBefore = page.next_before;
    historyState.versions = reset ? page.versions : historyState.versions.concat(page.versions);
    renderHistoryVersions();
    $('history-context').textContent = `${historyState.versions.length} revis\u00f5es listada(s) \u00b7 atual v${page.current_version}. O hist\u00f3rico n\u00e3o recalcula as an\u00e1lises.`;
    $('history-status').textContent = '';
  } catch (error) {
    if (generation === historyState.generation) $('history-status').textContent = `N\u00e3o foi poss\u00edvel carregar o hist\u00f3rico. ${error.message}`;
  } finally {
    if (generation === historyState.generation) historyState.busy = false;
  }
}

function showHistory(id = $('saved-project-list').value) {
  if (!id) return;
  historyState = {...historyState, id, generation:historyState.generation + 1, versions:[], nextBefore:null, headVersion:null, recovery:null, createdId:null};
  $('history-inspection').hidden = true;
  $('history-recovery').hidden = true;
  $('history-open-created').hidden = true;
  $('project-history').hidden = false;
  goTo($('project-history'));
  loadHistoryPage(true);
}

async function inspectHistoryVersion(version, mode) {
  const id = historyState.id, generation = historyState.generation;
  if (!id) return;
  $('history-inspection').hidden = false;
  $('history-inspection').innerHTML = '<p>Carregando revis\u00e3o salva</p>';
  try {
    if (mode === 'report') {
      const html = await window.SigmaFlowCases.versionReport(id, version);
      if (generation !== historyState.generation) return;
      $('history-inspection').innerHTML = `<h3>Relat\u00f3rio salvo \u00b7 v${version}</h3><iframe title="Relat\u00f3rio da revis\u00e3o v${version}" sandbox="allow-scripts" class="history-report-frame"></iframe>`;
      $('history-inspection').querySelector('iframe').srcdoc = html;
    } else {
      const project = await window.SigmaFlowCases.version(id, version);
      if (generation !== historyState.generation) return;
      $('history-inspection').innerHTML = `<h3>Dados da revis\u00e3o v${version}</h3><p><strong>${escapeHtml(project.title)}</strong> ? ${escapeHtml(project.phase)} ? ${escapeHtml(project.filename)}</p><p>SHA-256 da planilha: <code>${escapeHtml(project.dataset_sha256)}</code></p><p>${Object.keys(project.analyses || {}).length} an\u00e1lise(s) registrada(s). Consulte o relat\u00f3rio salvo ou baixe o pacote para ver os resultados e rastreabilidade.</p>`;
    }
  } catch (error) {
    if (generation === historyState.generation) $('history-inspection').innerHTML = `<p role="alert">${escapeHtml(error.message)}</p>`;
  }
}

function requestHistoryRecovery(operation, version) {
  historyState.recovery = {operation, version, id:historyState.id, generation:historyState.generation};
  const copying = operation === 'copy';
  $('history-recovery-title').textContent = copying ? `Copiar a revis\u00e3o v${version} para outro projeto` : `Restaurar a revis\u00e3o v${version} como uma nova vers\u00e3o`;
  $('history-recovery-description').textContent = copying ? 'A c\u00f3pia ter\u00e1 outro identificador e manter\u00e1 a rela\u00e7\u00e3o com o projeto de origem.' : 'A vers\u00e3o atual continuar? no hist\u00f3rico. A restaura??o ser? gravada como a pr?xima vers\u00e3o e exige a vers\u00e3o atual conhecida.';
  $('history-copy-title-label').hidden = !copying;
  const source = historyState.versions.find((item) => item.version === version);
  $('history-copy-title').value = copying ? `${(source?.title || 'Projeto').slice(0,130)} ? c\u00f3pia v${version}` : '';
  $('history-recovery-reason').value = '';
  $('history-recovery-status').textContent = '';
  $('history-recovery').hidden = false;
  $('history-recovery-confirm').disabled = false;
  $('history-recovery-confirm').textContent = copying ? 'Criar c\u00f3pia' : 'Criar nova revis\u00e3o';
  $('history-recovery').scrollIntoView({behavior:'smooth', block:'center'});
}

async function submitHistoryRecovery(event) {
  event.preventDefault();
  const request = historyState.recovery;
  if (!request || request.generation !== historyState.generation || request.id !== historyState.id) return;
  const reason = $('history-recovery-reason').value.trim();
  if (!reason) { $('history-recovery-reason').focus(); return; }
  $('history-recovery-confirm').disabled = true;
  $('history-recovery-status').textContent = 'Registrando a opera\u00e7\u00e3o?';
  try {
    let result;
    if (request.operation === 'copy') {
      result = await window.SigmaFlowCases.copyVersion(request.id, request.version, {title:$('history-copy-title').value.trim(), reason});
      historyState.createdId = result.id;
      $('history-recovery-status').textContent = `C\u00f3pia criada como ${result.title}, v${result.version}. O projeto de origem foi preservado.`;
      $('history-open-created').hidden = false;
      await refreshProjectList(result.id);
    } else {
      const expected = historyState.headVersion;
      result = await window.SigmaFlowCases.restoreVersion(request.id, request.version, {base_version:expected, reason});
      $('history-recovery-status').textContent = `Restaura\u00e7\u00e3o registrada como v${result.version}. As vers\u00f5es anteriores permanecem no hist\u00f3rico.`;
      if (currentCaseId === request.id) suspendWorkspaceAutosave(result.version, `O hist\u00f3rico criou a v${result.version}. Sua edi\u00e7\u00e3o em tela continua preservada; reabra a vers\u00e3o atual ou salve essa edi\u00e7\u00e3o como novo projeto.`);
      await loadHistoryPage(true);
      await refreshProjectList(request.id);
    }
  } catch (error) {
    $('history-recovery-status').textContent = error.code === 'version_conflict' ? `O projeto avan\u00e7ou para v${error.current_version}; atualize o hist\u00f3rico antes de restaurar.` : `N\u00e3o foi poss\u00edvel concluir. ${error.message}`;
    if (error.code === 'version_conflict') await loadHistoryPage(true);
  } finally {
    $('history-recovery-confirm').disabled = false;
  }
}

async function exportHistoryVersion(version) {
  try {
    const {blob, filename} = await window.SigmaFlowCases.export(historyState.id, version);
    const url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url; link.download = filename; link.hidden = true; document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    $('history-status').textContent = `Download da revis\u00e3o v${version} solicitado ao navegador.`;
  } catch (error) { $('history-status').textContent = `N\u00e3o foi poss\u00edvel exportar v${version}. ${error.message}`; }
}

async function openSavedProject() {
  const id = $('saved-project-list').value;
  return openProjectById(id);
}

async function openProjectById(id) {
  if (!id) return false;
  const request = await prepareWorkspaceSwitch();
  if (request == null) return false;
  const sourceEpoch = workspaceEpoch;
  const sourceEdits = workspaceEditVersion;
  $('load-project').textContent = 'Abrindo…';
  try {
    const project = await window.SigmaFlowCases.load(id);
    if (request !== workspaceSwitchRequest) return false;
    if (sourceEpoch !== workspaceEpoch || sourceEdits !== workspaceEditVersion) throw new Error('A edição local mudou enquanto o projeto era carregado. A abertura foi cancelada para preservá-la.');
    if (project?.id !== id || !Number.isInteger(project.version) || project.version < 1 || typeof project.file_base64 !== 'string') throw new Error('O projeto não retornou uma versão salva válida.');
    const binary = atob(project.file_base64);
    const bytes = new Uint8Array(binary.length);
    for (let i=0;i<binary.length;i++) bytes[i] = binary.charCodeAt(i);
    restoringProject = true;
    if (!applyFile(new File([bytes], project.filename))) throw new Error('O arquivo associado ao projeto é inválido.');
    currentFileData = project.file_base64;
    currentCaseId = project.id;
    currentCaseVersion = project.version;
    $('project-title').value = project.title || 'Projeto de melhoria';
    $('objective').value = project.objective || '';
    if (!await runDiagnosis(true, project) || request !== workspaceSwitchRequest) return false;
    savedEditVersion = workspaceEditVersion;
    $('case-workspace').hidden = false;
    $('save-status').textContent = `Projeto salvo · versão ${project.version} · ${new Date(project.updated_at).toLocaleString('pt-BR')}`;
    goTo($('case-workspace'));
    await refreshProjectList(project.id);
    return true;
  } catch (error) { if (request === workspaceSwitchRequest) showError(error.message || 'Não foi possível abrir o projeto salvo.'); return false; }
  finally {
    if (request === workspaceSwitchRequest) { restoringProject = false; $('load-project').textContent = 'Abrir'; finishWorkspaceSwitch(request); }
  }
}

$('save-project').addEventListener('click', () => persistProject(true));
$('export-project').addEventListener('click', exportProject);
$('load-project').addEventListener('click', openSavedProject);
$('saved-project-list').addEventListener('change', () => {
  $('load-project').disabled = !$('saved-project-list').value;
  $('delete-project').disabled = !$('saved-project-list').value;
  renderWorkspaceControls();
});
$('delete-project').addEventListener('click', async () => {
  const id = $('saved-project-list').value;
  if (!id || !confirm('Excluir o projeto salvo e a cópia local da planilha?')) return;
  try {
    await window.SigmaFlowCases.remove(id);
    if (id === currentCaseId) { currentCaseId = null; $('save-status').textContent = 'Projeto excluído do armazenamento local.'; }
    await refreshProjectList();
  } catch (error) { showError(error.message); }
});

$('history-project').addEventListener('click', () => showHistory());
$('execution-history-list').addEventListener('click', (event) => {
  const button = event.target.closest('button[data-execution-view]');
  if (!button) return;
  const result = executionHistory.find((item) => item.rastreabilidade?.run_id === button.dataset.executionView);
  if (!result) return;
  $('execution-history-view').innerHTML = `<h3>${escapeHtml(result.titulo || 'Resultado da execução')}</h3>${analysisMarkup(result)}`;
  $('execution-history-view').scrollIntoView({behavior:'smooth', block:'start'});
});
$('history-refresh').addEventListener('click', () => loadHistoryPage(true));
$('history-older').addEventListener('click', () => loadHistoryPage(false));
$('history-close').addEventListener('click', () => { $('project-history').hidden = true; });
$('history-recovery').addEventListener('submit', submitHistoryRecovery);
$('history-recovery-cancel').addEventListener('click', () => { $('history-recovery').hidden = true; historyState.recovery = null; });
$('history-open-created').addEventListener('click', async () => { const id = historyState.createdId; $('project-history').hidden = true; if (id) await openProjectById(id); });
$('history-list').addEventListener('click', (event) => {
  const button = event.target.closest('button[data-history-report],button[data-history-export],button[data-history-copy],button[data-history-restore]');
  if (!button) return;
  if (button.dataset.historyReport) inspectHistoryVersion(Number(button.dataset.historyReport), 'report');
  else if (button.dataset.historyExport) exportHistoryVersion(Number(button.dataset.historyExport));
  else if (button.dataset.historyCopy) requestHistoryRecovery('copy', Number(button.dataset.historyCopy));
  else requestHistoryRecovery('restore', Number(button.dataset.historyRestore));
});
$('reload-current-project').addEventListener('click', () => openProjectById(currentCaseId));
$('show-save-copy').addEventListener('click', showWorkspaceCopy);
$('conflict-save-copy').addEventListener('click', showWorkspaceCopy);
$('cancel-save-copy').addEventListener('click', () => { $('workspace-copy-panel').hidden = true; });
$('workspace-copy-panel').addEventListener('submit', async (event) => {
  event.preventDefault();
  const title = $('workspace-copy-title').value.trim();
  if (!title) return;
  $('save-project-copy').disabled = true;
  $('workspace-copy-status').textContent = 'Salvando a edi\u00e7\u00e3o como um projeto independente?';
  try {
    const saved = await persistProject(true, {asNew:true, title});
    if (saved) { $('workspace-copy-status').textContent = `Novo projeto salvo como v${saved.version}. O projeto original foi preservado.`; $('workspace-copy-panel').hidden = true; }
  } catch (error) { $('workspace-copy-status').textContent = `N\u00e3o foi poss\u00edvel salvar a c\u00f3pia. ${error.message}`; }
  finally { renderWorkspaceControls(); }
});

document.querySelectorAll('.dmaic-tabs [data-phase]').forEach((button) => button.addEventListener('click', () => setPhase(button.dataset.phase)));
document.querySelector('.dmaic-tabs').addEventListener('keydown', (event) => {
  if (!['ArrowLeft','ArrowRight'].includes(event.key)) return;
  const index = PHASES.indexOf(currentPhase);
  const next = PHASES[(index + (event.key === 'ArrowRight' ? 1 : PHASES.length - 1)) % PHASES.length];
  setPhase(next); document.querySelector(`[data-phase="${next}"]`).focus(); event.preventDefault();
});

CHARTER_FIELDS.forEach((key) => $(`charter-${key}`).addEventListener('input', () => { collectProjectFields(); renderPhaseChecks(); queueProjectSave(); }));
MEASURE_FIELDS.forEach((key) => $(`measure-${key}`).addEventListener('input', () => { collectProjectFields(); renderPhaseChecks(); queueProjectSave(); }));
CONTROL_FIELDS.forEach((key) => $(`control-${key}`).addEventListener('input', () => { collectProjectFields(); renderPhaseChecks(); queueProjectSave(); }));
$('measure-msa').addEventListener('change', () => { collectProjectFields(); renderPhaseChecks(); queueProjectSave(); });
$('pilot-form').addEventListener('input', updatePilotPlan);
$('pilot-form').addEventListener('change', updatePilotPlan);
$('pilot-form').addEventListener('submit', runPilot);
$('pilot-output').addEventListener('click', (event) => { if (event.target.closest('.report-open')) openReport(); });
$('objective').addEventListener('input', queueProjectSave);
$('project-title').addEventListener('input', queueProjectSave);

$('add-cause').addEventListener('click', () => {
  const text = $('cause-text').value.trim();
  if (!text) { $('cause-text').focus(); return; }
  projectState.causes.push({id:crypto.randomUUID(), category:$('cause-category').value, text, impact:3, frequency:3, status:'hipotese', evidence:'', whys:['','','','','']});
  $('cause-text').value = ''; renderProjectWorkspace(); queueProjectSave();
});
$('cause-list').addEventListener('input', (event) => {
  const card = event.target.closest('[data-cause-index]'); if (!card) return;
  const cause = projectState.causes[Number(card.dataset.causeIndex)];
  if (event.target.dataset.causeField) cause[event.target.dataset.causeField] = event.target.value;
  if (event.target.dataset.whyIndex) cause.whys[Number(event.target.dataset.whyIndex)] = event.target.value;
  renderPhaseChecks(); queueProjectSave();
});
$('cause-list').addEventListener('change', (event) => {
  const card = event.target.closest('[data-cause-index]'); if (!card) return;
  const cause = projectState.causes[Number(card.dataset.causeIndex)];
  if (event.target.dataset.causeField) cause[event.target.dataset.causeField] = event.target.value;
  renderCauses(); queueProjectSave();
});
$('cause-list').addEventListener('click', (event) => {
  const button = event.target.closest('[data-remove-cause]'); if (!button) return;
  const removed = projectState.causes.splice(Number(button.dataset.removeCause),1)[0];
  projectState.actions.forEach((action) => { if (action.causeId === removed?.id) action.causeId = ''; });
  renderProjectWorkspace(); queueProjectSave();
});

$('add-force').addEventListener('click', () => {
  const text = $('force-text').value.trim(); if (!text) { $('force-text').focus(); return; }
  projectState.forces.push({kind:$('force-type').value, text, impact:Number($('force-impact').value)});
  $('force-text').value = ''; renderForces(); queueProjectSave();
});
$('force-list').addEventListener('click', (event) => {
  const button = event.target.closest('[data-remove-force]'); if (!button) return;
  projectState.forces.splice(Number(button.dataset.removeForce),1); renderForces(); queueProjectSave();
});

$('add-action').addEventListener('click', () => {
  const action = $('action-text').value.trim();
  if (!action) { $('action-text').focus(); return; }
  projectState.actions.push({id:crypto.randomUUID(), action, causeId:$('action-cause').value, owner:$('action-owner').value.trim(), due:$('action-due').value, verification:$('action-check').value.trim(), impact:Number($('action-impact').value), effort:Number($('action-effort').value), status:'planejada'});
  ['action-text','action-owner','action-due','action-check'].forEach((id) => { $(id).value = ''; });
  renderActions(); queueProjectSave();
});
$('action-list').addEventListener('change', (event) => {
  const card = event.target.closest('[data-action-index]'); if (!card || !event.target.dataset.actionField) return;
  projectState.actions[Number(card.dataset.actionIndex)].status = event.target.value;
  renderActions(); queueProjectSave();
});
$('action-list').addEventListener('click', (event) => {
  const button = event.target.closest('[data-remove-action]'); if (!button) return;
  projectState.actions.splice(Number(button.dataset.removeAction),1); renderActions(); queueProjectSave();
});

refreshProjectList();
