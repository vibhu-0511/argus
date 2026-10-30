# ADR-004: Playwright MCP vs direct Playwright as tool

Status: accepted (P1-T02). This ADR is the Risk 4 mitigation.

## Context

Risk 4 is that Playwright MCP may not work with an MCP Python SDK v2 client, and that neither side had a stated claim about spec 2026-07-28. P1-T01 is the spike. A no-go is recorded here. A direct-Playwright implementation is not a task in this phase.

The spike is `docs/notes/p1-mcp-spike.md`, from `packages/repro-agent/spike_playwright_mcp.py`, run on 2026-10-30.

## Decision

Use Playwright MCP as the browser tool. The client is MCP Python SDK 2.3.0. The server is `@playwright/mcp` 0.0.83, launched as `npx -y @playwright/mcp@0.0.83 --headless --isolated`.

The repro allow-list is `navigate`, `snapshot`, `click`, `type`, `assert-visible`, and `screenshot`. `browser_run_code_unsafe` stays off. `page.evaluate` is not added. The same two limits apply to the fallback below.

The pinned server does not support spec 2026-07-28. SDK 2.3.0 in its default mode probes `server/discover` and falls back to `initialize`. The process completed `initialize` at protocol `2025-11-25`. `client.protocol_version` was `2025-11-25`. The discover result was empty. `serverInfo` was name `Playwright`, version `1.64.0-alpha-1790635538000`. That alpha string stays off the Playwright 1.64.1 row in `PLAN.md`.

The call evidence: `browser_navigate` and `browser_snapshot` both returned `is_error: false` against a local page titled `argus-p1-spike`. The process tool list included `browser_run_code_unsafe` and `browser_evaluate`. Neither was called. The list has no tool named `assert-visible`; that name is one of the six repro tools, defined later, and it is not `page.evaluate`.

The fallback, if a later run cannot initialize this server, is this ADR. Restart the server once, then stop with `tool-unavailable`. Direct Playwright is not built. P2-T00 re-checks the spec note; it does not by itself add a browser stack.

## Alternatives

- Direct Playwright as the tool now. The spike initialized and ran navigate plus snapshot, so the interop risk that would force this did not fire. Building it would be the unscheduled work Risk 4 refuses.
- Treat protocol `2025-11-25` as a no-go because it is not `2026-07-28`. The SDK did initialize the server. The spec gap is recorded here. It is not a reason to throw out the go.
- Turn on `browser_run_code_unsafe` or add `page.evaluate` so the model can improvise. The server README calls `browser_run_code_unsafe` RCE-equivalent. Egress control in P1-T05 does not make that tool safe.

## Consequences

P1-T04 defines the six allow-listed tools and no others. A killed server (P1-T15) restarts once and then stops `tool-unavailable`. It does not switch to a direct Playwright client. The Playwright row in the versions table stays 1.64.1 until a T00 task changes it. Whether `@playwright/mcp` 0.0.83 speaks spec 2026-07-28 is answered: it does not. The SDK 2.3.0 client can still initialize the 2025-11-25 handshake that this server speaks.
