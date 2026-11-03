# ADR-025: Sandbox tier selection

Status: proposed (P7-T15), drafted by Claude at the owner's request, for the owner to review. It is accepted when the owner approves it. All three tiers now have a real run on GitHub-hosted Linux runners (2026-11-03), but the runs are few, on shared runners, with a fixture and not a real fix-loop task. The numbers say what each tier costs. They do not show that one tier is safer than another, because the escape suite tests how a sandbox is configured and does not try kernel exploits. Everything said about what a tier adds beyond that is a claim from a source, labelled as such.

## Context

The fix loop runs model-written shell commands. They run in a container started by `fix_loop.sandbox`: `--network none`, 1 CPU, 512 MB, the worktree read-write, the bench checks read-only, no environment passed in. The phase asked to compare three isolation tiers on cold start and on an escape-test suite, and to pick the cheapest tier that passes the suite as the default. The three tiers:

| Tier | What it is | Where it was run |
|---|---|---|
| A | Docker container, `--network none` (runc) | Yes: Windows 11 with Docker Desktop (one run, kept as a plumbing check), and four GitHub-hosted `ubuntu-24.04` runs |
| B | Docker with the gVisor runtime (`runsc` release-20261026.0, [gvisor.dev](https://gvisor.dev)) | Yes: four GitHub-hosted runs, on the same runner as the A rows next to it |
| C | Firecracker v1.17.0 microVM | Yes: three GitHub-hosted runs, 30 boots each. `/dev/kvm` was present on the hosted `ubuntu-24.04` runner |

## What was measured

The runs are listed with their ids in `docs/notes/p7-github-tier-runs.md`. Cold start is `docker run` launched until the fixture prints its first line. Launch to exit is the whole run, including the fixture and removal. For the microVM only launch to exit exists (the guest console has no timestamps): firecracker launched until the process exited, which includes booting a guest kernel, the fixture and shutdown.

**A against B, on the same runner in the same job (four runs, 30 starts each, nearest-rank percentiles):**

| Run | A cold start p50 | B cold start p50 | B minus A | A launch to exit p50 | B launch to exit p50 | B minus A |
|---|---|---|---|---|---|---|
| 1 | 81.0 ms | 89.9 ms | +8.9 | 116.9 ms | 146.0 ms | +29.1 |
| 2 | 84.7 ms | 96.1 ms | +11.4 | 123.6 ms | 154.4 ms | +30.8 |
| 3 | 98.8 ms | 109.6 ms | +10.8 | 135.9 ms | 176.3 ms | +40.4 |
| 4 | 103.8 ms | 112.6 ms | +8.8 | 143.2 ms | 183.3 ms | +40.1 |

The gap between the tiers is steadier than the level of either one: the level moves by about 20 ms from run to run, because the runner is shared and, in run 4, was an AMD EPYC 7763.

**C (three runs, 30 boots each, all 30 of 30 passed):** launch to exit p50 1061, 1013 and 1056 ms; p95 1130, 1114 and 1121 ms. On the same runners, Docker's launch to exit p50 was 127.0, 117.2 and 119.9 ms. So a microVM run took about 8 to 9 times as long as a container run, on a fixture of a few `echo` commands. CPUs seen: AMD EPYC 9V74 and Intel Xeon Platinum 8370C.

**Escape probes (the 14-probe suite):**

- A: 14 of 14 in every suite run on Linux.
- B: 14 of 14 in 16 stand-alone suite runs. Inside `guard ablation --tier gvisor` the suite reported 13 of 14 in 4 of 4 runs: the `fork-bomb` probe ended as an `error` ("no verdict line (exit 2)"), not as an escape. The same suite run as separate processes straight after the ablation passed 3 of 3 times, with no `runsc` process left. The cause is not known; it happens only inside the ablation process. B is therefore reported as 14 of 14 when run alone and 13 of 14 inside the ablation, not as one clean number.
- C: **not run.** The probes run in containers and have not been ported into the microVM. The guest was seen to run the fixture and to mount `/checks` read-only; that is not the suite.

**Other results that matter:**

- Docker's first measured start failures (1 start in 30) were a bug in the timing code (`readline` then `communicate` lost lines on Linux), not a sandbox fault: stderr said `Read-only file system`. After the fix, 400 of 400 starts passed.
- Boots 2 to 30 of the microVM first failed with `Permission denied` on `/dev/kvm`, because an ACL set with `setfacl` is lost after the first microVM exits. A udev rule fixed it. This matters for anyone setting up a runner.
- The Windows run (Docker Desktop in a WSL2 VM: cold start p50 264.9 ms, p95 319.5 ms, 12 of 12 probes) is not comparable with the Linux runs and is not used below.

What these numbers cannot bear:

- **Few, shared runners.** Four runs for A and B, three for C, no confidence intervals, no control of the neighbours.
- **The fixture is a few commands.** It says nothing about overhead on a real fix-loop task, where the sandbox runs `npm`, a build and tests.
- **The suite does not separate A from B.** Both pass what can be run. The probes check network, mounts, sockets, limits and symlinks. They cannot show that no kernel flaw lets code out of a container, and so cannot show what gVisor or Firecracker add.
- **The escape suite and the fix-loop sandbox differ by one flag.** The suite adds `--pids-limit 128`; `fix_loop/sandbox.py` does not. The same fork probe through `fix_loop.sandbox.run` found 301 processes alive (T12).
- **Row C has no probes**, so it cannot be compared with A and B on pass rate.

## Decision

**The default sandbox tier stays Docker with `--network none` (tier A).** It is the tier the pipeline uses today. It is the cheapest of the three by the measured cost (about 9 to 11 ms less cold start and 29 to 40 ms less total than gVisor, and about 9 times faster than a microVM run on the fixture). It passes the suite as every tier that can run the suite does, so on this evidence nothing is bought by the more expensive tiers. That last point is a limit of the suite, not a proof that the tiers are equal.

Requirement that goes with the default: the production sandbox flags must include a pids limit, and a cap drop, before this default is called tested. At present only the suite adds a pids limit.

### When a stronger tier is required

These conditions are the proposal. The properties of the tiers are claims from sources, not measurements from this repo.

| Tier | What it adds (claim, source) | Cost seen here | Use it when |
|---|---|---|---|
| gVisor | A user-space kernel intercepts the sandbox's system calls, so less of the host kernel is exposed (the Firecracker paper's description of the approach, NSDI '20 section 2; [gvisor.dev](https://gvisor.dev)). The paper also says rich interfaces such as `/proc` made leak and covert-channel prevention hard for it | about +10 ms cold start and +30 to +40 ms total over A on a hosted runner, same fixture | Code from authors Argus does not control reaches `run_cmd` (the live issue adapter is built and the tracker is not owner-only), **and** a container escape would land on a host that holds more than a throwaway runner VM. Its cost is small enough on the fixture that this is the first step up |
| Firecracker | A hardware boundary: each sandbox is a microVM with its own guest kernel, one process per VM, a small device model, and a jailer (the paper's claims for v0.20; today's v1.17.0 code was not checked). The paper's own figures are boot to application code under 125 ms and under 5 MB overhead, **on its bare-metal test setup, not on Argus** | about 1 s launch to exit for the fixture on a hosted runner (boot of a guest kernel included); `/dev/kvm` was present there, needs a udev rule, and the escape probes are not ported | The same as for gVisor, and the code must be hostile enough that a kernel-level flaw is a real concern (for example the scorer or the repro container runs patched code from strangers on a shared host). On a hosted runner it is possible; whether hosted runners keep `/dev/kvm` was seen on a few runs and is not a guarantee |

Other triggers, in either direction:

- A probe in the escape suite fails on tier A on a Linux host: that tier is not acceptable as the default until it is fixed or replaced.
- The Actions runner stops being a thrown-away VM per run (a self-hosted, long-lived runner): a container escape then reaches something that persists, so a stronger tier is required.
- The scorer and gates (which today run the patched code on the runner host, outside any sandbox; ADR-024 risk 1) are moved into a sandbox: that sandbox runs a whole app and a browser, a bigger surface than `run_cmd`, so the tier should be reconsidered then.

### What must be measured before the default is revisited

1. A real fix-loop task under each tier, not only the fixture, for run-time overhead.
2. The escape probes inside the microVM (a launcher for `guard escape --tier firecracker` that runs the probes in the guest), so row C has a pass count.
3. Why the `fork-bomb` probe errors inside `guard ablation --tier gvisor` and not when the suite runs alone.
4. More runs, on more than one runner type, to put a spread on the A against B gap.
5. The decision rule, written before the numbers: the owner sets the limit on cold start and overhead that is acceptable. This ADR does not invent one.

## Alternatives

- **gVisor as the default.** Not chosen: the suite does not show a benefit over A, it costs about 10 to 40 ms more per start on the fixture, and one probe errors inside the ablation for a reason not yet known. It may be right once untrusted code reaches `run_cmd`; the table above says when.
- **Firecracker as the default.** Not chosen: about 8 to 9 times the run time of a container on the fixture, no probes ported, and a KVM device that needed a udev rule on the runner.
- **No default until all three are fully measured.** Not chosen: the pipeline already runs in Docker, and the three tiers now have real runs.
- **Pick the default by the paper's numbers.** Rejected: they are from 2020, from bare metal, for serverless workloads. The runs above are on a hosted runner.

## Consequences

- The default stays as it is. The only change this ADR asks for is the pids limit and a cap drop in `fix_loop/sandbox.py`, then a re-run of the suite through the real flags. Not done here.
- The phase's ablation table has three filled rows. Row C has no probe count and its cold start is a dash; the table says so.
- `gvisor.yml` and `firecracker.yml` now also run on a pull request that changes them, so they can run before they reach `main`; they can also be dispatched by hand once on `main`.
- The numbers are from one day and a few runs. Re-run them before quoting them.
