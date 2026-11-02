---
name: svg-transform-box-missing
description: "Use when a ticket says transform-box on a class changed from fill-box and the class is on an animated SVG element (a keyframes animation on a circle, path or rect). Not for other CSS properties."
allowed-tools: search read_file edit submit
metadata:
  argus-status: "unreviewed"
  argus-archetype: "svg-transform-box"
  argus-sources: "mut-0001,mut-0004,mut-0005"
---
Ticket form: "transform-box on .<class> changed from fill-box." The stylesheet no longer has a rule that sets it.

1. search the class name without the dot, path `.`. Hits are usually an `@keyframes` with the same name, a `prefers-reduced-motion` rule that lists the class, and the TSX that uses it.
2. read_file the stylesheet that holds the `@keyframes` and the neighbouring animation rules.
3. If it is not clear what the rule looked like, search `transform-box` in that stylesheet: a sibling rule such as `.ic-rise { transform-box: fill-box; transform-origin: bottom; animation: ... }` shows the form.
4. edit: add one new rule for the class on the line next to the sibling animation rule or the `@keyframes`. It sets `transform-box: fill-box`, a `transform-origin` (`center` for a rotate or pulse, `bottom` for a scaleY rise), and `animation:` naming the `@keyframes`, with timing copied from a neighbouring animation rule. Do not touch the reduced-motion rule.
5. submit.
