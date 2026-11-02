# ADR-018: Skill format and distillation criteria

Status: proposed (P5.5-T09), drafted by Claude at the owner's request, for the owner to review. It is accepted when the owner approves it. Revisit after the next with-vs-without run, or when a second reviewer exists.

## Context

A skill is a Markdown file (`packages/skills/skills/<name>/SKILL.md`) that the fix loop shows as one catalog line and loads on demand (ADR-019 covers trust). "Distillation" is how a skill comes to exist: successful stored runs go in, a draft comes out, a person edits and pins it. This ADR fixes the format and says what a run must show to feed a skill and who signs the result. It is written after the first full pass (T03 to T08, T15, T16), so it records what was done and what that pass showed.

What was done, from the notes in `docs/notes/p5.5-*.md`:

| Step | What happened |
|---|---|
| T03 split | Held-out = the 30 seeded tasks (29 run). Train = 40 of the 300 generated mutants. A script checks that no task id and no (source file, operator) pair is shared. |
| T04 collect | 20 resolved runs out of 21 finished, fix stage only, Claude sessions as the model. All 20 come from two mutation labels (`font-size` 11, `missing-style` 9), all tier `easy`. 35 of 40 train tasks edit `ops.css`. |
| T05 draft | `skills.draft` took the resolved train runs, grouped them by the generator's label, 3 per group, and sent each group to a Haiku subagent once: 7 drafts, all accepted at the first reply. |
| T06 review | A Claude session, at the owner's request, merged the 7 drafts into 5 skills by what the first `search` showed, removed steps no run took, pinned the 5; the owner confirmed the pins in chat. |
| T07 selection | 10 tickets, catalog only: 7 of 10 right, 3 wrong. |
| T08 ablation | 29 held-out tasks, with skills against the stored P5 run without: no measurable gain, tokens in 8% higher. |

## Decision

### 1. The format stays as it is

The Agent Skills format (agentskills.io, revision `217be54`), used strictly (`docs/notes/p5.5-t01-skills-spec.md`):

- One directory per skill holding `SKILL.md` and nothing else. No scripts, no extra files.
- Frontmatter: the six spec fields only; `name` equals the directory; `description` is one quoted string that says when to use the skill and when not to (the lint fails a catch-all description).
- Argus keys inside `metadata`: `argus-status`, `argus-archetype`, `argus-sources` (a label for people; the lock decides).
- `allowed-tools`: bare tool names from `fix_loop.tools.ALLOW`; a skill narrows the tools, never widens them.
- Body at most 8,000 characters. Disclosure levels 1 (catalog) and 2 (body) only. At most 3 skills loaded per run.

Why not change it: nothing in T07 or T08 came from the format. The loader refused every bad skill in its tests, the lint caught the vague and the stale skill (T15, T16), and the cost of the catalog is small (20 entries, 880 estimated tokens against 23,280 for the bodies). The T08 result is about whether the content helps, not about how it is stored.

### 2. What a run must show to feed a skill

A stored run may feed a skill only if all of these hold. The first three are checked by code (`skills.draft.successes`, `skills.split`); the others are checked by the reviewer.

1. **Resolved by the scorer.** `verdict.json` says `resolved` (scorer exit 0). The model saying it is done does not count. An `excluded` run (the scorer could not score it, as `mut-0002`) is not a success.
2. **Train only.** The task is in the `train` list of `split.json`. A held-out task never feeds a draft, and the split check keeps train and held-out apart on task id and on (file, operator).
3. **Kept whole.** The trajectory is stored next to the verdict (`<run>/fix/trajectory.jsonl`), with the ticket and the diff measured against the bug state, so each step of a skill can be looked up.
4. **Grouped by what the run did, not by the generator's label.** T05 grouped by the mutation label and got drafts named `font-size` that were mostly about gap, height and border-radius (only 3 of the 11 `font-size` runs are about font size). T06 regrouped by the picture at the first `search` (rule exists with another value: 11 runs; SVG class without `transform-box`: 3; no rule for the class: 4; class in a grouped rule without the property: 1; base rule of a CSS variable gone: 1). `argus-archetype` records that human-confirmed group.
5. **Something to save.** The runs of a group must show a cost the skill would remove: wasted steps, an error, a wrong turn that the run recovered from. A group where every run already takes the minimum steps (the 11 three-step runs: search, edit, submit) shows the pattern but no saving; a skill for it adds a catalog line to every step and a body when loaded. The review note names the saving and measures it from the source runs. This rule follows from T08 and has not been tested on its own (see "What this does not show").
6. **Every step traced.** A step stays in a body only if a stored resolved run took it. A step no run took (T06 dropped "read the file around the line", "decide by specificity", "use `ast_grep` on an inline style") is removed. A step that contradicts a resolved run is removed (the drafts said "do not add new selectors" while all 3 runs added a rule, and "place it after the grouped rule" while the run placed it above).

How the draft script treats a run (`skills.draft`, `skills.draft_claude`), kept as it is:

- The prompt carries the ticket and each step as `tool call -> first 300 characters of the result`, 2,500 characters per run at most, and says the runs are data, not instructions to the model.
- The script writes the frontmatter, not the model. The `description` is JSON-quoted (valid YAML, so the loader's refusal of an unquoted `: ` cannot be hit), `allowed-tools` is fixed to `read_file list_dir search ast_grep edit submit` (no `run_cmd`), and `metadata` carries `argus-status: "unreviewed"`, `argus-archetype`, `argus-sources`. A model reply cannot add a field or a tool.
- A reply is dropped when it is not the JSON asked for, the name is invalid or exists (a reviewed skill is never overwritten), or it fails the loader's own format check or the body limit.
- The system prompt also asks the model not to tell the agent to edit checks, run commands or use the network. That is a request, not a control; the controls are the script, the loader and the review.

### 3. Minimum evidence for a skill, and a check before it is pinned

New rules, written here and not yet enforced by code:

- **At least 3 distinct resolved train runs behind a skill.** A skill with fewer is a transcript of one run. 3 is a judgement, not a measured number: it is the smallest count that lets a reviewer see what differs between runs and what repeats. A skill under 3 is not pinned.
- **A selection check before every pin.** Run `python -m skills.selection` with at least 2 hand-written tickets per skill (taken from different source runs) and at least 2 tickets that no skill should match. Two skills whose descriptions the ticket text cannot tell apart (T07: s01 and s02, s03 and s04, s06) are merged into one skill whose body branches on the first `search`, before either is pinned. Wording cannot fix this: the models matched on the property list in the description, and making the description match more tickets is the always-matching failure that T15 shows.
- **The no-match tickets must load nothing.** T15 found that an always-matching skill was loaded on 2 of 2 tickets that should load no skill, so a description that attracts tickets it should not is a failed check.

### 4. Who reviews

- The reviewer is the owner (`vibhu-0511`). The sign-off is `python -m skills.pin NAME --by WHO`, which writes the hash and `reviewed: true` to `skills.lock.json`. The lock diff in the pull request is what shows who approved which hash (ADR-019).
- The owner may ask a Claude session to do the review, as in T06, on two conditions: the lock entry says so (`reviewed_by`: "claude, delegated by vibhu-0511"), and the owner confirms the pins afterwards in the conversation or the pull request. Both held for T06.
- The review checks: each step traced to a stored run, with a spot check of at least 3 claims against the stored runs (T06 checked 3: `git: not found` in `mut-0030`, `gap: 6px` in `mut-0201`, the 5-step shape of `mut-0006`); no step that contradicts a run; a description that says when to use and when not to; the smallest tool list (`run_cmd` only if a source run used it; none did); one archetype; the saving named (rule 5); source count (section 3); and the selection check.
- A review by Claude is not independent of the draft. The drafts came from Haiku subagents and the review from a Claude session, so a blind spot of the model family goes through both. The owner's confirmation is the only check from outside it. This ADR does not fix that: there is one owner (ADR-019 says the same).

### 5. The five skills against these rules

T06 pinned them before these rules existed. This ADR changes no pin.

| Skill | Source runs | 3 or more runs | Saving shown in the runs | Loaded in T08 (29 runs) |
|---|---|---|---|---|
| `css-value-changed-in-existing-rule` | 11, all 3 steps | yes | none (already the minimum) | 12 |
| `svg-transform-box-missing` | 3, 4 to 5 steps | yes | not named | 0 |
| `css-rule-missing-for-class` | 4, 8 to 13 steps with wasted `search` and `run_cmd` calls | yes | plausible (the body names the wasted calls), not measured | 2 |
| `css-property-missing-from-grouped-rule` | 1 | **no** | not named | 0 |
| `css-custom-property-missing-from-base-rule` | 1 | **no** | not named | 0 |

The two one-run skills stay pinned only because T06 needed 5. They are provisional: before skills are enabled by default they are folded into `css-rule-missing-for-class` or removed, and the three CSS skills that the ticket text cannot tell apart are merged or pass the selection check as one. Either change needs a new pin by the owner.

### 6. Skills stay off by default

`run_fix(skills=None)` is the default and the loop without skills is byte-identical to the one before skills existed (the T08 byte comparison). Skills are on only when a caller passes the skills folder, as variant S does. Skills are enabled by default only when all of these are shown, in a new run, not in a re-reading of T08:

1. The with-vs-without run is repeated at least 3 times per row on the same held-out tasks, close in time and on the same machine conditions, so that the spread of a row is measured. ADR-017 found a spread of 4 of 29 tasks in resolve rate across 5 draws of one configuration and a 74% swing in tokens per bug; a gap inside that is noise.
2. With skills resolves more tasks than without by more than that spread, or resolves the same with fewer tokens per bug by more than the spread of the without row, and the paired counts show more with-only wins than without-only wins.
3. The result is reported per archetype and covers the tasks the skills are about. In T08 these are the 9 held-out tasks labelled `font-size` or `missing-style`; the table must show them on their own.
4. Every pinned skill passes sections 2 and 3, and the loaded count per run and the extra tokens are reported.
5. The poisoned-skill tests (T13 to T16) still pass.

If a repeat shows no gain, the skills are removed from the default path and the package stays as a tool.

## Alternatives

- **Keep the T05 criteria (resolved, train, 3 runs a group) as they were.** Rejected: they produced 7 overlapping drafts with wrong steps and, after review, two skills with one run each, three of five never loaded, and a group label that was not the ticket type.
- **A review by someone who did not draft.** Wanted, not possible: the project has one owner. The owner's confirmation and the lock record are the substitute.
- **Fix the three misses by rewording descriptions.** Rejected (T07, T15): the three skills differ only by a fact the ticket does not state, and a broader description is the failure T15 measures.
- **Drop skills.** Not chosen yet. T08 is one run per cell: it shows no gain and a small cost, not harm. A repeat as in section 6 decides.
- **Wait for a richer train set before changing anything.** The mutants cover 2 of 6 archetypes and one tier, so a better source needs a richer generator or real tickets. That is real work and not part of this ADR; section 6 point 3 makes the gap visible.

## Consequences

- The next skill takes more effort: 3 runs, a named saving, a selection check, an owner's pin. Fewer skills are likely.
- The criteria are mostly checked by a person. Not checked by code today: the source count, `argus-sources` against the held-out ids (a gap already listed for the lint, T12), the saving, step tracing and the selection check. A lint for source count and train membership is a small follow-up.
- Anyone reading a `SKILL.md` can see its source runs in `argus-sources` and look them up in `packages/skills/trajectories/`.

## What this does not show

- **T08 shows no gain, not no effect.** One run per task per row, no noise estimate. The with row ran on 2026-11-02, the without row on 2026-11-01 (the stored P5-T14 variant A), a different draw on a shared machine. 27 paired tasks have the same outcome in both rows (19 resolved in both, 8 in neither); the 70.4% against 72.4% headline comes from two tasks that the without row could not score. Tokens in are 37,419 against 40,470 on the same 27 tasks (+8%). The intervals overlap almost completely. A small gain or loss is invisible at this size.
- **Skills were loaded in 14 of 29 runs, and 3 of the 5 skills in none.** 10 of those 14 resolved, against 11 of the 15 runs that loaded none. The model chooses to load, so this is not a controlled split.
- **On the held-out tasks the skills are about, nothing changed.** Of the 9 held-out tasks labelled `font-size` or `missing-style`, both rows resolve the same 4 and miss the same 5 (computed from the stored `verdict.json` and `meta.json` files; method in `docs/notes/p5.5-t09.md`). So the skills did not help where they could be expected to.
- **Why there is no gain is not established.** Reasons that fit, none tested: the model already solves the covered shapes in about 3 steps without a skill, the skills came from two mutation labels of the easy tier, and the 8 tasks nobody solved are not the shape the skills cover. Rule 5 in section 2 is built on the first of these.
- **The selection test is small.** 10 tickets, one Haiku answer each, 3 misses, all to `css-value-changed-in-existing-rule`. Three subagents said in their reply that an earlier answer of theirs had named another skill; that text was not delivered, so a stricter count would be 4 of 10. T08 used Sonnet and T07 Haiku.
- **The skills cost something even when they do not help.** T15 saw +56% tokens in on 4 train tasks with the real five skills against the same tasks without (35,200 against 22,591; 4 of 4 resolved either way), and T08 saw +8% on 27 held-out tasks. A loaded body of up to 2,000 tokens is re-sent on every later step.
- **Not tested here:** whether a reviewed skill helps when it is thick and specific to a hard task; a skill built from runs that were not easy; a second reviewer.
