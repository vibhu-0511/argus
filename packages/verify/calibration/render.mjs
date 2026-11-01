// Render real dcortex Canvas screens to PNG, with chosen CSS files swapped in per shot.
//
//   node render.mjs <jobs.json>
//
// jobs.json: { "base": "http://localhost:5199", "chrome": "<chrome.exe>", "shots": [
//   { "out": "a.png", "view": "landing", "css": { "apps/canvas/src/ops/radar.css": "<path to css text>" } } ] }
//
// Needs the platform's Canvas served by Vite at `base` (see README.md). There is no backend: /api replies are the mock
// below, the clock is frozen, and CSS modules are replaced in the browser, so the platform checkout is never written.
import { readFileSync, writeFileSync } from "node:fs";

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ?? "@playwright/test");

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
    flight("L11", "202", "YTZ", "EWR", 190, 290, { delayMinutes: { departure: 25 }, estimated: { departure: min(215) } }),
    flight("L12", "303", "YTZ", "YOW", 260, 330),
    flight("L13", "404", "YHZ", "YTZ", 340, 450),
    flight("L14", "505", "YTZ", "YQG", 430, 520, { cancelled: true, status: "cancelled" }),
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

const VIEWS = {
  // signed out: /api/auth/session answers 401, otherwise the console redirects a signed-in visitor to the radar
  landing: { path: "/", signedOut: true },
  "landing-login": { path: "/", signedOut: true, click: "Login" },
  "ops-radar": { path: "/ops/radar", ops: true },
  "ops-radar-departures": { path: "/ops/radar?mode=departures", ops: true },
  "ops-operations": { path: "/ops/operations", ops: true },
};

const jobs = JSON.parse(readFileSync(process.argv[2], "utf8"));
const opsHtml = await (await fetch(`${jobs.base}/ops.html`)).text();
const browser = await chromium.launch({ executablePath: jobs.chrome });
const report = [];

for (const shot of jobs.shots) {
  const view = VIEWS[shot.view];
  if (!view) throw new Error(`unknown view ${shot.view}`);
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce", serviceWorkers: "block" });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
  await page.clock.setFixedTime(NOW);
  await page.route((u) => u.pathname === "/api/events", (r) => r.abort());
  await page.route((u) => u.pathname.startsWith("/api/"), (r) => {
    const { pathname } = new URL(r.request().url());
    if (view.signedOut && pathname === "/api/auth/session") return r.fulfill({ status: 401, contentType: "application/json", body: "{}" });
    r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: answer(pathname), presentation }) });
  });
  if (view.ops) {
    await page.route((u) => u.pathname === "/ops" || u.pathname.startsWith("/ops/"), (r) => r.fulfill({ status: 200, contentType: "text/html", body: opsHtml }));
  }
  for (const [file, cssPath] of Object.entries(shot.css ?? {})) {
    const css = readFileSync(cssPath, "utf8");
    await page.route((u) => u.pathname === `/${file.replace("apps/canvas/", "")}`, async (r) => {
      const response = await r.fetch();
      const body = (await response.text()).replace(/const __vite__css = ".*"\n/, () => `const __vite__css = ${JSON.stringify(css)}\n`);
      r.fulfill({ response, body });
    });
  }
  await page.goto(`${jobs.base}${view.path}`, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  if (view.click) await page.getByRole("button", { name: view.click }).first().click();
  await page.waitForTimeout(700);
  await page.screenshot({ path: shot.out, animations: "disabled", caret: "hide" });
  report.push({ out: shot.out, errors });
  await context.close();
}
await browser.close();
writeFileSync(process.argv[2] + ".report.json", JSON.stringify(report, null, 1));
console.log(`rendered ${report.length} shots, ${report.filter((r) => r.errors.length).length} with page errors`);
