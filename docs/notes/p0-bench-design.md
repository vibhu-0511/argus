# P0 bench design notes

Read on 2026-10-29: [SWE-smith](https://arxiv.org/abs/2504.21798) and [SWE-bench Multimodal](https://arxiv.org/abs/2410.03859). This page is the design we take from them. It is not a result.

## What makes a task valid

SWE-bench keeps a task only when its fail-to-pass tests fail on the buggy tree and pass once the fix is applied, and its pass-to-pass tests stay green. SWE-smith inverts the collection order: set up one environment, synthesize a bug patch, and keep the patch only when it breaks at least one test that passed before. A patch that applies and changes source but breaks nothing is not a task. SWE-bench Multimodal uses the same fail-to-pass rule on JavaScript, then a person drops tasks that cannot be solved from the given statement.

Argus uses that rule with Playwright checks in place of unit tests. A task is valid only when `bench score` exits 1 on the buggy tree and 0 on the golden tree, the check list is non-empty, and the run is not an infra failure (exit 2). Exit 2 and anything in `bench/quarantine/` stay out of "attempted". For a mutation, the golden tree is the unmutated source. The same seed must produce the same patch, so the task set has a hash.

Two biases follow. A hand-seeded set looks like bugs a person would file, and it is too small and too shaped by what that person thought to write. A mutation set scales and is deterministic, and it is shaped by the operators: it over-represents class, flex, prop, element, and CSS edits, and under-represents bugs that span a flow of clicks. SWE-smith's procedural AST edits are the pattern for bugsmith. SWE-smith also writes issue text with a model. Bugsmith does not. A mutated task's ticket is a template that names the operator and the surface, so the one-shot baseline is not graded on invented prose.

## What makes a task flaky

SWE-bench Multimodal found tests that pass and fail on the same patch across repeated runs, and dropped them after ten validation runs. A flaky check does the same damage here. Resolve rate is resolved over attempted, with a Wilson interval. If a check flips, the same patch is resolved on one run and not on the next, and the interval describes the noise. `bench flake` runs each task's checks five times on the buggy tree and five times on the golden tree. A mixed result is quarantined. The likely UI causes are animation, font loading, and anything that reads the clock. Pixel diff is the check most exposed to that. A check that is valid once and flaky on the repeat is not a valid task.

## Which UI bugs are in scope

SWE-bench Multimodal is the reason the bench is visual and JavaScript: user-facing libraries, images in the statement or the tests, and JS, TS, HTML, and CSS. Argus is narrower than that dataset. The system under test is the dcortex Canvas in `config/platform.md`, on the five flows that do not need a flight seed: sign-in, the ops menu, the desk tabs, user admin, and the audit table.

In scope for P0: a bug that changes what those surfaces paint, hit-test, or compute as style. The operators are the ones in the phase: remove a class, swap flex direction, drop a prop, change an element, delete a CSS rule, change a unit, change z-index, change overflow. The checks are pixel diff, bounding box, and computed style. Those operators map onto the six archetype ids and the easy, medium, and hard rules in `docs/bug-archetypes.md`. Out of scope: a change with no visual effect, a mutant that breaks the build, legality and solve screens, and any write into platform tables. Those stay for later phases or for nobody.
