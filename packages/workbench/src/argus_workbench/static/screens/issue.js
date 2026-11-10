// Screen 1, New issue (P10-T03). Options come from GET /api/issues/options; the form is sent to POST /api/issues as
// multipart; the server is the only judge of what is valid. A refusal is a typed error with a field, shown next to that
// field, and the form (text, file, choices) is left as it was. Text is set with textContent only (dom.js).
import { ApiError } from '../api.js';
import { clear, el } from '../dom.js';

const FIELDS = ['text', 'screenshot', 'repo', 'route', 'ack_public_or_synthetic', 'trigger', 'scenario'];
const STYLE_HREF = '/static/screens/issue.css';

function ensureStyles() {
  if (!document.querySelector(`link[href="${STYLE_HREF}"]`)) {
    document.head.append(el('link', { rel: 'stylesheet', href: STYLE_HREF }));
  }
}

// First bytes decide the type, as on the server. This only fills the preview; the server still decides.
async function sniff(file) {
  const b = new Uint8Array(await file.slice(0, 8).arrayBuffer());
  const png = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  if (b.length >= 8 && png.every((v, i) => b[i] === v)) return { media_type: 'image/png', ext: 'png' };
  if (b.length >= 3 && b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return { media_type: 'image/jpeg', ext: 'jpg' };
  return null;
}

function megabytes(bytes) {
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export async function render(root, ctx) {
  ensureStyles();
  let opts;
  try {
    opts = await ctx.api('GET', '/api/issues/options');
  } catch (e) {
    root.append(el('p', { class: 'error', role: 'alert', text: `Could not load the form options: ${e.message}` }));
    return;
  }
  const view = el('div', { class: 'issue' });
  root.append(el('h2', { text: ctx.tab.title }), el('p', { text: ctx.tab.purpose }), view);
  draw(view, opts, ctx);
}

function draw(view, opts, ctx) {
  clear(view);
  const github = opts.triggers.find((t) => t.id === 'github');
  const form = el('form', { class: 'issue-form', novalidate: true });
  const githubPanel = el('section', { class: 'github-panel', hidden: true });
  const result = el('div', { class: 'issue-result', 'aria-live': 'polite' });
  const picked = { shot: null };

  // ---- trigger switch -------------------------------------------------------------------------------------------
  const triggerBox = el('fieldset', { class: 'trigger' }, el('legend', { text: 'How does the issue arrive?' }));
  for (const t of opts.triggers) {
    const radio = el('input', { type: 'radio', name: 'trigger', value: t.id, id: `trigger-${t.id}`, checked: t.id === 'typed' });
    triggerBox.append(el('label', { for: `trigger-${t.id}` }, radio, ` ${t.label} `, el('span', { class: 'chip', text: t.tag })));
  }
  githubPanel.append(
    el('h3', { text: github.label }),
    el('p', { text: github.blurb }),
    el('p', { class: 'note', text: 'Nothing here is connected to GitHub: no App is registered, so this tab only explains the path. File the issue with the form instead.' }),
  );

  // ---- fields ---------------------------------------------------------------------------------------------------
  const errors = {};
  const inputs = {};
  function field(name, labelText, control, ...extra) {
    const err = el('p', { class: 'field-error', id: `error-${name}`, role: 'alert' });
    errors[name] = err;
    inputs[name] = control;
    control.setAttribute('aria-describedby', `error-${name}`);
    return el('div', { class: 'field' }, el('label', { for: control.id }, labelText), control, ...extra, err);
  }

  const text = el('textarea', { id: 'f-text', name: 'text', rows: 8, placeholder: 'Describe the bug: what you saw, where, how to repeat it.' });
  const counter = el('span', { class: 'note', text: `0 / ${opts.max_text_chars} characters` });

  const fileInput = el('input', { type: 'file', id: 'f-screenshot', name: 'screenshot', accept: opts.media_types.join(',') });
  const fileInfo = el('span', { class: 'note', text: 'No screenshot. PNG or JPEG, up to ' + opts.max_file_mb + ' MB. It stays on this machine and goes only to the local workbench.' });
  const removeFile = el('button', { type: 'button', class: 'link', hidden: true, text: 'Remove screenshot' });
  // the drop zone is the whole screenshot field; it is created below, once field() has built it

  const repo = el('select', { id: 'f-repo', name: 'repo' });
  for (const r of opts.repos) repo.append(el('option', { value: r.id, text: r.built ? r.label : `${r.label} [not built here]` }));
  const repoNote = el('span', { class: 'note' });

  const route = el('select', { id: 'f-route', name: 'route' });
  for (const r of opts.routes) route.append(el('option', { value: r, text: r }));

  const scenario = el('select', { id: 'f-scenario', name: 'scenario' });
  for (const s of opts.scenarios) scenario.append(el('option', { value: s.id, text: s.label, selected: s.id === opts.default_scenario }));
  const scenarioNote = el('span', { class: 'note' });

  const ack = el('input', { type: 'checkbox', id: 'f-ack', name: 'ack_public_or_synthetic' });
  const ackLabel = el('label', { for: 'f-ack', class: 'ack' }, ack,
    ' Only public or synthetic code goes through free tiers, and free-tier prompts may be used for training. I confirm this issue and screenshot hold no private data.');
  errors.ack_public_or_synthetic = el('p', { class: 'field-error', id: 'error-ack_public_or_synthetic', role: 'alert' });
  inputs.ack_public_or_synthetic = ack;
  ack.setAttribute('aria-describedby', 'error-ack_public_or_synthetic');

  const seeded = opts.seeded.available
    ? el('button', { type: 'button', id: 'load-seeded', text: 'Load the real BUG-17 ticket' })
    : null;
  const preview = el('pre', { class: 'preview', 'aria-label': 'Ticket JSON that would be written' });
  const start = el('button', { type: 'submit', id: 'start', text: 'Start run', disabled: true });
  const hint = el('p', { class: 'note', id: 'start-hint' });
  const general = el('p', { class: 'field-error', id: 'error-general', role: 'alert' });
  errors.trigger = errors.scenario = general;

  const drop = field('screenshot', 'Screenshot (optional)', fileInput, fileInfo, removeFile);
  drop.classList.add('drop');
  form.append(
    field('text', 'Issue text', text, counter),
    drop,
    field('repo', 'Repo', repo, repoNote),
    field('route', 'Route to test (viewport ' + opts.viewport + ')', route),
    field('scenario', 'SIMULATED scenario (scripted, nothing here calls a model)', scenario, scenarioNote),
    el('div', { class: 'field' }, ackLabel, errors.ack_public_or_synthetic),
    seeded,
    el('h3', { text: 'Ticket that would be written' }), preview,
    general,
    el('div', { class: 'actions' }, start, hint),
  );

  // ---- state ----------------------------------------------------------------------------------------------------
  function clearErrors() {
    for (const p of Object.values(errors)) p.textContent = '';
    for (const c of Object.values(inputs)) c.removeAttribute('aria-invalid');
  }

  function showError(e) {
    clearErrors();
    const name = e instanceof ApiError && FIELDS.includes(e.field) ? e.field : null;
    if (name && inputs[name]) {
      inputs[name].setAttribute('aria-invalid', 'true');
      errors[name].textContent = e.message;
      if (inputs[name].focus) inputs[name].focus();
    } else {
      general.textContent = e.message || 'Something went wrong.';
    }
  }

  async function refresh() {
    const trimmed = text.value.trim();
    counter.textContent = `${trimmed.length} / ${opts.max_text_chars} characters`;
    const ticket = { id: '(assigned when the run is created)', text: trimmed };
    if (picked.shot) {
      const kind = await sniff(picked.shot);
      ticket.screenshot = { media_type: kind ? kind.media_type : '(not a PNG or JPEG: the server will refuse it)', path: kind ? `shots/screenshot.${kind.ext}` : '' };
      fileInfo.textContent = `${picked.shot.name} (${megabytes(picked.shot.size)})`;
    } else {
      fileInfo.textContent = 'No screenshot. PNG or JPEG, up to ' + opts.max_file_mb + ' MB. It stays on this machine and goes only to the local workbench.';
    }
    removeFile.hidden = !picked.shot;
    preview.textContent = JSON.stringify(ticket, null, 2);
    const missing = [];
    if (!trimmed) missing.push('the issue text');
    if (!ack.checked) missing.push('the acknowledgement');
    start.disabled = missing.length > 0 || start.dataset.busy === '1';
    hint.textContent = missing.length ? `To start, add: ${missing.join(' and ')}.` : 'Ready. Start creates the run and starts the scripted scenario.';
    const r = opts.repos.find((x) => x.id === repo.value);
    repoNote.textContent = r ? r.note : '';
    const s = opts.scenarios.find((x) => x.id === scenario.value);
    scenarioNote.textContent = s ? s.effect : '';
  }

  function setFile(file) {
    picked.shot = file || null;
    if (!file) fileInput.value = '';
    refresh();
  }

  text.addEventListener('input', refresh);
  ack.addEventListener('change', refresh);
  repo.addEventListener('change', refresh);
  scenario.addEventListener('change', refresh);
  fileInput.addEventListener('change', () => setFile(fileInput.files[0]));
  removeFile.addEventListener('click', () => { clearErrors(); setFile(null); });
  drop.addEventListener('dragover', (ev) => { ev.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('over'));
  drop.addEventListener('drop', (ev) => {
    ev.preventDefault();
    drop.classList.remove('over');
    const file = ev.dataTransfer && ev.dataTransfer.files[0];
    if (file) {
      const box = new DataTransfer();
      box.items.add(file);
      fileInput.files = box.files;
      setFile(file);
    }
  });

  if (seeded) {
    seeded.addEventListener('click', async () => {
      clearErrors();
      try {
        const ticket = await ctx.api('GET', '/api/issues/seeded/bug-17');
        text.value = ticket.text;
        if (ticket.has_screenshot) {
          const response = await fetch('/api/issues/seeded/bug-17/screenshot', { credentials: 'same-origin' });
          if (!response.ok) throw new Error('the seeded screenshot could not be loaded');
          const file = new File([await response.blob()], 'bug-17.png', { type: 'image/png' });
          const box = new DataTransfer();
          box.items.add(file);
          fileInput.files = box.files;
          picked.shot = file;
        }
        await refresh();
      } catch (e) {
        showError(e);
      }
    });
  }

  for (const radio of triggerBox.querySelectorAll('input')) {
    radio.addEventListener('change', () => {
      const typed = triggerBox.querySelector('input:checked').value === 'typed';
      form.hidden = !typed;
      githubPanel.hidden = typed;
    });
  }

  // ---- submit ---------------------------------------------------------------------------------------------------
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    if (start.dataset.busy === '1') return; // a double click makes one request
    start.dataset.busy = '1';
    start.disabled = true;
    clearErrors();
    const body = new FormData();
    body.append('trigger', 'typed');
    body.append('text', text.value);
    if (picked.shot) body.append('screenshot', picked.shot);
    body.append('repo', repo.value);
    body.append('route', route.value);
    body.append('scenario', scenario.value);
    body.append('ack_public_or_synthetic', ack.checked ? 'true' : 'false');
    let created;
    try {
      created = await ctx.api('POST', '/api/issues', body);
    } catch (e) {
      start.dataset.busy = '0';
      showError(e);
      await refresh();
      return;
    }
    try {
      await ctx.api('POST', `/api/runs/${created.run_id}/start`);
      ctx.go('run', created.run_id);
    } catch (e) {
      form.hidden = true;
      const missing = e instanceof ApiError && (e.code === 'not_found' || e.code === 'method_not_allowed');
      clear(result).append(
        el('p', { text: `Run ${created.run_id} was created in state received.` }),
        el('p', { class: missing ? 'note' : 'field-error', role: missing ? null : 'alert',
          text: missing ? 'The runner is not built in this checkout (POST /api/runs/{id}/start does not exist), so the run waits and nothing plays.' : `The run could not be started: ${e.message}` }),
        el('a', { href: `#/run/${created.run_id}`, text: 'Open the run' }),
      );
    }
  });

  view.append(triggerBox, githubPanel, form, result);
  refresh();
}
