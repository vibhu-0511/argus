# UI bug archetypes and difficulty tiers

Written for P0-T12. A seeded or mutated task stores one of these archetype ids and one tier in `meta.json`. `meta.archetype` stays an open string (ADR-001). These six are the values tasks use. The bug report's low, medium, and high severity is a different scale and does not set the tier.

An archetype is in scope only when the edit changes what one of the five flows paints, hit-tests, or computes as style. A change with no visual effect, a mutant that breaks the build, and a check that reads the clock stay out, as in `docs/notes/p0-bench-design.md`.

## Archetypes

Each id is the string stored in `meta.archetype`. The operators are the ones P0-T22 and P0-T23 implement. They are named here so a later mutant has one archetype. They are not implemented in this file.

| Id | What changes | Operators | Usual check |
|---|---|---|---|
| `font-size` | A length the surface paints or boxes: `font-size`, and the same kind of edit on `height`, `padding`, `gap`, or `line-height` | change a unit | `computed_style` of that property |
| `flex-direction` | A row lays out as a column, or the reverse | swap flex direction | `computed_style` of `flex-direction`, or a bounding box when the check cannot read the property |
| `overflow` | Content is clipped, or it spills out of its box | change `overflow` | bounding box, or pixel diff when the clip is the symptom |
| `z-index` | One painted thing covers another | change `z-index` | pixel diff of the covered region |
| `missing-style` | A class or a rule the surface depends on is gone, so paint or layout drops | remove a class, delete a CSS rule | `computed_style` of a property that rule set |
| `wrong-element` | The node is a different control than the surface expects | change an element, drop a prop | bounding box of the control |

`packages/bench/tasks/seeded/bug-17` is `font-size`. Its golden patch has six hunks in `apps/canvas/src/ops/radar.css`, and the check reads `font-size`. No other archetype has a task directory yet. BUG-13 (Radar connection card cut off; `overflow` hidden and a max height) and BUG-16 (admin list text cut with an ellipsis) are the same kind of bug as `overflow`. Their causes are in the bug report. They are not task directories.

## Tiers

The tier is read off the patch and the checks. It is not a guess about whether a model can fix the bug.

**easy.** All of these hold:

- The patch touches one file.
- The patch has one hunk, and that hunk is one selector or one JSX node.
- A check reads the property that hunk changes.
- That file is used by one of the five flows.

**medium.** The patch still touches one file, and any of these hold:

- More than one hunk, all of the same archetype. Bug 17 is medium for this reason.
- The check is a bounding box or a pixel diff, and it does not read the property the hunk changes.
- The file is a shared stylesheet used by more than one of the five flows, and the ticket names one flow.

**hard.** Any of these hold:

- The patch touches more than one file.
- The patch mixes two archetypes.
- The failure shows on one flow only because a second rule, in a second file, is what makes the edit visible.

P0-T13 uses these rules. It asks for ten tasks in each tier. It does not ask for an even split across the six archetypes.
