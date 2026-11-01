// Serves the platform's Canvas for the repro runner. Read-only use of the checkout: the Vite cache goes to RIG_CACHE and
// the CSS of the buggy / golden tree is swapped in the browser (run-script.mjs), so the checkout's own state does not matter.
// Bound to 127.0.0.1 only. The sandbox reaches it as host.docker.internal through the proxy container (Docker Desktop
// relays that name to the host loopback); allowedHosts is open only because the Host header is then not "localhost".
import { pathToFileURL } from "node:url";
import path from "node:path";

const platform = process.env.ARGUS_PLATFORM_REPO;
if (!platform) throw new Error("set ARGUS_PLATFORM_REPO");
const root = path.resolve(platform, "apps", "canvas");
const base = (await import(pathToFileURL(path.join(root, "vite.config.ts")).href)).default;
export default {
  ...base,
  root,
  cacheDir: process.env.RIG_CACHE,
  server: { host: "127.0.0.1", allowedHosts: true, port: Number(process.env.RIG_PORT ?? 5199), strictPort: true, proxy: {} },
};
