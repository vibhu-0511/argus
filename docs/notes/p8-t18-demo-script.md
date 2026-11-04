# P8-T18 Demo video: script, local rehearsal and recording checklist

Date: 2026-11-04. **Nothing was recorded. The box stays unticked.** The criterion "a video under 4 minutes is linked in the README; it shows a success, a verifier rejection and a quota refusal" needs you to record and publish a video, and the success scene needs the real install of P8-T16. What is here: a timed storyboard, two rehearsal scripts that reproduce the rejection and the quota refusal on this machine, their real output, and a checklist.

## What the video must show, and where each scene comes from

| Scene | Real or rehearsed | Source |
|---|---|---|
| 1 Success | **Real once P8-T16 is done** (issue, label, Actions run, PR). Today it can only be rehearsed: `rehearse.py good` runs repro and verify on the demo shop with a hand-fed patch | T16 owner steps; `packages/app/examples/demo-script/rehearse.py good` |
| 2 Verifier rejection | Rehearsed. A wrong patch (`bad.diff`) is handed to the verify step, which runs the tenant's start command, routes and tests and says no. Also `python -m verify ci` on a screenshot pair that the pixel check refuses | `rehearse.py bad`; `packages/verify/fixtures/ci/over` |
| 3 Quota refusal | Rehearsed with a fake model call. Shows the refusal happens before any request is sent | `packages/app/examples/demo-script/quota_refusal.py` |

Say so in the video. The patches in scene 2 are written by hand, not by a model, and the quota numbers in scene 3 are made up for the demo (the real limits are in `docs/quotas.md`). Put these as on-screen captions. Do not call a rehearsal a run.

## Storyboard (target 3:40, hard limit 4:00)

Terminal at the repo root of `argus`, font 18 or larger, one browser window with a clean profile. The running time is a plan; the command times below were measured once on this machine (`uv run` of the rehearsal about 15 s, so cut the wait in the edit).

| Time | On screen | Say (plain, short) |
|---|---|---|
| 0:00 to 0:20 | The README title of the Argus repo. Then the demo shop page `http://127.0.0.1:18770/cart` showing "2 items" for 2 mugs and 1 sticker pack | "Argus turns a labelled issue into a pull request. Here the cart says 2 items. It should say 3." |
| 0:20 to 0:50 | The demo repo's Issues page: the filed bug, then adding the label `argus` | "A person with write access adds one label. That starts one run in the repo's own Actions." (real, T16. If T16 is not done, skip this row and start the terminal at 0:20.) |
| 0:50 to 1:35 | **Scene 1.** Real: the Actions run with the steps Repro, Fix, Verify green, then the pull request (verdict row, judge row, links). Rehearsal: the terminal, `uv run --all-packages python packages/app/examples/demo-script/rehearse.py good` and the two result blocks (`repro` ends `exited 1`, `verify` ends `exited 0`) | "Repro sees the bug: the test fails. Fix makes a patch. Verify applies it on a fresh copy, starts the app, checks both pages and runs the tests. Green." |
| 1:35 to 2:35 | **Scene 2.** Terminal: `uv run --all-packages python packages/app/examples/demo-script/rehearse.py bad`. Show `bad.diff` (one line: `max(...)` instead of `sum(...)`), then the verify block: `exited 1`, the failing test and `2 items`. Then `uv run --all-packages python -m verify ci packages/verify/fixtures/ci/over; echo $?` (prints `1`) and open `before.png` and `after.png` of that folder; show `verdict.json` says `"ok": true` | "A plausible wrong fix. The model says it is fine; the verifier does not trust it. It runs the real tests and the badge still says 2. Rejected. And the screenshot check: the verdict file says ok, but too many pixels changed, so it refuses." |
| 2:35 to 2:55 | **Recovery.** Run `rehearse.py good` again (cut to the result) | "Same issue, a correct patch, the verifier says yes." (Rehearsal: say the patch is hand-fed. Do not claim the system retried by itself; no retry loop exists in P8.) |
| 2:55 to 3:25 | **Scene 3.** Terminal: `uv run --all-packages python packages/app/examples/demo-script/quota_refusal.py`. Show: tenant acme call 1 allowed, call 2 `REFUSED before sending`, "model requests sent so far" does not go up, tenant globex still allowed | "Each tenant has its own budget. Over the budget, the call is refused before it leaves, so one tenant cannot burn the shared free tier. Another tenant carries on." |
| 3:25 to 3:45 | The README limits section and the free-tier caveat | "Free-tier models, small budgets, one repo at a time. The links are below." |

## What runs today (checked 2026-11-04)

Run on this branch (`p8/owner-prep`, Windows 11, Git Bash, no network, no model).

**Success and rejection.** `uv run --all-packages python packages/app/examples/demo-script/rehearse.py good` exits 0 (16 s). The repro block: `routes answered: /, /cart`, the test command `exited 1`, and the failing test `test_badge_counts_items_not_lines` with `"id='cart-count'>3 items<" not found in "...2 items..."`. The verify block: `ok: true`, `exited 0`, `Ran 3 tests ... OK`.

`rehearse.py bad` exits 1 (14.5 s). Same repro block, then:

```
== patch handed to verify (bad.diff)
== verify: exit code 1
{ "ok": false, "output": "routes answered: /, /cart\ntest command `python -m unittest discover -s tests -p \"check_*.py\"` exited 1\nF..\n====...\nFAIL: test_badge_counts_items_not_lines ...\nAssertionError: \"id='cart-count'>3 items<\" not found in \"<h1>Cart <span class='badge' id='cart-count'>2 items</span>...\"\n...FAILED (failures=1)" }
```

The scripts copy the demo shop to a temp folder, commit it, hand over `good.diff` or `bad.diff` where the fix step would put its patch, and call `python -m argus_app.runner` for the steps `repro` and `verify` (the real runner code of P8-T06; only the fix step is replaced by the file). The temp folder is deleted at the end.

**Screenshot rejection.** `python -m verify ci packages/verify/fixtures/ci/match` exits 0; `.../over` exits 1 although its `verdict.json` is `{"ok": true}` (the changed-pixel ratio is over the 0.02 limit). The command prints nothing; show the exit code with `echo $?`. It does not call a model.

**Quota refusal.** `uv run --all-packages python packages/app/examples/demo-script/quota_refusal.py`:

- On this branch (no per-tenant budgets yet, they are P8-T07 on branch `p8/quota`) it shows the shared hard stop of P0-T07, exit 0:

  ```
  shared limit: 1 request a day
  call 1: call allowed (model requests sent so far: 1)
  call 2: REFUSED before sending: demo-model would exceed requests_per_day: 2 of 1 (model requests sent so far: 1)
  ```

  ("2 of 1" is what the ledger prints: the count this call would reach, and the cap.)

- With P8-T07 (run in a throwaway detached checkout of `p8/quota`, removed afterwards) the same file shows the tenant version, exit 0. **Use this one in the video**, after `p8/quota` is merged into `stack/p8-app`:

  ```
  per-tenant budget: 1 request a day each
  acme   call 1: call allowed (model requests sent so far: 1)
  acme   call 2: REFUSED before sending: tenant acme: demo-model would exceed tenant_requests_per_day: 2 of 1 (model requests sent so far: 1)
  globex call 1: call allowed (model requests sent so far: 2)
  ```

The tests behind both: `packages/argus-core/tests/test_ledger.py`, `packages/flow/tests/test_tenant_ledger.py` (on `p8/quota`).

## Not covered by any local fixture

- A refusal shown from a real run: the quota in scene 3 is a fake model call. Nothing in the running service builds tenant budgets yet (the T07 note says so), so there is no real tenant refusal to record until ADR-028 decides where budgets live.
- A rejection coming from a model's own wrong patch: the patches are hand-fed. If you want that, a real model run is needed (local Ollama `gemma4:e4b` only, per the P8 rules), and a good run may simply succeed.
- A rejected patch in the pull request body (verdict `failed_check`): `argus_app.pr` renders it (test `test_a_rejected_verdict_is_written_as_it_is`), but no running code opens that PR yet (see the gap in `p8-t16-owner-steps.md`).
- The success scene as a real run. Without T16 the video would show a rehearsal, and the task says "a success". Decide whether a rehearsed success is acceptable; I would not tick T18 on it.

## Recording checklist

Before:

- [ ] P8-T16 is done (real issue, label, run, PR), or you decided to show the rehearsal and say so on screen.
- [ ] `p8/quota` is merged so scene 3 shows the tenant refusal.
- [ ] Rehearse each command twice, from a clean shell, in the order of the table. No leftover process on port 18770 (`netstat -ano | findstr 18770`).
- [ ] Clean browser profile: no other tabs, no bookmarks bar, no extensions, notifications off. Close Slack, mail, the Windows notification area.
- [ ] No private names on screen: not `dcortex`, not the private repo, not account emails or billing pages. Check the terminal prompt, the window titles, the tab titles and the file explorer.
- [ ] No secret on screen: `ARGUS_MODEL_API_KEY`, the App private key, the webhook secret, tokens. Do not run `env`, do not open Render or GitHub secret pages, do not show `settings.json`. The Actions log masks secrets, but scroll past the "Set up job" block fast or crop it. Read the trajectory file before showing it (redact it with `argus_core.redact` first).
- [ ] Screen: 1920 by 1080, terminal font 18 or larger, dark or light theme with enough contrast, zoom the browser to 125 percent.
- [ ] Captions ready for: "patch written by hand, not by a model" (scene 2), "numbers made up for the demo" (scene 3), and the model name and number of model runs if any real run is shown.

During:

- [ ] Record the screen and the microphone in one take per scene; cut the 15 s waits of `uv run`.
- [ ] Say the free-tier caveat once (scene end).
- [ ] Do not claim anything that did not happen on screen (a retry, a model fix, a PR from a rejected patch).

After:

- [ ] Total length under 4:00 on the final file (check the file, not the plan).
- [ ] Captions or subtitles on; the audio is audible at low volume; no music with a licence problem.
- [ ] Upload (YouTube unlisted or public, or GitHub release asset); open the link in a private window to check it plays.
- [ ] Add the link to the README (P8-T17). Tick `P8-T18` in `TASKS.md` only when the video is under 4 minutes and shows a success, a verifier rejection and a quota refusal, as seen in the final file. Say in the README line which scenes are rehearsed.
