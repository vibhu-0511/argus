// Prepare a detached git worktree of the platform repo with the dom2src plugin added to its Vite config.
// Writes only inside the worktree: the platform repo's working tree and its node_modules are only read (linked).
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { worktree } from "./wt.mjs";

const repo = process.env.ARGUS_PLATFORM_REPO;
if (!repo) throw new Error("set ARGUS_PLATFORM_REPO to the dcortex-platform checkout (see config/platform.md)");
const wt = worktree();
if (!fs.existsSync(path.join(wt, ".git"))) {
  execFileSync("git", ["-C", repo, "worktree", "add", "--detach", wt, "HEAD"], { stdio: "inherit" });
}

// pnpm installs are not repeated: the worktree reuses the platform repo's installed dependencies.
for (const dir of ["node_modules", path.join("apps", "canvas", "node_modules")]) {
  const link = path.join(wt, dir);
  if (!fs.existsSync(link)) fs.symlinkSync(path.join(repo, dir), link, "junction");
}

const plugin = fileURLToPath(new URL("../src/index.ts", import.meta.url)).replaceAll("\\", "/");
const cache = path.join(wt, ".vite-cache").replaceAll("\\", "/");
fs.writeFileSync(
  path.join(wt, "apps", "canvas", "vite.dom2src.config.ts"),
  [
    'import base from "./vite.config.ts";',
    `import { dom2srcPlugin } from ${JSON.stringify(plugin)};`,
    "",
    `export default { ...base, cacheDir: ${JSON.stringify(cache)}, plugins: [dom2srcPlugin(), ...(base as any).plugins] };`,
    "",
  ].join("\n"),
);
console.log(`canvas worktree ready: ${wt} @ ${execFileSync("git", ["-C", wt, "rev-parse", "--short", "HEAD"]).toString().trim()}`);
