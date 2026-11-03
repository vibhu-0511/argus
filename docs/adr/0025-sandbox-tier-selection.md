# ADR-025: Sandbox tier selection

Status: proposed (P7-T15), drafted by Claude at the owner's request, for the owner to review. It is accepted when the owner approves it. **Only one of the three tiers was measured.** Row A of the ablation (Docker with `--network none`) was run; row B (gVisor) and row C (Firecracker) were not run, and there is no comparison between tiers in this ADR because none exists. Everything said about gVisor and Firecracker below is a claim from a source, labelled as such, not a result from this repo. Revisit when rows B and C exist (owner steps in `docs/notes/p7-t13.md`), when the live issue adapter is built, or when the scorer moves into the sandbox.

## Context

The fix loop runs model-written shell commands. They run in a container started by `fix_loop.sandbox`: `--network none`, 1 CPU, 512 MB, the worktree read-write, the bench checks read-only, no environment passed in. The phase asked to compare three isolation tiers on cold start and on an escape-test suite, and to pick the cheapest tier that passes the suite as the default. The three tiers:

| Tier | What it is | Where it was run |
|---|---|---|
| A | Docker container, `--network none` (runc) | Yes, on this Windows 11 machine with Docker Desktop (WSL2) |
| B | Docker with the gVisor runtime (`runsc`, [gvisor.dev](https://gvisor.dev)) | No |
| C | Firecracker microVM on a KVM host | No |

## What was measured and what was not

**Row A**, from `packages/guard/results/ablation-docker.json` (`guard ablation --tier docker`, one run, 2026-11-03):

| Item | Value |
|---|---|
| Starts | 30 requested, 30 passed the fixture check |
| Cold start p50 / p95 | 264.9 ms / 319.5 ms (min 221.2 ms, max 405.4 ms; nearest-rank, so p95 is the 29th of 30 values) |
| Fixture run time p50 / p95 | 182.4 ms / 228.9 ms. This is the time after the first line until the container exited and was removed; there is no bare-host baseline here, so it is not a ratio |
| Escape probes passed | 12 of 12 (the 12-probe suite: TCP, HTTPS, DNS, metadata address, host file read, write to the read-only mount, docker socket, fork bomb, symlink, secrets in env, host processes, `mount`) |
| Later check | After the two DNS probes were added in T21 the suite has 14 probes; the stored T21 output (`packages/guard/results/dns-exfil-local.txt`) shows 14 of 14 on the docker tier. This is a separate run from the ablation, not part of row A |

What the row A numbers can bear:

- **The machine is not a Linux runner.** Docker Desktop runs Linux containers in a WSL2 VM, so the cold start includes that boundary. The number is not comparable with a Linux host and not with any other tier measured elsewhere. Load on the machine during the run was not measured.
- **One run, N = 30, no repeat of the whole experiment, no confidence interval.**
- **The escape suite and the fix-loop sandbox differ by one flag.** The suite adds `--pids-limit 128`; `fix_loop/sandbox.py` does not. The same fork probe through `fix_loop.sandbox.run` found 301 processes alive (T12). So "12 of 12 on the Docker tier" holds for the suite's flags, and the real fix-loop container passes the fork probe only if the flag is added to the sandbox. This was not done (see Consequences).
- **The fixture is a few `echo`, `cat`, `uname` and `dmesg` commands.** It says nothing about overhead on a real fix-loop task.
- The probes were checked to be able to fail: a test weakens the container on purpose and requires a fail from six of them. Three were given no positive control (read-only mount write, docker socket, metadata address).

**Rows B and C are empty, and that means "not run", not zero.**

- B: this machine has no `runsc` and gVisor runs on Linux only (Linux 5.6 or newer, x86_64 or ARM64, per the install guide). The plumbing exists (`ARGUS_SANDBOX_RUNTIME`, `guard sandbox-run`, `guard escape --tier gvisor`, `.github/workflows/gvisor.yml`) and was tested with Docker replaced. `ablation-gvisor.json` says `status: not_run`; `sandbox-run-runsc.json` says `unavailable`. `gvisor.yml` never ran.
- C: this machine has no `/dev/kvm`. No microVM has booted. `.github/workflows/firecracker.yml` never ran. Whether a GitHub-hosted runner has `/dev/kvm` is **not confirmed** by any source read (T00): GitHub calls nested virtualization unsupported. Two things for the escape suite and cold start on this tier do not exist yet: a launcher for `guard escape --tier firecracker` and a cold-start harness for N boots. `ablation-firecracker.json` says `status: not_run`.
- The phase says that if Firecracker is cut, row C stays empty and this ADR says why. The reason row C is empty is: no KVM here, no confirmed KVM on a hosted runner, no launcher, no harness. Whether to take the cut formally or to keep trying a KVM runner is the owner's call.
- Because row B has no run, the task that fills the ablation (P7-T13) is not complete, and the hypothesis of the phase ("stronger tiers pass more probes at a higher cold start; the cheapest tier that passes is the default") **was not tested**.

## Decision

**The default sandbox tier is Docker with `--network none` (tier A).** The reason is narrow: it is the tier the pipeline uses today, and it is the only one with evidence here (12 of 12 probes, and 14 of 14 on the later suite, on one Windows machine). It is not chosen because it was shown to be as safe as the others, or cheaper than them: no such comparison was made. The escape suite tests how a container is configured; it cannot show that no kernel flaw lets code out of a container.

Requirement that goes with the default: the production sandbox flags must include a pids limit, and a cap drop, before this default is called tested. At present only the suite adds a pids limit.

### When a stronger tier is required

These conditions are the proposal. The properties of the tiers are claims from sources, not measurements from this repo.

| Tier | What it adds (claim, source) | Use it when |
|---|---|---|
| gVisor | A user-space kernel intercepts the sandbox's system calls, so less of the host kernel is exposed (the Firecracker paper's description of the approach, NSDI '20 section 2; [gvisor.dev](https://gvisor.dev)). The paper also says rich interfaces such as `/proc` made leak and covert-channel prevention hard for it. Cost is not claimed here; it was not measured | Code from authors Argus does not control reaches `run_cmd` (the live issue adapter is built and the tracker is not owner-only), **and** a container escape would land on a host that holds more than a throwaway runner VM |
| Firecracker | A hardware boundary: each sandbox is a microVM with its own guest kernel, one process per VM, a small device model, and a jailer (the paper's claims for v0.20; today's v1.17.0 code was not checked). The paper's own figures are boot to application code under 125 ms and under 5 MB overhead, **on its bare-metal test setup, not on Argus** | The same as for gVisor, and the code must be hostile enough that a kernel-level flaw is a real concern (for example the scorer or the repro container runs patched code from strangers on a shared host). It needs `/dev/kvm`, which is not confirmed on hosted runners, so it means a self-hosted or other KVM-capable Linux runner |

Other triggers, in either direction:

- A probe in the escape suite fails on tier A on a Linux host: that tier is not acceptable as the default until it is fixed or replaced.
- The Actions runner stops being a thrown-away VM per run (a self-hosted, long-lived runner): a container escape then reaches something that persists, so a stronger tier is required.
- The scorer and gates (which today run the patched code on the runner host, outside any sandbox; ADR-024 risk 1) are moved into a sandbox: that sandbox runs a whole app and a browser, a bigger surface than `run_cmd`, so the tier should be reconsidered then.

### What must be measured before the default is revisited

1. Row B on a Linux host: install `runsc` (`docs/notes/p7-t10.md`), run `guard ablation --tier gvisor --n 30`, and keep the result.
2. Row A **again on the same Linux host**, so A and B are compared on one machine. The Windows numbers stay as a separate file.
3. Escape probes on B (needs only the `runsc` runtime) and, if row C is attempted, a launcher for the Firecracker tier and a cold-start harness for N boots (neither exists).
4. A real fix-loop task under each tier, not only the fixture, for run-time overhead.
5. A repeat of the whole run, to see the spread between runs.
6. For C: a run of `firecracker.yml` that prints the `/dev/kvm` line, or a statement that no KVM runner is available (which would be the reason to cut it).
7. The decision rule, written before the numbers: the owner sets the limit on cold start and overhead that is acceptable. This ADR does not invent one.

## Alternatives

- **gVisor as the default.** Not chosen: it was not run once; the install, the registration with Docker and the behaviour of the fix-loop image under it are unseen. It may be right on a Linux host; this ADR cannot say.
- **Firecracker as the default.** Not chosen: no microVM has booted, no KVM was seen on any machine used, and the hosted-runner question is open. It would also need a launcher and a harness that do not exist.
- **No default until all three are measured.** Not chosen: the pipeline already runs in Docker. Naming it the default and listing what is missing is more honest than leaving the question open.
- **Pick the default by the paper's numbers.** Rejected: they are from 2020, from bare metal, for serverless workloads.

## Consequences

- The default stays as it is. The only change this ADR asks for is the pids limit and a cap drop in `fix_loop/sandbox.py`, then a re-run of the suite through the real flags. Not done here.
- The phase's ablation table has one filled row. Anyone reading it must not read the dashes in B and C as a result.
- If the owner takes the Firecracker cut, the unbuilt launcher and harness for C can stay unbuilt, and `firecracker.yml` and `firecracker_run.py` stay as written-but-unrun code.
- The row A numbers are tied to Windows and Docker Desktop. They are useful for the plumbing (the harness works, 30 starts pass) and not as a Linux figure.
