# P7 workflows on GitHub: the first real runs

Date: 2026-11-03. Commit `18de91e` (the head of `stack/p7-guard` when PR [#15](https://github.com/vibhu-0511/argus/pull/15) was opened). Each workflow ran twice, once for the push and once for the pull request, and every run succeeded. Source: `gh run list --branch stack/p7-guard` and the job logs.

## What ran

| Workflow | Run (push) | Run (pull request) | What the log shows |
|---|---|---|---|
| `secret-scan.yml` (job `scan`) | [41568774973](https://github.com/vibhu-0511/argus/actions/runs/41568774973) | [41568788877](https://github.com/vibhu-0511/argus/actions/runs/41568788877) | `python3 .github/workflows/check_no_secrets.py` printed `clean` |
| `egress.yml` (job `probe`) | [41568774763](https://github.com/vibhu-0511/argus/actions/runs/41568774763) | not triggered by a pull request | the sandbox could not reach the host over TCP, HTTPS or DNS; the control container could |
| `guard.yml` (job `guard`) | [41568774853](https://github.com/vibhu-0511/argus/actions/runs/41568774853) | [41568788853](https://github.com/vibhu-0511/argus/actions/runs/41568788853) | 14 of 14 escape probes passed; `guard verify-log` printed `OK 14 records` for the run's log and `OK 6 records` for the committed sample (checked against its head hash); the head hash went to the run summary |

## Excerpts from the job logs (copied, not re-run)

Egress probe, job `probe` of run 41568774763 (`guard.egress --context actions --control`):

```
"probe": "egress",
"context": "actions",
  "tcp": "connect-failed",
  "https": "connect-failed",
  "dns": "connect-failed"
"no_egress_held": true,
"control_results": { "tcp": "reached", "https": "reached", "dns": "reached" },
"control_saw_reached": true
```

Escape suite and log verification, job `guard` of run 41568774853:

```
14 probes: 14 pass, 0 fail, 0 error
OK 14 records, head cdba690f3e232605f39234e2e910372acb1cd9088219d3cac6a23e9df689bdcf
OK 6 records, head cbfd750d793c49e944e0ce8c91f39338282787d6360255db76bf240c864e4410
```

## What this closes and what it does not

- P7-T03 criterion 4 (CI secret scan is green): met by the `scan` job on both runs.
- P7-T05 (the same probe fails to reach an external host locally and on a GitHub Actions run): the local result is `packages/guard/results/egress-local.json`; the Actions result is the excerpt above (the uploaded artifact `egress-actions` was not downloaded; this note holds the lines from the log).
- P7-T17 (the workflow is green): met on both runs. That it fails when a probe escapes, a secret is planted or the log is edited is shown by the tests in `packages/guard/tests/test_guard_ci.py`, which ran locally only (no GitHub workflow runs the `guard` package tests); the workflow itself was not run with a planted failure on GitHub.
- Not shown: the escape suite on the gVisor and Firecracker tiers, and the App token against real GitHub. A hosted `ubuntu-latest` runner ran the Docker tier only.
- The control container "reached" the external host on the runner, so the probe is able to see a leak there.
