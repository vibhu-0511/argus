// Build DOM with textContent only. Nothing in this app turns text into markup: no HTML-string APIs, no document
// write, no dynamic code (tests/test_static.py scans every script for them). A ticket text, run id or reviewer note that
// contains a script tag shows up as plain text.

const BAD_ATTR = /^(on|style$|srcdoc$)/i;
const URL_ATTR = /^(href|src|action|formaction)$/i;

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (name === 'class') node.className = String(value);
    else if (name === 'text') node.textContent = String(value);
    else if (BAD_ATTR.test(name)) throw new Error(`attribute ${name} is not allowed`);
    else if (URL_ATTR.test(name) && !/^(#|\/(?!\/))/.test(String(value))) throw new Error(`${name} must be a same-origin path`);
    else node.setAttribute(name, value === true ? '' : String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function clear(node) {
  node.replaceChildren();
  return node;
}
