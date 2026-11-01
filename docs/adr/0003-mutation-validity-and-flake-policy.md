# ADR-003: Mutation validity and flake policy

Status: accepted (P0-T27).

## Context

Bugsmith can emit a patch that builds, a patch that does not, and a patch the checks cannot see. The scorer's exits are 0, 1, and 2, and a side that never scores is `None`. Those are different outcomes. A mutant kept on "non-zero" would mix a real check failure with a harness failure and with a build that never ran. A task whose repeats do not agree is a separate problem: later phases sample a set, and a check that flips cannot stay in that set. The policy has to say which mutant is kept, when a task is quarantined, and what "attempted" leaves out.

## Decision

`judge_mutant` keeps a mutant only on exit 1, then exit 0, with a non-empty check list. It returns the first match, in this order. An empty check list is `empty-checks`. A mutant exit of `None` is `build-break`. Exit 2 on either side is `infra`. A mutant exit of 0 is `no-observable-change`. An original exit of `None` is `build-break`. Mutant exit 1 and original exit 0 is `keep`. Every other pair is `not-fail-then-pass`.

`flake_all` is the flake threshold. `_RUNS` is 5, so the function scores the buggy tree five times and the golden tree five times. `_take` moves the task into `packages/bench/quarantine/` when the buggy codes are mixed, or the golden codes are mixed, or any of those codes is exit 2. `bench flake --all` calls `flake_all` with that default directory.

Exit 2 and any id in that quarantine directory are excluded from "attempted". The ablation sample is drawn after that exclusion.

`docs/notes/p0-t26.md` records the kept set from the run that applied this rule: seed 1, kept 300, task-set hash `6547a4dcab4fd9bf892d7ca46828ff0da4ef70ac8a5e4fa171809e88b5a6e023`.

## Alternatives

- Keep any non-zero mutant exit. Exit 2 is infra, and `None` means that side never scored. Both would be stored as if the checks had failed.
- Quarantine only when the five codes disagree. Five exit 2s are one value. `_take` still moves the task, because any exit 2 is enough.
- Retry a mixed run until the codes agree. The disagreement is the signal. The task moves to `packages/bench/quarantine/`.
- Draw the ablation sample from the kept 300, and apply quarantine afterward. An id that fails the five-and-five rule would already be in the sample.

## Consequences

P0-T26 wrote a task only when `judge_mutant` returned `keep`. The same seed is what makes the hash a name for that set: seed 1, 300 kept tasks, hash `6547a4dcab4fd9bf892d7ca46828ff0da4ef70ac8a5e4fa171809e88b5a6e023`. A task that lands in `packages/bench/quarantine/`, and any score of exit 2, stays out of "attempted". The ablation sample is taken after that exclusion.
