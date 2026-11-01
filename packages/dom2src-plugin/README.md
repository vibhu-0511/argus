# dom2src-plugin

Vite plugin that stamps `data-src="file:line:col"` on JSX host elements in development and test. The value is the repo-relative path of the JSX tag that created the element. There is no component-name suffix and no second attribute. A host written in a component's return and a host written at a call site each get that one attribute. Component tags are left alone.

Mode `production` does not run the transform. The plugin sets `enforce: 'pre'` so the hook still sees JSX. `@vitejs/plugin-react` is also `enforce: 'pre'`, so list `dom2srcPlugin()` before `react()`.

```ts
import { dom2srcPlugin } from "@argus/dom2src-plugin";
import react from "@vitejs/plugin-react";

export default {
  plugins: [dom2srcPlugin(), react()],
};
```

## Install

From the repo root:

```
pnpm install
```

## Commands

```
pnpm --filter @argus/dom2src-plugin test
pnpm --filter @argus/dom2src-plugin run test:attribute
```

`test` is `node --test test/transform.test.ts`. `test:attribute` is the Playwright fixture. It needs a Chromium install (`pnpm --filter @argus/dom2src-plugin exec playwright install chromium` when the machine does not already have one). The fixture is not the dcortex dev server.

## Against the real Canvas

`test:canvas` adds the plugin to a throwaway git worktree of the dcortex-platform repo and drives the five flows in Chromium:

```
ARGUS_PLATFORM_REPO=<platform checkout> pnpm --filter @argus/dom2src-plugin run test:canvas
```

`canvas/setup.mjs` makes a detached worktree at `ARGUS_CANVAS_WORKTREE` (default: a folder in the OS temp dir), links the platform repo's installed `node_modules` into it, and writes `apps/canvas/vite.dom2src.config.ts` there. The platform repo's own working tree is never written. There is no BFF: `canvas/canvas.spec.ts` answers `/api` with a synthetic admin session and 403 for the reads, so each screen draws its denied or empty state. For every stamped element the test opens the Canvas source at the stamped line and column and checks the tag is there.

Elements from the prebuilt `@dcortex/canvas-ui` package (the shell, the desk header) and from `node_modules` are not stamped. The test lists them as unstamped and requires each one to be a router `<Link>`, an SVG node, or a canvas-ui element. It needs the private platform repo, so CI does not run it.
