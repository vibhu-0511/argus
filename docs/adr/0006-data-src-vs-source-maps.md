# ADR-006: data-src attribute vs source maps

Status: accepted (P2-T04).

## Context

P2 needs a mapping from a DOM node to a source location. React 19 removed `_debugSource` from Fiber nodes (issue #32574, PR #28265). `_debugStack` does not yield a filesystem path. Checked 2026-10-30, and not from that issue: Babel's `sourceSelf` option says `__source` and `__self` were removed since React 19.2. The React 19.3 blog's notable-changes list does not mention `jsxDEV` or `_debugSource`.

The two candidates are a build-time `data-src` attribute and source maps. Source maps map generated code back to source. A DOM node does not carry that map. `data-src` is on the host element `locate()` reads.

## Decision

The build-time `data-src` attribute is the route. Source maps are not the DOM-to-source path. Production builds do not emit the attribute.

`packages/dom2src-plugin` stamps `data-src="file:line:col"` on JSX host elements in development and test, enforce pre, and skips production.

Robustness. `_debugSource` is gone. `_debugStack` does not yield a filesystem path. A source map stays with the generated code, and the DOM node does not carry it. The attribute is on the host element. The unit test is `node --test test/transform.test.ts`, 7 passed, including the five Canvas flow files read in memory. Playwright tests in `packages/dom2src-plugin/test/attribute.spec.ts` use a Vite fixture, not the dcortex dev server. Dev: 5 host elements, 0 missing `data-src`.

Build cost. The stamp runs in development and test. The unit test reads those five flow files in memory. The attribute tests use a Vite fixture. The dcortex checkout was not edited. `apps/canvas/vite.config.ts` still has `sourcemap: true` and does not register this plugin. That flag does not put a location on a DOM node.

Production safety. The plugin skips production. `npm run test:attribute`, 2 passed. The fixture production build has 0 elements with `data-src`.

## Alternatives

- Read `_debugSource` or `_debugStack` on the Fiber node. React 19 removed `_debugSource` (issue #32574, PR #28265). `_debugStack` does not yield a filesystem path. Babel's `sourceSelf` option says `__source` and `__self` were removed since React 19.2.
- Use source maps as the DOM-to-source path. They map generated code back to source. A DOM node does not carry that map. `apps/canvas/vite.config.ts` still has `sourcemap: true` and does not register this plugin.

## Consequences

`locate()` reads `data-src` on the host element. Development and test builds stamp `data-src="file:line:col"`. Production builds do not emit the attribute. The dcortex checkout was not edited. `apps/canvas/vite.config.ts` still has `sourcemap: true` and does not register this plugin.
