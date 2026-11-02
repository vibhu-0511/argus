# skills

P5.5 skills for the fix loop: reviewed playbooks the agent can load on demand, and the tools that make, check and measure them.

**Status.** The skills are off by default (`run_fix(skills=None)`). On the 29 held-out tasks they showed no measurable gain and cost about 8% more tokens in (`docs/notes/p5.5-t08.md`, ADR-018). Turn them on only by passing the skills folder to `run_fix`.

## The 5 skills

In `skills/<name>/SKILL.md` (Agent Skills format, strict subset: `docs/notes/p5.5-t01-skills-spec.md`). Each is reviewed and pinned in `skills.lock.json` (review of 2026-11-02: `docs/notes/p5.5-t06.md`). The source runs are stored in `trajectories/`; the ids are in each skill's `argus-sources`.

| Skill | Archetype (what the first `search` shows) | Backed by (train runs) | Tools | Loaded in the 29 held-out runs |
|---|---|---|---|---|
| `css-value-changed-in-existing-rule` | `css-wrong-value`: the rule exists with another value | 11 (3 steps each) | search edit submit | 12 |
| `svg-transform-box-missing` | `svg-transform-box`: an animated SVG class has no `transform-box` rule | 3 | search read_file edit submit | 0 |
| `css-rule-missing-for-class` | `css-rule-deleted`: no stylesheet rule for the class, only a `className` in TSX | 4 (8 to 13 steps) | search read_file edit submit | 2 |
| `css-property-missing-from-grouped-rule` | `css-grouped-rule-property`: the class sits in a grouped rule without the property | **1** (thin) | search read_file edit submit | 0 |
| `css-custom-property-missing-from-base-rule` | `css-token-base-rule`: the base rule of a CSS variable is gone, only the theme override is left | **1** (thin) | search read_file edit submit | 0 |

All 20 source runs are train mutants of two generator labels (`font-size`, `missing-style`), all easy. The archetype ids above are the groups the review made from what the runs did, not the generator labels. The two thin skills rest on one run each; ADR-018 treats them as provisional. The first three skills cannot be told apart by ticket text alone (the selection test missed 3 of 10 tickets for that reason, `docs/notes/p5.5-t07.md`).

## What the loader does (`fix_loop.skills`, in `packages/fix-loop`)

1. **Read and check.** `load_skills(directory, lock)` reads each `<name>/SKILL.md` and returns `(loadable skills, refusals)`. A skill that fails a check is left out and logged as `skill refused: <name> (<reason>): <detail>`.
2. **Catalog (level 1).** `catalog` appends one line per loadable skill (name and description, nothing else) to the system message, with two lines telling the model to call `load_skill` when a ticket matches. No skill, no catalog, no tool: the prompt is the same bytes as before skills existed. In the test, 20 skills add 880 estimated tokens against 23,280 for their bodies.
3. **`load_skill` (level 2).** `load_skill {"name"}` returns the body, frontmatter stripped, as `<skill_content name="...">...</skill_content>`. `name` is an enum of the loadable names (`tool_spec`); any other name is `not-found`. A second call for the same name answers "already loaded". At most 3 skills load per run (`MAX_LOADED_SKILLS`); a fourth fails with a message. `loaded_names` reads the loads back from a stored trajectory, which is how "skills loaded per run" is counted.
4. **Refusals.** Checks run in this order and the first failure stops the skill:

   | Reason | When |
   |---|---|
   | `bad-frontmatter` | not UTF-8, no closing `---`, a repeated key, a field outside the six spec fields, a bad `name` (it must equal the directory), a `metadata` value that is not a string |
   | `too-large` | body over 8,000 characters (`MAX_BODY_CHARS`) |
   | `unreviewed` | no `reviewed: true` entry in `skills.lock.json` (a draft has none; the flag inside the file is never read) |
   | `not-pinned`, `hash-mismatch` | the entry has no valid `sha256`, or the file no longer hashes to it (CRLF read as LF; the hash covers the frontmatter) |
   | `tool-not-allowed` | `allowed-tools` names something outside `fix_loop.tools.ALLOW` (`Bash(curl:*)` is refused) |

   A missing or broken lock trusts nothing: every skill is `unreviewed` and the run goes on without skills. The lint adds `vague-description` and `stale-path` (below); the loader does not refuse on those.
5. **Allowlist at run time.** `tool_denied` runs before every tool call. While at least one skill is loaded the agent may call only the tools every loaded skill lists in `allowed-tools` (a skill with none gets `read_file list_dir search ast_grep`). `submit` and `load_skill` always pass. A skill narrows the tools and never widens them. A refused call is a `ToolError` `not-allowed` with a message starting `tool-not-allowed:`. The check is on tool names, not arguments, so it is not a sandbox (ADR-019).

## Commands

From the repo root. None makes a model call unless it says so.

```
uv run --package skills python -m skills.lint [--skills DIR] [--lock FILE] [--repo PLATFORM_CHECKOUT]
uv run --all-packages python -m skills.pin NAME --by WHO
uv run --all-packages python -m skills.split split|check
uv run --all-packages python -m skills.selection prompts OUT_DIR [--with-any]
uv run --all-packages python -m skills.selection score [ANSWERS_JSON]
uv run --all-packages python -m skills.draft --runs packages/skills/trajectories --dry-run
uv run --all-packages python -m skills.draft_claude prepare|finish --runs RUNS --work DIR
uv run --all-packages python -m skills.collect [--runs RUNS] [--out DIR]
uv run --all-packages python -m eval.skills_ablation packages/eval/results/t14/A packages/eval/results/t08/S
uv run --all-packages python -m pytest packages/skills/tests -q
```

- `skills.lint` is the CI check (`.github/workflows/skills-lint.yml`): the loader's own format and trust checks, plus extra files next to `SKILL.md`, a lock entry for a missing skill, `vague-description` (too short, no "not for" clause, or a catch-all phrase) and, with `--repo` or `ARGUS_PLATFORM_REPO`, `stale-path` (a backticked repo path that does not exist). Exit 1 on any problem.
- `skills.pin` is the owner's sign-off: it writes `reviewed: true`, who, the date and the SHA-256 to the lock, only if the loader would accept the skill. Any later edit to a skill needs a new pin.
- `skills.split` builds and checks `split.json`: held-out is the 30 seeded tasks (29 run), train is 40 mutants, and the check fails on a shared task id or a shared (file, operator) pair.
- `skills.collect` and `skills.draft` / `skills.draft_claude` make drafts from resolved train runs. Drafts are marked unreviewed and are not loadable until the owner reviews and pins them. The model calls (`draft` with a provider, `draft_claude` with subagents) are the only commands here that need a model.
- `skills.selection` builds and scores the catalog-only selection test (answers from a model are stored in `selection/answers.json`).

## Where things are

| Path | What |
|---|---|
| `skills/` | the 5 skills |
| `skills.lock.json` | the trust anchor: review flag and hash per skill |
| `split.json` | train and held-out ids |
| `trajectories/` | the 20 resolved train runs behind the skills, `ledger.json`, the T15 runs (`t15/`) |
| `draft-runs/p55-t05/` | the 7 draft prompts and replies, `ledger.json` |
| `selection/` | the 10 tickets and the stored answers |
| `break-its/t16/` | the recorded stale-skill runs |

Decisions: ADR-018 (format and distillation criteria), ADR-019 (trust model). Notes for each task: `docs/notes/p5.5-*.md`. Results of the with-vs-without run and the phase report: `docs/notes/p5.5-t17.md`.
