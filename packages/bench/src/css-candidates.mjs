/**
 * Emit CSS mutation candidates in walk order.
 * Files are sorted repo-relative paths. Operators are delete-rule, change-unit,
 * z-index, overflow. Seeds are base, base+1, ... until every edit site has been seen.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { applyOperator, cssOperators, parseSource } from "../../bugsmith/src/index.ts";

const ORDER = ["delete-rule", "change-unit", "z-index", "overflow"];
const SIMPLE = /^\.[A-Za-z_][\w-]*$/;

function trackedCss(repo) {
  const proc = spawnSync("git", ["-C", repo, "ls-files", "*.css"], { encoding: "utf8" });
  if (proc.status !== 0) throw new Error(proc.stderr || "git ls-files failed");
  return proc.stdout.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).sort();
}

function siteCount(operator, source) {
  const parsed = parseSource(source);
  let count = 0;
  operator.edit(parsed, {
    seed: 0,
    pick(n) {
      count = n;
      return 0;
    },
  });
  return count;
}

function firstDiff(before, after) {
  const n = Math.min(before.length, after.length);
  for (let i = 0; i < n; i++) if (before[i] !== after[i]) return i;
  return n;
}

function simpleClass(selector) {
  for (const part of selector.split(",")) {
    const sel = part.trim();
    if (SIMPLE.test(sel)) return sel;
  }
  return null;
}

function changedRule(before, at, filePath) {
  const parsed = parseSource({ path: filePath, text: before });
  return parsed.rules.find((item) => item.span.start <= at && at < item.span.end) ?? null;
}

function declarationAt(rule, index) {
  return (
    rule.declarations.find((decl) => decl.span.start <= index && index < decl.span.end) ??
    rule.declarations.find((decl) => decl.valueSpan.start <= index && index < decl.valueSpan.end) ??
    null
  );
}

function pickDeclaration(rule) {
  const prefer = ["font-size", "line-height", "letter-spacing", "z-index", "overflow", "overflow-x", "overflow-y"];
  for (const name of prefer) {
    const hit = rule.declarations.find((decl) => decl.property === name);
    if (hit) return hit;
  }
  return rule.declarations.find((decl) => /^-?\d+(?:\.\d+)?px$/.test(decl.value.trim())) ?? rule.declarations[0] ?? null;
}

function describe(before, patch, filePath) {
  const applied = patchToText(before, patch);
  const at = firstDiff(before, applied);
  const rule = changedRule(before, at, filePath);
  if (!rule) return { selector: null, property: null, expected: null };
  const selector = simpleClass(rule.selector.replace(/\r/g, ""));
  const decl = declarationAt(rule, at) ?? pickDeclaration(rule);
  if (!decl) return { selector, property: null, expected: null };
  return { selector, property: decl.property.trim(), expected: decl.value.trim() };
}

function patchToText(before, patch) {
  const lines = before.split("\n");
  const nl = before.endsWith("\n");
  if (nl) lines.pop();
  const hunks = [...patch.matchAll(/@@ -(\d+),(\d+) \+(\d+),(\d+) @@\n([\s\S]*?)(?=\n@@ |\n?$)/g)];
  if (hunks.length === 0) return before;
  let cursor = 0;
  const out = [];
  for (const hunk of hunks) {
    const start = Number(hunk[1]) - 1;
    const body = hunk[5].split("\n");
    if (body.at(-1) === "") body.pop();
    out.push(...lines.slice(cursor, start));
    for (const line of body) {
      if (line.startsWith("\\")) continue;
      if (line.startsWith("-")) continue;
      if (line.startsWith("+")) out.push(line.slice(1));
      else out.push(line.slice(1));
    }
    const removed = body.filter((line) => line.startsWith("-")).length;
    const context = body.filter((line) => line.startsWith(" ")).length;
    cursor = start + removed + context;
  }
  out.push(...lines.slice(cursor));
  return out.join("\n") + (nl ? "\n" : "");
}

function emit(row) {
  process.stdout.write(JSON.stringify(row) + "\n");
}

function walk(repo, base) {
  for (const rel of trackedCss(repo)) {
    const text = readFileSync(path.join(repo, rel), "utf8");
    const source = { path: rel, text };
    process.stderr.write(`file ${rel}\n`);
    for (const id of ORDER) {
      const operator = cssOperators[id];
      const count = siteCount(operator, source);
      if (!count) continue;
      const seen = new Set();
      let k = 0;
      while (seen.size < count) {
        const seed = base + k;
        k += 1;
        if (k > count * 40) break;
        const result = applyOperator(operator, source, seed);
        if (!result || seen.has(result.patch)) continue;
        seen.add(result.patch);
        const info = describe(text, result.patch, rel);
        emit({
          path: rel,
          operatorId: result.operatorId,
          archetype: result.archetype,
          attempt: seed,
          patch: result.patch,
          selector: info?.selector ?? null,
          property: info?.property ?? null,
          expected: info?.expected ?? null,
        });
      }
    }
  }
}

const repo = process.argv[2];
const base = Number(process.argv[3]);
if (!repo || !Number.isInteger(base)) {
  process.stderr.write("usage: css-candidates.mjs <repo> <seed>\n");
  process.exit(2);
}
walk(repo, base);
