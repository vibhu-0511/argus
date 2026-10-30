import assert from "node:assert/strict";
import { test } from "node:test";
import { applyOperator, type MutationOperator } from "../src/index.ts";

const jsx = {
  path: "apps/canvas/src/ops/Row.tsx",
  text: [
    "export function Row() {",
    "  return (",
    "    <div className=\"flex flex-row gap-2\">",
    "      <span className=\"label\">Radar</span>",
    "    </div>",
    "  );",
    "}",
    "",
  ].join("\n"),
};

const css = {
  path: "apps/canvas/src/ops/radar.css",
  text: ".a { font-size: 20px; overflow: hidden; }\n.b { z-index: 2; }\n",
};

const jsxOperator: MutationOperator = {
  id: "probe-jsx",
  archetype: "wrong-element",
  language: "jsx",
  edit(file, ctx) {
    if (file.elements.length < 2) return null;
    const i = ctx.pick(file.elements.length);
    const el = file.elements[i];
    return { span: el.nameSpan, replacement: `${el.name}S${ctx.seed}` };
  },
};

const cssOperator: MutationOperator = {
  id: "probe-css",
  archetype: "font-size",
  language: "css",
  edit(file, ctx) {
    const decls = file.rules.flatMap((rule) => rule.declarations);
    if (decls.length < 2) return null;
    const i = ctx.pick(decls.length);
    return { span: decls[i].valueSpan, replacement: `v${ctx.seed}` };
  },
};

function bytes(text: string): Buffer {
  return Buffer.from(text, "utf8");
}

test("same seed and source bytes return the same patch", () => {
  const first = applyOperator(jsxOperator, jsx, 1);
  const second = applyOperator(jsxOperator, jsx, 1);
  const other = applyOperator(jsxOperator, jsx, 2);
  assert.ok(first && second && other, "jsx operator returned no patch");
  assert.equal(first.archetype, "wrong-element");
  assert.equal(first.operatorId, "probe-jsx");
  assert.match(first.patch, /^--- a\/apps\/canvas\/src\/ops\/Row\.tsx\n\+\+\+ b\/apps\/canvas\/src\/ops\/Row\.tsx\n@@ /);
  assert.deepEqual(bytes(first.patch), bytes(second.patch));
  assert.notDeepEqual(bytes(first.patch), bytes(other.patch));

  const roundTrip = Buffer.from(jsx.text, "utf8").toString("utf8");
  const fromBytes = applyOperator(jsxOperator, { path: jsx.path, text: roundTrip }, 1);
  assert.ok(fromBytes, "byte round-trip returned no patch");
  assert.deepEqual(bytes(first.patch), bytes(fromBytes.patch));

  const cssFirst = applyOperator(cssOperator, css, 1);
  const cssSecond = applyOperator(cssOperator, css, 1);
  const cssOther = applyOperator(cssOperator, css, 2);
  assert.ok(cssFirst && cssSecond && cssOther, "css operator returned no patch");
  assert.equal(cssFirst.archetype, "font-size");
  assert.match(cssFirst.patch, /^--- a\/apps\/canvas\/src\/ops\/radar\.css\n\+\+\+ b\/apps\/canvas\/src\/ops\/radar\.css\n@@ /);
  assert.deepEqual(bytes(cssFirst.patch), bytes(cssSecond.patch));
  assert.notDeepEqual(bytes(cssFirst.patch), bytes(cssOther.patch));

  const again = applyOperator(jsxOperator, jsx, 1);
  assert.ok(again);
  assert.deepEqual(bytes(first.patch), bytes(again.patch));
});
