/* Contrato simples para persistir casos na pasta local do SigmaFlow. */
(() => {
  const apiError = (response, body, fallback) => Object.assign(new Error(body.error || fallback), {
    status:response.status, code:body.code || null, current_version:body.current_version ?? null,
  });
  const api = async (url, options = {}) => {
    const response = await fetch(url, {cache:'no-store', ...options});
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw apiError(response, body, 'Não foi possível acessar o projeto local.');
    return body;
  };
  const projectUrl = (id) => `/api/projetos/${encodeURIComponent(id)}`;
  const versionUrl = (id, version) => `${projectUrl(id)}/versoes/${encodeURIComponent(version)}`;

  window.SigmaFlowCases = {
    list: () => api('/api/projetos'),
    load: (id) => api(`/api/projetos/${encodeURIComponent(id)}`),
    history: (id, {limit = 50, before = null} = {}) => api(`${projectUrl(id)}/historico?limit=${encodeURIComponent(limit)}${before == null ? '' : `&before=${encodeURIComponent(before)}`}`),
    version: (id, version) => api(versionUrl(id, version)),
    versionReport: async (id, version) => {
      const response = await fetch(`${versionUrl(id, version)}/relatorio`, {cache:'no-store'});
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw apiError(response, body, 'Não foi possível abrir o relatório salvo desta versão.');
      }
      if (!(response.headers.get('Content-Type') || '').includes('text/html')) throw new Error('O servidor não retornou um relatório HTML válido.');
      return response.text();
    },
    copyVersion: (id, version, {title, reason}) => api(`${versionUrl(id, version)}/copiar`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title, reason}),
    }),
    restoreVersion: (id, version, {base_version, reason}) => api(`${versionUrl(id, version)}/restaurar`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({base_version, reason}),
    }),
    save: (project) => api(`/api/projetos/${encodeURIComponent(project.id)}`, {
      method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(project),
    }),
    export: async (id, version) => {
      const response = await fetch(`/api/projetos/${encodeURIComponent(id)}/exportar?version=${encodeURIComponent(version)}`, {cache:'no-store', headers:{'X-SigmaFlow-Export':'1'}});
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw apiError(response, body, 'Não foi possível preparar o pacote do projeto.');
      }
      const disposition = response.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename\s*=\s*"?([^";]+)"?/i);
      const filename = (match?.[1] || `sigmaflow-${id}-v${version}.zip`).trim().replace(/[/\\\x00-\x1f]/g, '_');
      return {blob:await response.blob(), filename};
    },
    remove: (id) => api(`/api/projetos/${encodeURIComponent(id)}`, {method:'DELETE'}),
  };
})();
