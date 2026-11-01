import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { dom2srcPlugin } from "../src/index.ts";

const root = path.dirname(fileURLToPath(import.meta.url));

// dom2srcPlugin() is enforce: "pre" and is listed before react() so the hook still sees JSX.
export default defineConfig(({ mode }) => ({
  root,
  plugins: [dom2srcPlugin(), react()],
  cacheDir: path.join(root, "node_modules", mode === "production" ? ".vite-prod" : ".vite-dev"),
  server: { host: "127.0.0.1", port: 5191, strictPort: true },
  preview: { host: "127.0.0.1", port: 5192, strictPort: true },
}));
