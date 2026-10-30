import type { Page } from "@playwright/test";
import pixelmatch from "pixelmatch";
import { PNG } from "pngjs";

export type CheckVerdict = { ok: boolean; reason: string };

/** The five flows in config/platform.md. Ops uses /ops/radar; the other ops paths are the same menu. */
export const FLOWS = [
  { id: "sign-in", path: "/login" },
  { id: "ops", path: "/ops/radar" },
  { id: "desk", path: "/desk?sel=console" },
  { id: "admin-users", path: "/admin/users" },
  { id: "audit", path: "/admin/audit" },
] as const;

export async function computedStyle(
  page: Page,
  selector: string,
  property: string,
  expected: string,
): Promise<CheckVerdict> {
  const actual = await page.locator(selector).evaluate(
    (element, name) => getComputedStyle(element).getPropertyValue(name),
    property,
  );
  const ok = actual.trim() === expected;
  return { ok, reason: ok ? `${property}=${actual.trim()}` : `${property} is ${actual.trim()}, expected ${expected}` };
}

export async function boundingBox(
  page: Page,
  selector: string,
  limits: { minWidth?: number; maxWidth?: number; minHeight?: number; maxHeight?: number },
): Promise<CheckVerdict> {
  const box = await page.locator(selector).boundingBox();
  if (!box) return { ok: false, reason: `${selector} has no box` };
  const fails: string[] = [];
  if (limits.minWidth !== undefined && box.width < limits.minWidth) fails.push(`width ${box.width} < ${limits.minWidth}`);
  if (limits.maxWidth !== undefined && box.width > limits.maxWidth) fails.push(`width ${box.width} > ${limits.maxWidth}`);
  if (limits.minHeight !== undefined && box.height < limits.minHeight) fails.push(`height ${box.height} < ${limits.minHeight}`);
  if (limits.maxHeight !== undefined && box.height > limits.maxHeight) fails.push(`height ${box.height} > ${limits.maxHeight}`);
  return { ok: fails.length === 0, reason: fails.length === 0 ? `${box.width}x${box.height}` : fails.join("; ") };
}

export async function pixelDiff(
  page: Page,
  selector: string,
  baseline: Buffer,
  maxChangedRatio: number,
): Promise<CheckVerdict> {
  const shot = await page.locator(selector).screenshot();
  const actual = PNG.sync.read(shot);
  const expected = PNG.sync.read(baseline);
  if (actual.width !== expected.width || actual.height !== expected.height) {
    return {
      ok: false,
      reason: `size ${actual.width}x${actual.height} vs baseline ${expected.width}x${expected.height}`,
    };
  }
  const changed = pixelmatch(expected.data, actual.data, null, actual.width, actual.height, { threshold: 0.1 });
  const ratio = changed / (actual.width * actual.height);
  return { ok: ratio <= maxChangedRatio, reason: `changed ${(ratio * 100).toFixed(2)}%` };
}
