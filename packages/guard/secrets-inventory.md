# Argus secrets inventory

P7-T03. Names and places only: **no value is written in this file, in any other file, in a log or in a trace.** It extends the names-only list in [threat-model.md](threat-model.md) (section 2) with who can read each secret. Built from `render.yaml`, `.github/workflows/*.yml` and the `os.environ` reads in `packages/*/src`, on 2026-11-03.

"Who can read it" means who can see the value, not who can use it. The scopes the GitHub tokens actually have on GitHub were not checked here (the comments in `render.yaml` say what they should be). Anyone with the Render dashboard, or admin on the repository, can read or replace every secret in their store; with one owner that is accepted (threat model, ASI03).

## Secrets

| Secret | Where it lives | Used by | Who can read it |
|---|---|---|---|
| `GITHUB_WEBHOOK_SECRET` | Render env var (`render.yaml`, `sync: false`) | `flow.webhook`, the HMAC check | Owner (Render dashboard); the running Render service |
| `GITHUB_WRITE_TOKEN` | Render env var | `flow.github_write` (branch, draft PR, label, comment) | Owner; the Render service |
| `GITHUB_DISPATCH_TOKEN` | Render env var | `flow.actions` (dispatch, read run and artifact) | Owner; the Render service |
| `GITHUB_TOKEN` (the poller's, read only) | Render env var | `flow.github_read` | Owner; the Render service |
| `ARGUS_FLOW_DATABASE_URL` (the DB password is inside the URL) | Render env var | `flow.config`, `flow.db_wake` | Owner; the Render service; the Neon account holder |
| `ARGUS_MODEL_API_KEY` | GitHub Actions repository secret; reaches the runner only as the env of the step "Run the step in the sandbox" in `agent-job.yml` | `flow.agent_job` (all three steps get it, repro and fix use it) | Repository admins can replace it but not read it back; the step's process on the runner; never the sandbox container (no `-e`). Not masked by GitHub in a file the step writes, so it is redacted on the way out (below) |
| `ARGUS_PLATFORM_TOKEN` | GitHub Actions repository secret | The platform checkout step in `agent-job.yml` only (`persist-credentials: false`) | Same as above; the checkout step |
| `PLATFORM_REPO_TOKEN` | GitHub Actions repository secret | The platform checkout step in `golden.yml` (manual dispatch only) | Same as above; the checkout step |
| `GITHUB_TOKEN` (the Actions job token, read only by `permissions: contents: read`) | Issued by GitHub per job; `actions/checkout` keeps none (`persist-credentials: false` in `secret-scan.yml`) | `actions/checkout` | The job's steps; expires with the job |
| Provider keys for local runs (`MISTRAL_API_KEY`, `GROQ_API_KEY`) | The developer's local environment | The judge, the ablation, local fix runs | The owner's user account and any process it starts |
| Trace keys (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_EXPORTER_OTLP_TRACES_HEADERS`) | The developer's local environment; read by `argus_core.telemetry` only | The trace exporter (the Basic header is built from them and sent, never stored) | The owner's user account |

## Not secrets (listed so nobody hunts for them)

| Name | Where | Why it is not secret |
|---|---|---|
| `ARGUS_FLOW_QA_REVIEWERS` | Render env var | A list of GitHub logins. It is an authorization list, so only the owner should change it |
| `ARGUS_RUN_KEY`, `ARGUS_STEP`, `ARGUS_FLOW_REPO` | Workflow env, Render env | Identifiers |
| `FLOW_CI_PG_PASSWORD` | `flow.yml` | The password of a throwaway Postgres service in CI, named `flow-ci-throwaway-not-a-secret`; the container is destroyed with the job |

## Rules the code enforces

| Rule | Where | Test or check |
|---|---|---|
| A secret is an environment variable, never a file in the repo | Whole repo | `.github/workflows/check_no_secrets.py` fails on a token shape in any tracked file; run by `.github/workflows/secret-scan.yml` and by `packages/guard/tests/test_secret_scan.py` |
| A git remote URL has no user and no token | Developer checkouts and CI | The same script reads `git config remote.*.url` and `pushurl` and fails on a user or token before the host (user:token@host); `test_a_token_in_a_remote_url_is_flagged` |
| A secret does not reach a trajectory file | `argus_core.types.Trajectory.to_jsonl`, used by the fix loop, the repro agent and the eval replays | `packages/guard/tests/test_redact.py::test_trajectory_file_has_no_secret` |
| A secret does not reach a span | `argus_core.telemetry.RedactingExporter`, between the spans and every exporter | `packages/guard/tests/test_redact.py::test_spans_have_no_secret` |
| Only the named model secret appears in workflows | `check_no_secrets.py` (`MARKERS`, `ALLOWED`) | Run in `secret-scan.yml` |

What is masked (`argus_core.redact`, also `guard.redact`): the value of every environment variable whose name contains `KEY`, `TOKEN`, `SECRET`, `PASSWORD` or `CREDENTIAL` (value of six or more characters), and these shapes: GitHub `ghp_`, `gho_`, `ghu_`, `ghs_` (including `ghs_<APPID>_<JWT>`) and `ghr_`; `github_pat_`; `gsk_`; `sk-`; `Bearer <value>`; the user and token part of an http or https URL (user:token@host).

## Gaps

- The failure scrub in `flow.agent_job.scrub` is a separate copy of the same idea. It was not changed (outside this task). Its regex does not mask the `ghs_<APPID>_<JWT>` shape; see `docs/notes/p7-t03.md`.
- A success `output` (a patch) and the `argus-result` artifact are written as the step made them and are **not** redacted. The trajectory in the artifact is.
- Environment values shorter than six characters, and secrets in an unusual shape that are not in a secret-named variable, are not masked.
