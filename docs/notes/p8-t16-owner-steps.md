# P8-T16 Install the App on a public repo and run one issue: preparation and owner steps

Date: 2026-11-04. **Nothing real ran. The box stays unticked.** The criterion "a real issue produces a PR; the issue, PR and trace links are in the README; the repo is public and holds no private code" needs a registered App, an installation, a secret, a real Actions run and a model key. None of those were used. What exists is the folder to publish and the local checks that it is a valid tenant.

## What is built

| Item | Where |
|---|---|
| The demo repo, to be published as its own public repo | `packages/app/examples/demo-repo/` |
| Tenant config (start, test, two routes, small budget) | `.argus.yml` in that folder |
| Five-line caller of the reusable workflow | `.github/workflows/argus.yml` (same text as `packages/app/docs/tenant-workflow.yml`; a test compares them) |
| Issue template, label `bug` | `.github/ISSUE_TEMPLATE/bug.md` |
| The app and the seeded UI bug | `shopsite/` (stdlib server, two pages), `tests/check_cart.py` |
| Check that the folder is a valid tenant | `packages/app/tests/test_demo_repo.py` (6 tests) |

The bug: the cart badge shows "2 items" for two mugs and one sticker pack, and should say "3 items". `shopsite/pages.py` counts lines (`count = len(cart)`) instead of adding quantities. `tests/check_cart.py` fails on it and passes with the one-line fix. The folder is only made-up data in Python and plain text; the test refuses images, binaries and a few secret-looking words.

Checks that ran (local, no network, no model, no GitHub):

- The config loads with `argus_app.config.load_config`.
- The workflow file equals the five-line example.
- The unmodified folder fails the tests with `test_badge_counts_items_not_lines`; after the one-line fix they pass.
- `argus_app.runner` ran repro, fix (a fake fix agent that applies the one-line fix, no model) and verify on a git copy of the folder: repro saw `exited 1` and both routes answering, verify saw `exited 0`.

Proof: `uv run --all-packages python -m pytest packages/app/tests/test_demo_repo.py -q`.

## A gap you must know before the steps

Nothing in the running code carries a finished Actions run to a pull request. `argus_app.pr.open_or_update_pr` (T09) is tested but called by no production code, `flow.workflow.open_pr_step` still opens a generic PR without the verdict, and the P6 dispatch (`P6-T04`) is open. The reusable workflow ends by uploading the artifact `argus-result` (7 days) and does not push. So steps 1 to 7 below are expected to end with a green run and an artifact holding `patch.diff`, but **no PR will appear until a small piece of glue exists**: it downloads the artifact, reads the verify folder, mints a write token with `flow.installations.mint_for_repo(store, repo, "write")` and calls `open_or_update_pr(creator_client(token), ticket_id, patch, evidence, issue_title=...)`. That glue is not built and is not part of T09 or T04. Decide whether it is a new task (my suggestion) before you spend model quota on this. Also unresolved: where screenshots and the trajectory are stored so that the PR can link them; the Actions artifact is private and expires, and `argus_app.runner` makes no screenshots.

## Owner steps

Do the T02 and T03 owner steps first (`p8-t02-owner-steps.md`, `p8-t03-owner-steps.md`). You need the registered App, the Render service with the App id, key and webhook secret, and the demo repo selected in the installation.

1. **Create the public repo from the folder.** Copy it out of this repo so it has its own history:

   ```bash
   cp -r packages/app/examples/demo-repo ../argus-demo-shop && cd ../argus-demo-shop
   git init -b main && git add -A && git commit -m "Add the demo shop."
   gh repo create <owner>/argus-demo-shop --public --source . --push
   ```

   `.gitattributes` keeps the files LF. Pick a licence in the GitHub UI if you want one (not added here). Check on the repo page that it is public. Nothing in the folder is private; a test enforces a short word list, so look at the file list once yourself.

2. **Check the folder works as a repo.** In the new clone: `python -m unittest discover -s tests -p "check_*.py"` must **fail** on `test_badge_counts_items_not_lines` (that is the seeded bug), and `python -m shopsite 18770` then `curl -s http://127.0.0.1:18770/cart` must show `2 items`.

3. **Point the caller at a version that exists.** `.github/workflows/argus.yml` says `vibhu-0511/argus/.github/workflows/argus-reusable.yml@main`. A reusable workflow is only found on the ref you name, so `@main` works only after the Argus branch with `argus-reusable.yml` is on `main` of `vibhu-0511/argus`. Until then use the branch or commit that holds it. Is `vibhu-0511/argus` public? A workflow in a public repo can call a reusable workflow only from a public repo, or from an internal or private one that allows access; check this before step 6 (from memory, not verified).

4. **Install the App** on this repo: GitHub, the App page, **Install App**, your account, **Only select repositories**, `argus-demo-shop`. In the Render service, **Recent deliveries** of the App must show an `installation` event answered 202. Run the check of T03 step 5 for this repo (`200` for the demo repo, and the tenant id printed).

5. **Set the tenant secret.** Demo repo, Settings, Secrets and variables, Actions, new repository secret `ARGUS_MODEL_API_KEY` = your own key. The model is the free-tier model the workflow expects (Groq per the workflow input text). Enter it in the browser or with `gh secret set ARGUS_MODEL_API_KEY` (it asks for the value); never in chat, a file or a command line.

6. **Create the labels.** `gh label create argus --repo <owner>/argus-demo-shop` (the `bug` label already exists by default). The intake label is `argus` (`ARGUS_INTAKE_LABEL` on the service, `argus` in the workflow's `if`).

7. **File the issue** from the template (Issues, New issue, Bug report), or:

   ```bash
   gh issue create --repo <owner>/argus-demo-shop --label bug --title "[bug] Cart badge says 2 items for 3 items" \
     --body "Page: /cart. I see: the badge says 2 items. I expected: 3 items (2 mugs and 1 sticker pack)."
   ```

   Then **add the label** `argus` (that is the trigger; a template does not add it on purpose, so nothing runs before you are ready): `gh issue edit <n> --repo <owner>/argus-demo-shop --add-label argus`. The person who adds the label must have write access (T08 ignores others).

8. **Watch the run.** Actions tab, workflow `argus`, run named `argus <owner>/argus-demo-shop#<n>`. Expected steps: two checkouts, `uv sync`, Repro (the baseline: routes answer, tests exit 1), the sandbox image build, Fix (the model; the only step with the key), Verify (`exited 0`), artifact upload. Read the log; `gh run view <id> --log`. A failure here is real data: copy the error into this note, do not tick.

9. **Where the links come from** (fill the README table of the demo repo only with what you see):
   - Issue: the issue page URL.
   - Pull request: the Pull requests tab. Title `Argus fix for <owner>/argus-demo-shop#<n>`, branch `argus/<slug>-<hash>` (`flow.states.branch_name`). Only after the glue described above exists.
   - Trace: `trajectory.jsonl` inside the artifact `argus-result` (`gh run download <id> -n argus-result`). It expires after 7 days and is private, so for a README link publish a copy: run it through `argus_core.redact` first, then commit it to the demo repo (for example `trace/issue-<n>.jsonl`) and link that file. Read the file before you publish it.

10. **Tick.** Tick `P8-T16` in `TASKS.md` only when all three links in the README are real, the PR was produced from the issue by the system (not by hand), and the repo is public. Record the date, the run URL and the model name and run count here and in `docs/architecture/p8.md`.

## Not done or not verified

- The App was not installed, no secret was set, no label was added, no Actions run happened, no model was called, no PR exists, and no link was created. The README table in the demo folder says "(not run yet)" in every cell.
- The reusable workflow has never run on GitHub (`p8-t04-owner-steps.md`); the fix step's real model wiring has never run.
- Whether a free-tier model can fix this bug in the 60000-token, 12-step budget is unknown. If it cannot, that is a result: report it, and change the budget or the bug in the open.
- Port 18770 and the Python version on the runner (the workflow sets up 3.12 through `uv`; the tenant `start` and `test` commands use the runner's `python`) are not verified on a real runner.
- Whether a public repo can call this reusable workflow depends on the visibility of `vibhu-0511/argus`; not checked.
