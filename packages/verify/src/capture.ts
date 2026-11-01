/** Capture contract for pixel screenshots. The font wait stays. A different font family still fails the pixel check. */

export const FONT_WAIT = "document.fonts.ready";
export const NETWORK_IDLE = "networkidle";

type Capturable = {
  evaluate(fn: () => unknown): Promise<unknown>;
  waitForLoadState(state: string): Promise<unknown>;
  screenshot(): Promise<Uint8Array>;
};

export async function capture(page: Capturable): Promise<Uint8Array> {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForLoadState(NETWORK_IDLE);
  return page.screenshot();
}
