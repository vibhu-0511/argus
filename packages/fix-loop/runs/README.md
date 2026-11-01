# fix-loop runs

Raw per-task output. Each directory is one run id: `trajectory.jsonl` (the loop's own recorder), `answers.jsonl` (the model's replies), `diff.patch` (the worktree diff against the platform HEAD), `verdict.json`. `p3-a-claude-results.json` is the table below as data, derived from those directories.

Model for every run here: **Claude (a session as the model)**, driven through `python -m fix_loop.turn`. This is not the OpenAI-compatible endpoint path, not a Groq or Mistral run, and not comparable with one. It substitutes for the plan's Devstral row (see `docs/notes/p3-finish.md`). Token counts are chars/4 estimates of the messages, not provider usage. No latency was recorded.

## Variant A (no compaction), seeded set

Step cap 20. Token cap 400000 (estimated tokens in + out, summed over steps). A stop on `step-cap` or `token-cap` still scores the worktree diff and keeps its stop reason (ADR-008).

**Resolved 20/29, Wilson 95% `[0.507695, 0.827246]`.** The denominator is 29, not 30: `bug-17` is excluded (see below). By tier: easy 9/10 `[0.595844, 0.982124]`, medium 5/9 `[0.266647, 0.811225]`, hard 6/10 `[0.312670, 0.831822]`.

Stop reasons over the 29: submit 23, token-cap 5, step-cap 1. Of the 29, 18 were `submit` and resolved, 5 `submit` and unresolved, 4 `token-cap` and unresolved, 1 `token-cap` and resolved (seed-h06), 1 `step-cap` and resolved (seed-h05).

Estimated tokens per bug, mean over the 29: 202904 in, 205 out, 0 cached. Peak prompt: mean 37407, max 179383. Steps: mean 7.8, median 7.

| Task | Tier | Run id | Stop reason | Verdict | Steps | Est. tokens in | Est. tokens out | Peak prompt (est.) |
|---|---|---|---|---|---|---|---|---|
| bug-17 | medium | `p3-a-claude-bug-17` | none | excluded (setup error) | 0 | — | — | — |
| seed-e01 | easy | `p3-pilot-v3-seed-e01` | submit | resolved | 7 | 111997 | 167 | 21782 |
| seed-e02 | easy | `p3-a-claude-seed-e02` | submit | resolved | 7 | 54001 | 161 | 15997 |
| seed-e03 | easy | `p3-a-claude-seed-e03` | submit | resolved | 4 | 15480 | 104 | 5104 |
| seed-e04 | easy | `p3-a-claude-seed-e04` | submit | resolved | 4 | 19654 | 91 | 7574 |
| seed-e05 | easy | `p3-a-claude-seed-e05` | submit | unresolved | 9 | 299310 | 232 | 62319 |
| seed-e06 | easy | `p3-a-claude-seed-e06` | submit | resolved | 7 | 13504 | 133 | 4320 |
| seed-e07 | easy | `p3-a-claude-seed-e07` | submit | resolved | 9 | 375168 | 172 | 52417 |
| seed-e08 | easy | `p3-a-claude-seed-e08` | submit | resolved | 5 | 244323 | 119 | 61542 |
| seed-e09 | easy | `p3-a-claude-seed-e09` | submit | resolved | 4 | 21964 | 97 | 8346 |
| seed-e10 | easy | `p3-a-claude-seed-e10` | submit | resolved | 5 | 284765 | 128 | 72104 |
| seed-h01 | hard | `p3-pilot-v2-seed-h01` | token-cap | unresolved | 9 | 404864 | 221 | 56098 |
| seed-h02 | hard | `p3-a-claude-seed-h02` | token-cap | unresolved | 8 | 427388 | 185 | 61971 |
| seed-h03 | hard | `p3-a-claude-seed-h03` | submit | resolved | 6 | 66373 | 171 | 16270 |
| seed-h04 | hard | `p3-a-claude-seed-h04` | submit | unresolved | 17 | 225075 | 410 | 23494 |
| seed-h05 | hard | `p3-a-claude-seed-h05` | step-cap | resolved | 20 | 378377 | 648 | 31978 |
| seed-h06 | hard | `p3-a-claude-seed-h06` | token-cap | resolved | 8 | 443945 | 164 | 66905 |
| seed-h07 | hard | `p3-a-claude-seed-h07` | submit | unresolved | 8 | 106279 | 227 | 20560 |
| seed-h08 | hard | `p3-a-claude-seed-h08` | submit | resolved | 5 | 23724 | 159 | 5887 |
| seed-h09 | hard | `p3-a-claude-seed-h09` | submit | resolved | 5 | 30412 | 144 | 8428 |
| seed-h10 | hard | `p3-a-claude-seed-h10` | submit | resolved | 20 | 310009 | 640 | 28396 |
| seed-m01 | medium | `p3-pilot-v3-seed-m01` | token-cap | unresolved | 7 | 401271 | 169 | 71926 |
| seed-m02 | medium | `p3-a-claude-seed-m02` | submit | resolved | 10 | 242114 | 306 | 39026 |
| seed-m03 | medium | `p3-a-claude-seed-m03` | submit | resolved | 7 | 370841 | 193 | 62370 |
| seed-m04 | medium | `p3-a-claude-seed-m04` | submit | unresolved | 6 | 24902 | 188 | 5784 |
| seed-m05 | medium | `p3-a-claude-seed-m05` | token-cap | unresolved | 4 | 538752 | 67 | 179383 |
| seed-m06 | medium | `p3-a-claude-seed-m06` | submit | resolved | 6 | 14758 | 118 | 4116 |
| seed-m07 | medium | `p3-a-claude-seed-m07` | submit | unresolved | 7 | 70766 | 217 | 12021 |
| seed-m08 | medium | `p3-a-claude-seed-m08` | submit | resolved | 6 | 334380 | 164 | 70403 |
| seed-m09 | medium | `p3-a-claude-seed-m09` | submit | resolved | 5 | 29813 | 151 | 8286 |

Run versions. The three pilot tasks keep their pilot runs (`p3-pilot-v3-seed-e01`, `p3-pilot-v3-seed-m01`, `p3-pilot-v2-seed-h01`). The other 26 are `p3-a-claude-*`. The driver, caps and prompt are the same; the v2 h01 run scored through `uv run bench`, the later ones through the repo venv.

`BUG-17` (`bug-17`, `p3-a-claude-bug-17`): excluded before any model turn. `bug.patch` does not apply to platform HEAD `ac86acc` (`radar.css:70`), and `golden.patch` does not apply either; neither applies at any of the last 24 commits that touched `radar.css`. The file has drifted since the task was written. It is left out of the denominator, as `baseline.py` does for a setup error. `bench golden --all` cannot pass it either.

## Caveats

- Some subagents sent two `edit` answers at the same time against the "one at a time" rule (reported for seed-m03, m04, m08, m09, h08, h09, h10). Both lines were stored and replayed in file order, and the stored answers match the step counts for every run. The score reads the final tree, so the verdicts stand, but step order in those trajectories may differ from the order the model intended.
- Several subagents saw `failed: model response is not a tool call` after a `run_cmd` whose JSON held doubled backslashes. That is the loop's malformed-call path working as designed, and it counted as a step.
- `run_cmd` runs BusyBox `sh` and `grep` in the Alpine sandbox: no `grep --include`, and long `find` or `grep -r` commands hit the 30 s timeout.
- A Claude session keeps its own memory. These runs say nothing about how a stateless model would behave, and the context strategies could not be tested on it.

## Not valid, kept for the record

- `p3-pilot-v1-invalid/` (three runs, token cap 150000, all `token-cap`). The driver crashed on any non-ASCII observation (Windows stdout is cp1252) and the Bash tool cut long observations without saying so, so the model did not see what the loop sent. Fixed before v2.
- v2 runs for seed-e01 and seed-m01 were deleted with 0 answers: a concurrent edit to the root `pyproject.toml` added `packages/verify` (no `pyproject.toml`) as a workspace member, so every `uv run` failed. They were rerun as v3 through the repo venv. The v2 seed-h01 run lost no step to that error and is kept.
