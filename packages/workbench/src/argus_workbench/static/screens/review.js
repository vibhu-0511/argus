// Screen 3: Review and decision (P10-T07). Everything is set with textContent through el(); no markup is built from API text.
// The before/after report is shown only in an <iframe sandbox> with no tokens (no scripts, no same origin), and the report
// route sends its own CSP, so even a direct visit is inert. Approve is disabled here AND refused by the server.
import { clear, el } from '../dom.js';

const CSS_ID = 'review-css';

function loadCss() {
  if (document.getElementById(CSS_ID)) return;
  document.head.append(el('link', { id: CSS_ID, rel: 'stylesheet', href: '/static/screens/review.css' }));
}

function checkRow(c) {
  return el('li', { class: `check ${c.status.replace(' ', '-')}` },
    el('span', { class: 'check-name', text: c.name }),
    el('span', { class: 'check-status', text: c.status }),
    el('span', { class: 'check-reason', text: c.route ? `${c.reason} (${c.route})` : c.reason }));
}

function judgeCard(j) {
  return el('section', { class: `card judge ${j.label === 'fail' ? 'judge-fail' : ''}`, 'aria-label': 'Judge' },
    el('h3', { text: 'Judge' }),
    el('p', { class: 'judge-label', text: `Label: ${j.label}${j.advisory ? ' (advisory)' : ''}` }),
    el('p', { text: j.advisory_note }),
    j.note ? el('p', { text: `Judge note: ${j.note}` }) : null,
    el('p', { text: `Alpha: ${j.alpha}   Order disagreement: ${j.order_disagreement}` }),
    el('p', { class: 'note', text: j.alpha_note }),
    el('p', { class: 'note', text: `Design text, no judge runs in this build: ${j.family}; ${j.model}` }));
}

function patchCard(p) {
  if (p.empty) return el('section', { class: 'card' }, el('h3', { text: 'Patch' }), el('p', { text: 'The patch is empty. No PR will be raised.' }));
  return el('section', { class: 'card' }, el('h3', { text: 'Patch' }),
    el('p', { text: `${p.files.length} file(s), +${p.added} -${p.removed}` }),
    el('ul', {}, p.files.map((f) => el('li', { text: f }))));
}

function option(value, text) {
  return el('option', { value, text: text || value });
}

function decisionPanel(data, ctx, runId, reload) {
  const box = el('section', { class: 'card decide', 'aria-label': 'Decision' }, el('h3', { text: 'Decision' }));
  if (data.decision) {
    const d = data.decision;
    box.append(el('p', { class: 'decided', role: 'status', text: `Decided: ${d.decision}${d.reason ? ` - ${d.reason}` : ''} (${d.decided_at})` }));
    if (data.follow_up_run_id) box.append(el('p', {}, el('a', { href: `#/run/${data.follow_up_run_id}`, text: `Follow-up run ${data.follow_up_run_id}` })));
    if (d.decision === 'approve') box.append(el('p', {}, el('a', { href: `#/pr/${runId}`, text: 'Open the PR screen' })));
    return box;
  }
  const approve = el('button', { type: 'button', text: 'Approve' });
  if (!data.approve.enabled) {
    approve.disabled = true;
    approve.title = data.approve.disabled_reason;
  }
  const changes = el('button', { type: 'button', text: 'Request changes' });
  const reject = el('button', { type: 'button', text: 'Reject' });
  const form = el('div', { class: 'decide-form' });
  const msg = el('p', { class: 'error', role: 'alert' });
  box.append(el('div', { class: 'buttons' }, approve, changes, reject),
    ...(data.approve.enabled ? [] : [el('p', { class: 'note', text: `Approve is disabled: ${data.approve.disabled_reason}` })]), form, msg); // native append would print a null as text

  function open(action) {
    clear(form);
    msg.textContent = '';
    const key = crypto.randomUUID(); // one key per opened panel: pressing Confirm twice cannot decide twice
    let select = null;
    const note = el('textarea', { id: 'decision-note', rows: '3', maxlength: '2000' });
    let label = 'Note';
    if (action === 'approve') label = data.approve.needs_reason ? 'Written reason (required: the judge says fail)' : 'Note (optional)';
    if (action === 'request-changes') {
      label = 'Note for the next run (required)';
      select = el('select', { id: 'decision-reason' }, option('', 'Reason (optional)'), data.change_reasons.map((r) => option(r)));
    }
    if (action === 'reject') {
      label = 'Say what (required when the reason is Other)';
      select = el('select', { id: 'decision-reason' }, option('', 'Choose a reason'), data.reject_reasons.map((r) => option(r)));
    }
    const confirm = el('button', { type: 'button', text: `Confirm ${action}` });
    confirm.addEventListener('click', async () => {
      msg.textContent = '';
      // approve sends its text as `reason` (the server requires it when the judge says fail); the others send `note`
      const body = action === 'approve'
        ? { action, reason: note.value, note: '', idempotency_key: key }
        : { action, reason: select ? select.value : '', note: note.value, idempotency_key: key };
      confirm.disabled = true;
      try {
        const out = await ctx.api('POST', `/api/runs/${runId}/decision`, body);
        if (action === 'request-changes' && out.new_run_id) {
          try {
            await ctx.api('POST', `/api/runs/${out.new_run_id}/start`);
          } catch (e) {
            msg.textContent = `The new run ${out.new_run_id} was created but not started: ${e.message}`;
          }
          ctx.go('run', out.new_run_id);
          return;
        }
        await reload();
      } catch (e) {
        confirm.disabled = false;
        if (e.code === 'already_decided') await reload();
        else msg.textContent = e.message;
      }
    });
    form.append(...(select ? [el('label', { for: 'decision-reason', text: 'Reason' }), select] : []), // native append prints a null as text
      el('label', { for: 'decision-note', text: label }), note, confirm);
  }
  approve.addEventListener('click', () => open('approve'));
  changes.addEventListener('click', () => open('request-changes'));
  reject.addEventListener('click', () => open('reject'));
  return box;
}

export async function render(root, ctx) {
  loadCss();
  root.append(el('h2', { text: ctx.tab.title }), el('p', { text: ctx.tab.purpose }));
  if (!ctx.arg) {
    root.append(el('p', { class: 'note', text: 'Open a run to review it: finish a run on the Run screen, or pick one in History.' }));
    return;
  }
  const runId = ctx.arg;
  const body = el('div', { class: 'review' });
  root.append(body);

  async function load() {
    clear(body);
    let data;
    try {
      data = await ctx.api('GET', `/api/runs/${runId}/review`);
    } catch (e) {
      body.append(el('p', { class: 'error', role: 'alert', text: `Nothing to review for ${runId}: ${e.message}` }));
      return;
    }
    body.append(
      el('p', { class: 'tag', text: `${data.origin} run ${runId}, state ${data.display_state}. Not a model result.` }),
      el('p', {}, el('a', { href: `#/run/${runId}`, text: 'Open the trajectory' })),
      el('section', { class: 'card', 'aria-label': 'Checks' }, el('h3', { text: 'Checks' }),
        el('p', { class: data.verdict_ok ? 'verdict-ok' : 'verdict-fail', text: data.verdict_ok ? 'Verdict: pass' : `Verdict: fail. First failure: ${data.first_failure}` }),
        el('ol', { class: 'checks' }, data.checks.map(checkRow)),
        data.short_circuit_note ? el('p', { class: 'note', text: data.short_circuit_note }) : null),
      judgeCard(data.judge),
      patchCard(data.patch),
      data.report_url
        ? el('section', { class: 'card', 'aria-label': 'Report' }, el('h3', { text: 'Before and after report' }),
          el('iframe', { class: 'report', sandbox: '', src: data.report_url, title: 'Before and after report (sandboxed)' }),
          el('p', {}, el('a', { href: data.report_url, text: 'Open the report on its own page' })))
        : el('p', { class: 'note', text: 'No report was written for this run.' }),
      decisionPanel(data, ctx, runId, load),
    );
  }
  await load();
}
