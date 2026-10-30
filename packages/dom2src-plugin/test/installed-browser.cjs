const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

// Reuse a Playwright browser already on this machine. This file does not download one.
const pkg = path.dirname(require.resolve("playwright-core/package.json"));
const browsers = JSON.parse(fs.readFileSync(path.join(pkg, "browsers.json"), "utf8"));
const revision = browsers.browsers.find((browser) => browser.name === "chromium").revision;
const folder = `chromium-${revision}`;

function has(dir) {
  return Boolean(dir) && fs.existsSync(path.join(dir, folder));
}

function find() {
  if (has(process.env.PLAYWRIGHT_BROWSERS_PATH)) return process.env.PLAYWRIGHT_BROWSERS_PATH;
  const local = path.join(os.homedir(), "AppData", "Local", "ms-playwright");
  if (has(local)) return local;
  const cache = path.join(os.tmpdir(), "cursor-sandbox-cache");
  if (!fs.existsSync(cache)) return undefined;
  for (const name of fs.readdirSync(cache)) {
    const candidate = path.join(cache, name, "playwright");
    if (has(candidate)) return candidate;
  }
  return undefined;
}

const found = find();
if (found) process.env.PLAYWRIGHT_BROWSERS_PATH = found;
