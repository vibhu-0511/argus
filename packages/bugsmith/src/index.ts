/**
 * Deterministic JSX/CSS mutation pipeline.
 * No model call and no clock: a seed is mixed with the source UTF-8 bytes only.
 *
 * P0-T22 and P0-T23 fill `jsxOperators` and `cssOperators`.
 */

import { changeUnit, deleteRule, overflow as overflowOperator, zIndex } from "./operators/css.ts";
import { changeElement, dropProp, removeClass, swapFlexDirection } from "./operators/jsx.ts";

export type Archetype =
  | "font-size"
  | "flex-direction"
  | "overflow"
  | "z-index"
  | "missing-style"
  | "wrong-element";

export type JsxOperatorId =
  | "remove-class"
  | "swap-flex-direction"
  | "drop-prop"
  | "change-element";

export type CssOperatorId = "delete-rule" | "change-unit" | "z-index" | "overflow";

/** Archetype each later operator must report. Ids match docs/bug-archetypes.md. */
export const OPERATOR_ARCHETYPE: Record<JsxOperatorId | CssOperatorId, Archetype> = {
  "remove-class": "missing-style",
  "swap-flex-direction": "flex-direction",
  "drop-prop": "wrong-element",
  "change-element": "wrong-element",
  "delete-rule": "missing-style",
  "change-unit": "font-size",
  "z-index": "z-index",
  overflow: "overflow",
};

export type SourceFile = {
  /** Repo-relative path. Copied into the unified diff headers. */
  path: string;
  /** File contents. Hashed as UTF-8 bytes with the seed. */
  text: string;
};

export type Span = { start: number; end: number };

export type Edit = { span: Span; replacement: string };

export type ClassToken = { text: string; span: Span };

export type JsxProp = {
  /** Attribute name, or `"..."` for a `{...spread}`. */
  name: string;
  /** Attribute text, not including the leading space. */
  span: Span;
  nameSpan: Span;
  /** Quoted text without quotes, a `{...}` expression, or null for a boolean attribute. */
  value: string | null;
  valueSpan: Span | null;
};

export type JsxClassName = {
  span: Span;
  raw: string;
  /** Empty when the value is not a string literal. Tokens are in source order. */
  tokens: ClassToken[];
};

export type JsxElement = {
  name: string;
  nameSpan: Span;
  closeNameSpan: Span | null;
  openSpan: Span;
  selfClosing: boolean;
  props: JsxProp[];
  className: JsxClassName | null;
};

export type CssDeclaration = {
  property: string;
  propertySpan: Span;
  value: string;
  valueSpan: Span;
  /** Property through its semicolon, when the semicolon is present. */
  span: Span;
};

export type CssRule = {
  selector: string;
  selectorSpan: Span;
  /** Selector through the closing brace. */
  span: Span;
  declarations: CssDeclaration[];
};

export type ParsedSource = {
  path: string;
  text: string;
  language: "jsx" | "css";
  elements: JsxElement[];
  rules: CssRule[];
};

export type OperatorContext = {
  /** The seed passed to `applyOperator`, unchanged. */
  readonly seed: number;
  /**
   * Integer in `[0, count)`. Each call advances a counter mixed from the seed,
   * the operator id, and the source UTF-8 bytes. Same inputs, same sequence.
   */
  pick(count: number): number;
};

export type MutationOperator = {
  readonly id: string;
  readonly archetype: Archetype;
  readonly language: "jsx" | "css";
  /** Pure function of `file` and `ctx`. Return null when the file has no site. */
  edit(file: ParsedSource, ctx: OperatorContext): Edit | null;
};

export type JsxOperator = MutationOperator & { readonly language: "jsx" };
export type CssOperator = MutationOperator & { readonly language: "css" };

/** P0-T22. Each operator edits one span chosen from the seed. */
export const jsxOperators: Record<JsxOperatorId, JsxOperator> = {
  "remove-class": removeClass,
  "swap-flex-direction": swapFlexDirection,
  "drop-prop": dropProp,
  "change-element": changeElement,
};

/** P0-T23. Each operator edits one span chosen from the seed. */
export const cssOperators: Record<CssOperatorId, CssOperator> = {
  "delete-rule": deleteRule,
  "change-unit": changeUnit,
  "z-index": zIndex,
  overflow: overflowOperator,
};

export type OperatorResult = {
  /** Unified diff. Byte-identical for the same operator, source bytes, and seed. */
  patch: string;
  archetype: Archetype;
  operatorId: string;
};

const CONTEXT = 3;

export function languageOf(path: string): "jsx" | "css" {
  return path.endsWith(".css") ? "css" : "jsx";
}

export function parseSource(source: SourceFile): ParsedSource {
  const language = languageOf(source.path);
  if (language === "css") {
    return { path: source.path, text: source.text, language, elements: [], rules: parseCss(source.text) };
  }
  return { path: source.path, text: source.text, language, elements: parseJsx(source.text), rules: [] };
}

/**
 * Parse `source`, ask `operator` for one edit, and return a unified diff.
 * The same operator, the same source UTF-8 bytes, and the same seed return
 * the same patch string. Returns null when the operator applies nothing.
 */
export function applyOperator(
  operator: MutationOperator,
  source: SourceFile,
  seed: number,
): OperatorResult | null {
  if (!Number.isInteger(seed)) throw new Error("seed must be an integer");
  const parsed = parseSource(source);
  if (parsed.language !== operator.language) return null;
  const edit = operator.edit(parsed, operatorContext(seed, source.text, operator.id));
  if (!edit) return null;
  if (!Number.isInteger(edit.span.start) || !Number.isInteger(edit.span.end)) {
    throw new Error("edit span must be integers");
  }
  if (edit.span.start < 0 || edit.span.end > source.text.length || edit.span.start > edit.span.end) {
    throw new Error("edit span is outside the source");
  }
  const next = source.text.slice(0, edit.span.start) + edit.replacement + source.text.slice(edit.span.end);
  if (next === source.text) return null;
  const patch = unifiedDiff(source.path, source.text, next);
  if (patch === "") return null;
  return { patch, archetype: operator.archetype, operatorId: operator.id };
}

function operatorContext(seed: number, source: string, operatorId: string): OperatorContext {
  const enc = new TextEncoder();
  let state = fnv1a(enc.encode(source));
  state = fnv1a(enc.encode(operatorId), state);
  const s = seed >>> 0;
  state = fnv1a(new Uint8Array([s & 0xff, (s >>> 8) & 0xff, (s >>> 16) & 0xff, s >>> 24]), state);
  if (state === 0) state = 0x6d2b79f5;
  return {
    seed,
    pick(count: number): number {
      if (!Number.isInteger(count) || count < 1) throw new Error("pick count must be a positive integer");
      const choice = state % count;
      state = mix32(state);
      return choice;
    },
  };
}

function fnv1a(bytes: Uint8Array, hash = 2166136261): number {
  let h = hash >>> 0;
  for (let i = 0; i < bytes.length; i++) {
    h ^= bytes[i];
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function mix32(h: number): number {
  let x = h >>> 0;
  x = Math.imul(x ^ (x >>> 16), 0x7feb352d);
  x = Math.imul(x ^ (x >>> 15), 0x846ca68b);
  x = (x ^ (x >>> 16)) >>> 0;
  return x === 0 ? 0x6d2b79f5 : x;
}

function unifiedDiff(path: string, before: string, after: string): string {
  if (before === after) return "";
  const old = splitLines(before);
  const neu = splitLines(after);
  const a = old.lines;
  const b = neu.lines;
  let lo = 0;
  while (lo < a.length && lo < b.length && a[lo] === b[lo]) lo++;
  let aHi = a.length;
  let bHi = b.length;
  while (aHi > lo && bHi > lo && a[aHi - 1] === b[bHi - 1]) {
    aHi--;
    bHi--;
  }
  if (lo === aHi && lo === bHi && a.length > 0) {
    lo = a.length - 1;
    aHi = a.length;
    bHi = b.length;
  }
  const from = Math.max(0, lo - CONTEXT);
  const suffix = Math.min(CONTEXT, a.length - aHi, b.length - bHi);
  const oldCount = lo - from + (aHi - lo) + suffix;
  const newCount = lo - from + (bHi - lo) + suffix;
  const body: string[] = [];
  const emit = (prefix: string, line: string, mark: boolean) => {
    body.push(prefix + line);
    if (mark) body.push("\\ No newline at end of file");
  };
  const oldMissing = (index: number) => a.length > 0 && index === a.length - 1 && !old.nl;
  const newMissing = (index: number) => b.length > 0 && index === b.length - 1 && !neu.nl;
  for (let k = from; k < lo; k++) emit(" ", a[k], oldMissing(k) || newMissing(k));
  for (let k = lo; k < aHi; k++) emit("-", a[k], oldMissing(k));
  for (let k = lo; k < bHi; k++) emit("+", b[k], newMissing(k));
  for (let k = 0; k < suffix; k++) emit(" ", a[aHi + k], oldMissing(aHi + k) || newMissing(bHi + k));
  const oldRange = oldCount === 0 ? "0,0" : `${from + 1},${oldCount}`;
  const newRange = newCount === 0 ? "0,0" : `${from + 1},${newCount}`;
  return `--- a/${path}\n+++ b/${path}\n@@ -${oldRange} +${newRange} @@\n${body.join("\n")}\n`;
}

function splitLines(text: string): { lines: string[]; nl: boolean } {
  if (text === "") return { lines: [], nl: true };
  const nl = text.endsWith("\n");
  const lines = text.split("\n");
  if (nl) lines.pop();
  return { lines, nl };
}

function isWs(c: string | undefined): boolean {
  return c === " " || c === "\n" || c === "\t" || c === "\r" || c === "\f";
}

function isIdentStart(c: string | undefined): boolean {
  if (!c) return false;
  const code = c.charCodeAt(0);
  return (code >= 65 && code <= 90) || (code >= 97 && code <= 122) || c === "_" || c === "$";
}

function isIdentPart(c: string | undefined): boolean {
  if (!c) return false;
  const code = c.charCodeAt(0);
  return isIdentStart(c) || (code >= 48 && code <= 57) || c === "-";
}

function parseCss(text: string): CssRule[] {
  const rules: CssRule[] = [];
  parseCssRules(text, 0, text.length, rules);
  return rules;
}

function parseCssRules(text: string, from: number, to: number, out: CssRule[]): void {
  let i = from;
  while (i < to) {
    i = skipCssGap(text, i, to);
    if (i >= to || text[i] === "}") return;
    const selStart = i;
    let j = i;
    while (j < to && text[j] !== "{" && text[j] !== "}") {
      if (text.startsWith("/*", j)) {
        j = skipCssComment(text, j, to);
        continue;
      }
      j++;
    }
    if (j >= to || text[j] !== "{") return;
    const bodyClose = matchCssBrace(text, j, to);
    const rawSel = text.slice(selStart, j);
    const lead = rawSel.length - rawSel.trimStart().length;
    const selector = rawSel.trim();
    if (selector.length > 0) {
      out.push({
        selector,
        selectorSpan: { start: selStart + lead, end: selStart + lead + selector.length },
        span: { start: selStart, end: Math.min(to, bodyClose + 1) },
        declarations: parseDeclarations(text, j + 1, bodyClose),
      });
    }
    parseCssRules(text, j + 1, bodyClose, out);
    i = bodyClose + 1;
  }
}

function parseDeclarations(text: string, from: number, to: number): CssDeclaration[] {
  const decls: CssDeclaration[] = [];
  let i = from;
  while (i < to) {
    i = skipCssGap(text, i, to);
    if (i >= to || text[i] === "}") break;
    let j = i;
    let colon = -1;
    let brace = -1;
    let quote = "";
    while (j < to && text[j] !== ";" && text[j] !== "}") {
      if (!quote && text.startsWith("/*", j)) {
        j = skipCssComment(text, j, to);
        continue;
      }
      const c = text[j];
      if (quote) {
        if (c === "\\") j += 2;
        else {
          if (c === quote) quote = "";
          j++;
        }
        continue;
      }
      if (c === '"' || c === "'") {
        quote = c;
        j++;
        continue;
      }
      if (c === "{") {
        brace = j;
        break;
      }
      if (c === ":" && colon < 0) colon = j;
      j++;
    }
    if (brace >= 0) {
      i = matchCssBrace(text, brace, to) + 1;
      continue;
    }
    if (colon < 0) {
      i = text[j] === ";" ? j + 1 : j;
      continue;
    }
    const rawProp = text.slice(i, colon);
    const propLead = rawProp.length - rawProp.trimStart().length;
    const property = rawProp.trim();
    const semi = j < to && text[j] === ";" ? j : j;
    const rawVal = text.slice(colon + 1, semi);
    const valLead = rawVal.length - rawVal.trimStart().length;
    const value = rawVal.trim();
    const end = semi < to && text[semi] === ";" ? semi + 1 : semi;
    if (property.length > 0) {
      decls.push({
        property,
        propertySpan: { start: i + propLead, end: i + propLead + property.length },
        value,
        valueSpan: { start: colon + 1 + valLead, end: colon + 1 + valLead + value.length },
        span: { start: i + propLead, end },
      });
    }
    i = end;
  }
  return decls;
}

function skipCssGap(text: string, i: number, to: number): number {
  while (i < to) {
    if (isWs(text[i])) {
      i++;
      continue;
    }
    if (text.startsWith("/*", i)) {
      i = skipCssComment(text, i, to);
      continue;
    }
    break;
  }
  return i;
}

function skipCssComment(text: string, i: number, to: number): number {
  const end = text.indexOf("*/", i + 2);
  if (end === -1 || end + 2 > to) return to;
  return end + 2;
}

function matchCssBrace(text: string, open: number, limit: number): number {
  let depth = 0;
  let i = open;
  let quote = "";
  while (i < limit) {
    if (!quote && text.startsWith("/*", i)) {
      i = skipCssComment(text, i, limit);
      continue;
    }
    const c = text[i];
    if (quote) {
      if (c === "\\") i += 2;
      else {
        if (c === quote) quote = "";
        i++;
      }
      continue;
    }
    if (c === '"' || c === "'") {
      quote = c;
      i++;
      continue;
    }
    if (c === "{") depth++;
    else if (c === "}") {
      depth--;
      if (depth === 0) return i;
    }
    i++;
  }
  return Math.max(open, limit - 1);
}

type Frame =
  | { kind: "code"; depth: number | null }
  | { kind: "text"; element: JsxElement }
  | { kind: "template" };

type ReadTag =
  | { kind: "close"; name: string; nameSpan: Span; next: number }
  | { kind: "open"; element: JsxElement; next: number };

/**
 * ponytail: a scanner, not a JS parser. It misses tags inside regex literals
 * and treats `Identifier<T>` as a type argument. Upgrade path: a real JSX
 * parser if an operator edits the wrong span.
 */
function parseJsx(text: string): JsxElement[] {
  const elements: JsxElement[] = [];
  const stack: Frame[] = [{ kind: "code", depth: null }];
  let i = 0;
  while (i < text.length) {
    const frame = stack[stack.length - 1];
    if (frame.kind === "template") {
      if (text[i] === "\\") {
        i += 2;
        continue;
      }
      if (text[i] === "`") {
        stack.pop();
        i++;
        continue;
      }
      if (text[i] === "$" && text[i + 1] === "{") {
        stack.push({ kind: "code", depth: 1 });
        i += 2;
        continue;
      }
      i++;
      continue;
    }
    if (frame.kind === "text") {
      if (text[i] === "{") {
        stack.push({ kind: "code", depth: 1 });
        i++;
        continue;
      }
      if (text[i] === "<") {
        const tag = readTag(text, i);
        if (!tag) {
          i++;
          continue;
        }
        i = tag.next;
        if (tag.kind === "close") {
          if (tag.name === frame.element.name) {
            frame.element.closeNameSpan = tag.nameSpan;
            stack.pop();
          }
          continue;
        }
        elements.push(tag.element);
        if (!tag.element.selfClosing) stack.push({ kind: "text", element: tag.element });
        continue;
      }
      i++;
      continue;
    }
    if (frame.depth !== null && text[i] === "{") {
      frame.depth++;
      i++;
      continue;
    }
    if (frame.depth !== null && text[i] === "}") {
      frame.depth--;
      i++;
      if (frame.depth === 0) stack.pop();
      continue;
    }
    if (text[i] === "'" || text[i] === '"') {
      i = skipQuoted(text, i);
      continue;
    }
    if (text[i] === "`") {
      stack.push({ kind: "template" });
      i++;
      continue;
    }
    if (text[i] === "/" && text[i + 1] === "/") {
      i += 2;
      while (i < text.length && text[i] !== "\n") i++;
      continue;
    }
    if (text[i] === "/" && text[i + 1] === "*") {
      const end = text.indexOf("*/", i + 2);
      i = end === -1 ? text.length : end + 2;
      continue;
    }
    if (text[i] === "<" && canStartJsx(text, i)) {
      const tag = readTag(text, i);
      if (!tag) {
        i++;
        continue;
      }
      i = tag.next;
      if (tag.kind === "close") continue;
      elements.push(tag.element);
      if (!tag.element.selfClosing) stack.push({ kind: "text", element: tag.element });
      continue;
    }
    i++;
  }
  return elements;
}

function canStartJsx(text: string, lt: number): boolean {
  let j = lt - 1;
  while (j >= 0 && isWs(text[j])) j--;
  if (j < 0) return true;
  return !isIdentPart(text[j]);
}

function readTag(text: string, lt: number): ReadTag | null {
  let i = lt + 1;
  let closing = false;
  if (text[i] === "/") {
    closing = true;
    i++;
  }
  if (text[i] === ">") {
    const nameSpan = { start: i, end: i };
    if (closing) return { kind: "close", name: "", nameSpan, next: i + 1 };
    return { kind: "open", element: makeElement("", nameSpan, [], { start: lt, end: i + 1 }, false), next: i + 1 };
  }
  if (!isIdentStart(text[i])) return null;
  const nameStart = i;
  i++;
  while (i < text.length && (isIdentPart(text[i]) || text[i] === ".")) i++;
  const name = text.slice(nameStart, i);
  const nameSpan = { start: nameStart, end: i };
  if (closing) {
    while (i < text.length && isWs(text[i])) i++;
    if (text[i] !== ">") return null;
    return { kind: "close", name, nameSpan, next: i + 1 };
  }
  const props: JsxProp[] = [];
  while (i < text.length) {
    while (i < text.length && isWs(text[i])) i++;
    if (text[i] === ">") {
      i++;
      return { kind: "open", element: makeElement(name, nameSpan, props, { start: lt, end: i }, false), next: i };
    }
    if (text[i] === "/" && text[i + 1] === ">") {
      i += 2;
      return { kind: "open", element: makeElement(name, nameSpan, props, { start: lt, end: i }, true), next: i };
    }
    const before = i;
    if (text[i] === "{") {
      const end = skipBraces(text, i);
      props.push({
        name: "...",
        span: { start: i, end },
        nameSpan: { start: i, end },
        value: text.slice(i, end),
        valueSpan: { start: i, end },
      });
      i = end;
      if (i === before) return null;
      continue;
    }
    if (!isIdentStart(text[i])) return null;
    const propStart = i;
    while (i < text.length && isIdentPart(text[i])) i++;
    const propName = text.slice(propStart, i);
    const propNameSpan = { start: propStart, end: i };
    while (i < text.length && isWs(text[i])) i++;
    if (text[i] !== "=") {
      props.push({ name: propName, span: { start: propStart, end: i }, nameSpan: propNameSpan, value: null, valueSpan: null });
      continue;
    }
    i++;
    while (i < text.length && isWs(text[i])) i++;
    let value: string | null = null;
    let valueSpan: Span | null = null;
    if (text[i] === '"' || text[i] === "'") {
      const quoted = readQuoted(text, i);
      value = quoted.value;
      valueSpan = quoted.span;
      i = quoted.next;
    } else if (text[i] === "{") {
      const end = skipBraces(text, i);
      value = text.slice(i, end);
      valueSpan = { start: i, end };
      i = end;
    } else {
      return null;
    }
    props.push({ name: propName, span: { start: propStart, end: i }, nameSpan: propNameSpan, value, valueSpan });
    if (i === before) return null;
  }
  return null;
}

function makeElement(name: string, nameSpan: Span, props: JsxProp[], openSpan: Span, selfClosing: boolean): JsxElement {
  return {
    name,
    nameSpan,
    closeNameSpan: null,
    openSpan,
    selfClosing,
    props,
    className: classFromProps(props),
  };
}

function classFromProps(props: JsxProp[]): JsxClassName | null {
  const prop = props.find((item) => item.name === "className" && item.value !== null && item.valueSpan !== null);
  if (!prop || prop.value === null || prop.valueSpan === null) return null;
  if (prop.value.startsWith("{")) {
    const inner = prop.value.slice(1, -1).trim();
    const quoted = (inner.startsWith('"') && inner.endsWith('"')) || (inner.startsWith("'") && inner.endsWith("'"));
    if (!quoted) return { span: prop.valueSpan, raw: prop.value, tokens: [] };
    const raw = inner.slice(1, -1);
    const start = prop.valueSpan.start + prop.value.indexOf(inner) + 1;
    return { span: { start, end: start + raw.length }, raw, tokens: classTokens(raw, start) };
  }
  return { span: prop.valueSpan, raw: prop.value, tokens: classTokens(prop.value, prop.valueSpan.start) };
}

function classTokens(raw: string, start: number): ClassToken[] {
  const tokens: ClassToken[] = [];
  let i = 0;
  while (i < raw.length) {
    while (i < raw.length && isWs(raw[i])) i++;
    const tokenStart = i;
    while (i < raw.length && !isWs(raw[i])) i++;
    if (i > tokenStart) {
      tokens.push({ text: raw.slice(tokenStart, i), span: { start: start + tokenStart, end: start + i } });
    }
  }
  return tokens;
}

function skipQuoted(text: string, open: number): number {
  return readQuoted(text, open).next;
}

function readQuoted(text: string, open: number): { value: string; span: Span; next: number } {
  const q = text[open];
  let i = open + 1;
  while (i < text.length && text[i] !== q) {
    if (text[i] === "\\") i += 2;
    else i++;
  }
  const end = i;
  const next = i < text.length ? i + 1 : i;
  return { value: text.slice(open + 1, end), span: { start: open + 1, end }, next };
}

function skipBraces(text: string, open: number): number {
  let i = open;
  let depth = 0;
  while (i < text.length) {
    const c = text[i];
    if (c === "'" || c === '"') {
      i = skipQuoted(text, i);
      continue;
    }
    if (c === "`") {
      i++;
      while (i < text.length && text[i] !== "`") {
        if (text[i] === "\\") {
          i += 2;
          continue;
        }
        if (text[i] === "$" && text[i + 1] === "{") {
          i = skipBraces(text, i + 1);
          continue;
        }
        i++;
      }
      i++;
      continue;
    }
    if (c === "/" && text[i + 1] === "/") {
      i += 2;
      while (i < text.length && text[i] !== "\n") i++;
      continue;
    }
    if (c === "/" && text[i + 1] === "*") {
      const end = text.indexOf("*/", i + 2);
      i = end === -1 ? text.length : end + 2;
      continue;
    }
    if (c === "{") depth++;
    if (c === "}") {
      depth--;
      i++;
      if (depth === 0) return i;
      continue;
    }
    i++;
  }
  return i;
}
