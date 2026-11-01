import { chromium } from "playwright";
import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

async function run(scriptPath, htmlPath) {
  const source = await readFile(scriptPath, "utf8");
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.goto(pathToFileURL(htmlPath).href);
  const expect = (locator) => ({
    toBeVisible: async () => {
      if (!(await locator.isVisible())) throw new Error("not visible");
    },
    toBeHidden: async () => {
      if (await locator.isVisible()) throw new Error("visible");
    },
  });
  const test = async (_name, fn) => {
    await fn({ page });
  };
  try {
    const go = new Function("test", "expect", "page", `return (async () => {\n${source}\n})()`);
    await go(test, expect, page);
    return "pass";
  } catch {
    return "fail";
  } finally {
    await browser.close();
  }
}

const names = ["valid", "passes-on-bug", "fails-on-golden"];
const out = {};
for (const name of names) {
  out[name] = {
    buggy: await run(`/work/${name}.mjs`, "/work/buggy.html"),
    golden: await run(`/work/${name}.mjs`, "/work/golden.html"),
  };
}
console.log(JSON.stringify(out));
