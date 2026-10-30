import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { dom2srcPlugin, transformJsx } from "../src/index.ts";

const sample = [
  "function Button() {",
  "  return <button type=\"button\">Save</button>;",
  "}",
  "",
  "export function Page() {",
  "  return (",
  "    <div>",
  "      <Button />",
  "      <span>Hi</span>",
  "    </div>",
  "  );",
  "}",
  "",
].join("\n");

const stamped = [
  "function Button() {",
  "  return <button type=\"button\" data-src=\"src/Page.tsx:2:10\">Save</button>;",
  "}",
  "",
  "export function Page() {",
  "  return (",
  "    <div data-src=\"src/Page.tsx:7:5\">",
  "      <Button />",
  "      <span data-src=\"src/Page.tsx:9:7\">Hi</span>",
  "    </div>",
  "  );",
  "}",
  "",
].join("\n");

test("stamps data-src on a definition host and a call-site host", () => {
  const out = transformJsx(sample, "src/Page.tsx", "development");
  assert.equal(out, stamped);
  assert.equal(transformJsx(out, "src/Page.tsx", "development"), out);
  assert.match(out, /<Button \/>/);
  for (const value of values(out)) {
    assert.match(value, /^src\/Page\.tsx:\d+:\d+$/);
  }
});

test("stamps only the opening host tag", () => {
  const src = ["<img alt=\"\" />", "<>", "  <br />", "</>", ""].join("\n");
  const out = transformJsx(src, "a.tsx", "test");
  assert.equal(out, ["<img alt=\"\"  data-src=\"a.tsx:1:1\"/>", "<>", "  <br  data-src=\"a.tsx:3:3\"/>", "</>", ""].join("\n"));
  const spread = `<div {...props} className="a"></div>\n`;
  assert.equal(
    transformJsx(spread, "a.tsx", "development"),
    `<div {...props} className="a" data-src="a.tsx:1:1"></div>\n`,
  );
  const kept = `<div data-src="keep.tsx:4:2"></div>\n`;
  assert.equal(transformJsx(kept, "a.tsx", "development"), kept);
});

test("stamps a host nested in an attribute expression", () => {
  const src = [
    "export function Pane() {",
    "  return <Frame center={<>",
    "    <button type=\"button\">Notes</button>",
    "  </>} />;",
    "}",
    "",
  ].join("\n");
  const out = transformJsx(src, "Pane.tsx", "development");
  assert.match(out, /<button type="button" data-src="Pane.tsx:3:5">Notes<\/button>/);
  assert.equal(out.includes("data-src=\"Pane.tsx:2:"), false);
  assert.equal(out.replace(/ data-src="[^"]*"/g, ""), src);
});

test("leaves comparisons, types, strings, and regexes unchanged", () => {
  const src = [
    "const n = a < b;",
    "const f = <T,>(x: T) => x;",
    "const s = useState<string>(\"\");",
    "const q = \"<div>\";",
    "const re = /<div>/;",
    "export const Z = () => <em>e</em>;",
    "",
  ].join("\n");
  const out = transformJsx(src, "a.tsx", "development");
  assert.equal(out.replace(/ data-src="[^"]*"/g, ""), src);
  assert.match(out, /<em data-src="a\.tsx:6:24">e<\/em>/);
  assert.equal(out.includes("data-src=\"a.tsx:1:"), false);
  assert.equal(out.includes("data-src=\"a.tsx:2:"), false);
  assert.equal(out.includes("data-src=\"a.tsx:4:"), false);
  assert.equal(out.includes("data-src=\"a.tsx:5:"), false);
});

test("production invocation does not add data-src", () => {
  assert.equal(transformJsx(sample, "src/Page.tsx", "production"), sample);
  assert.equal(sample.includes("data-src"), false);
  const plugin = dom2srcPlugin();
  assert.equal(plugin.apply({}, { command: "build", mode: "production" }), false);
  assert.equal(plugin.transform(sample, "src/Page.tsx"), null);
  plugin.configResolved({ mode: "production", root: "C:/repo" });
  assert.equal(plugin.transform(sample, "src/Page.tsx"), null);
});

test("plugin is enforce pre and runs for development and test", () => {
  const plugin = dom2srcPlugin();
  assert.equal(plugin.name, "@argus/dom2src-plugin");
  assert.equal(plugin.enforce, "pre");
  assert.equal(plugin.apply({}, { command: "serve", mode: "development" }), true);
  plugin.configResolved({ mode: "development", root: "C:/repo" });
  const dev = plugin.transform(sample, "src/Page.tsx");
  assert.ok(dev);
  assert.equal(dev.code, stamped);
  assert.equal(dev.map, null);
  assert.equal(plugin.transform("const n = 1;", "src/Page.ts"), null);
  assert.equal(plugin.transform(sample, "C:/repo/node_modules/ui/Button.tsx"), null);

  const testPlugin = dom2srcPlugin();
  assert.equal(testPlugin.apply({}, { command: "build", mode: "test" }), true);
  testPlugin.configResolved({ mode: "test", root: "C:/repo" });
  const tested = testPlugin.transform(sample, "src/Page.tsx");
  assert.ok(tested);
  assert.equal(tested.code, stamped);
});

// Reads the private dcortex-platform checkout, so it runs only where ARGUS_PLATFORM_REPO is set.
test("five canvas flows get repo-relative data-src with no tag suffix", { skip: !process.env.ARGUS_PLATFORM_REPO }, () => {
  const repo = process.env.ARGUS_PLATFORM_REPO as string;
  const flows = [
    { flow: "sign-in", file: "apps/canvas/src/screens/AuthModal.tsx", marker: '<div className="auth-backdrop"' },
    { flow: "sign-in", file: "apps/canvas/src/screens/Landing.tsx", marker: '<button type="button" className="landing-cta"' },
    { flow: "ops", file: "apps/canvas/src/ops/Radar.tsx", marker: '<div className="radar-screen"' },
    { flow: "ops", file: "apps/canvas/src/ops/Operations.tsx", marker: '<span className="ops-clock"' },
    { flow: "ops", file: "apps/canvas/src/ops/Launchpad.tsx", marker: '<div className="ops-horizon-loading"' },
    { flow: "ops", file: "apps/canvas/src/ops/Rules.tsx", marker: '<div className="ops-rules-note"' },
    { flow: "desk", file: "apps/canvas/src/screens/Desk.tsx", marker: '<button type="button" className="desk-notes-btn"' },
    { flow: "user-admin", file: "apps/canvas/src/screens/UserAdmin.tsx", marker: '<div className="pill warn" data-testid="user-admin-denied"' },
    { flow: "audit", file: "apps/canvas/src/screens/AuditLog.tsx", marker: '<div className="pill warn" data-testid="audit-denied"' },
  ];
  for (const item of flows) {
    const abs = path.join(repo, item.file);
    const text = fs.readFileSync(abs, "utf8");
    const at = text.indexOf(item.marker);
    assert.ok(at >= 0, `${item.flow} ${item.file} has ${item.marker}`);
    const { line, col } = lineCol(text, at);
    const out = transformJsx(text, abs, "development");
    const value = `${item.file}:${line}:${col}`;
    assert.ok(out.includes(`data-src="${value}"`), `${item.file} ${value}`);
    assert.equal(transformJsx(text, abs, "production"), text, item.file);
    assert.equal(out.replace(/ data-src="[^"]*"/g, ""), text, item.file);
    assert.equal(transformJsx(out, abs, "test"), out, item.file);
    for (const stampedValue of values(out)) {
      assert.match(stampedValue, /^apps\/canvas\/[^":]+:\d+:\d+$/, stampedValue);
      assert.equal(/^[A-Za-z]:/.test(stampedValue), false);
    }
  }
  const landing = fs.readFileSync(path.join(repo, "apps/canvas/src/screens/Landing.tsx"), "utf8");
  const landingOut = transformJsx(landing, path.join(repo, "apps/canvas/src/screens/Landing.tsx"), "development");
  const call = landingOut.split(/\r?\n/).find((row) => row.includes("<AuthModal"));
  assert.ok(call);
  assert.equal(call.includes("data-src"), false);
});

function values(source: string): string[] {
  return [...source.matchAll(/data-src="([^"]*)"/g)].map((match) => match[1]);
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
