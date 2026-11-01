import assert from "node:assert/strict";
import test from "node:test";
import { capture, FONT_WAIT, NETWORK_IDLE } from "../src/capture.ts";

test("capture waits for fonts and network idle", async () => {
  const seen: string[] = [];
  const page = {
    async evaluate(fn: () => unknown) {
      seen.push(String(fn));
    },
    async waitForLoadState(state: string) {
      seen.push(state);
    },
    async screenshot() {
      seen.push("screenshot");
      return new Uint8Array();
    },
  };
  await capture(page);
  assert.equal(FONT_WAIT, "document.fonts.ready");
  assert.ok(seen[0].includes(FONT_WAIT));
  assert.equal(seen[1], NETWORK_IDLE);
  assert.equal(seen[2], "screenshot");
});
