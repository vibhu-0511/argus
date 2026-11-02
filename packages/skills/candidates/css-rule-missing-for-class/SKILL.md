---
name: css-rule-missing-for-class
description: "Use when a ticket says a CSS property on a class changed from a stated value, but no stylesheet has a rule for that class any more: it appears only as a className in TSX. The fix adds one small rule. Not when a rule for the class exists, not for a class named inside a grouped selector list, not for SVG animation or CSS variables."
allowed-tools: search read_file edit submit
metadata:
  argus-status: "unreviewed"
  argus-archetype: "css-rule-deleted"
  argus-sources: "mut-0018,mut-0030,mut-0042,mut-0055"
---
Ticket form: "<property> on .<class> changed from <value>." The class is used in TSX but has no rule of its own.

1. search `.<class>` under apps/canvas, with the dot. Nothing found, or only longer class names that start with it (`.ops-show-chip` for `.ops-show`), means there is no rule of its own. If you find the rule with another value, use css-value-changed-in-existing-rule instead.
2. search the class without the dot. Hits only in `.tsx` files confirm the rule is gone. Do not search `platform/`, do not search for the old value, and do not use run_cmd (the sandbox has no git and its grep lacks `--include`): none of that found anything in the runs.
3. search the shared start of the class name (`ops-rules-`, `ops-logo`) to find the stylesheet and the sibling rules. read_file it when you need a line to anchor on.
4. edit: keep the closest sibling rule of the same family as it is, and add next to it one new line `.<class> { <property>: <ticket value>; }`. Declare only the property the ticket names. For `gap` also add `display: flex`, because gap does nothing without it.
5. submit.
