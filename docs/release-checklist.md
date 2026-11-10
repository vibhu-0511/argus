# Public release checklist (P8-T19)

Date: 2026-11-04. Branch `p8/readme-release`. **Result: 2 of 4 items done, 2 open. The `P8-T19` box stays unticked.** The task needs all four, including the licence, which is the owner's decision.

| # | Item | State | Evidence |
|---|---|---|---|
| 1 | Licence file present | **open** (owner decision) | No licence file in the repo. See 1 below |
| 2 | Secret scan green | **done** | `clean`, exit 0. See 2 below |
| 3 | No private data in fixtures | **open** for the wider `docs/` folder; **done** for the fixtures, examples and the files the public README links | See 3 below |
| 4 | Quota limits documented | **done** | `docs/quotas.md` and the Limits section of `docs/landing/README.md`. See 4 below |

## 1. Licence file: open

- Checked: no `LICENSE`, `LICENCE` or `COPYING` file at the repo root or tracked anywhere (`git ls-files` filtered by those names printed nothing), and no `license` field in `pyproject.toml` or in any `packages/*/pyproject.toml`.
- **The licence is the owner's decision. None was chosen and no `LICENSE` file was added.** Without one, others have no right to use or copy the code, even in a public repo.
- To close: the owner picks a licence, adds `LICENSE` at the root, and fills the "Licence" line of `docs/landing/README.md` (marked OWNER TO FILL).

## 2. Secret scan: done

Run the way `.github/workflows/guard.yml` runs it (step "Secret scan": `python3 .github/workflows/check_no_secrets.py`), from the repo root, after the change below. It scans every tracked text file for token shapes and credentialed URLs, the git remotes, and workflow files for model-secret names.

```
$ python .github/workflows/check_no_secrets.py
clean
exit=0
```

First run, before any change, failed with exit 1 and two hits:

```
packages/app/tests/test_config_intake.py:16: ghp_...
packages/app/tests/test_manifest.py:82: http...
```

Both are made-up values in P8 tests, not credentials: `ghp_fake-token-for-tests-not-real-0000` (a fake token the test passes to a mock) and `https://u:p@flow.example.test` (a URL with a user that the manifest loader must refuse). The scan was right to flag the shapes; the values are fake. The fix follows the existing pattern in the script: the two matched texts were added to `ALLOWED_MATCHES` in `.github/workflows/check_no_secrets.py`, matched by text and not by path, so a real token in the same files still fails. `packages/guard/tests/test_secret_scan.py` and `test_guard_ci.py`: 14 passed.

Not shown: this scan has not run on GitHub (`guard.yml` and `secret-scan.yml` have not run there). It checks tracked files only, not git history. Run it again just before the push. It does not look inside binary files.

## 3. No private data in fixtures: open for `docs/`, done for the rest

Method: a script listed tracked text files under the folders below and matched email addresses, the private platform repo name (`dcortex`), Windows or home paths, private IP ranges, internal host names, Render and Neon host names, and the owner's handle.

**Fixtures, examples and the files the public README links** (`packages/app/tests/fixtures`, `packages/app/examples`, `packages/app/docs`, `docs/landing`, `docs/onboarding.md`, `docs/quotas.md`): 26 files.

| Kind | Hits | Verdict |
|---|---|---|
| Private repo name | 1 at first: a comment in `packages/app/tests/fixtures/second-repo/.argus.yml` named the private platform ("dcortex monorepo") | **fixed**: the comment now says "a pnpm monorepo". 0 after |
| Email | 1: `demo@example.test` in `packages/app/examples/demo-script/rehearse.py` | fine: `.test` is a reserved name, made-up |
| Owner handle | 4: `vibhu-0511` in the five-line workflow (`docs/onboarding.md`, `packages/app/docs/tenant-workflow.yml`, the demo repo's `argus.yml`) and the README | not private: it is the path of the repo the tenant workflow calls. The owner must confirm the public repo really lives at `vibhu-0511/argus`, or change all four |
| Private hosts, private IPs, home paths, Render or Neon hosts | 0 | none |

The demo repo is made-up data (a shop with invented products), and the second-repo fixture holds a few lines of Python. Re-run after the fix: only the 4 handle hits and the 1 `example.test` email remain.

**The rest of `docs/` (149 files) is not clean, and whether it ships is the owner's decision.** Hits:

| Kind | Hits | Where |
|---|---|---|
| Private platform repo name `dcortex` | 68 matches in 22 files. The full repo path `dcortex-ai/dcortex-platform` is in 4 of them (`docs/notes/p6-t04.md`, `p7-t04-app-permissions.md`, `p8-t03-owner-steps.md`, `docs/architecture/p6.md`) | docs; also outside `docs/`: `config/platform.md`, `.github/workflows/agent-job.yml`, `golden.yml`, `packages/guard/threat-model.md`, `packages/target-app/README.md`, stored trajectories in `packages/fix-loop/runs` and `packages/eval/results`, a test in `packages/flow/tests` (not scanned for this item) |
| Owner's Windows user path `C:\Users\vibha` | 3 lines in `docs/notes/p2-conformance-fixes.md` and `docs/notes/p3-swarm-prompt.md` | docs |
| Render service name `argus-flow.onrender.com` | 3 lines (`docs/architecture/p6.md`, `docs/notes/p6-t12.md`, `docs/notes/p8-t02-owner-steps.md`) | a public hostname of the owner's own service |
| Neon host names | 3 lines in `p6-t11.md`, `p6-t14.md`: `aws.neon.tech`, `console.neon.tech`, a masked `ep-....neon.tech` | generic provider names, no endpoint |
| Docker Desktop names (`host.docker.internal` 10 matches, `192.168.65.x` 6 matches) | 16 matches | not private data: the default names of Docker Desktop |
| Placeholder database users such as `PW@127.0.0.1` | 6 matches | placeholders, loopback |
| Co-author lines `noreply@anthropic.com` | 5 matches | public address |
| False positives of the script | 11 matches: npm package versions such as `mcp@0.0.83` (8) and the file name `env.local` (3) | not addresses or hosts |

To close, the owner decides one of: (a) publish only the files the README links and keep `docs/notes` and `docs/architecture` private; (b) publish everything after replacing the platform repo name and the two home paths; (c) accept that the platform repo name is public. This was not done here, because it changes other phases' documents and the choice is the owner's. Also not checked: binary files (screenshots under `packages/*`), file history, and the stored trajectories.

## 4. Quota limits documented: done

- `docs/quotas.md` (checked 2026-10-29): Groq requests per day and tokens per minute from response headers, tokens per day and requests per minute from the published table and labelled "published only"; Mistral and hosted Gemma stated as not measured.
- `docs/landing/README.md`, section "Limits": the same numbers with how each was obtained, the fact that a tenant's own plan was not confirmed, the 30 minute run cut-off, one run per issue, and what is not measured.
- Checked: every number in the README's quota table equals the number in `docs/quotas.md` (1000, 8000, 200000, 30).

## Related, outside the four items

| Item | State |
|---|---|
| README blanks (App page, issue, PR, trace, video, licence) | open: 6 places marked OWNER TO FILL, see `docs/notes/p8-t17.md` |
| App registered, first real run on GitHub, install timed under 10 minutes | open: owner steps in `docs/notes/p8-t02-owner-steps.md`, `p8-t16-owner-steps.md` |
| ADR-024 to ADR-028 accepted | open: all are *proposed* until the owner approves them |
