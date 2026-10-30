import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { parseSource } from "../src/index.ts";
import { removeClass } from "../src/operators/jsx.ts";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");

const marker = {
  path: "Marker.tsx",
  text: [
    "export function Marker() {",
    "  return (",
    "    <div className=\"marker\">Radar</div>",
    "  );",
    "}",
    "",
  ].join("\n"),
};

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

test("removeClass skips a lone class that is not flex-row or flex-col", () => {
  const parsed = parseSource(marker);
  const tokens = parsed.elements.flatMap((el) => el.className?.tokens ?? []);
  assert.deepEqual(
    tokens.map((token) => token.text),
    ["marker"],
  );
  const edit = removeClass.edit(parsed, { seed: 1, pick: () => 0 });
  assert.equal(edit, null);
});

test("a mutant that scores 0 is rejected as no-observable-change", () => {
  const dir = mkdtempSync(path.join(tmpdir(), "argus-p0-t25-"));
  const script = path.join(dir, "judge_signal.py");
  writeFileSync(
    script,
    [
      "from argus_bench.validity import judge_mutant",
      "keep, reason = judge_mutant(0, 0, [\"computed_style\"])",
      "assert keep is False and reason == \"no-observable-change\"",
      "print(reason)",
      "",
    ].join("\n"),
  );
  try {
    const result = spawnSync("uv", ["run", "python", script], {
      cwd: repoRoot,
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
      encoding: "utf8",
    });
    assert.equal(result.status, 0, result.stderr || result.error?.message);
    assert.equal(result.stdout.trim(), "no-observable-change");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("the operators fixture still yields a removeClass edit", () => {
  const parsed = parseSource(jsx);
  const edit = removeClass.edit(parsed, { seed: 1, pick: () => 0 });
  assert.ok(edit);
});
