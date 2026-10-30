import { execFileSync } from "node:child_process";
import { createServer, type Server } from "node:http";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { FLOWS, boundingBox, computedStyle, pixelDiff } from "../src/checks";

const PLATFORM = process.env.ARGUS_PLATFORM_REPO ?? "";
const CLOCK = ".radar-clock-time { font-size: 20px; font-weight: 600; }";
const CLOCK_BROKEN = ".radar-clock-time { font-size: 64px; font-weight: 600; background: #ff00aa; display: inline-block; }";

function worktree(name: string): string {
  const dir = mkdtempSync(path.join(tmpdir(), `argus-${name}-`));
  execFileSync("git", ["worktree", "add", "--detach", dir, "HEAD"], { cwd: PLATFORM, stdio: "pipe" });
  return dir;
}

function drop(dir: string) {
  execFileSync("git", ["worktree", "remove", "--force", dir], { cwd: PLATFORM, stdio: "pipe" });
  rmSync(dir, { recursive: true, force: true });
}

function serve(cssFile: string): Promise<{ server: Server; origin: string }> {
  const css = readFileSync(cssFile);
  const server = createServer((req, res) => {
    const url = new URL(req.url ?? "/", "http://127.0.0.1");
    if (url.pathname === "/radar.css") {
      res.setHeader("content-type", "text/css");
      res.end(css);
      return;
    }
    const flow = FLOWS.find((item) => item.path.split("?")[0] === url.pathname);
    if (!flow) {
      res.statusCode = 404;
      res.end("missing");
      return;
    }
    res.setHeader("content-type", "text/html; charset=utf-8");
    res.end(
      `<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/radar.css">` +
        `<body style="margin:24px;background:#fff"><p id="flow">${flow.id}</p>` +
        `<span class="radar-clock-time" id="probe">Radar</span></body>`,
    );
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") throw new Error("no port");
      resolve({ server, origin: `http://127.0.0.1:${address.port}` });
    });
  });
}

async function visitFlows(page: Page, origin: string) {
  for (const flow of FLOWS) {
    await page.goto(`${origin}${flow.path}`);
    await expect(page.locator("#flow")).toHaveText(flow.id);
    await expect(page.locator("#probe")).toBeVisible();
  }
}

test("checks pass on a clean dcortex worktree and fail on a hand-broken copy", async ({ page }) => {
  test.skip(!PLATFORM, "set ARGUS_PLATFORM_REPO to a dcortex-platform checkout");
  test.setTimeout(300_000);
  const clean = worktree("clean");
  const broken = worktree("broken");
  const css = "apps/canvas/src/ops/radar.css";
  const brokenCss = path.join(broken, css);
  const source = readFileSync(brokenCss, "utf8");
  if (!source.includes(CLOCK)) throw new Error("clock rule missing");
  writeFileSync(brokenCss, source.replace(CLOCK, CLOCK_BROKEN));
  const cleanSite = await serve(path.join(clean, css));
  const brokenSite = await serve(brokenCss);
  try {
    await visitFlows(page, cleanSite.origin);
    await page.goto(`${cleanSite.origin}/ops/radar`);
    const style = await computedStyle(page, "#probe", "font-size", "20px");
    const box = await boundingBox(page, "#probe", { maxWidth: 160, maxHeight: 40 });
    const baseline = await page.locator("#probe").screenshot();
    const same = await pixelDiff(page, "#probe", baseline, 0);
    expect(style.ok, style.reason).toBe(true);
    expect(box.ok, box.reason).toBe(true);
    expect(same.ok, same.reason).toBe(true);

    await visitFlows(page, brokenSite.origin);
    await page.goto(`${brokenSite.origin}/ops/radar`);
    const brokenStyle = await computedStyle(page, "#probe", "font-size", "20px");
    const brokenBox = await boundingBox(page, "#probe", { maxWidth: 160, maxHeight: 40 });
    const brokenPixels = await pixelDiff(page, "#probe", baseline, 0);
    expect(brokenStyle.ok, brokenStyle.reason).toBe(false);
    expect(brokenBox.ok, brokenBox.reason).toBe(false);
    expect(brokenPixels.ok, brokenPixels.reason).toBe(false);
  } finally {
    cleanSite.server.close();
    brokenSite.server.close();
    drop(clean);
    drop(broken);
  }
});
