---
name: css-token-base-rule-desk
description: "Use when a ticket says a CSS custom property (--name) on the .cid-desk selector changed from a stated value, and only the html[data-theme=light] override still sets it. The fix adds the base rule. Not for ordinary properties such as gap or font-size."
allowed-tools: search read_file edit submit
metadata:
  argus-status: "reviewed"
  argus-archetype: "css-token-base-rule"
  argus-sources: "mut-0003"
---
Ticket form: "--<name> on .cid-desk changed from <value>." The base rule that set the token is gone.

1. read_file `apps/canvas/src/insights/desk.css` first. It is the one stylesheet that sets every `--desk-*` token, so go straight to it. Do not search for the token before you have read it: a repo-wide search for `--desk-bg` returns a long list of unrelated hits and wastes steps.
2. edit: add a base rule `.cid-desk { --<name>: <ticket value>; }` on the line just above the `html[data-theme="light"] .cid-desk {` override rule, and keep the override as it is. Restore only the token the ticket names: the original base rule may have set more tokens, and nothing in the ticket says which, so do not guess them.
3. submit.
