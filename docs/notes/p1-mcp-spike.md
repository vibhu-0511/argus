# P1 MCP spike

Run on 2026-10-30. Decision: **go**.

The script is `packages/repro-agent/spike_playwright_mcp.py`. It installs MCP Python SDK `mcp==2.3.0` and launches `npx -y @playwright/mcp@0.0.83 --headless --isolated`. The server's working directory is a temporary directory. The script serves a one-page site on `127.0.0.1`, calls `browser_navigate` to that URL, then calls `browser_snapshot`. Exit code of the recorded run: 0.

## Versions from the process

| Fact | Value |
|---|---|
| MCP Python SDK (`importlib.metadata`) | 2.3.0 |
| Server package argument | `@playwright/mcp@0.0.83` |
| Handshake | `initialize` |
| Initialize protocol version | `2025-11-25` |
| `client.protocol_version` | `2025-11-25` |
| Discover result | none |
| `serverInfo` | name `Playwright`, version `1.64.0-alpha-1790635538000` |

SDK 2.3.0 in `mode="auto"` probes `server/discover` and falls back to `initialize`. This server completed `initialize` at `2025-11-25`. That is a protocol the SDK can initialize, so the spike is a go. The negotiated version is not spec `2026-07-28`. ADR-004 (P1-T02) is where that difference is decided. This session does not build a direct-Playwright tool.

`serverInfo.version` is the alpha build the server reported on `initialize`. The pinned Playwright row in `PLAN.md` stays 1.64.1. Tool schemas from that alpha, and from the Playwright `next` dist-tag, are not copied onto that row.

## Tool list from the process

`browser_close`, `browser_resize`, `browser_console_messages`, `browser_handle_dialog`, `browser_emulate_media`, `browser_evaluate`, `browser_file_upload`, `browser_drop`, `browser_find`, `browser_fill_form`, `browser_press_key`, `browser_type`, `browser_navigate`, `browser_navigate_back`, `browser_network_requests`, `browser_network_request`, `browser_run_code_unsafe`, `browser_take_screenshot`, `browser_snapshot`, `browser_click`, `browser_drag`, `browser_hover`, `browser_select_option`, `browser_tabs`, `browser_wait_for`.

`browser_run_code_unsafe` was present. The script does not call it.

`browser_evaluate` was present. The script does not call it. `page.evaluate` is not added. The `browser_navigate` result text includes a generated `page.goto` snippet; that text is the tool result, not a call to `browser_run_code_unsafe` or `page.evaluate`.

## Calls

`browser_navigate` to the local page returned `is_error: false`. The page title in that result was `argus-p1-spike`.

`browser_snapshot` returned `is_error: false`. The snapshot text included `heading "argus-p1-spike"`.

## Allow-list

A go. The repro allow-list is these six tools: `navigate`, `snapshot`, `click`, `type`, `assert-visible`, `screenshot`.

`browser_run_code_unsafe` stays off that list. `page.evaluate` is not added. The server list has no tool named `assert-visible`; that name is the repro tool to define later, not a `page.evaluate` escape hatch.
