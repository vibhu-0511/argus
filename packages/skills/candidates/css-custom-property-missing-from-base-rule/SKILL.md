---
name: css-custom-property-missing-from-base-rule
description: "Use when a ticket says a CSS custom property (--name) on a selector changed from a stated value, and only a theme override such as html[data-theme=light] still sets it. The fix adds the base rule. Not for ordinary properties such as gap or font-size."
allowed-tools: search read_file edit submit
metadata:
  argus-status: "unreviewed"
  argus-archetype: "css-token-base-rule"
  argus-sources: "mut-0003"
---
Ticket form: "--<name> on .<selector> changed from <value>." The base rule that set the token is gone.

1. search the token name (`--desk-bg`), path `.`. Hits are the light-theme override, which sets another value, and the places that read it with `var(--desk-bg)`. No rule sets the ticket's value.
2. read_file the stylesheet that holds the override.
3. edit: add a base rule `.<selector> { --<name>: <ticket value>; }` on the line just above the theme override rule, and keep the override as it is. Anchor `old` on rule text such as `html[data-theme="light"] .cid-desk {`, not on a comment: a comment with a non-ASCII dash came back garbled and edit answered not-found.
4. submit.
