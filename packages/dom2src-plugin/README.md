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

From `packages/dom2src-plugin`:

```
npm install
```

## Commands

```
npm test
npm run test:attribute
```

`npm test` is `node --test test/transform.test.ts`. `test:attribute` is the Playwright fixture. It needs a Chromium install (`npx playwright install chromium` when the machine does not already have one). The fixture is not the dcortex dev server.
