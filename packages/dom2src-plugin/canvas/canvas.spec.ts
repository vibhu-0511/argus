// The dom2src plugin applied to the real dcortex Canvas, served by a Vite dev server from a worktree of the
// platform repo (canvas/setup.mjs). There is no BFF: /api is answered here with a synthetic admin session, one
// synthetic desk-monitor reply, and 403 for every other read, so each screen draws its own denied/empty state.
// Nothing here touches a database or a real tenant.
import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { PORT, worktree } from "./wt.mjs";

const BASE = `http://127.0.0.1:${PORT}`;
const root = worktree();

type Flow = { name: string; url: string; files: string[]; click?: string; after?: { selector: string; file: string } };
const flows: Flow[] = [
  { name: "sign-in /login", url: "/login", files: ["screens/Landing.tsx"], click: ".landing-cta", after: { selector: ".auth-backdrop", file: "screens/AuthModal.tsx" } },
  { name: "sign-in /ops/login", url: "/ops/login", files: ["screens/Landing.tsx", "ops/OpsApp.tsx"] },
  { name: "ops /ops/radar", url: "/ops/radar", files: ["ops/Radar.tsx", "ops/TopMenu.tsx"] },
  { name: "ops /ops/operations", url: "/ops/operations", files: ["ops/Operations.tsx", "ops/Timeline.tsx"] },
  { name: "ops /ops/launchpad", url: "/ops/launchpad", files: ["ops/Launchpad.tsx"] },
  { name: "ops /ops/rules", url: "/ops/rules", files: ["ops/Rules.tsx"] },
  { name: "desk console", url: "/desk?sel=console", files: ["screens/Desk.tsx"] },
  { name: "desk timeline", url: "/desk?sel=timeline", files: ["screens/Desk.tsx", "desk/DeskTimelineBoard.tsx"] },
  { name: "desk crew", url: "/desk?sel=crew", files: ["screens/Desk.tsx", "desk/DeskCrewBoard.tsx"] },
  { name: "desk brief", url: "/desk?sel=brief", files: ["screens/Desk.tsx", "desk/DeskBriefBoard.tsx"] },
  { name: "user admin", url: "/admin/users", files: ["screens/UserAdmin.tsx"] },
  { name: "audit", url: "/admin/audit", files: ["screens/AuditLog.tsx"] },
];

const presentation = { timezone: "UTC", locale: "en", currency: "USD", contextHash: "synthetic", customerName: "Synthetic" };
const session = {
  subject: "admin",
  roles: ["admin"],
  permissions: ["users:admin", "config:read"],
  presentation: { customerName: "Synthetic", supportedLocales: ["en"] },
};
const deskMonitor = {
  date: "2026-10-30",
  zone: "UTC",
  now: "2026-10-30T12:00:00Z",
  currentBankId: "b1",
  banks: [
    { id: "b1", startMinute: 0, endMinute: 720 },
    { id: "b2", startMinute: 720, endMinute: 1440 },
  ],
  rows: [],
  strip: [],
};

async function mockBackend(page: Page) {
  await page.route((u) => u.pathname.startsWith("/api/"), (route) => {
    const { pathname } = new URL(route.request().url());
    if (pathname === "/api/auth/session") return route.fulfill({ json: { data: session, presentation } });
    if (pathname === "/api/read/desk-monitor") return route.fulfill({ json: { data: deskMonitor, presentation } });
    if (pathname === "/api/events" || pathname === "/api/client-events") return route.fulfill({ status: 204, body: "" });
    return route.fulfill({ status: 403, json: { error: { code: "forbidden", message: "synthetic" } } });
  });
  // The ops console is a second Vite entry that the BFF serves under /ops; in dev it is /ops.html.
  await page.route((u) => u.pathname.startsWith("/ops/") && !u.pathname.includes("."), async (route) => {
    if (route.request().resourceType() !== "document") return route.continue();
    const html = await (await fetch(`${BASE}/ops.html`)).text();
    return route.fulfill({ body: html, contentType: "text/html" });
  });
}

function sourceFiles(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true, recursive: true })
    .filter((e) => e.isFile() && e.name.endsWith(".tsx") && !e.name.includes(".test."))
    .map((e) => path.join(e.parentPath, e.name));
}

function classTokens(files: string[]): Set<string> {
  const tokens = new Set<string>();
  for (const file of files) {
    for (const m of fs.readFileSync(file, "utf8").matchAll(/className=(?:"([^"]*)"|\{`([^`]*)`\})/g)) {
      for (const t of (m[1] ?? m[2]).split(/[\s$]+/)) if (/^[a-z][\w-]*$/.test(t)) tokens.add(t);
    }
  }
  return tokens;
}

// Class names that only the workspace package @dcortex/canvas-ui (prebuilt dist/, not part of apps/canvas) uses.
const appClasses = classTokens(sourceFiles(path.join(root, "apps/canvas/src")));
const libraryClasses = new Set([...classTokens(sourceFiles(path.join(root, "platform/canvas-ui/src")))].filter((t) => !appClasses.has(t)));

for (const flow of flows) {
  test(flow.name, async ({ page }) => {
    await mockBackend(page);
    await page.goto(BASE + flow.url);
    await page.waitForSelector("#root *[data-src]");
    if (flow.click) await page.click(flow.click);
    if (flow.after) await page.waitForSelector(flow.after.selector);
    await page.waitForTimeout(1500);

    const hosts = await page.evaluate(() =>
      [...document.querySelectorAll("#root *")].map((el) => ({
        tag: el.localName,
        src: el.getAttribute("data-src"),
        svg: el instanceof SVGElement,
        link: el.localName === "a" && el.hasAttribute("data-menu-id"),
        classes: [...el.classList],
        ancestorClasses: [...(el.parentElement?.closest("[class]")?.classList ?? [])],
        up: (() => {
          const out: string[] = [];
          for (let n: Element | null = el; n; n = n.parentElement) out.push(...n.classList);
          return out;
        })(),
      })),
    );

    const stamped = hosts.filter((h) => h.src);
    expect(stamped.length, "stamped host elements").toBeGreaterThan(0);
    const files = new Set<string>();
    for (const h of stamped) {
      const m = /^(apps\/canvas\/src\/[^:]+\.tsx):(\d+):(\d+)$/.exec(h.src!);
      expect(m, `${h.tag} data-src ${h.src}`).not.toBeNull();
      files.add(m![1].slice("apps/canvas/src/".length));
      // The value must point at the opening tag of this element in the source file, not just look right.
      const line = fs.readFileSync(path.join(root, m![1]), "utf8").split("\n")[Number(m![2]) - 1] ?? "";
      expect(line.slice(Number(m![3]) - 1).startsWith(`<${h.tag}`), `${h.src} is not <${h.tag}: ${line.trim().slice(0, 60)}`).toBe(true);
    }
    for (const file of flow.files) expect([...files], `${flow.url} stamps ${file}`).toContain(file);
    if (flow.after) {
      const src = await page.getAttribute(flow.after.selector, "data-src");
      expect(src).toMatch(new RegExp(String.raw`^apps/canvas/src/${flow.after.file.replace(".", "\\.")}:\d+:\d+$`));
    }

    // Everything unstamped is explained: a router <Link> (a component, not a host tag), an SVG node from
    // lucide-react (node_modules, skipped by design), or markup owned by the prebuilt @dcortex/canvas-ui.
    const unexplained = hosts.filter((h) => !h.src && !h.link && !h.svg && !h.up.some((c) => libraryClasses.has(c)));
    expect(unexplained.map((h) => `${h.tag}.${h.classes.join(".")}`), "unstamped, unexplained").toEqual([]);

    const unstamped = hosts.length - stamped.length;
    test.info().annotations.push({ type: "hosts", description: `${stamped.length} stamped, ${unstamped} unstamped (${[...files].join(", ")})` });
  });
}
