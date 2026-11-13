function renderChart(chart) {
  if (!chart) return '';
  const colors = ['#247e68', '#c87939', '#bb5250', '#8b9c72'];
  const fmt = (value) => Number(value).toLocaleString('pt-BR', {maximumFractionDigits: 3});
  const shortLabel = (value) => String(value).length > 24 ? String(value).slice(0, 23) + '…' : String(value);
  let graphic = '';
  let legend = '';
  let note = '';
  if (chart.tipo === 'intervalos' && Array.isArray(chart.itens) && chart.itens.length) {
    const finite = (value) => value != null && value !== '' && Number.isFinite(Number(value));
    const items = chart.itens.filter((item) => finite(item.value));
    if (!items.length) return '';
    const reference = finite(chart.referencia?.value) ? Number(chart.referencia.value) : null;
    const values = items.flatMap((item) => [item.value, item.lower, item.upper].filter(finite).map(Number));
    if (reference !== null) values.push(reference);
    let min = Math.min(...values), max = Math.max(...values);
    const padding = max === min ? Math.max(1, Math.abs(max) * .05) : (max - min) * .12;
    min = min >= 0 ? Math.max(0, min - padding) : min - padding;
    max += padding;
    const width = 600, left = 105, right = 35, top = 42, rowHeight = 66;
    const axisY = top + items.length * rowHeight;
    const height = axisY + 48;
    const x = (value) => left + (Number(value) - min) / (max - min) * (width - left - right);
    const intervalText = (item) => finite(item.lower) && finite(item.upper) && Number(item.lower) <= Number(item.upper)
      ? `IC: ${fmt(item.lower)} a ${fmt(item.upper)}` : 'IC indisponível';
    const grid = Array.from({length:5}, (_, index) => {
      const value = min + (max - min) * index / 4, xx = x(value);
      return `<line x1="${xx}" y1="${top-12}" x2="${xx}" y2="${axisY}" class="chart-grid"/><text x="${xx}" y="${axisY+20}" text-anchor="${index===0?'start':index===4?'end':'middle'}" class="chart-label">${escapeHtml(fmt(value))}</text>`;
    }).join('');
    const target = reference !== null ? `<line x1="${x(reference)}" y1="${top-17}" x2="${x(reference)}" y2="${axisY}" stroke="${colors[1]}" stroke-width="1.7" stroke-dasharray="5 4"><title>${escapeHtml(`${chart.referencia.label || 'Meta'}: ${fmt(reference)}`)}</title></line>` : '';
    const points = items.map((item,index) => {
      const yy = top + index * rowHeight + 10, xx = x(item.value);
      const hasInterval = finite(item.lower) && finite(item.upper) && Number(item.lower) <= Number(item.upper);
      const bounds = hasInterval ? `<line x1="${x(item.lower)}" y1="${yy}" x2="${x(item.upper)}" y2="${yy}" stroke="${colors[0]}" stroke-width="2.5"/><line x1="${x(item.lower)}" y1="${yy-6}" x2="${x(item.lower)}" y2="${yy+6}" stroke="${colors[0]}" stroke-width="2"/><line x1="${x(item.upper)}" y1="${yy-6}" x2="${x(item.upper)}" y2="${yy+6}" stroke="${colors[0]}" stroke-width="2"/>` : '';
      return `<g><title>${escapeHtml(`${item.label}: ${fmt(item.value)}; ${intervalText(item)}`)}</title><text x="${left-12}" y="${yy+4}" text-anchor="end" class="chart-label">${escapeHtml(shortLabel(item.label))}</text>${bounds}<circle cx="${xx}" cy="${yy}" r="5" fill="${colors[0]}"/><text x="${left}" y="${yy+25}" class="chart-value">${escapeHtml(`${fmt(item.value)} · ${intervalText(item)}`)}</text></g>`;
    }).join('');
    const accessible = `${chart.titulo || 'Comparação por período'}. ${items.map((item) => `${item.label}: ${fmt(item.value)}, ${intervalText(item)}`).join('; ')}${reference !== null ? `. ${chart.referencia.label || 'Meta'}: ${fmt(reference)}` : ''}`;
    graphic = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(accessible)}">${grid}${target}${points}<line x1="${left}" y1="${axisY}" x2="${width-right}" y2="${axisY}" class="chart-axis"/></svg>`;
    legend = `<div class="chart-legend"><span><i style="background:${colors[0]}"></i>Ponto: estimativa · segmento: intervalo de confiança por período</span>${reference !== null ? `<span><i style="background:${colors[1]}"></i>${escapeHtml(chart.referencia.label || 'Meta')} = ${escapeHtml(fmt(reference))} (tracejada)</span>` : ''}</div>`;
    note = `<p class="chart-caption">${chart.nota ? `${escapeHtml(chart.nota)} ` : ''}Os intervalos por período não substituem o intervalo da diferença entre antes e depois. Consulte os indicadores e as limitações da análise.</p>`;
    if (items.length < chart.itens.length) note += '<p class="chart-caption">Itens sem estimativa numérica não foram desenhados; valores ausentes não foram convertidos em zero.</p>';
  } else if (chart.tipo === 'barras' && chart.itens.length) {
    const width = 600, left = 170, right = 70, top = 20, rowHeight = 35;
    const height = top + chart.itens.length * rowHeight + 30;
    const values = chart.itens.map((item) => Number(item.value));
    let min = Math.min(0, ...values), max = Math.max(0, ...values);
    if (max === min) max = min + 1;
    const x = (value) => left + (value - min) / (max - min) * (width - left - right);
    const zero = x(0);
    graphic = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(chart.titulo)}"><line x1="${zero}" y1="${top-8}" x2="${zero}" y2="${height-20}" class="chart-axis"/>` + chart.itens.map((item, i) => {
      const pos = x(Number(item.value));
      const start = Math.min(zero, pos), barWidth = Math.max(Math.abs(pos - zero), item.value === 0 ? 0 : 1);
      const y = top + i * rowHeight;
      const valueX = item.value < 0 ? Math.max(left - 4, pos - 5) : Math.min(width - right + 5, pos + 5);
      return `<text x="${left-10}" y="${y+15}" text-anchor="end" class="chart-label"><title>${escapeHtml(item.label)}</title>${escapeHtml(shortLabel(item.label))}</text><rect x="${start}" y="${y}" width="${barWidth}" height="20" rx="3" fill="${colors[0]}"><title>${escapeHtml(item.label)}: ${escapeHtml(fmt(item.value))}</title></rect><text x="${valueX}" y="${y+15}" text-anchor="${item.value < 0 ? 'end' : 'start'}" class="chart-value">${escapeHtml(fmt(item.value))}</text>`;
    }).join('') + '</svg>';
  } else if (chart.tipo === 'sobrevivencia' && chart.pontos.length) {
    const width = 600, height = 320, left = 65, right = 22, top = 20, bottom = 68;
    const points = chart.pontos;
    const maxTime = points.reduce((maximum, point) => Math.max(maximum, Number(point.tempo)), 0);
    const timeRange = maxTime > 0 ? maxTime : 1;
    const x = (time) => left + Number(time) / timeRange * (width - left - right);
    const y = (survival) => top + (100 - Number(survival)) / 100 * (height - top - bottom);
    const timeLabel = chart.x_label || 'Tempo';
    const timeFmt = (value) => Number(value).toLocaleString('pt-BR', {maximumSignificantDigits: 6});
    // Keep every supplied point, including tied times. A missing confidence limit
    // starts a new segment; Number(null) would otherwise create a false zero.
    const stepPath = (key) => {
      let connected = false;
      return points.map((point) => {
        if (point[key] == null || !Number.isFinite(Number(point[key]))) {
          connected = false;
          return '';
        }
        const xx = x(point.tempo), yy = y(point[key]);
        const command = connected ? `H ${xx} V ${yy}` : `M ${xx} ${yy}`;
        connected = true;
        return command;
      }).join(' ').trim();
    };
    const pointTitle = (point) => `${timeLabel}: ${timeFmt(point.tempo)}; Sobrevivência: ${fmt(point.sobrevivencia)}%; Em risco: ${fmt(point.risco)}; Falhas: ${fmt(point.falhas)}; Censuras: ${fmt(point.censuras)}`;
    const grid = [0, 25, 50, 75, 100].map((value) => {
      const yy = y(value);
      return `<line x1="${left}" y1="${yy}" x2="${width-right}" y2="${yy}" class="chart-grid"/><text x="${left-8}" y="${yy+4}" text-anchor="end" class="chart-label">${value}%</text>`;
    }).join('');
    const ticks = Array.from({length: maxTime > 0 ? 6 : 1}, (_, i) => {
      const value = maxTime * i / 5, xx = x(value);
      return `<line x1="${xx}" y1="${height-bottom}" x2="${xx}" y2="${height-bottom+5}" class="chart-axis"/><text x="${xx}" y="${height-bottom+21}" text-anchor="${i === 0 ? 'start' : i === 5 ? 'end' : 'middle'}" class="chart-label">${escapeHtml(timeFmt(value))}</text>`;
    }).join('');
    const confidence = ['inferior', 'superior'].map((key) => {
      const path = stepPath(key);
      return path ? `<path d="${path}" fill="none" stroke="${colors[1]}" stroke-width="1.5" stroke-dasharray="5 4"/>` : '';
    }).join('');
    const dots = points.map((point) => `<circle cx="${x(point.tempo)}" cy="${y(point.sobrevivencia)}" r="2" fill="${colors[0]}"><title>${escapeHtml(pointTitle(point))}</title></circle>`).join('');
    const censored = points.filter((point) => Number(point.censuras) > 0).map((point) => {
      const xx = x(point.tempo), yy = y(point.sobrevivencia);
      return `<path d="M ${xx-4} ${yy} H ${xx+4} M ${xx} ${yy-4} V ${yy+4}" fill="none" stroke="${colors[0]}" stroke-width="1.8"><title>${escapeHtml(`Censura: ${pointTitle(point)}`)}</title></path>`;
    }).join('');
    graphic = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(chart.titulo)}">${grid}<line x1="${left}" y1="${top}" x2="${left}" y2="${height-bottom}" class="chart-axis"/><line x1="${left}" y1="${height-bottom}" x2="${width-right}" y2="${height-bottom}" class="chart-axis"/>${ticks}${confidence}<path d="${stepPath('sobrevivencia')}" fill="none" stroke="${colors[0]}" stroke-width="2.5"/>${dots}${censored}<text x="${(left+width-right)/2}" y="${height-18}" text-anchor="middle" class="chart-label">${escapeHtml(timeLabel)}</text></svg>`;
    legend = `<div class="chart-legend"><span><i style="background:${colors[0]}"></i>Kaplan–Meier</span>${confidence ? `<span><i style="background:${colors[1]}"></i>Limites de confiança pontuais (tracejados)</span>` : ''}${censored ? '<span>+ Censura</span>' : ''}</div>`;
    note = chart.nota ? `<p class="chart-caption">${escapeHtml(chart.nota)}</p>` : '';
  } else if (chart.tipo === 'linhas' && chart.rotulos.length && chart.series.length) {
    const width = 600, height = 280, left = 65, right = 18, top = 18, bottom = 43;
    const values = chart.series.flatMap((series) => series.valores.map(Number));
    let min = Math.min(...values), max = Math.max(...values);
    const padding = max === min ? Math.max(1, Math.abs(max) * 0.05) : (max - min) * 0.12;
    min -= padding; max += padding;
    const x = (i) => chart.rotulos.length === 1 ? (left + width - right) / 2 : left + i * (width - left - right) / (chart.rotulos.length - 1);
    const y = (value) => top + (max - value) * (height - top - bottom) / (max - min);
    const grid = Array.from({length: 5}, (_, i) => { const value = min + (max-min)*i/4; const yy = y(value); return `<line x1="${left}" y1="${yy}" x2="${width-right}" y2="${yy}" class="chart-grid"/><text x="${left-8}" y="${yy+4}" text-anchor="end" class="chart-label">${escapeHtml(fmt(value))}</text>`; }).join('');
    const lines = chart.series.map((series, j) => {
      const points = series.valores.map((v, i) => `${x(i)},${y(Number(v))}`).join(' ');
      const dots = j === 0 ? series.valores.map((v, i) => `<circle cx="${x(i)}" cy="${y(Number(v))}" r="2.7" fill="${colors[j]}"><title>${escapeHtml(chart.rotulos[i])}: ${escapeHtml(fmt(v))}</title></circle>`).join('') : '';
      return `<polyline fill="none" stroke="${colors[j % colors.length]}" stroke-width="${j === 0 ? 2.5 : 1.5}" ${j === 0 ? '' : 'stroke-dasharray="5 4"'} points="${points}"/>${dots}`;
    }).join('');
    graphic = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(chart.titulo)}">${grid}${lines}<text x="${left}" y="${height-12}" class="chart-label">${escapeHtml(shortLabel(chart.rotulos[0]))}</text><text x="${width-right}" y="${height-12}" text-anchor="end" class="chart-label">${escapeHtml(shortLabel(chart.rotulos[chart.rotulos.length-1]))}</text></svg>`;
    legend = `<div class="chart-legend">${chart.series.map((series, i) => `<span><i style="background:${colors[i % colors.length]}"></i>${escapeHtml(series.nome)}</span>`).join('')}</div>`;
  }
  if (!graphic) return '';
  const truncated = chart.total > chart.mostrados ? `<p class="chart-caption">Gráfico: primeiros ${chart.mostrados} de ${chart.total} itens. Os indicadores consideram todos os dados analisados.</p>` : '';
  return `<figure class="result-chart"><figcaption><strong>${escapeHtml(chart.titulo)}</strong><span>${escapeHtml(chart.eixo)}</span></figcaption>${graphic}${legend}${note}${truncated}</figure>`;
}
