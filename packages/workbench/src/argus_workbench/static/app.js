// Tab router. Five tabs from GET /api/tabs; the hash picks the screen: #/<tab> or #/<tab>/<run id>.
// Each screen is one ES module, screens/<id>.js, exporting render(root, ctx). ctx = {tab, tabs, arg, api, go}.
// `arg` is the run id from the hash, only when it matches [a-z0-9-]{1,64}; otherwise null.

import { api } from './api.js';
import { clear, el } from './dom.js';

const RUN_ID = /^[a-z0-9-]{1,64}$/;
let tabs = [];

function parseHash() {
  const [, id, arg] = location.hash.split('/');
  return { id: id || 'issue', arg: arg && RUN_ID.test(arg) ? arg : null };
}

export function go(id, arg) {
  location.hash = arg ? `#/${id}/${arg}` : `#/${id}`;
}

function drawTabs(activeId) {
  const nav = clear(document.getElementById('tabs'));
  for (const t of tabs) {
    nav.append(
      el('a', { href: `#/${t.id}`, class: `tab ${t.level}`, title: t.detail, 'aria-current': t.id === activeId ? 'page' : null },
        el('span', { class: 'tab-name', text: `${t.n}. ${t.short}` }),
        el('span', { class: 'tab-label', text: t.label }),
        el('span', { class: 'tab-status', text: t.status })),
    );
  }
}

async function route() {
  const { id, arg } = parseHash();
  const tab = tabs.find((t) => t.id === id) || tabs[0];
  drawTabs(tab.id);
  const root = clear(document.getElementById('screen'));
  try {
    const screen = await import(`./screens/${tab.id}.js`); // tab.id comes from the server's fixed list of five
    await screen.render(root, { tab, tabs, arg, api, go });
  } catch (e) {
    root.append(el('p', { class: 'error', role: 'alert', text: `This screen could not be shown: ${e.message}` }));
  }
}

async function main() {
  try {
    tabs = (await api('GET', '/api/tabs')).tabs;
  } catch (e) {
    document.getElementById('screen').append(el('p', { class: 'error', role: 'alert', text: `Could not load the tabs: ${e.message}` }));
    return;
  }
  window.addEventListener('hashchange', route);
  await route();
}

main();
