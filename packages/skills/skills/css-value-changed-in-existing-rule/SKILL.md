---
name: css-value-changed-in-existing-rule
description: "Use when a ticket says a CSS property on a class (font-size, gap, height, margin-top, border-radius) changed from a stated value, and the stylesheet still has a rule for that class with a different value for that property. Not for a class with no rule, a property missing from the rule, an SVG animation or a CSS variable."
allowed-tools: search edit submit
metadata:
  argus-status: "reviewed"
  argus-archetype: "css-wrong-value"
  argus-sources: "mut-0190,mut-0195,mut-0201,mut-0206,mut-0212,mut-0217,mut-0223,mut-0228,mut-0234,mut-0239,mut-0245"
---
Ticket form: "<property> on .<class> changed from <value>." The ticket value is the one to restore.

1. search the selector with its leading dot under apps/canvas, for example `.ops-horizon-sub`. The hit is the rule, on one line.
2. Check that the line has the property the ticket names, with a value that is not the ticket's value. If search finds no rule for the class, or the rule has no such property, stop and use css-rule-missing-for-class or css-property-missing-from-grouped-rule instead.
3. edit: `old` is a stretch of that line that includes the wrong declaration plus enough neighbours to be unique (for example `.ops-leg-card { display: flex; flex-direction: column; gap: 6px;`). `new` is the same text with only that value replaced by the ticket's value. Leave every other declaration as it is.
4. submit. The search hit is enough; do not read the whole stylesheet.
