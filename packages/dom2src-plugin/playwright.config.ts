import { defineConfig } from "@playwright/test";

const dev = "http://127.0.0.1:5191";
const prod = "http://127.0.0.1:5192";

export default defineConfig({
  testDir: "test",
  testMatch: "attribute.spec.ts",
  timeout: 30_000,
  use: {
    viewport: { width: 1280, height: 800 },
    launchOptions: { args: ["--no-proxy-server"] },
  },
  webServer: [
    {
      command: "node ./node_modules/vite/bin/vite.js --config fixture/vite.config.ts --host 127.0.0.1 --port 5191 --strictPort --mode development",
      url: dev,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "node fixture/preview-prod.mjs",
      url: prod,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
