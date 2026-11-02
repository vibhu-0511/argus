// Runs one repro script on the buggy tree and on the golden tree, inside the argus-repro image. Prints one JSON line:
//   {"buggy": {"result": "pass|fail|error", "detail": "..."}, "golden": {...}}
//
//   node run-script.mjs <dir>     dir (read-only mount): meta.json, script.txt, css/*
//   meta.json: { "base": "http://argus-app:5297", "trees": { "buggy": { "<repo path of a css file>": "css/b0.css" }, "golden": {...} } }
//
// The app is the platform's Canvas served by Vite (rig/vite.config.mjs). There is no backend: /api answers are the mock
// below (copied from packages/verify/calibration/render.mjs, which made the P4 calibration shots; 10 of its 14 flights), the clock
// is frozen, and the CSS files a task edits are swapped in the browser, so both trees render from the same server.
// `expect` is a small stand-in for @playwright/test (not in the image): the matchers below, `.not`, 3 s polling.
import { chromium } from "playwright";
import { readFile } from "node:fs/promises";

const dir = process.argv[2] ?? "/work";
const meta = JSON.parse(await readFile(`${dir}/meta.json`, "utf8"));
const source = (await readFile(`${dir}/script.txt`, "utf8")).replace(/^\s*import\s[^\n]*\n?/gm, "").replace(/^\s*export\s+/gm, "");

const NOW = new Date("2026-10-01T12:00:00Z");
const min = (m) => new Date(NOW.getTime() + m * 60_000).toISOString();
const presentation = { timezone: "America/Toronto", locale: "en", currency: "CAD", contextHash: "h1", customerName: "Porter", operationalTimezone: "America/Toronto" };
const POS = { YTZ: [43.63, -79.4], YYZ: [43.68, -79.63], YOW: [45.32, -75.67], YUL: [45.47, -73.74], YHZ: [44.88, -63.51], YQG: [42.28, -82.96], EWR: [40.69, -74.17] };
const at = (iata) => ({ iata, position: { lat: POS[iata][0], lon: POS[iata][1] } });
const flight = (id, no, from, to, dep, arr, extra = {}) => ({
  legId: id, carrier: "PD", flightNumber: no, operationalDate: "2026-10-01", origin: at(from), destination: at(to),
  status: "scheduled", cancelled: false, scheduled: { departure: min(dep), arrival: min(arr) }, times: { departure: min(dep), arrival: min(arr) }, estimated: {}, actual: {},
  delayMinutes: {}, touchesBase: true, staffing: { status: "full" }, ...extra,
});
const FLIGHTS = {
  asOf: min(0), window: { from: min(-1440), to: min(0), hours: 24 }, base: "YTZ", unplacedStations: [],
  flights: [
    flight("L1", "118", "YTZ", "EWR", -300, -180, { actual: { blockOff: min(-298) } }),
    flight("L2", "431", "YTZ", "YQG", -200, -110, { delayMinutes: { departure: 35 }, estimated: { departure: min(-165) } }),
    flight("L3", "205", "YUL", "YTZ", -90, 5, { staffing: { status: "short" } }),
    flight("L4", "322", "YTZ", "YOW", -60, 10, { actual: { blockOff: min(-58) } }),
    flight("L5", "540", "YHZ", "YTZ", -30, 60),
    flight("L6", "611", "YTZ", "YYZ", -10, 45, { cancelled: true, status: "cancelled" }),
    flight("L7", "712", "EWR", "YTZ", 20, 140, { staffing: { status: "short" } }),
    flight("L8", "813", "YTZ", "YHZ", 45, 190),
    flight("L9", "914", "YQG", "YTZ", 80, 160),
    flight("L10", "101", "YTZ", "YUL", 130, 215, { staffing: { status: "short" } }),
  ],
};
const TASKS = [
  { taskId: "t1", type: "crew.check_in_gap_detected", status: "open", createdAt: min(-4), crewName: "M. Stewart", routeDesc: "YTZ→YQG" },
  { taskId: "t2", type: "crew.legality_breach_detected", status: "open", createdAt: min(-40), acknowledgedAt: min(-30), crewName: "A. Kaur" },
  { taskId: "t3", type: "crew.check_in_gap_detected", status: "closed", createdAt: min(-300), routeDesc: "PD 431" },
];
const AIRPORTS = {
  airports: [
    ["YTZ", "Billy Bishop", "Toronto", 43.63, -79.4, true], ["YYZ", "Pearson", "Toronto", 43.68, -79.63, false],
    ["YOW", "Macdonald-Cartier", "Ottawa", 45.32, -75.67, false], ["YUL", "Trudeau", "Montreal", 45.47, -73.74, false],
    ["YHZ", "Stanfield", "Halifax", 44.88, -63.51, false], ["YQG", "Windsor", "Windsor", 42.28, -82.96, false],
    ["EWR", "Newark Liberty", "Newark", 40.69, -74.17, false],
  ].map(([iata, name, city, lat, lon, hub]) => ({ iata, name, city, position: { lat, lon, latitude: lat, longitude: lon }, tz: "America/Toronto", airline: { hub, crewBase: hub } })),
  unknownStations: [],
};
function answer(pathname) {
  if (pathname === "/api/auth/session") return { subject: "admin", roles: ["admin"], presentation: { customerName: "Porter", supportedLocales: ["en"] } };
  if (pathname === "/api/tasks") return { tasks: TASKS };
  if (pathname === "/api/read/ops/flights") return FLIGHTS;
  if (pathname === "/api/read/document-expiry") return { documents: [], summary: { total: 0 } };
  if (pathname === "/api/read/turnaround-risks") return { breaches: [], summary: { warning: 0, critical: 0 } };
  if (pathname === "/api/reference/airports") return AIRPORTS;
  return {};
}

// ---- expect -----------------------------------------------------------------------------------------------
class ExpectError extends Error {}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const squash = (s) => String(s ?? "").replace(/\s+/g, " ").trim();
const same = (actual, want) => (want instanceof RegExp ? want.test(actual) : squash(actual) === squash(want));
const has = (actual, want) => (want instanceof RegExp ? want.test(actual) : squash(actual).includes(squash(want)));
const isLocator = (x) => x && typeof x.isVisible === "function";
const isPage = (x) => x && typeof x.goto === "function";

async function poll(check, negate, label, ms = 3000) {
  const end = Date.now() + ms;
  let seen;
  for (;;) {
    let ok = false;
    try {
      [ok, seen] = await check();
    } catch (e) {
      if (e?.name === "TimeoutError" || /strict mode violation/.test(String(e))) seen = String(e).split("\n")[0];
      else throw e;
    }
    if (ok !== negate) return;
    if (Date.now() > end) throw new ExpectError(`${negate ? "not " : ""}${label}; last seen: ${JSON.stringify(seen)}`);
    await sleep(100);
  }
}

const LOCATOR = {
  toBeVisible: (l) => async () => [await l.isVisible(), "hidden"],
  toBeHidden: (l) => async () => [!(await l.isVisible()), "visible"],
  toBeEnabled: (l) => async () => [await l.isEnabled(), "disabled"],
  toBeDisabled: (l) => async () => [await l.isDisabled(), "enabled"],
  toBeChecked: (l) => async () => [await l.isChecked(), "unchecked"],
  toHaveText: (l, want) => async () => { const t = await l.innerText({ timeout: 1000 }); return [same(t, want), t]; },
  toContainText: (l, want) => async () => { const t = await l.innerText({ timeout: 1000 }); return [has(t, want), t]; },
  toHaveCount: (l, n) => async () => { const c = await l.count(); return [c === n, c]; },
  toHaveCSS: (l, name, want) => async () => {
    const v = await l.evaluate((el, prop) => getComputedStyle(el).getPropertyValue(prop), name, { timeout: 1000 });
    return [want instanceof RegExp ? want.test(v) : v === want, v];
  },
  toHaveAttribute: (l, name, want) => async () => {
    const v = await l.getAttribute(name, { timeout: 1000 });
    return [want === undefined ? v !== null : want instanceof RegExp ? want.test(v ?? "") : v === want, v];
  },
  toHaveClass: (l, want) => async () => { const v = (await l.getAttribute("class", { timeout: 1000 })) ?? ""; return [want instanceof RegExp ? want.test(v) : v.split(/\s+/).includes(want) || v === want, v]; },
  toHaveValue: (l, want) => async () => { const v = await l.inputValue({ timeout: 1000 }); return [want instanceof RegExp ? want.test(v) : v === want, v]; },
};
const PAGE = {
  toHaveURL: (p, want) => async () => [want instanceof RegExp ? want.test(p.url()) : p.url() === want || p.url().endsWith(want), p.url()],
  toHaveTitle: (p, want) => async () => { const t = await p.title(); return [same(t, want), t]; },
};
const VALUE = {
  toBe: (a, b) => a === b, toEqual: (a, b) => JSON.stringify(a) === JSON.stringify(b), toBeTruthy: (a) => !!a, toBeFalsy: (a) => !a,
  toContain: (a, b) => a.includes(b), toBeGreaterThan: (a, b) => a > b, toBeLessThan: (a, b) => a < b,
  toBeGreaterThanOrEqual: (a, b) => a >= b, toBeLessThanOrEqual: (a, b) => a <= b,
};

function expect(subject) {
  const build = (negate) => new Proxy({}, {
    get(_, name) {
      if (name === "not") return build(!negate);
      return async (...args) => {
        const table = isLocator(subject) ? LOCATOR : isPage(subject) ? PAGE : null;
        if (table && table[name]) return poll(table[name](subject, ...args), negate, `${name}(${args.map(String).join(", ")})`);
        if (!table && VALUE[name]) {
          if (VALUE[name](subject, ...args) === negate) throw new ExpectError(`${negate ? "not " : ""}${name}(${args.map(String).join(", ")}); got ${JSON.stringify(subject)}`);
          return;
        }
        throw new TypeError(`unsupported matcher ${String(name)} in this runner`);
      };
    },
  });
  return build(false);
}

// ---- one tree ---------------------------------------------------------------------------------------------
async function run(browser, css) {
  const context = await browser.newContext({ baseURL: meta.base, viewport: { width: 1280, height: 800 }, reducedMotion: "reduce", serviceWorkers: "block" });
  context.setDefaultTimeout(5000);
  const page = await context.newPage();
  await page.clock.setFixedTime(NOW);
  const ops = await (await fetch(`${meta.base}/ops.html`)).text();
  await page.route((u) => u.pathname === "/api/events", (r) => r.abort());
  await page.route((u) => u.pathname.startsWith("/api/"), (r) => {
    const { pathname } = new URL(r.request().url());
    let signedOut = false;
    try { const at = new URL(r.request().frame().url()).pathname; signedOut = at === "/login"; } catch { /* no frame: signed in */ }
    if (signedOut && pathname === "/api/auth/session") return r.fulfill({ status: 401, contentType: "application/json", body: "{}" });
    r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: answer(pathname), presentation }) });
  });
  await page.route((u) => u.pathname === "/ops" || u.pathname.startsWith("/ops/"), (r) => r.fulfill({ status: 200, contentType: "text/html", body: ops }));
  for (const [file, rel] of Object.entries(css)) {
    const text = await readFile(`${dir}/${rel}`, "utf8");
    await page.route((u) => u.pathname === `/${file.replace("apps/canvas/", "")}`, async (r) => {
      const response = await r.fetch();
      const body = (await response.text()).replace(/const __vite__css = ".*"\n/, () => `const __vite__css = ${JSON.stringify(text)}\n`);
      r.fulfill({ response, body });
    });
  }
  await page.goto("/login", { waitUntil: "networkidle" }).catch(() => {}); // the landing screen; "/" only redirects to /ops
  try {
    let go;
    try {
      go = new Function("test", "expect", "page", "context", `return (async () => {\n${source}\n})()`);
    } catch (e) {
      return { result: "error", detail: String(e).slice(0, 700) };
    }
    const test = Object.assign(async (_name, fn) => { await fn({ page, context }); }, { describe: async (_n, fn) => fn(), beforeEach: () => {}, afterEach: () => {}, use: () => {}, setTimeout: () => {}, step: async (_n, fn) => fn() });
    await go(test, expect, page, context);
    return { result: "pass", detail: "" };
  } catch (e) {
    const bad = e instanceof ExpectError || e?.name === "TimeoutError";
    return { result: bad ? "fail" : "error", detail: `${e?.name}: ${String(e?.message ?? e).split("\n")[0]}`.slice(0, 700) };
  } finally {
    await context.close();
  }
}

const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
try {
  const out = {};
  for (const tree of ["buggy", "golden"]) out[tree] = await run(browser, meta.trees[tree]);
  console.log(JSON.stringify(out));
} finally {
  await browser.close();
}
