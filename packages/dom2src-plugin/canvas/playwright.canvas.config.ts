import path from "node:path";
import { defineConfig } from "@playwright/test";
import { PORT, worktree } from "./wt.mjs";

export default defineConfig({
  testDir: ".",
  testMatch: "canvas.spec.ts",
  timeout: 60_000,
  use: { viewport: { width: 1280, height: 800 }, launchOptions: { args: ["--no-proxy-server"] } },
  webServer: {
    command: `node node_modules/vite/bin/vite.js --config vite.dom2src.config.ts --host 127.0.0.1 --port ${PORT} --strictPort --mode development`,
    cwd: path.join(worktree(), "apps", "canvas"),
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
