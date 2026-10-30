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

## Verifier follow-up (2026-10-31)

The decision stands. Two statements above were fixture-only and are now backed by a run on the real Canvas. `packages/dom2src-plugin/canvas/` adds this plugin to a detached worktree of dcortex-platform at `ac86acc75` (the platform repo's working tree is untouched) and serves it with that repo's own Vite 6.4.3. With `/api` answered by a synthetic session and 403 for reads, 12 routes of the five flows were opened in Chromium: `/login` (and the sign-in modal), `/ops/login`, `/ops/radar`, `/ops/operations`, `/ops/launchpad`, `/ops/rules`, `/desk?sel=console|timeline|crew|brief`, `/admin/users`, `/admin/audit`. 12 passed. On each route the screen's own file carries `data-src`, and every stamped value points at the matching opening tag in the source file.

What this does not show: elements rendered by the prebuilt workspace package `@dcortex/canvas-ui` (the page shell and desk header, 61 to 122 elements per route) and SVG nodes from `lucide-react` carry no `data-src`, so `locate()` would return `no-source-info` for them. The desk console tab showed only shell elements because the synthetic desk-monitor reply has no rows. Responses were synthetic, so this says nothing about data-dependent markup. `apps/canvas/vite.config.ts` in the platform repo is still unchanged. Commands and counts: `docs/notes/p2-conformance-fixes.md`.
