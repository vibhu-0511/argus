# MCP 2026-07-28 notes

Read on 2026-10-30: [The 2026-07-28 Specification](https://blog.modelcontextprotocol.io/posts/2026-07-28/) and the `@playwright/mcp` 0.0.83 README on its npm page. The README describes a stdio server (`npx @playwright/mcp@latest`), `--headless`, and `--isolated`. It does not name spec `2026-07-28`, `server/discover`, `input_required`, or `io.modelcontextprotocol/tasks`.

The three changes below are the ones named in the versions table. Each section says what this repo uses the change for, then one question the P1-T01 spike did not answer.

## Stateless core

The spec retires the `initialize` / `initialized` handshake and the session id. Each request carries its protocol version and client identity, and a client that wants capabilities up front calls `server/discover`.

This repo uses that fact for the repro agent: one local Playwright MCP process for a run, with the browser carried across navigate, snapshot, click, type, assert-visible, and screenshot. P1 is that child process, not a load-balanced HTTP fleet. P6's control plane is DBOS, separate from this session.

Open question: the spike kept a single process from `initialize` through snapshot. It does not say whether a new process, with no session id, can keep driving the same browser by passing an explicit handle, which is the stateless-core replacement for session state.

## MRTR `input_required` / `inputResponses`

The spec replaces server-initiated elicitation, sampling, and roots requests with a result of `resultType: "input_required"`. The client retries the original call with the answers in `inputResponses`.

This repo uses that for the P6 QA wait (ADR-023), with a GitHub review comment as the fallback. P1's vague-ticket break may later ask for a missing route or element; that question is the same shape.

Open question: both spike tool results were ordinary completions. The run did not observe `input_required` and did not send `inputResponses`, so it does not say whether `@playwright/mcp` 0.0.83 can pause a tool call for a user answer.

## Tasks as `io.modelcontextprotocol/tasks`

The spec moves Tasks out of the core protocol and into the `io.modelcontextprotocol/tasks` extension. Long work is polled with `tasks/get`, and `tasks/update` carries mid-flight input.

This repo does not use that extension in P1. The repro loop generates a script, runs it, and revises until the retry cap, and the stop reason is recorded by the loop.

Open question: the spike recorded the initialize protocol version and the tool names. It did not record whether the server's capabilities advertise `io.modelcontextprotocol/tasks`, so there is no spike evidence for treating a killed server mid-run as a task handle.
