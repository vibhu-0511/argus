---
name: css-property-missing-from-grouped-rule
description: "Use when a ticket says a CSS property on a class changed from a stated value, and the class appears only inside a grouped selector list (a, b, c { ... }) whose declarations do not set that property. The fix adds a dedicated one-line rule. Not when the class has its own rule, and not when it has no rule at all."
allowed-tools: search read_file edit submit
metadata:
  argus-status: "unreviewed"
  argus-archetype: "css-grouped-rule-property"
  argus-sources: "mut-0006"
---
Ticket form: "<property> on .<class> changed from <value>." The class is in a grouped rule that no longer sets the property.

1. search `.<class>` under apps/canvas. The hit is a rule such as `.a, .b, .c, .d { background: ...; border: ...; }` that names the class but has no `<property>`. If the class has its own rule with another value, use css-value-changed-in-existing-rule. If there is no rule at all, use css-rule-missing-for-class.
2. read_file the stylesheet near the hit if you need the exact first characters of the grouped rule to anchor on.
3. edit: `old` is the start of the grouped rule; `new` is a dedicated line `.<class> { <property>: <ticket value>; }` followed by the same start of the grouped rule. Leave the grouped rule unchanged.
4. submit.
