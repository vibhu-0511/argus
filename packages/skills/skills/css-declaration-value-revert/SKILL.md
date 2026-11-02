---
name: css-declaration-value-revert
description: "Fixes a CSS property whose value was changed away from its original, such as a font-size or gap on a class rule. Use when a ticket reports a style property on a selector changed from a stated value."
allowed-tools: read_file list_dir search ast_grep edit submit
metadata:
  argus-status: "unreviewed"
  argus-archetype: "font-size"
  argus-sources: "mut-0190,mut-0195,mut-0201"
---
1. Search the app folder named in the ticket for the selector, for example `.ops-horizon-sub`, to find the CSS rule.
2. Read the file around the matching line with read_file.
3. Find the declaration for the property the ticket names, for example `font-size` or `gap`, and compare its current value with the original value the ticket states.
4. Use edit to change only that declaration's value back to the original. Leave the other declarations in the rule unchanged.
5. If the selector matches several rules, edit only the rule that holds the declaration the ticket names.
6. Read the edited rule again to confirm the value is restored and nothing else moved.
7. Call submit.
