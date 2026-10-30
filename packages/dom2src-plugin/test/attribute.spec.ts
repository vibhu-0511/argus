// This fixture is not the dcortex dev server.
import { expect, test } from "@playwright/test";

const dev = "http://127.0.0.1:5191";
const prod = "http://127.0.0.1:5192";

test("counts host elements without data-src", async ({ page }) => {
  await page.goto(dev);
  const hosts = page.locator("#root *");
  await expect(hosts).toHaveCount(5);
  const missing = await hosts.evaluateAll((nodes) => nodes.filter((node) => !node.hasAttribute("data-src")).length);
  expect(missing).toBe(0);
});

test("production build carries no data-src", async ({ page }) => {
  await page.goto(prod);
  await expect(page.locator("#root *")).toHaveCount(5);
  expect(await page.locator("[data-src]").count()).toBe(0);
});
