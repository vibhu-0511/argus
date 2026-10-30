import { chromium } from "playwright";

const dir = process.env.ARGUS_USER_DATA_DIR;
if (!dir) {
  process.exit(2);
}
const context = await chromium.launchPersistentContext(dir, {
  headless: true,
  // ponytail: --no-sandbox because this image runs Chromium as root; drop it if the runtime gives a user namespace.
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
const page = context.pages()[0] ?? (await context.newPage());
await page.setContent("<h1>Sign in</h1><button>Sign in</button>");
const visible = await page.getByRole("heading", { name: "Sign in" }).isVisible();
await page.getByRole("button", { name: "Sign in" }).click();
await page.screenshot({ path: "/tmp/argus-repro-shot.png" });
await context.close();
process.exit(visible ? 0 : 1);
