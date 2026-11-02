---
name: restore-missing-css-property
description: "Fixes a UI ticket where a CSS property on one class (for example transform-box, padding or gap) no longer matches the value the ticket names, because the rule was never set or was dropped. Use when a ticket says a style changed from an old value on a specific class."
allowed-tools: read_file list_dir search ast_grep edit submit
metadata:
  argus-status: "unreviewed"
  argus-archetype: "missing-style"
  argus-sources: "mut-0005,mut-0006,mut-0018"
---
1. Take the class or selector and the property named in the ticket.
2. Search the apps/canvas tree for the class name with search to find the stylesheet that defines it. Start with the component's own folder.
3. Read that stylesheet around the match. Check whether a rule with this exact selector sets the property.
4. Search the same file for the property name to see whether the property exists on other selectors. A grouped selector list such as `.a, .b, .c { ... }` often holds the shared value, and the reported class may have been left out of its own rule.
5. If the selector has no rule for the property, add a dedicated rule for it with the value the ticket names, using edit. Place it after the grouped rule so it applies to this selector alone.
6. If the property needs a display mode to take effect (gap needs flex or grid, for example), check the selector's display. Add the display value in the same rule if it is missing.
7. Keep the edit to the one stylesheet and the one selector. Do not rewrite other rules or rename classes.
8. Search for the selector again and confirm there is one rule that sets the property with the new value.
9. Call submit.
