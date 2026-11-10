// Screen 5, History and dashboard (P10-T09). The four metrics come from real result files or show a dash with the
// reason. Simulated and replay runs are listed with a badge and are in no number. Every value is set as text.
import { clear, el } from '../dom.js';

const DASH = '—';
const pct = (x) => `${(x * 100).toFixed(1)}%`;
const num = (x) => Math.round(x).toLocaleString('en-US');

function backing(source) {
  if (!source) return DASH;
  const n = source.n === undefined ? '' : `, ${source.n} task${source.n === 1 ? '' : 's'}`;
  return `${source.file} (run ${source.run_id || DASH}${n})`;
}

// One row per metric: [name, value text, limit text, where it comes from]. A missing value is a dash plus the reason.
function metricRows(m) {
  const rr = m.resolve_rate;
  const tk = m.tokens_per_bug;
  const lt = m.latency;
  const qs = m.quota_share;
  const dash = (x) => [DASH, x.reason, DASH];
  return [
    ['Resolve rate', ...(rr.value === null ? dash(rr)
      : [`${pct(rr.value)} (${rr.successes}/${rr.total})`, `Wilson 95%: ${pct(rr.ci_low)} to ${pct(rr.ci_high)}`, backing(rr.source)])],
    ['Tokens per bug', ...(tk.value === null ? dash(tk)
      : [`in ${num(tk.tokens_in)}, out ${num(tk.tokens_out)}, cached ${num(tk.tokens_cached)}`, 'cached shown apart', backing(tk.source)])],
    ['Latency', ...(lt.value === null ? dash(lt)
      : [`p50 ${lt.p50.toFixed(1)} s, p95 ${lt.p95 === null ? DASH : lt.p95.toFixed(1) + ' s'}`, 'wall clock per task, coordinator waits included; several tasks ran at once (as the result file says)', backing(lt.source)])],
    ['Quota share', ...(qs.value === null ? dash(qs)
      : [`${qs.tenants.length} tenant${qs.tenants.length === 1 ? '' : 's'}, ${num(qs.total_tokens)} tokens`, `ledger day ${qs.day}`, backing(qs.source)])],
  ];
}

function metricsTable(m) {
  const head = el('tr', {}, ...['Metric', 'Value', 'Limit', 'Backed by'].map((h) => el('th', { scope: 'col', text: h })));
  const body = metricRows(m).map((r) => el('tr', {}, el('th', { scope: 'row', text: r[0] }), ...r.slice(1).map((c) => el('td', { text: c }))));
  return el('table', { class: 'metrics', 'aria-label': 'The four metrics' }, el('thead', {}, head), el('tbody', {}, body));
}

function tenantTable(qs) {
  if (qs.value === null) return null;
  const head = el('tr', {}, ...['Tenant', 'Tokens', 'Requests', 'Share'].map((h) => el('th', { scope: 'col', text: h })));
  const rows = qs.tenants.map((t) => el('tr', {}, el('th', { scope: 'row', text: t.tenant }),
    el('td', { text: num(t.tokens) }), el('td', { text: num(t.requests) }), el('td', { text: pct(t.share) })));
  return el('table', { class: 'tenants', 'aria-label': 'Quota share per tenant' }, el('thead', {}, head), el('tbody', {}, rows));
}

function runsTable(runs) {
  const cols = ['Run', 'Created', 'State', 'Stop reason', 'Scenario', 'Origin', 'Decision', 'PR'];
  const head = el('tr', {}, ...cols.map((h) => el('th', { scope: 'col', text: h })));
  const rows = runs.map((r) => el('tr', { class: `origin-${r.origin.toLowerCase()}` },
    el('th', { scope: 'row' }, el('a', { href: `#/review/${r.run_id}`, text: r.run_id })),
    el('td', { text: r.created_at }),
    el('td', { text: r.display_state }),
    el('td', { text: r.stop_reason || DASH }),
    el('td', { text: r.scenario || DASH }),
    el('td', {}, el('span', { class: `badge ${r.origin.toLowerCase()}`, text: r.origin })),
    el('td', { text: r.decision || DASH }),
    el('td', { text: r.pr ? 'yes' : 'no' })));
  return el('table', { class: 'runs', 'aria-label': 'Runs' }, el('thead', {}, head), el('tbody', {}, rows));
}

export async function render(root, ctx) {
  const m = await ctx.api('GET', '/api/history/metrics');
  const list = el('div', { id: 'run-list' });
  const filter = el('select', { id: 'origin-filter', 'aria-label': 'Filter by origin' },
    ...[['', 'All runs'], ['SIMULATED', 'Simulated'], ['REPLAY', 'Replay']].map(([v, t]) => el('option', { value: v, text: t })));

  async function drawRuns() {
    const q = filter.value ? `?origin=${encodeURIComponent(filter.value)}` : '';
    const h = await ctx.api('GET', `/api/history${q}`);
    clear(list);
    list.append(h.empty ? el('p', { class: 'note', 'data-empty': h.empty.code, text: h.empty.message }) : runsTable(h.runs));
  }
  filter.addEventListener('change', () => drawRuns().catch((e) => list.replaceChildren(el('p', { class: 'error', role: 'alert', text: e.message }))));

  const notes = [
    m.banner && el('p', { class: 'note', role: 'status', text: m.banner }),
    el('p', { class: 'note', text: `Simulated and replay runs are listed below with a badge. They are in no number above (${m.excluded.SIMULATED} simulated, ${m.excluded.REPLAY} replay in the store).` }),
    ...m.skipped.map((s) => el('p', { class: 'note', text: `Left out: ${s.file} (${s.reason}).` })),
  ];
  root.append(...[ // Node.append turns null into the text "null", so empty slots are dropped first
    el('link', { rel: 'stylesheet', href: '/static/screens/history.css' }),
    el('h2', { text: ctx.tab.title }),
    el('p', { text: ctx.tab.purpose }),
    ...notes,
    metricsTable(m.metrics),
    tenantTable(m.metrics.quota_share),
    el('h3', { text: 'Runs' }),
    el('label', {}, 'Show ', filter),
    list,
    el('p', {}, el('a', { href: '#/issue', text: 'Start another issue' })),
  ].filter(Boolean));
  await drawRuns();
}
