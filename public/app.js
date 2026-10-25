const $ = (id) => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const state = { snapshot: null, direction: 'long', horizon: 4, targetIndex: -1, stopIndex: null, dirty: false };
const money = (n) => Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pct = (n) => `${Math.round(n * 100)}%`;
const finite = (n) => typeof n === 'number' && Number.isFinite(n);
const probability = (n) => finite(n) && n >= 0 && n <= 1;
const text = (id, value) => { $(id).textContent = value; };
const fmtTime = (iso) => {
  if (typeof iso !== 'string' || !iso) return 'Timestamp unavailable';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? 'Timestamp unavailable' : new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(d) + ' UTC';
};
const hourLabel = (n) => !finite(n) ? 'Not reached' : n < 1 ? `${Math.round(n * 60)} min` : `${n < 10 ? n.toFixed(1) : Math.round(n)} trading h`;
function svgNode(tag, attrs = {}, value) {
  const node = document.createElementNS(NS, tag);
  Object.entries(attrs).forEach(([key, val]) => node.setAttribute(key, String(val)));
  if (value !== undefined) node.textContent = value;
  return node;
}
function add(svg, tag, attrs, value) { const node = svgNode(tag, attrs, value); svg.append(node); return node; }
function linePath(values, x, y) { return values.map((v, i) => `${i ? 'L' : 'M'}${x(v, i).toFixed(2)},${y(v, i).toFixed(2)}`).join(' '); }
function validateSnapshot(s) {
  if (s?.schemaVersion !== 1 || !['demo', 'live'].includes(s.mode) || !finite(s.referencePrice) || s.referencePrice <= 0 || !s.model || !s.status || !s.instrument) throw new Error('Unsupported or incomplete model snapshot.');
  if (!Array.isArray(s.levels) || s.levels.length < 2 || !s.levels.every((v, i) => finite(v) && v > 0 && (!i || v > s.levels[i - 1]))) throw new Error('The snapshot price grid is invalid.');
  if (!Array.isArray(s.horizons) || s.horizons.length < 2) throw new Error('The snapshot has no usable time horizons.');
  for (const h of s.horizons) {
    if (!finite(h.tradingHours) || h.tradingHours < 0 || !Array.isArray(h.results) || h.results.length !== s.levels.length || !Array.isArray(h.scenario) || h.scenario.length < 1) throw new Error('The snapshot horizon data is incomplete.');
    if (!h.scenario.every((p) => [p.hours, p.p10, p.p50, p.p90].every(finite) && p.p10 <= p.p50 && p.p50 <= p.p90)) throw new Error('Invalid scenario paths in the snapshot.');
    for (const r of h.results) {
      if (!r || !probability(r.touch) || !probability(r.finish) || !Array.isArray(r.range) || r.range.length !== 2 || !r.range.every(probability) || r.range[0] > r.range[1] || !Array.isArray(r.targetBeforeStop) || r.targetBeforeStop.length !== s.levels.length || !r.targetBeforeStop.every((v) => v === null || probability(v))) throw new Error('The snapshot probability data is invalid.');
    }
  }
  return s;
}
function showMessage(message, error = true) {
  text('form-message', message); $('form-message').hidden = !message;
  $('form-message').style.color = error ? 'var(--warning)' : 'var(--muted)';
}
function nearestIndex(price) {
  return state.snapshot.levels.reduce((best, value, index, levels) => Math.abs(value - price) < Math.abs(levels[best] - price) ? index : best, 0);
}
function markDirty() {
  if (!state.snapshot) return;
  state.dirty = true;
  $('results').style.opacity = '.5';
  showMessage('Inputs changed. Select Calculate to update the estimate.', false);
}
function chooseDirection(direction) {
  state.direction = direction;
  document.querySelectorAll('[data-direction]').forEach((b) => { const active = b.dataset.direction === direction; b.classList.toggle('active', active); b.setAttribute('aria-pressed', String(active)); });
  if (state.snapshot) {
    const entry = Number($('entry').value) || state.snapshot.referencePrice;
    const reference = state.snapshot.referencePrice;
    const anchor = direction === 'long' ? Math.max(entry, reference) : Math.min(entry, reference);
    const suggested = anchor + (direction === 'long' ? 1 : -1) * Math.max(.5, reference * .012);
    $('target').value = state.snapshot.levels[nearestIndex(suggested)].toFixed(2);
    $('stop').value = '';
    markDirty();
  }
}
function calculate(event) {
  event?.preventDefault();
  if (!state.snapshot) return;
  const s = state.snapshot;
  const entry = Number($('entry').value);
  const target = Number($('target').value);
  const hasStop = $('stop').value.trim() !== '';
  const stop = hasStop ? Number($('stop').value) : null;
  const invalid = (message) => { state.dirty = true; $('results').style.opacity = '.4'; showMessage(message); };
  if (!finite(entry) || entry <= 0 || !finite(target) || target <= 0 || (hasStop && (!finite(stop) || stop <= 0))) return invalid('Enter a valid positive price for your entry, target and optional stop.');
  const first = s.levels[0], last = s.levels.at(-1);
  if (target < first || target > last || (hasStop && (stop < first || stop > last))) return invalid(`This snapshot supports targets and stops from $${money(first)} to $${money(last)}. Choose a price within that grid.`);
  const ti = nearestIndex(target), si = hasStop ? nearestIndex(stop) : null;
  const targetUsed = s.levels[ti], stopUsed = hasStop ? s.levels[si] : null;
  if (state.direction === 'long' && (targetUsed <= entry || targetUsed <= s.referencePrice)) return invalid('For a long position, the target must be above both your entry and the model reference price. This snapshot estimates future touches from the reference.');
  if (state.direction === 'short' && (targetUsed >= entry || targetUsed >= s.referencePrice)) return invalid('For a short position, the target must be below both your entry and the model reference price. This snapshot estimates future touches from the reference.');
  if (hasStop && ((state.direction === 'long' && (stopUsed >= entry || stopUsed >= s.referencePrice)) || (state.direction === 'short' && (stopUsed <= entry || stopUsed <= s.referencePrice)))) return invalid('The stop must be on the loss side of both your entry and the model reference price. A stop already passed by the reference cannot be evaluated as a future stop.');
  const notices = [];
  if (Math.abs(targetUsed - target) > .000001) notices.push(`Target snapped from $${money(target)} to the published $${money(targetUsed)} level.`);
  if (hasStop && Math.abs(stopUsed - stop) > .000001) notices.push(`Stop snapped from $${money(stop)} to the published $${money(stopUsed)} level.`);
  $('target').value = targetUsed.toFixed(2);
  if (hasStop) $('stop').value = stopUsed.toFixed(2);
  state.targetIndex = ti; state.stopIndex = si; state.dirty = false;
  $('results').style.opacity = '1';
  showMessage(notices.join(' '), false);
  const mismatch = Math.abs(entry - s.referencePrice) > .005;
  $('entry-message').hidden = !mismatch;
  text('entry-message', `Your entry is $${money(entry)}. All probabilities still start at the snapshot reference of $${money(s.referencePrice)}.`);
  renderResults();
}
function renderResults() {
  if (state.targetIndex < 0) return;
  const s = state.snapshot, h = s.horizons[state.horizon], r = h.results[state.targetIndex], target = s.levels[state.targetIndex];
  text('touch-value', Math.round(r.touch * 100));
  text('range-value', `${Math.round(r.range[0] * 100)}–${Math.round(r.range[1] * 100)}% sensitivity range`);
  text('finish-value', pct(r.finish));
  const beforeStop = state.stopIndex === null ? null : r.targetBeforeStop[state.stopIndex];
  text('before-stop-value', state.stopIndex === null ? 'Add a stop' : beforeStop === null ? 'Unavailable' : pct(beforeStop));
  text('median-value', hourLabel(r.medianHitHours));
  text('result-description', `Chance of reaching $${money(target)} within ${h.label.toLowerCase()}, starting from $${money(s.referencePrice)} at ${fmtTime(s.asOf)}.${s.mode === 'demo' ? ' Synthetic demonstration.' : ''}`);
  text('horizon-pill', h.label);
  text('trading-time', `${h.tradingHours.toFixed(1)} trading hours inside this calendar window. Holidays may differ.`);
  $('experimental-tag').hidden = !h.experimental;
  $('horizon').value = state.horizon;
  $('horizon').setAttribute('aria-valuetext', `${h.label}${h.experimental ? ', experimental' : ''}`);
  document.querySelectorAll('[data-horizon]').forEach((b) => { const selected = Number(b.dataset.horizon) === state.horizon; b.classList.toggle('active', selected); b.setAttribute('aria-pressed', String(selected)); });
  renderScenario(h, target, state.stopIndex === null ? null : s.levels[state.stopIndex]);
  renderTimeChart();
  $('results').setAttribute('aria-busy', 'false');
}
function setHorizon(index) {
  if (!state.snapshot) return;
  state.horizon = Math.max(0, Math.min(state.snapshot.horizons.length - 1, Number(index)));
  if (state.dirty) { calculate(); return; }
  renderResults();
}
function renderScenario(h, target, stop) {
  const svg = $('scenario-chart'); svg.replaceChildren();
  const values = h.scenario, width = 650, left = 14, right = 62, top = 20, bottom = 294;
  const all = values.flatMap((p) => [p.p10, p.p90]); all.push(target); if (stop !== null) all.push(stop);
  let low = Math.min(...all), high = Math.max(...all), pad = Math.max((high - low) * .12, .3); low -= pad; high += pad;
  const maxHours = Math.max(...values.map((p) => p.hours), 1);
  const x = (p) => left + (p.hours / maxHours) * (width - left - right);
  const y = (price) => bottom - (price - low) / (high - low) * (bottom - top);
  for (let i = 0; i < 5; i++) { const v = low + (high - low) * i / 4, py = y(v); add(svg, 'line', { x1: left, x2: width - right, y1: py, y2: py, class: 'grid-line' }); add(svg, 'text', { x: width - right + 12, y: py + 3 }, money(v)); }
  const upper = linePath(values, x, (p) => y(p.p90));
  const lower = [...values].reverse().map((p) => `L${x(p).toFixed(2)},${y(p.p10).toFixed(2)}`).join(' ');
  add(svg, 'path', { d: `${upper} ${lower} Z`, class: 'scenario-band' });
  add(svg, 'path', { d: upper, class: 'percentile-line' });
  add(svg, 'path', { d: linePath(values, x, (p) => y(p.p10)), class: 'percentile-line' });
  add(svg, 'path', { d: linePath(values, x, (p) => y(p.p50)), class: 'median-line' });
  for (const [price, cls, label] of [[target, 'target-line', 'TARGET'], ...(stop === null ? [] : [[stop, 'stop-line', 'STOP']])]) { add(svg, 'line', { x1: left, x2: width - right, y1: y(price), y2: y(price), class: cls }); add(svg, 'text', { x: left + 5, y: y(price) - 7, style: `fill:${cls === 'target-line' ? '#77924d' : '#ad735a'};font-size:8px;letter-spacing:.06em` }, `${label} $${money(price)}`); }
  add(svg, 'circle', { cx: x(values[0]), cy: y(values[0].p50), r: 4, class: 'marker' });
  add(svg, 'text', { x: left, y: 321 }, 'SNAPSHOT START'); add(svg, 'text', { x: width - right, y: 321, 'text-anchor': 'end' }, `${h.tradingHours.toFixed(1)} TRADING H`);
  svg.setAttribute('aria-label', `${h.label} price scenarios. Target $${money(target)}. Ending 10th percentile $${money(values.at(-1).p10)}, median $${money(values.at(-1).p50)}, 90th percentile $${money(values.at(-1).p90)}.${stop === null ? '' : ` Stop $${money(stop)}.`}`);
}
function renderTimeChart() {
  const svg = $('time-chart'); svg.replaceChildren();
  const hs = state.snapshot.horizons, left = 25, right = 594, top = 16, bottom = 155;
  const x = (_, i) => left + i / (hs.length - 1) * (right - left), y = (h) => bottom - h.results[state.targetIndex].touch * (bottom - top);
  for (let i = 0; i <= 2; i++) { const py = bottom - i / 2 * (bottom - top); add(svg, 'line', { x1: left, x2: right, y1: py, y2: py, class: 'grid-line' }); add(svg, 'text', { x: left, y: py - 6, style: 'font-size:8px' }, `${i * 50}%`); }
  const line = linePath(hs, x, y);
  add(svg, 'path', { d: `${line} L${right},${bottom} L${left},${bottom} Z`, class: 'probability-area' });
  add(svg, 'path', { d: line, class: 'probability-line' });
  hs.forEach((h, i) => { const selected = i === state.horizon; if (selected) add(svg, 'line', { x1: x(h, i), x2: x(h, i), y1: top, y2: bottom, stroke: 'var(--muted)', 'stroke-dasharray': '2 4' }); add(svg, 'circle', { cx: x(h, i), cy: y(h), r: selected ? 5 : 2.5, class: 'marker' }); if (selected) add(svg, 'text', { x: Math.max(left + 14, Math.min(right - 14, x(h, i))), y: Math.max(12, y(h) - 12), 'text-anchor': 'middle', style: 'fill:var(--ink);font-size:11px' }, pct(h.results[state.targetIndex].touch)); });
  const table = $('time-table'); table.replaceChildren();
  hs.forEach((h, i) => { const button = document.createElement('button'); button.type = 'button'; button.dataset.horizon = i; button.className = i === state.horizon ? 'active' : ''; button.setAttribute('aria-label', `${h.label}: ${pct(h.results[state.targetIndex].touch)} chance of touch`); button.setAttribute('aria-pressed', String(i === state.horizon)); button.textContent = h.id; const strong = document.createElement('strong'); strong.textContent = pct(h.results[state.targetIndex].touch); button.append(strong); button.addEventListener('click', () => setHorizon(i)); table.append(button); });
  svg.setAttribute('aria-label', `Touch probability by time horizon. ${hs.map((h) => `${h.label}: ${pct(h.results[state.targetIndex].touch)}`).join('; ')}.`);
}
function renderHistory() {
  const svg = $('history-chart'); svg.replaceChildren();
  const history = (state.snapshot.history || []).filter((p) => finite(p.price) && p.price > 0 && (!$('nasdaq-toggle').checked || (finite(p.nasdaq) && p.nasdaq > 0)));
  if (history.length < 2) { add(svg, 'text', { x: 560, y: 100, 'text-anchor': 'middle' }, 'No usable historical prices in this snapshot.'); return; }
  const overlay = $('nasdaq-toggle').checked;
  const first = history[0].price, firstN = history[0].nasdaq;
  const points = history.map((p) => ({ ...p, value: overlay ? (p.price / first - 1) * 100 : p.price, nv: overlay ? (p.nasdaq / firstN - 1) * 100 : null }));
  const all = points.flatMap((p) => overlay ? [p.value, p.nv] : [p.value]);
  let low = Math.min(...all), high = Math.max(...all); const pad = Math.max((high - low) * .15, .03); low -= pad; high += pad;
  const left = 3, right = 1058, top = 20, bottom = 167;
  const x = (_, i) => left + i / (points.length - 1) * (right - left), y = (n) => bottom - (n - low) / (high - low) * (bottom - top);
  for (let i = 0; i < 4; i++) { const n = low + i / 3 * (high - low); add(svg, 'line', { x1: left, x2: right, y1: y(n), y2: y(n), class: 'grid-line' }); add(svg, 'text', { x: right + 12, y: y(n) + 3 }, `${money(n)}${overlay ? '%' : ''}`); }
  const path = linePath(points, x, (p) => y(p.value));
  add(svg, 'path', { d: `${path} L${right},${bottom} L${left},${bottom} Z`, fill: 'var(--band)', opacity: '.55' });
  add(svg, 'path', { d: path, class: 'history-line' });
  if (overlay) add(svg, 'path', { d: linePath(points, x, (p) => y(p.nv)), fill: 'none', stroke: '#8c9e70', 'stroke-width': 2 });
  add(svg, 'text', { x: left, y: 194 }, fmtTime(history[0].time)); add(svg, 'text', { x: right, y: 194, 'text-anchor': 'end' }, fmtTime(history.at(-1).time));
  text('history-caption', `${state.snapshot.mode === 'demo' ? 'Synthetic demonstration history; not observed market prices.' : 'Archived model-source history; not a TradingView price feed.'}${overlay ? ' WTI (black) and Nasdaq (green), indexed to percentage change from the first observation.' : ' Nasdaq overlay is available only when matching observations exist.'}`);
  svg.setAttribute('aria-label', `${state.snapshot.mode === 'demo' ? 'Synthetic' : 'Archived'} WTI prices from $${money(history[0].price)} to $${money(history.at(-1).price)}.${overlay ? ' Nasdaq overlay is shown as indexed percentage returns.' : ''}`);
}
function populate(snapshot) {
  state.snapshot = snapshot;
  const s = snapshot;
  text('market-price', `$${money(s.lastPrice ?? s.referencePrice)}`); const unit = document.createElement('span'); unit.textContent = ' / bbl'; $('market-price').append(unit);
  text('instrument', `${s.instrument.symbol} · futures proxy`);
  text('reference-label', `Model reference $${money(s.referencePrice)} · ${s.mode === 'demo' ? 'synthetic prices' : 'delayed source data'}`);
  const nasdaq = s.market?.nasdaq;
  text('nasdaq-price', nasdaq && finite(nasdaq.price) ? `${money(nasdaq.price)}${finite(nasdaq.changePct) ? ` (${nasdaq.changePct >= 0 ? '+' : ''}${nasdaq.changePct.toFixed(2)}%)` : ''}` : 'Not connected');
  text('mode-label', s.mode === 'demo' ? 'Demonstration' : 'Research snapshot');
  text('mode-description', s.mode === 'demo' ? 'Synthetic data · not a live market estimate · uncalibrated' : 'Delayed market data · unvalidated statistical estimates');
  text('snapshot-time', `Data: ${fmtTime(s.asOf)}`); $('snapshot-time').dateTime = s.asOf;
  const age = Date.now() - new Date(s.asOf).getTime();
  if (s.mode === 'live' && (!finite(age) || age > 2 * 60 * 60 * 1000)) { $('data-notice').classList.add('warning'); text('mode-label', 'Stale data'); text('mode-description', 'This estimate uses an old snapshot. Do not interpret it as current market conditions.'); }
  text('model-state', s.mode === 'demo' ? 'Synthetic data · not calibrated' : s.model.calibrated ? 'Calibration supplied with snapshot' : 'Research model · not calibrated');
  text('volatility-value', finite(s.model.annualVolatility) ? pct(s.model.annualVolatility) : 'Unavailable');
  text('paths-value', finite(s.model.paths) ? s.model.paths.toLocaleString('en-US') : 'Unavailable');
  text('calibration-value', s.model.calibrated ? 'See model record' : 'Not validated');
  text('range-method', s.model.rangeMethod || 'Model sensitivity range; not a validated confidence interval.');
  text('publish-state', s.status.mode === 'shock' || s.status.mode === 'shock_mode' ? 'Shock mode' : 'Snapshot held stable');
  text('publish-reason', s.status.reason || 'Same inputs. Same snapshot. Same answer.');
  if (finite(s.market?.brentSpread)) text('spread-value', `Brent–WTI spread $${money(s.market.brentSpread)}`);
  const history = s.history || [];
  $('nasdaq-toggle').disabled = history.filter((p) => finite(p.nasdaq) && p.nasdaq > 0).length < 2;
  ['entry', 'target', 'stop', 'calculate', 'horizon'].forEach((id) => { $(id).disabled = false; });
  $('entry').value = s.referencePrice.toFixed(2);
  const step = +(s.levels[1] - s.levels[0]).toFixed(4);
  for (const id of ['target', 'stop']) { $(id).step = 'any'; $(id).min = s.levels[0]; $(id).max = s.levels.at(-1); }
  text('grid-note', `Published grid: $${money(s.levels[0])}–$${money(s.levels.at(-1))}, in $${money(step)} steps. Other targets and stops are visibly snapped to the nearest level.`);
  $('target').value = s.levels[nearestIndex(s.referencePrice + Math.max(1, s.referencePrice * .012))].toFixed(2);
  $('horizon').max = s.horizons.length - 1;
  const preferred = s.horizons.findIndex((h) => h.id === '1d'); state.horizon = preferred >= 0 ? preferred : 0;
  const labels = $('horizon-labels'); labels.replaceChildren();
  s.horizons.forEach((h, i) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = h.id; b.dataset.horizon = i; b.setAttribute('aria-label', h.label); b.addEventListener('click', () => setHorizon(i)); labels.append(b); });
  renderContext(s);
  renderHistory(); calculate();
}
function renderContext(s) {
  const container = $('source-details'); container.replaceChildren();
  const sources = Array.isArray(s.dataSources) ? s.dataSources : [];
  if (!sources.length) {
    const p = document.createElement('p'); p.textContent = 'Demonstration fixture. No live sources were queried for these results.'; container.append(p);
  }
  for (const source of sources) {
    const p = document.createElement('p');
    const age = Date.now() - new Date(source.asOf).getTime();
    const status = !source.asOf ? 'Unavailable' : age > 4 * 3600000 ? 'Stale' : 'Available';
    p.textContent = `${source.symbol} · ${status} · ${source.usage} · ${fmtTime(source.asOf)} · ${source.source}`;
    container.append(p);
  }
  const headlines = $('headline-list'); headlines.replaceChildren();
  for (const item of (Array.isArray(s.headlines) ? s.headlines : []).slice(0, 8)) {
    let url;
    try { url = new URL(item.url); } catch { continue; }
    if (url.protocol !== 'https:') continue;
    const li = document.createElement('li'), a = document.createElement('a');
    a.href = url.href; a.target = '_blank'; a.rel = 'noopener noreferrer';
    a.textContent = item.title; li.append(a);
    const small = document.createElement('small'); small.textContent = ` ${item.source} · ${item.publishedAt ? fmtTime(item.publishedAt) : 'Date unavailable'} · context only`; li.append(small); headlines.append(li);
  }
  if (!headlines.children.length) { const li = document.createElement('li'); li.textContent = 'No verified headlines included in this snapshot.'; headlines.append(li); }
}
async function loadSnapshot() {
  try {
    const response = await fetch('data/snapshot.json', { cache: 'no-cache' });
    if (!response.ok) throw new Error(`Snapshot request failed (${response.status}).`);
    populate(validateSnapshot(await response.json()));
  } catch (error) {
    console.error('Snapshot load failed:', error);
    text('mode-label', 'Snapshot unavailable'); text('mode-description', 'The published data could not be loaded. Serve this folder over HTTP and check data/snapshot.json.'); $('data-notice').classList.add('error');
    text('range-value', 'No estimate available'); text('result-description', 'No substitute numbers are shown when data fails.'); $('results').setAttribute('aria-busy', 'false');
    ['entry', 'target', 'stop', 'calculate', 'horizon'].forEach((id) => { $(id).disabled = true; });
    showMessage('Unable to load a valid snapshot. Check the server or try reloading the page.');
  }
}
function setTheme(dark) {
  document.body.classList.toggle('dark', dark); $('theme-button').setAttribute('aria-label', `Switch to ${dark ? 'light' : 'dark'} theme`);
  try { localStorage.setItem('wti-theme', dark ? 'dark' : 'light'); } catch { /* Theme still works when storage is disabled. */ }
}
try { const saved = localStorage.getItem('wti-theme'); if (saved) setTheme(saved === 'dark'); } catch { /* Private storage can be unavailable. */ }
$('theme-button').addEventListener('click', () => setTheme(!document.body.classList.contains('dark')));
$('scenario-form').addEventListener('submit', calculate);
['entry', 'target', 'stop'].forEach((id) => $(id).addEventListener('input', markDirty));
document.querySelectorAll('[data-direction]').forEach((b) => b.addEventListener('click', () => chooseDirection(b.dataset.direction)));
$('horizon').addEventListener('input', (event) => setHorizon(event.target.value));
$('nasdaq-toggle').addEventListener('change', renderHistory);
const dialog = $('method-dialog');
['method-button', 'method-button-secondary'].forEach((id) => $(id).addEventListener('click', () => dialog.showModal()));
['close-dialog', 'understood'].forEach((id) => $(id).addEventListener('click', () => dialog.close()));
dialog.addEventListener('click', (event) => { if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close(); } });
loadSnapshot();
