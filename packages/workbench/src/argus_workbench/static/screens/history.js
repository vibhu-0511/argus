// Screen "history". Placeholder from the page shell (P10-T02); P10-T09 replaces this module with the real screen.
import { el } from '../dom.js';

export async function render(root, ctx) {
  root.append(
    el('h2', { text: ctx.tab.title }),
    el('p', { text: ctx.tab.purpose }),
    el('p', { class: 'note', text: 'This screen is not built yet in this checkout.' }),
  );
}
