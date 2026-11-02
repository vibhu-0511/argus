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

1. search the token name (`--desk-bg`), path `.`. Hits are the light-theme override, which sets another value, and the places that read it with `var(--desk-bg)`. No rule sets the ticket's value.
2. read_file `apps/canvas/src/insights/desk.css`, the stylesheet that holds the override.
3. edit: add a base rule `.cid-desk { --<name>: <ticket value>; }` on the line just above the theme override rule, and keep the override as it is. Restore only the token the ticket names: the original base rule may have set more tokens, and nothing in the ticket says which, so do not guess them. Anchor `old` on rule text such as `html[data-theme="light"] .cid-desk {`, not on a comment.
4. submit.
