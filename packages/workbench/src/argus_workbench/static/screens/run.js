// Screen 2: Live run (P10-T06). Shows one run: stage bar, step timeline with tokens, quota meter, Start / Stop / Retry.
//
// POLLING, not SSE: while GET /api/runs/{id} says poll.again, this page asks again after poll.interval_ms and stops
// as soon as the run is not playing. The page is built once and updated in place, so a click is never lost to a redraw.
// All text goes in with textContent (dom.js); nothing from a run is ever treated as markup. Style comes from run.css
// (no inline style, the CSP forbids it), so the meter is a native <meter> and not a div with a width.

import { clear, el } from '../dom.js';

const DASH = '—';
const NUMBER = new Intl.NumberFormat('en-US');
const n = (value) => (value === null || value === undefined ? DASH : NUMBER.format(value));

function ensureStyles() {
  if (!document.querySelector('link[data-screen="run"]')) {
    document.head.append(el('link', { rel: 'stylesheet', href: '/static/screens/run.css', 'data-screen': 'run' }));
  }
}

function buildMeter(box, meter) {
  clear(box);
  box.append(el('h3', { text: 'Quota meter' }));
  if (!meter.rows.length) {
    box.append(el('p', { class: 'meter-empty', text: `${DASH} no ledger data` }), el('p', { class: 'note', text: meter.note }));
    return;
  }
  for (const r of meter.rows) {
    const caption = r.cap === null
      ? `${r.model}: ${n(r.used)} ${r.limit}, no quota row for this model`
      : `${r.model}: ${n(r.used)} of ${n(r.cap)} ${r.limit} (${r.percent}%)${r.over ? ', over the cap' : ''}`;
    box.append(
      el('div', { class: `meter-row${r.over ? ' over' : ''}` },
        el('span', { class: 'meter-name', text: caption }),
        r.cap === null ? null : el('meter', { min: 0, max: 100, low: 60, high: 90, optimum: 0, value: r.percent, 'aria-label': caption }),
        r.illustrative ? el('span', { class: 'badge badge-illustrative', text: 'ILLUSTRATIVE' }) : null),
    );
  }
  box.append(el('p', { class: 'note', text: meter.note }));
}

function stepRow(s) {
  const what = [s.text, s.tool_error && s.tool_error !== s.text ? `error: ${s.tool_error}` : null].filter(Boolean).join(' | ');
  return el('tr', { class: s.repeat ? 'repeat' : null },
    el('td', { text: s.index + 1 }), el('td', { text: s.stage || DASH }),
    el('td', { text: s.repeat ? `${s.tool} (repeated call)` : s.tool || DASH }), el('td', { text: what || DASH }),
    el('td', { class: 'num', text: n(s.tokens_in) }), el('td', { class: 'num', text: n(s.tokens_out) }), el('td', { class: 'num', text: n(s.tokens_cached) }),
    el('td', { text: s.stop_reason || '' }));
}

function build(view, ctx) {
  const id = ctx.arg;
  const ui = { onChange: () => {}, rows: 0 };
  const title = el('p', { class: 'run-title' });
  const badge = el('span', { class: 'badge' });
  const pill = el('span', { class: 'pill', role: 'status' });
  const originNote = el('p', { class: 'note' });
  const reason = el('div', { class: 'reason', role: 'status', hidden: true });
  const stages = el('ol', { class: 'stages', 'aria-label': 'Stages' });
  const message = el('p', { class: 'error', role: 'alert', hidden: true });
  const meterBox = el('section', { class: 'meter' });
  const body = el('tbody');
  const empty = el('p', { class: 'note', text: 'No steps yet.' });
  const totals = el('tfoot');

  const fail = (e) => {
    message.hidden = false;
    message.textContent = e.message || String(e);
  };
  const act = async (fn) => {
    message.hidden = true;
    try {
      await fn();
    } catch (e) {
      fail(e);
    }
    ui.onChange();
  };

  const start = el('button', { type: 'button', text: 'Start run' });
  const stop = el('button', { type: 'button', text: 'Stop run' });
  const cancel = el('button', { type: 'button', text: 'Cancel', hidden: true });
  const retry = el('button', { type: 'button', text: 'Retry (new run)' });
  const hint = el('p', { class: 'note hint' });
  const next = el('p', { class: 'next', hidden: true });
  let confirming = false;
  const setConfirming = (on) => {
    confirming = on;
    stop.textContent = on ? 'Confirm stop' : 'Stop run';
    cancel.hidden = !on;
  };
  start.addEventListener('click', () => act(() => ctx.api('POST', `/api/runs/${id}/start`)));
  stop.addEventListener('click', () => {
    if (!confirming) return setConfirming(true);
    setConfirming(false);
    return act(() => ctx.api('POST', `/api/runs/${id}/stop`));
  });
  cancel.addEventListener('click', () => setConfirming(false));
  retry.addEventListener('click', async () => {
    message.hidden = true;
    try {
      const made = await ctx.api('POST', `/api/runs/${id}/retry`);
      ctx.go('run', made.state.run_id);
    } catch (e) {
      fail(e);
      ui.onChange();
    }
  });

  view.append(
    el('h2', { text: 'Live run' }), title, originNote, reason,
    el('div', { class: 'controls' }, start, stop, cancel, retry), hint, message, next,
    stages, meterBox,
    el('h3', { text: 'Steps' }), empty,
    el('table', { class: 'steps' },
      el('thead', {}, el('tr', {}, ...['#', 'Stage', 'Tool', 'What', 'In', 'Out', 'Cached', 'Stop reason'].map((h) => el('th', { scope: 'col', text: h })))),
      body, totals),
  );

  ui.fail = fail;
  ui.update = (d) => {
    const run = d.run;
    clear(title).append(el('code', { text: run.run_id }), ' ', badge, ' ', pill);
    badge.className = `badge badge-${d.origin.tag.toLowerCase()}`;
    badge.textContent = d.origin.tag;
    pill.className = `pill state-${run.display_state}`;
    pill.textContent = run.display_state;
    if (run.created_by_retry_of) title.append(' ', el('a', { href: `#/run/${run.created_by_retry_of}`, text: `retry of ${run.created_by_retry_of}` }));
    originNote.textContent = d.origin.note;

    reason.hidden = !d.reason;
    if (d.reason) {
      reason.className = `reason kind-${d.reason.kind}`;
      clear(reason).append(el('strong', { text: d.reason.label }), el('p', { text: d.reason.text }));
      if (d.reason.kind === 'quota' && d.actions.retry.reset_text) reason.append(el('p', { text: `Retry opens when the quota resets: ${d.actions.retry.reset_text}.` }));
    }

    clear(stages).append(...d.stages.map((s) => el('li', { class: `stage s-${s.status}`, 'aria-current': s.status === 'running' ? 'step' : null },
      el('strong', { text: s.label }), el('span', { class: 'stage-status', text: s.status }),
      el('span', { class: 'stage-count', text: `${s.steps} step${s.steps === 1 ? '' : 's'}, ${n(s.tokens)} tokens` }))));

    buildMeter(meterBox, d.meter);

    empty.hidden = d.steps.length > 0;
    if (d.steps.length < ui.rows) {
      clear(body); // fewer steps than shown: start the list again
      ui.rows = 0;
    }
    for (const s of d.steps.slice(ui.rows)) body.append(stepRow(s));
    ui.rows = d.steps.length;
    // a repeat flag can turn on for earlier rows when the third identical call arrives: refresh the flag on all rows
    [...body.children].forEach((tr, i) => tr.classList.toggle('repeat', Boolean(d.steps[i] && d.steps[i].repeat)));
    clear(totals).append(el('tr', {},
      el('th', { scope: 'row', colspan: 4, text: `Total, ${d.origin.tag}` }),
      el('td', { class: 'num', text: n(d.totals.tokens_in) }), el('td', { class: 'num', text: n(d.totals.tokens_out) }),
      el('td', { class: 'num', text: n(d.totals.tokens_cached) }), el('td')));

    // T14: a way forward from this screen (the tabs carry no run id). Only a run that has a verdict to review gets it.
    const reviewable = ['awaiting-qa', 'done', 'rejected'].includes(run.state) || (d.reason && d.reason.kind === 'verifier');
    next.hidden = !reviewable;
    clear(next).append(el('a', { href: `#/review/${run.run_id}`, text: 'Open the review of this run' }));
    const a = d.actions;
    start.hidden = run.state !== 'received';
    start.disabled = !a.start.enabled;
    start.title = a.start.why;
    stop.disabled = !a.stop.enabled;
    stop.title = a.stop.why;
    if (!a.stop.enabled) setConfirming(false);
    retry.disabled = !a.retry.enabled;
    retry.title = a.retry.why;
    hint.textContent = [
      run.state === 'received' ? `Start: ${a.start.why}.` : null,
      a.retry.enabled ? null : `Retry is disabled: ${a.retry.why}${a.retry.reset_text ? ` (${a.retry.reset_text})` : ''}.`,
    ].filter(Boolean).join(' ');
  };
  return ui;
}

export async function render(root, ctx) {
  if (!ctx.arg) {
    root.append(el('h2', { text: ctx.tab.title }), el('p', { text: 'No run is open.' }),
      el('p', {}, 'Start one from ', el('a', { href: '#/issue', text: 'New issue' }), '.'));
    return;
  }
  ensureStyles();
  const view = el('section', { class: 'run' });
  root.append(view);
  const ui = build(view, ctx);
  let timer = null;
  const poll = async () => {
    clearTimeout(timer);
    if (!view.isConnected) return; // the person went to another screen or run: stop asking
    let data;
    try {
      data = await ctx.api('GET', `/api/runs/${encodeURIComponent(ctx.arg)}`);
    } catch (e) {
      ui.fail(e);
      return;
    }
    if (!view.isConnected) return;
    ui.update(data);
    if (data.poll.again) timer = setTimeout(poll, data.poll.interval_ms);
  };
  ui.onChange = poll;
  await poll();
}
