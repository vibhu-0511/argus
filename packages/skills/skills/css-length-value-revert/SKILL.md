---
name: css-length-value-revert
description: "Fixes a CSS length (px) on a named selector, such as height, gap, width, or padding, that a ticket says changed from its original value. Use when a ticket names a class and a sizing or spacing property that now has a different value."
allowed-tools: read_file list_dir search ast_grep edit submit
metadata:
  argus-status: "unreviewed"
  argus-archetype: "font-size"
  argus-sources: "mut-0239,mut-0245"
---
1. Use search on the directory the ticket points to (for example apps/canvas) for the class name from the ticket.
2. Use read_file on the stylesheet the search returns. Find every rule that targets that selector, including its pseudo-class variants.
3. Find the declaration the ticket names. Compare its current value with the value the ticket says it had before.
4. Use edit to set only that declaration back to the value the ticket gives. Leave the other declarations in the rule unchanged.
5. Use search again for the same selector to confirm one rule now carries the restored value.
6. Use submit.
