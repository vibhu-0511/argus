import assert from "node:assert/strict";
import { test } from "node:test";
import { applyOperator, parseSource } from "../src/index.ts";
import { cssOperatorList } from "../src/operators/css.ts";
import { changedSource, jsxOperatorList } from "../src/operators/jsx.ts";

const jsx = {
  path: "Row.tsx",
  text: [
    "export function Row() {",
    "  return (",
    "    <div className=\"alpha flex-row\" id=\"a\">",
    "      <span className=\"beta flex-col\" title=\"b\">Radar</span>",
    "    </div>",
    "  );",
    "}",
    "",
  ].join("\n"),
};

const css = {
  path: "radar.css",
  text: ".a { font-size: 20px; overflow: hidden; z-index: 2; }\n.b { font-size: 12px; overflow: visible; z-index: 4; }\n",
};

function stillParses(kind: "jsx" | "css", path: string, before: string, operator: (typeof jsxOperatorList)[number] | (typeof cssOperatorList)[number]) {
  const parsed = parseSource({ path, text: before });
  let calls = 0;
  const edit = operator.edit(parsed, {
    seed: 1,
    pick(count: number) {
      const choice = calls % count;
      calls += 1;
      return choice;
    },
  });
  assert.ok(edit, `${operator.id} found no edit`);
  const next = changedSource(parsed, edit);
  assert.notEqual(next, before);
  const again = parseSource({ path, text: next });
  assert.equal(again.language, kind);
}

test("jsx operators are deterministic and the changed source still parses", () => {
  assert.equal(jsxOperatorList.length, 4);
  for (const operator of jsxOperatorList) {
    const first = applyOperator(operator, jsx, 1);
    const second = applyOperator(operator, jsx, 1);
    const other = applyOperator(operator, jsx, 2);
    assert.ok(first && second && other, operator.id);
    assert.equal(first.patch, second.patch);
    assert.notEqual(first.patch, other.patch);
    assert.equal(first.archetype, operator.archetype);
    stillParses("jsx", jsx.path, jsx.text, operator);
  }
});

test("css operators are deterministic and the changed source still parses", () => {
  assert.equal(cssOperatorList.length, 4);
  for (const operator of cssOperatorList) {
    const first = applyOperator(operator, css, 1);
    const second = applyOperator(operator, css, 1);
    const other = applyOperator(operator, css, 2);
    assert.ok(first && second && other, operator.id);
    assert.equal(first.patch, second.patch);
    assert.notEqual(first.patch, other.patch);
    assert.equal(first.archetype, operator.archetype);
    stillParses("css", css.path, css.text, operator);
  }
});
