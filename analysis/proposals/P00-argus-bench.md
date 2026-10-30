# P00-argus-bench

### DESIGN-009
- Severity: Med
- Section: P0-T24, P0-T27, P0-T29
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P0-T24 | Build mutation validity filter: keep only fail-before, pass-after mutants | [ME] | build | 4 | P0-T15, P0-T22, P0-T23 | Filter rejects a mutant with no visual change and a mutant that breaks the build; for kept mutants the scorer fails on the mutant and passes on the original |

| P0-T27 | Write ADR-003: Mutation validity and flake policy | [ME] | doc | 1 | P0-T26 | ADR states the validity rule, the flake threshold, and what happens to quarantined tasks |

| P0-T29 | Run ablation: seeded vs mutated bugs under the one-shot baseline | [ME] | eval | 2 | P0-T26, P0-T28 | Both rows of the Ablation table are filled from a real run, with Wilson 95% intervals; runs used the ledger and stayed under quota |
```

- Proposed text:

```
| P0-T24 | Build mutation validity filter: keep only fail-before, pass-after mutants | [ME] | build | 4 | P0-T15, P0-T22, P0-T23 | Filter rejects a mutant with no visual change and a mutant that breaks the build; a mutant is kept only on exit 1 on the mutant then exit 0 on the original, with a non-empty check list |

| P0-T27 | Write ADR-003: Mutation validity and flake policy | [ME] | doc | 1 | P0-T26 | ADR states the validity rule, the flake threshold, and that exit 2 and quarantined tasks are excluded from "attempted" |

| P0-T29 | Run ablation: seeded vs mutated bugs under the one-shot baseline | [ME] | eval | 2 | P0-T26, P0-T28 | Both rows of the Ablation table are filled from a real run, with Wilson 95% intervals; the mutated sample is drawn after quarantine; runs used the ledger and stayed under quota |
```

### EDGE-001
- Severity: Med
- Section: P0-T15
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P0-T15 | Build scorer CLI: run a task's checks against a tree and emit a JSON verdict | [ME] | build | 4 | P0-T10, P0-T11 | `bench score <task> --tree <path>` returns exit 0 on pass, 1 on fail, 2 on infra error; JSON verdict validates; no network access needed |
```

- Proposed text:

```
| P0-T15 | Build scorer CLI: run a task's checks against a tree and emit a JSON verdict | [ME] | build | 4 | P0-T10, P0-T11 | `bench score <task> --tree <path>` returns exit 0 on pass, 1 on fail, 2 on infra error; JSON verdict validates; no network access needed; `bench score` keeps the unsliced log |
```

### PLAN-010
- Severity: Low
- Section: P0-T12, P0-T13
- Owner: [PAIR] (P0-T12); [CLAUDE] (P0-T13)
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P0-T12 | Define 6 UI bug archetypes and 3 difficulty tiers | [PAIR] | doc | 1 | P0-T02 | `docs/bug-archetypes.md` lists archetypes and tier criteria; every later seeded task references one archetype |

| P0-T13 | Generate boilerplate for 30 seeded bug tasks | [CLAUDE] | build | 3 | P0-T10, P0-T11, P0-T12 | 30 task directories exist under `bench/tasks/seeded/`, all pass `bench validate`, 10 per tier |
```

- Proposed text:

```
| P0-T12 | Define 6 UI bug archetypes and 3 difficulty tiers | [PAIR] | doc | 1 | P0-T02 | `docs/bug-archetypes.md` lists archetypes and tier criteria |

| P0-T13 | Generate boilerplate for 30 seeded bug tasks | [CLAUDE] | build | 3 | P0-T10, P0-T11, P0-T12 | 30 task directories exist under `bench/tasks/seeded/`, all pass `bench validate`, 10 per tier, and each task references one archetype |
```

### PLAN-020
- Severity: Med
- Section: Done when, P0-T29
- Owner: [CLAUDE] (Done when, nearest task P0-T00); [ME] (P0-T29)
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
- The Ablation tables below are filled in by you from real runs, with the baseline row of the phase report included.

| P0-T29 | Run ablation: seeded vs mutated bugs under the one-shot baseline | [ME] | eval | 2 | P0-T26, P0-T28 | Both rows of the Ablation table are filled from a real run, with Wilson 95% intervals; runs used the ledger and stayed under quota |
```

- Proposed text:

```
- The Ablation tables below are filled in by you from real runs, with the baseline row of the phase report included. "Filled in" does not cover the $-equivalent cell, which stays "—" until P5-T11. This phase does not create `prices.json`.

| P0-T29 | Run ablation: seeded vs mutated bugs under the one-shot baseline | [ME] | eval | 2 | P0-T26, P0-T28 | Both rows of the Ablation table are filled from a real run, with Wilson 95% intervals, and the $-equivalent cell stays "—" until P5-T11; this task does not create `prices.json`; runs used the ledger and stayed under quota |
```

Hours and tasks in this file: unchanged.
