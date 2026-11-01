// stdin: JSON [[a.png, b.png], ...]  stdout: JSON [changed-pixel ratio, ...]  (-1 when the sizes differ)
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";

const require = createRequire(path.join(process.env.BENCH_MODULES, "x.js"));
const { PNG } = require("pngjs");
const pixelmatch = (await import(pathToFileURL(require.resolve("pixelmatch")).href)).default;
const pairs = JSON.parse(readFileSync(0, "utf8"));
const out = pairs.map(([a, b]) => {
  const left = PNG.sync.read(readFileSync(a));
  const right = PNG.sync.read(readFileSync(b));
  if (left.width !== right.width || left.height !== right.height) return -1;
  return pixelmatch(left.data, right.data, null, left.width, left.height, { threshold: 0.1 }) / (left.width * left.height);
});
console.log(JSON.stringify(out));
