import { createServer, type Server } from "node:http";
import { existsSync, readFileSync } from "node:fs";
import { createInterface } from "node:readline";
import path from "node:path";
import { chromium, type Page } from "@playwright/test";
import { FLOWS, boundingBox, computedStyle, pixelDiff, type CheckVerdict } from "./checks.ts";

type Params = Record<string, unknown>;
type CheckInput = { type: string; params?: Params };
type Input = { tree: string; task_dir: string; checks: CheckInput[] };
type Row = { type: string; ok: boolean; reason: string };

const OPS_ALIASES = ["/ops/operations", "/ops/launchpad", "/ops/rules", "/ops/login"];

function pathname(flow: string): string {
  const mark = flow.indexOf("?");
  return mark === -1 ? flow : flow.slice(0, mark);
}

const SERVED = new Set<string>([...FLOWS.map((item) => pathname(item.path)), ...OPS_ALIASES]);

function flowId(pathName: string): string {
  const hit = FLOWS.find((item) => pathname(item.path) === pathName);
  if (hit) return hit.id;
  return pathName === "/ops/login" ? "sign-in" : "ops";
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[ch] ?? ch);
}

function inside(root: string, target: string): boolean {
  const rel = path.relative(root, target);
  return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
}

function sheetFile(tree: string, params: Params): string {
  const rel = typeof params.css === "string" && params.css.length > 0 ? params.css : "apps/canvas/src/ops/radar.css";
  const root = path.resolve(tree);
  const full = path.resolve(root, rel);
  if (!inside(root, full)) throw new Error(`css escapes tree: ${rel}`);
  if (!existsSync(full)) throw new Error(`missing css: ${rel}`);
  return full;
}

// ponytail: brace scan ignores `{` inside strings; a descendant rule is skipped unless params.selector names it.
function selectorsDeclaring(css: string, property: string): string[] {
  const cleaned = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const escaped = property.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const decl = new RegExp(`(?:^|;)\\s*${escaped}\\s*:`, "i");
  const simple = /^\.[A-Za-z_][\w-]*$/;
  const found: string[] = [];
  const walk = (text: string) => {
    let i = 0;
    while (i < text.length) {
      const open = text.indexOf("{", i);
      if (open < 0) return;
      let depth = 1;
      let j = open + 1;
      while (j < text.length && depth > 0) {
        if (text[j] === "{") depth += 1;
        else if (text[j] === "}") depth -= 1;
        j += 1;
      }
      if (depth !== 0) return;
      const body = text.slice(open + 1, j - 1);
      const prelude = text.slice(i, open);
      i = j;
      if (body.includes("{")) {
        walk(body);
        continue;
      }
      if (!decl.test(body)) continue;
      for (const raw of prelude.split(",")) {
        const sel = raw.trim();
        if (simple.test(sel)) found.push(sel);
      }
    }
  };
  walk(cleaned);
  return [...new Set(found)];
}

function elementHtml(selector: string): string | null {
  if (!/^[#.][\w-]+(?:[#.][\w-]+)*$/.test(selector)) return null;
  const id = selector.match(/#([\w-]+)/)?.[1];
  const classes = [...selector.matchAll(/\.([\w-]+)/g)].map((match) => match[1]);
  if (id === "probe" || (classes.length === 1 && classes[0] === "radar-clock-time" && !id)) return null;
  const idAttr = id ? ` id="${escapeHtml(id)}"` : "";
  const classAttr = classes.length ? ` class="${escapeHtml(classes.join(" "))}"` : "";
  return `<span${idAttr}${classAttr}>${escapeHtml(selector)}</span>`;
}

function pageHtml(id: string, sheetCount: number, elements: string[], stamp: number | null = null): string {
  const links = Array.from({ length: sheetCount }, (_, index) => {
    const href = stamp === null ? `/sheets/${index}` : `/sheets/${index}?v=${stamp}`;
    return `<link rel="stylesheet" href="${href}">`;
  }).join("");
  return (
    `<!doctype html><meta charset="utf-8">${links}` +
    `<body style="margin:24px;background:#fff"><p id="flow">${escapeHtml(id)}</p>` +
    `<span class="radar-clock-time" id="probe">Radar</span>${elements.join("")}</body>`
  );
}

function serve(pages: Map<string, string>, sheets: Buffer[]): Promise<{ server: Server; origin: string }> {
  const server = createServer((req, res) => {
    const url = new URL(req.url ?? "/", "http://127.0.0.1");
    const sheet = /^\/sheets\/(\d+)$/.exec(url.pathname);
    if (sheet) {
      const body = sheets[Number(sheet[1])];
      if (!body) {
        res.statusCode = 404;
        res.end("missing");
        return;
      }
      res.setHeader("content-type", "text/css");
      res.setHeader("cache-control", "no-store");
      res.end(body);
      return;
    }
    const html = pages.get(url.pathname);
    if (!html) {
      res.statusCode = 404;
      res.end("missing");
      return;
    }
    res.setHeader("content-type", "text/html; charset=utf-8");
    res.setHeader("cache-control", "no-store");
    res.end(html);
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") throw new Error("no port");
      resolve({ server, origin: `http://127.0.0.1:${address.port}` });
    });
  });
}

function closeServer(server: Server): Promise<void> {
  return new Promise((resolve, reject) => {
    server.close((err) => (err ? reject(err) : resolve()));
  });
}

function crash(err: unknown): boolean {
  const message = err instanceof Error ? err.message : String(err);
  return /browser has been closed|Target closed|Protocol error|has been disconnected|Executable doesn't exist|browserType\.launch/i.test(
    message,
  );
}

function textOf(err: unknown): string {
  return err instanceof Error ? (err.stack ?? err.message) : String(err);
}

function numberParam(params: Params, camel: string, snake: string): number | undefined {
  const value = params[camel] ?? params[snake];
  if (value === undefined) return undefined;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) throw new Error(`${camel} is not a number`);
  return parsed;
}

function readBaseline(taskDir: string, rel: unknown): Buffer {
  if (typeof rel !== "string" || rel.length === 0) throw new Error("pixel_diff baseline is missing");
  const root = path.resolve(taskDir);
  const full = path.resolve(root, rel);
  if (!inside(root, full)) throw new Error(`baseline escapes task dir: ${rel}`);
  if (!existsSync(full)) throw new Error(`missing baseline: ${rel}`);
  return readFileSync(full);
}

async function readStyle(page: Page, selector: string, property: string): Promise<string> {
  const actual = await page.locator(selector).first().evaluate(
    (element, name) => getComputedStyle(element).getPropertyValue(name),
    property,
  );
  return actual.trim();
}

async function minPx(page: Page, selectors: string[], property: string, floor: number): Promise<CheckVerdict> {
  if (selectors.length === 0) return { ok: false, reason: `no selector declares ${property}` };
  const fails: string[] = [];
  const notes: string[] = [];
  for (const selector of selectors) {
    const actual = await readStyle(page, selector, property);
    const px = Number.parseFloat(actual);
    if (!Number.isFinite(px) || px < floor) fails.push(`${selector} ${property} is ${actual}, expected >= ${floor}px`);
    else notes.push(`${selector} ${property}=${actual}`);
  }
  if (fails.length > 0) return { ok: false, reason: fails.join("; ") };
  return { ok: true, reason: notes.join("; ") };
}

async function runOne(page: Page, origin: string, taskDir: string, check: CheckInput, cssText: string): Promise<Row> {
  const params = check.params ?? {};
  const flow = typeof params.flow === "string" && params.flow.length > 0 ? params.flow : "/ops/radar";
  if (!flow.startsWith("/") || !SERVED.has(pathname(flow))) throw new Error(`flow ${flow} is not one of the five flows`);
  await page.goto(`${origin}${flow}`, { waitUntil: "load" });
  const selector = typeof params.selector === "string" ? params.selector : "";
  try {
    if (check.type === "computed_style") {
      const property = String(params.property ?? params.prop ?? "");
      if (!property) throw new Error("computed_style needs property");
      if (typeof params.expected === "string") {
        if (!selector) throw new Error("computed_style expected needs selector");
        const verdict = await computedStyle(page, selector, property, params.expected);
        return { type: check.type, ...verdict };
      }
      if (params.min_px !== undefined || params.minPx !== undefined) {
        const floor = Number(params.min_px ?? params.minPx);
        if (!Number.isFinite(floor)) throw new Error("computed_style min_px is not a number");
        const selectors = selector ? [selector] : selectorsDeclaring(cssText, property);
        const verdict = await minPx(page, selectors, property, floor);
        return { type: check.type, ...verdict };
      }
      throw new Error("computed_style needs expected or min_px");
    }
    if (check.type === "bounding_box") {
      if (!selector) throw new Error("bounding_box needs selector");
      const verdict = await boundingBox(page, selector, {
        minWidth: numberParam(params, "minWidth", "min_width"),
        maxWidth: numberParam(params, "maxWidth", "max_width"),
        minHeight: numberParam(params, "minHeight", "min_height"),
        maxHeight: numberParam(params, "maxHeight", "max_height"),
      });
      return { type: check.type, ...verdict };
    }
    if (check.type === "pixel_diff") {
      if (!selector) throw new Error("pixel_diff needs selector");
      const ratio = numberParam(params, "maxChangedRatio", "max_changed_ratio") ?? 0;
      const verdict = await pixelDiff(page, selector, readBaseline(taskDir, params.baseline), ratio);
      return { type: check.type, ...verdict };
    }
    throw new Error(`unknown check type: ${check.type}`);
  } catch (err) {
    if (crash(err)) throw err;
    return { type: check.type, ok: false, reason: textOf(err) };
  }
}

async function scoreInput(
  page: Page,
  origin: string,
  input: Input,
  pages: Map<string, string>,
  sheets: Buffer[],
  stamp: number | null,
): Promise<Row[]> {
  const tree = path.resolve(input.tree);
  const cssPaths: string[] = [];
  const cssText = new Map<string, string>();
  const elements = new Map<string, string>();
  for (const check of input.checks) {
    const params = check.params ?? {};
    const file = sheetFile(tree, params);
    if (!cssText.has(file)) {
      cssText.set(file, readFileSync(file, "utf8"));
      cssPaths.push(file);
    }
    const text = cssText.get(file) ?? "";
    const selector = typeof params.selector === "string" ? params.selector : "";
    if (selector) {
      const html = elementHtml(selector);
      if (html) elements.set(selector, html);
    } else if (check.type === "computed_style" && (params.min_px !== undefined || params.minPx !== undefined)) {
      const property = String(params.property ?? params.prop ?? "");
      for (const sel of selectorsDeclaring(text, property)) {
        const html = elementHtml(sel);
        if (html) elements.set(sel, html);
      }
    }
  }
  pages.clear();
  sheets.length = 0;
  for (const file of cssPaths) sheets.push(readFileSync(file));
  for (const pathName of SERVED) {
    pages.set(pathName, pageHtml(flowId(pathName), sheets.length, [...elements.values()], stamp));
  }
  const results: Row[] = [];
  for (const check of input.checks) {
    const file = sheetFile(tree, check.params ?? {});
    results.push(await runOne(page, origin, input.task_dir, check, cssText.get(file) ?? ""));
  }
  return results;
}

async function launchPage(): Promise<{ browser: Awaited<ReturnType<typeof chromium.launch>>; page: Page; site: { server: Server; origin: string }; pages: Map<string, string>; sheets: Buffer[] }> {
  const pages = new Map<string, string>();
  const sheets: Buffer[] = [];
  const site = await serve(pages, sheets);
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-proxy-server", "--disable-background-networking"],
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.setDefaultTimeout(10_000);
  await page.route("**/*", (route) => {
    const host = new URL(route.request().url()).hostname;
    if (host === "127.0.0.1" || host === "localhost") return route.continue();
    return route.abort();
  });
  return { browser, page, site, pages, sheets };
}

async function main(): Promise<void> {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) chunks.push(chunk as Buffer);
  const input = JSON.parse(Buffer.concat(chunks).toString("utf8")) as Input;
  const opened = await launchPage();
  try {
    const results = await scoreInput(opened.page, opened.site.origin, input, opened.pages, opened.sheets, null);
    await opened.browser.close();
    await closeServer(opened.site.server);
    process.stdout.write(`${JSON.stringify({ checks: results })}\n`);
  } catch (err) {
    await opened.browser.close().catch(() => undefined);
    await closeServer(opened.site.server).catch(() => undefined);
    throw err;
  }
}

async function serveMany(): Promise<void> {
  const out = process.stdout as NodeJS.WriteStream & { _handle?: { setBlocking?: (blocking: boolean) => void } };
  out._handle?.setBlocking?.(true);
  const opened = await launchPage();
  let stamp = 0;
  try {
    const lines = createInterface({ input: process.stdin });
    for await (const line of lines) {
      if (!line.trim()) continue;
      const input = JSON.parse(line) as Input;
      const results = await scoreInput(opened.page, opened.site.origin, input, opened.pages, opened.sheets, stamp);
      stamp += 1;
      process.stdout.write(`${JSON.stringify({ checks: results })}\n`);
    }
  } finally {
    await opened.browser.close().catch(() => undefined);
    await closeServer(opened.site.server).catch(() => undefined);
  }
}

const entry = process.argv.includes("--serve") ? serveMany : main;
entry()
  .then(() => process.exit(0))
  .catch((err: unknown) => {
    process.stderr.write(textOf(err));
    process.exit(2);
  });
