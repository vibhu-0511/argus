import fs from "node:fs";
import path from "node:path";

/**
 * Contract for later tasks:
 * - Attribute name is `data-src`. Value is repo-relative `file:line:col`.
 * - No component-name suffix and no second attribute.
 * - Every JSX host element (lowercase intrinsic tag) gets the location of the
 *   JSX that created it: a component definition's returned host, or a host
 *   written at a call site. Component tags are not host elements.
 * - `enforce: 'pre'` so the transform still sees JSX. `@vitejs/plugin-react`
 *   is also `enforce: 'pre'`, so list `dom2srcPlugin()` before `react()`.
 * - Development and test stamp the attribute. Mode `production` does not.
 */

export type Dom2SrcMode = "development" | "test" | "production";

export type Dom2SrcPlugin = {
  name: "@argus/dom2src-plugin";
  enforce: "pre";
  apply: (config: { mode?: string }, env: { command?: "build" | "serve"; mode: string }) => boolean;
  configResolved: (config: { mode: string; root: string }) => void;
  transform: (code: string, id: string) => { code: string; map: null } | null;
};

export function dom2srcPlugin(): Dom2SrcPlugin {
  let mode: Dom2SrcMode = "development";
  let root: string | undefined;
  return {
    name: "@argus/dom2src-plugin",
    enforce: "pre",
    apply(_config, env) {
      mode = env.mode === "production" || env.mode === "test" ? env.mode : "development";
      return mode !== "production";
    },
    configResolved(config) {
      mode = config.mode === "production" || config.mode === "test" ? config.mode : "development";
      root = config.root;
    },
    transform(code, id) {
      if (mode === "production") return null;
      const file = jsxPath(id);
      if (!file) return null;
      const next = transformJsx(code, file, mode, root);
      if (next === code) return null;
      return { code: next, map: null };
    },
  };
}

export function transformJsx(
  code: string,
  filename: string,
  mode: Dom2SrcMode = "development",
  fallbackRoot?: string,
): string {
  if (mode === "production") return code;
  const spots = hostOpenings(code);
  if (spots.length === 0) return code;
  const rel = repoRelative(filename.split("?")[0], fallbackRoot);
  let next = code;
  for (let i = spots.length - 1; i >= 0; i--) {
    const spot = spots[i];
    next = next.slice(0, spot.at) + ` data-src="${rel}:${spot.line}:${spot.col}"` + next.slice(spot.at);
  }
  return next;
}

function jsxPath(id: string): string | null {
  if (id.includes("\0")) return null;
  const clean = id.split("?")[0];
  const posix = clean.replaceAll("\\", "/");
  if (posix.includes("/node_modules/")) return null;
  if (!/\.(tsx|jsx)$/i.test(posix)) return null;
  return clean;
}

function repoRelative(filename: string, fallbackRoot?: string): string {
  const clean = filename.replace(/^\/@fs\//, "");
  if (!path.isAbsolute(clean)) return clean.replaceAll("\\", "/").replace(/^\.\//, "");
  const file = path.resolve(clean);
  const base = findGitRoot(path.dirname(file)) ?? (fallbackRoot ? path.resolve(fallbackRoot) : null);
  if (base) {
    const rel = path.relative(base, file);
    if (rel && !rel.startsWith("..") && !path.isAbsolute(rel)) return rel.replaceAll("\\", "/");
  }
  const fromCwd = path.relative(process.cwd(), file);
  if (fromCwd && !fromCwd.startsWith("..") && !path.isAbsolute(fromCwd)) return fromCwd.replaceAll("\\", "/");
  return path.basename(file);
}

function findGitRoot(startDir: string): string | null {
  let dir = path.resolve(startDir);
  for (;;) {
    if (fs.existsSync(path.join(dir, ".git"))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

type Spot = { at: number; line: number; col: number };

type Frame = { kind: "code"; depth: number | null } | { kind: "text"; name: string } | { kind: "template" };

type OpenTag = {
  kind: "open";
  name: string;
  host: boolean;
  hasSrc: boolean;
  selfClosing: boolean;
  insertAt: number;
  next: number;
};

type CloseTag = { kind: "close"; name: string; next: number };

/**
 * ponytail: a scanner, not a JS parser. It misses `<` inside a regex that
 * does not start after `= ( [ { : ; , ! ? & |`. Upgrade path: a JSX parser
 * if a stamp lands inside a regex or a type argument.
 */
function hostOpenings(text: string): Spot[] {
  const spots: Spot[] = [];
  walk(text, 0, [{ kind: "code", depth: null }], spots);
  spots.sort((a, b) => a.at - b.at);
  return spots;
}

function walk(text: string, start: number, stack: Frame[], spots: Spot[]): number {
  let i = start;
  while (i < text.length && stack.length > 0) {
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
        const tag = readTag(text, i, spots);
        if (!tag) {
          i++;
          continue;
        }
        const lt = i;
        i = tag.next;
        if (tag.kind === "close") {
          if (tag.name === frame.name) stack.pop();
          continue;
        }
        if (tag.host && !tag.hasSrc) spots.push({ at: tag.insertAt, ...lineCol(text, lt) });
        if (!tag.selfClosing) stack.push({ kind: "text", name: tag.name });
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
    if (text[i] === "/" && canStartRegex(text, i)) {
      i = skipRegex(text, i);
      continue;
    }
    if (text[i] === "<" && canStartJsx(text, i)) {
      const tag = readTag(text, i, spots);
      if (!tag) {
        i++;
        continue;
      }
      const lt = i;
      i = tag.next;
      if (tag.kind === "close") continue;
      if (tag.host && !tag.hasSrc) spots.push({ at: tag.insertAt, ...lineCol(text, lt) });
      if (!tag.selfClosing) stack.push({ kind: "text", name: tag.name });
      continue;
    }
    i++;
  }
  return i;
}

function lineCol(text: string, index: number): { line: number; col: number } {
  let line = 1;
  let col = 1;
  for (let i = 0; i < index; i++) {
    if (text[i] === "\n") {
      line++;
      col = 1;
    } else col++;
  }
  return { line, col };
}

function canStartJsx(text: string, lt: number): boolean {
  let j = lt - 1;
  while (j >= 0 && isWs(text[j])) j--;
  if (j < 0) return true;
  if (!isIdentPart(text[j])) return true;
  const end = j + 1;
  while (j >= 0 && isIdentPart(text[j])) j--;
  const word = text.slice(j + 1, end);
  return word === "return" || word === "throw" || word === "yield" || word === "await";
}

function canStartRegex(text: string, slash: number): boolean {
  let j = slash - 1;
  while (j >= 0 && isWs(text[j])) j--;
  if (j < 0) return true;
  return "([{:;,=!?&|~^-+*%<>".includes(text[j]);
}

function skipRegex(text: string, open: number): number {
  let j = open + 1;
  let cls = false;
  while (j < text.length) {
    if (text[j] === "\\") {
      j += 2;
      continue;
    }
    if (text[j] === "\n") return open + 1;
    if (text[j] === "[") cls = true;
    else if (text[j] === "]") cls = false;
    else if (text[j] === "/" && !cls) return j + 1;
    j++;
  }
  return j;
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

function isHost(name: string): boolean {
  return /^[a-z][A-Za-z0-9-]*$/.test(name);
}

function readTag(text: string, lt: number, spots: Spot[]): OpenTag | CloseTag | null {
  let i = lt + 1;
  let closing = false;
  if (text[i] === "/") {
    closing = true;
    i++;
  }
  if (text[i] === ">") {
    if (closing) return { kind: "close", name: "", next: i + 1 };
    return openTag("", false, i, i + 1, false);
  }
  if (!isIdentStart(text[i])) return null;
  const nameStart = i;
  i++;
  while (i < text.length && (isIdentPart(text[i]) || text[i] === ".")) i++;
  const name = text.slice(nameStart, i);
  if (closing) {
    while (i < text.length && isWs(text[i])) i++;
    if (text[i] !== ">") return null;
    return { kind: "close", name, next: i + 1 };
  }
  let hasSrc = false;
  while (i < text.length) {
    while (i < text.length && isWs(text[i])) i++;
    if (text[i] === ">") return openTag(name, hasSrc, i, i + 1, false);
    if (text[i] === "/" && text[i + 1] === ">") return openTag(name, hasSrc, i, i + 2, true);
    const before = i;
    if (text[i] === "{") {
      i = walk(text, i + 1, [{ kind: "code", depth: 1 }], spots);
      if (i === before) return null;
      continue;
    }
    if (!isIdentStart(text[i])) return null;
    const propStart = i;
    while (i < text.length && isIdentPart(text[i])) i++;
    const propName = text.slice(propStart, i);
    if (propName === "data-src") hasSrc = true;
    while (i < text.length && isWs(text[i])) i++;
    if (text[i] !== "=") continue;
    i++;
    while (i < text.length && isWs(text[i])) i++;
    if (text[i] === '"' || text[i] === "'") i = skipQuoted(text, i);
    else if (text[i] === "{") i = walk(text, i + 1, [{ kind: "code", depth: 1 }], spots);
    else return null;
    if (i === before) return null;
  }
  return null;
}

function openTag(name: string, hasSrc: boolean, insertAt: number, next: number, selfClosing: boolean): OpenTag {
  return { kind: "open", name, host: isHost(name), hasSrc, selfClosing, insertAt, next };
}

function skipQuoted(text: string, open: number): number {
  const q = text[open];
  let i = open + 1;
  while (i < text.length && text[i] !== q) {
    if (text[i] === "\\") i += 2;
    else i++;
  }
  return i < text.length ? i + 1 : i;
}
