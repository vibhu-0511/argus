// Screen 4: PR raised (P10-T08). Everything is set with textContent through el(); the PR title and body are shown as plain text
// (the body in a <pre>), so a title with $(...) or a tag in it is only text. The PR is a draft on a MOCK GitHub: the page says so.
// Mark ready is disabled here and explained: it needs a real QA signal on a real PR.
import { clear, el } from '../dom.js';

const CSS_ID = 'pr-css';

function loadCss() {
  if (document.getElementById(CSS_ID)) return;
  document.head.append(el('link', { id: CSS_ID, rel: 'stylesheet', href: '/static/screens/pr.css' }));
}

function row(name, ...value) {
  return el('div', { class: 'pr-row' }, el('dt', { text: name }), el('dd', {}, ...value));
}

function statesCard(states, current) {
  return el('section', { class: 'card', 'aria-label': 'PR states' }, el('h3', { text: 'States of this screen' }),
    el('ul', { class: 'pr-states' }, states.map((s) => el('li', { class: s.id === current ? 'current' : '' },
      el('strong', { text: s.id }),
      el('span', { text: ` ${s.text} ` }),
      el('em', { text: s.id === current ? '(this run)' : s.reachable ? '' : '(not reachable in this build: needs a real PR)' })))));
}

function prCard(data) {
  const pr = data.pr;
  const traj = pr.links.trajectory;
  const report = pr.links.report;
  return el('section', { class: 'card', 'aria-label': 'Pull request' },
    el('h3', { text: pr.title }),
    el('p', { class: 'badge', text: data.state === 'draft' ? 'Draft' : data.state }),
    el('dl', {},
      row('Branch', el('code', { text: pr.branch })),
      row('Number and URL', `#${pr.number} `, el('code', { text: pr.url }), ' (mock: this address does not exist)'),
      row('This call', `${pr.action}${pr.updates ? `, updated ${pr.updates} time(s) since the first` : ''}; same branch, so never a second PR`),
      row('Verdict', pr.verdict_ok ? 'pass' : 'fail'),
      row('Judge label (advisory)', pr.judge_label),
      row('CI', `${pr.ci.state}. ${pr.ci.note}`),
      row('Trajectory', traj ? el('a', { href: traj, text: 'Open the trajectory file' }) : 'not available'),
      row('Before and after', report ? el('a', { href: report, text: 'Open the report on its own page' }) : 'not available'),
      row('Origin', `${pr.origin} (the run was ${pr.run_origin}); transport: ${pr.transport}`)),
    el('h4', { text: 'Body (plain text)' }),
    el('pre', { class: 'pr-body', text: pr.body }),
    el('h4', { text: 'Backport follow-up' }),
    el('p', { text: `Target ${pr.backport.target_branch} (${pr.backport.target_note}). ${pr.backport.conflict_note} Status: ${pr.backport.status}.` }));
}

function readyGate(data) {
  const button = el('button', { type: 'button', text: 'Mark ready for review' });
  button.disabled = true;
  button.title = data.mark_ready.reason;
  return el('section', { class: 'card', 'aria-label': 'Mark ready' }, el('h3', { text: 'Mark ready for review' }), button,
    el('p', { class: 'note', text: `Disabled: ${data.mark_ready.reason}` }));
}

export async function render(root, ctx) {
  loadCss();
  root.append(el('h2', { text: ctx.tab.title }), el('p', { text: ctx.tab.purpose }));
  if (!ctx.arg) {
    root.append(el('p', { class: 'note', text: 'Open a run to see its PR: approve a run on the Review screen.' }));
    return;
  }
  const runId = ctx.arg;
  const body = el('div', { class: 'pr' });
  root.append(body);

  async function load() {
    clear(body);
    let data;
    try {
      data = await ctx.api('GET', `/api/runs/${runId}/pr`);
    } catch (e) {
      body.append(el('p', { class: 'error', role: 'alert', text: `Nothing to show for ${runId}: ${e.message}` }));
      return;
    }
    const msg = el('p', { class: 'error', role: 'alert' });
    body.append(
      el('p', { class: 'mock-banner', role: 'note', text: data.mock_note }),
      el('p', { class: 'tag', text: `${data.origin} run ${runId}. Not a model result.` }));
    if (data.pr) {
      const update = el('button', { type: 'button', text: 'Approve again: find the PR and update it' });
      update.addEventListener('click', async () => {
        update.disabled = true;
        msg.textContent = '';
        try {
          await ctx.api('POST', `/api/runs/${runId}/pr`);
          await load();
        } catch (e) {
          update.disabled = false;
          msg.textContent = e.message;
        }
      });
      body.append(prCard(data), readyGate(data), el('div', { class: 'buttons' }, update), msg);
    } else {
      const card = el('section', { class: 'card no-pr', 'aria-label': 'No PR' }, el('h3', { text: 'No PR' }), el('p', { role: 'status', text: data.reason }));
      if (data.can_raise) {
        const raise = el('button', { type: 'button', text: 'Raise the PR now' });
        raise.addEventListener('click', async () => {
          raise.disabled = true;
          msg.textContent = '';
          try {
            await ctx.api('POST', `/api/runs/${runId}/pr`);
            await load();
          } catch (e) {
            raise.disabled = false;
            msg.textContent = e.message;
          }
        });
        card.append(raise);
      }
      body.append(card, msg);
    }
    body.append(
      statesCard(data.states, data.state),
      el('p', {}, el('a', { href: `#/review/${runId}`, text: 'Back to the review' }), ' ', el('a', { href: '#/history', text: 'Back to history' })));
  }
  await load();
}
