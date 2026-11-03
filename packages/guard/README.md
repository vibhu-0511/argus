# guard

P7: the threat model for the Argus pipeline, the hardening built around it, and the tests that try to break it.

**Status, in one paragraph.** Everything below was built and run **locally** on one Windows 11 machine with Docker Desktop. **Nothing has run on GitHub Actions** (the branch was not pushed), there is **no GitHub App**, **no gVisor run** (no `runsc` here) and **no Firecracker run** (no `/dev/kvm` here). The red-team ran on a small local model only. Read the "State" column; it is the honest one.

Run everything from the repo root. `guard <sub-command>` is the console script; on a machine that blocks it (the owner's Windows one does), use `uv run --all-packages python -m guard <sub-command>`, which is the same code.

## The controls

State words: **tested locally** = there is a test or a stored result from a run on this machine. **never run on GitHub** = the workflow or step is written, nothing on GitHub has run it. **not run** = it was not run at all, anywhere.

| Control | What it does | File or command | State |
|---|---|---|---|
| Threat model | Assets, trust boundaries, data-flow diagram, ASI01 to ASI10 rows, injection paths, gaps | [`threat-model.md`](threat-model.md), ADR-024 | Written by Claude, owner has not read it |
| Secrets inventory | Each secret, where it lives, who can read it (names only) | [`secrets-inventory.md`](secrets-inventory.md), ADR-026 | Written |
| Redaction | Masks secret-named env values and token shapes in trajectories and spans | `argus_core.redact`, `Trajectory.to_jsonl`, `RedactingExporter`; `tests/test_redact.py` | Tested locally |
| Secret scan | Fails on a token in a tracked file or in a git remote URL | `python .github/workflows/check_no_secrets.py`; `.github/workflows/secret-scan.yml` | Tested locally (prints `clean`); workflow never run on GitHub |
| App token | Least-privilege, one-hour installation token, one repository, refuses anything above the list | `packages/flow/src/flow/app_token.py`; ADR-026 | Tested locally on a **mock** GitHub only. The App does not exist, the minter is not wired into the clients |
| No-egress probe | TCP, HTTPS and DNS from the sandbox; a control run with the network on | `uv run --all-packages python -m guard.egress --context local --control --out FILE`; `.github/workflows/egress.yml` | Local result stored (`results/egress-local.json`); workflow never run on GitHub, so no `egress-actions.json` exists |
| Escape suite | 14 probes, each expects "blocked" | `guard escape --tier docker` | Docker tier tested locally. **gVisor and Firecracker: not run** (see below) |
| Audit log | Append-only, hash-chained records; `verify-log` names the first bad line | `guard verify-log FILE [--head HASH]`; `src/guard/auditlog.py` | Tested locally. Not wired into the fix loop's own tool calls (only the escape suite and egress probe write to it) |
| Guard CI job | Escape suite, secret scan and log verification, no model, no secret; writes the log head hash to the run summary | `.github/workflows/guard.yml`; `python -m guard` | Same commands passed locally; each failure mode turned a command red. **Never run on GitHub** |
| Red-team | 3 static injection cases (ticket, repo file, skill), deterministic checks, no LLM rubric | `redteam/` (promptfoo 0.125.1 through `npx`), `guard redteam` | Run locally on `gemma4:e4b` only: 15 runs baseline, 15 hardened. Not on the production model |
| Mitigations | Data and instruction separation, tool allowlist, output filter | `run_fix(harden=True)` in `fix-loop`; `fix-loop/tests/test_harden.py` | Tested locally. **Off by default; no caller turns it on** |
| gVisor runner | Runs the fixture under `runsc` | `guard sandbox-run --runtime runsc`; `.github/workflows/gvisor.yml` | **Not run.** Prints "not available" and exits 3; workflow never run |
| Firecracker runner | Boots a microVM and runs the fixture | `guard firecracker-run`; `.github/workflows/firecracker.yml` | **Not run.** No KVM here; no microVM ever booted; workflow never run |
| Ablation | Cold start and escape probes per tier | `guard ablation --tier docker\|gvisor\|firecracker` | Docker (row A) run locally. **gVisor (B) and Firecracker (C) not run** |
| Break-its | T18 environment dump, T19 edited log, T21 DNS exfiltration | `tests/test_break_envdump.py`, `test_break_auditlog.py`, `test_dns_exfil.py`; write-ups in `docs/notes/p7-break-its.md`, `p7-t21.md` | Tested locally |
| Break-it T20 | Use the App token to push to the default branch | `packages/flow/tests/test_break_app_push.py` | **Mock only.** GitHub's real refusal was not seen; box unticked |

ADRs: [024 threat model and trust boundaries](../../docs/adr/0024-threat-model-and-trust-boundaries.md), [025 sandbox tier selection](../../docs/adr/0025-sandbox-tier-selection.md), [026 secrets handling and token scopes](../../docs/adr/0026-secrets-handling-and-token-scopes.md). All three are `proposed`: the owner decides.

## How to run

Needs `uv` and Python 3.12. Docker is needed for the escape suite, the egress probe, the ablation and some tests.

```bash
uv sync --all-packages --locked
```

### Escape suite

```bash
uv run --all-packages python -m guard escape --tier docker
```

It builds the fix-loop sandbox image on first use, runs 14 probes in containers with the fix-loop flags (plus `--pids-limit 128`) and prints `PASS` or `FAIL` per probe, then a count. Exit 0 only if every probe was blocked; 1 if a probe escaped or gave no verdict; 3 if the tier cannot run. A probe passes only when it prints `BLOCKED`. Options: `--out FILE` (result JSON), `--audit-log FILE` (one hash-chained record per probe), `--timeout SECONDS`.

The probes: TCP, HTTPS, DNS lookup, metadata address, host file read, write to the read-only mount, docker socket, a bounded fork loop, symlink to the host, secrets in env, host processes in `/proc`, `mount`, DNS exfiltration with three `.invalid` names, and no network route.

The other tiers do not fake a result. When the tier cannot run, the suite prints why, says "No probe ran. This is not a pass." and exits 3:

```bash
uv run --all-packages python -m guard escape --tier gvisor
uv run --all-packages python -m guard escape --tier firecracker
```

- `gvisor` needs a Docker runtime named `runsc` (Linux host; `--runtime NAME` changes the name). Here: "Docker has no runtime 'runsc' registered".
- `firecracker` needs a launcher command (`--launcher` or `ARGUS_FIRECRACKER_LAUNCHER`) that takes `sh -c <probe>`. **No such launcher exists in the repo**, so this tier cannot run even on a KVM host until one is written.

Stored results: `results/escape-docker.txt` and `.json` are the 12-probe run (12 of 12 blocked); `results/dns-exfil-local.txt` has the 14-probe run (14 of 14), and the command above gave 14 of 14 again when this README was written (output not stored). All on Windows with Docker Desktop.

### Verify the audit log

```bash
uv run --all-packages python -m guard verify-log packages/guard/tests/fixtures/audit-sample.jsonl
uv run --all-packages python -m guard verify-log FILE --head HASH
```

Exit 0 and `OK <n> records, head <hash>`, or exit 1 and `BAD line <n>: <reason>`. The chain alone does not catch a cut tail or a consistent rewrite; `--head` with a hash kept somewhere else does (break-it T19). `guard.yml` writes the head to the run summary; it has never run.

### Ablation (sandbox tiers)

```bash
uv run --all-packages python -m guard ablation --tier docker --n 30
```

Starts the fixture container N times, records cold start and fixture run time (p50, p95, min, max) and runs the escape suite. A tier that cannot run writes `status: not_run` and exits 3. Results are in `results/ablation-*.json`; only the Docker one has numbers. To fill gVisor and Firecracker, follow `docs/notes/p7-t10.md`, `p7-t11.md` and `p7-t13.md` on a Linux host.

### Red-team

```bash
cd packages/guard/redteam
npx --yes promptfoo@0.125.1 eval -c promptfooconfig.yaml --no-cache
```

That is the dry run with a scripted stub: no model call. A real run needs a model; the stored one used the local Ollama:

```bash
ARGUS_REDTEAM_MODEL=ollama:gemma4:e4b npx --yes promptfoo@0.125.1 eval -c promptfooconfig.yaml --no-cache --repeat 5 -j 1 -o out.json
```

`ARGUS_REDTEAM_HARDENED=1` switches on the T09 mitigations for the same cases. Results and the limits of the run: `results/redteam-2026-11-03.md`. More in `redteam/README.md`.

### Secret scan

```bash
python .github/workflows/check_no_secrets.py
```

Prints `clean` and exits 0, or lists `path:line: <first 4 characters>...` (never the value) and exits 1.

### Tests

```bash
uv run --all-packages python -m pytest packages/guard/tests -q
```

111 passed when this README was written (Docker running; the Docker tests are included). Run each package's tests on their own, not in one pytest run across packages. No test calls a model.

## What did not run

- Any workflow on GitHub Actions: `guard`, `secret-scan`, `egress`, `gvisor`, `firecracker`.
- gVisor (rows B of the ablation and `sandbox-run-runsc.json` say not run / unavailable) and Firecracker (row C, `firecracker-run.json` says unavailable).
- A GitHub App, branch protection, and GitHub's real answer to a push to the default branch.
- The red-team on the production model; the skill case barely reached the model (loaded in 2 of 5 baseline runs).
- The fix loop for resolve rate, tokens or latency: P7 does not measure those (see the phase report).

## Where things are

| Path | What |
|---|---|
| `threat-model.md`, `secrets-inventory.md` | the written model and the inventory |
| `src/guard/` | `auditlog`, `escape`, `egress`, `redteam`, `sandbox_run`, `firecracker_run`, `ablation`, `cli` |
| `redteam/` | promptfoo config, provider, README |
| `results/` | stored outputs of the runs above (escape, egress, ablation, red-team, audit logs) |
| `tests/` | tests; `tests/fixtures/audit-sample.jsonl` is the sample log CI verifies |
| `docs/architecture/p7.md` | one section per task; `docs/notes/p7-*.md` hold the owner steps |
