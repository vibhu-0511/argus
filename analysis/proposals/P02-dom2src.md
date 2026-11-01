# P02-dom2src

### DESIGN-014
- Severity: Med
- Section: Done when, P2-T02, P2-T08
- Owner: [CLAUDE] (Done when, nearest task P2-T00); [PAIR] (P2-T02); [ME] (P2-T08)
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
- A Vite plugin adds a `data-src="file:line:col"` attribute to every JSX host element in test/dev builds and strips it from production builds (both asserted by tests on all 6 target-app routes).

- `locate()` returns file and line for an element given a selector, and returns a typed "ambiguous" result with candidates when a wrapper component is involved.

| P2-T02 | Build Vite plugin that injects `data-src` on JSX host elements | [PAIR] | build | 4 | P2-T00, P0-T09 | In a dev build, every host element in the 6 routes carries `data-src="file:line:col"`; a unit test checks a sample file's transform output |

| P2-T08 | Handle ambiguity: wrapper components and repeated elements return candidates | [ME] | build | 2 | P2-T07 | For a wrapper-rendered button, locate() returns an `ambiguous` result with at least 2 ranked candidates and the call stack hint |
```

- Proposed text:

```
- A Vite plugin adds a repo-relative `data-src="file:line:col"` attribute, with no tag suffix, for the definition and the JSX call site, to every JSX host element in test/dev builds, and the plugin is absent from production builds (both asserted by tests on all 6 target-app routes).

- `locate()` returns file and line for an element given a selector, and returns a typed "ambiguous" result with candidates when a wrapper component is involved; `locate()` stays the Python tool, with no client and no companion server.

| P2-T02 | Build Vite plugin that injects `data-src` on JSX host elements | [PAIR] | build | 4 | P2-T00, P0-T09 | In a dev build, every host element in the 6 routes carries repo-relative `data-src="file:line:col"` for the definition and the JSX call site, with no tag suffix; the plugin is absent from production and registered before JSX; a unit test checks a sample file's transform output |

| P2-T08 | Handle ambiguity: wrapper components and repeated elements return candidates | [ME] | build | 2 | P2-T07 | For a wrapper-rendered button, locate() returns an `ambiguous` result with at least 2 ranked candidates, the definition and the JSX call site; `locate()` stays the Python tool, with no client and no companion server |
```

### PLAN-003
- Severity: Low
- Section: P2-T00
- Owner: [CLAUDE]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P2-T00 | Re-verify pinned versions via web search | [CLAUDE] | doc | 1 | P1-T16 | Versions table re-checked, including MCP spec, MCP Python SDK and `@playwright/mcp`; if Playwright MCP still lacks 2026-07-28 support, note it for ADR-004 |
```

- Proposed text:

```
| P2-T00 | Re-verify pinned versions via web search | [CLAUDE] | doc | 1 | P1-T16 | Versions table re-checked, including MCP spec, MCP Python SDK and `@playwright/mcp` |
```

Hours and tasks in this file: unchanged.
