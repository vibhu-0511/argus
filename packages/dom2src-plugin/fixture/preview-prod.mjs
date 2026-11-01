import path from "node:path";
import { fileURLToPath } from "node:url";
import { build, preview } from "vite";

const configFile = path.join(path.dirname(fileURLToPath(import.meta.url)), "vite.config.ts");

await build({ configFile, mode: "production" });
await preview({ configFile, mode: "production" });
