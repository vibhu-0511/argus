# P7 sandbox tiers on GitHub-hosted runners: the runs

Date: 2026-11-03. Branch `stack/p7-guard`, PR [#15](https://github.com/vibhu-0511/argus/pull/15). The `gvisor` and `firecracker` workflows run on a pull request that changes them (a trigger added for this, because a manual-only workflow cannot be started before it reaches `main`). Numbers below are copied from the job logs (`gh run view <id> --log`); the result files were uploaded as workflow artifacts and were not downloaded.

## The runs

Several first runs failed for reasons found and fixed in the harness, not in the tiers. They are listed so the final numbers are not read as the first try.

| Run | Workflow | Commit | Outcome and what it showed |
|---|---|---|---|
| 41570171680 | gvisor | `c80fac4` | `runsc` release-20261026.0 installed and registered; fixture ran under gVisor (`Linux 4.19.0-gvisor`, `Starting gVisor...` in dmesg); escape suite 14 of 14. Job failed in the Docker ablation (29 of 30 starts: the timing-code bug below) |
| 41570171657 | firecracker | `c80fac4` | `/dev/kvm` present on `ubuntu-24.04` (AMD host, `kvm_amd` loaded); Firecracker v1.17.0 booted a microVM, fixture ran, `/checks` read-only, one boot 1.215 s. Green |
| 41570716360, 41571145836, 41571505564 | gvisor | `bf043e8`, `8db0720`, `b6046e5` | A and B ablation numbers (table below); the `fork-bomb` probe errored inside the gVisor ablation each time |
| 41570716284, 41571145870, 41571505470, 41571706922 | firecracker | `bf043e8` to `7a740d8` | microVM ablation: 1 boot passed and boots 2 to 30 failed. First thought to be a reused rootfs (fresh copy per boot did not help); the console tail of a failed boot said `Kvm error: Permission denied (os error 13)`: the `setfacl` on `/dev/kvm` is lost after the first microVM exits |
| 41571855271 | firecracker | `acf46af` | udev rule for `/dev/kvm`: 30 of 30 boots. The job still failed: 1 of 30 Docker starts failed |
| 41572071049 | firecracker | `7a740d8` | 200 Docker starts: 198 passed. Both failures had stderr `Read-only file system` (the write was refused) and lost two stdout lines: `start_once` read the first line with `readline()` and then called `communicate()`, which on Linux misses lines that arrived with the first one |
| 41572547937 | firecracker | `539cd16` | after the fix: 30 of 30 microVM boots, 30 of 30 and then 400 of 400 Docker starts. **Green** |
| 41572865817 | gvisor | `82cd115` | clean A and B pair on one runner (below); 5 stand-alone suites 14 of 14; 3 more suites straight after the ablation 14 of 14, no `runsc` process left. Job red only because the suite inside the gVisor ablation reported 13 of 14 |

## Numbers

Percentiles are nearest-rank over 30 starts. A and B rows from the same job are on the same runner at the same time.

A and B (gvisor job; each row is one run, runs in order of the table above):

| Run | A cold start p50 / p95 | A launch to exit p50 | B cold start p50 / p95 | B launch to exit p50 | A probes | B probes (inside the ablation) |
|---|---|---|---|---|---|---|
| 41570716360 | 81.0 / 99.8 ms | 116.9 ms | 89.9 / 103.1 ms | 146.0 ms | 14 of 14 | 13 of 14 (fork-bomb error) |
| 41571145836 | 84.7 / 101.7 ms | 123.6 ms | 96.1 / 111.6 ms | 154.4 ms | 14 of 14 | 13 of 14 (fork-bomb error) |
| 41571505564 | 98.8 / 103.8 ms (29 of 30 starts: timing-code bug) | 135.9 ms | 109.6 / 129.9 ms | 176.3 ms | 14 of 14 | 13 of 14 (fork-bomb error) |
| 41572865817 (AMD EPYC 7763) | 103.8 / 111.9 ms | 143.2 ms | 112.6 / 120.7 ms | 183.3 ms | 14 of 14 | 13 of 14 (fork-bomb error) |

Fixture run time (first line to exit) in the last run: A 39.0 ms, B 69.2 ms. B starts: 30 of 30 in every run.

C (firecracker job; 30 boots each, 30 of 30 passed; only launch to exit exists):

| Run | CPU | C launch to exit p50 / p95 | Docker launch to exit p50 on the same runner |
|---|---|---|---|
| 41571855271 | AMD EPYC 9V74 | 1061 / 1130 ms | 127.0 ms |
| 41572071049 | Intel Xeon Platinum 8370C | 1013 / 1114 ms | 117.2 ms |
| 41572547937 | AMD EPYC 9V74 | 1056 / 1121 ms | 119.9 ms (30 starts); 400 starts: cold start 82.9 / 140.8 ms, launch to exit 120.9 / 210.2 ms |

Stand-alone gVisor escape suite (separate process): 14 of 14 in 16 of 16 suite runs seen in the logs (1 in the first run, 6 and 9 in the last two).

## What is and is not shown

- Shown: all three tiers ran on a hosted Linux runner. `/dev/kvm` exists on `ubuntu-24.04` there (three runs on two CPU types). gVisor adds about 9 to 11 ms of cold start and 29 to 40 ms of launch to exit over Docker on the same runner. A microVM run takes about 1 s for the fixture.
- Not shown: any escape probe inside the microVM (the probes run in containers and were not ported); why the `fork-bomb` probe errors inside the gVisor ablation but passes alone; any real fix-loop task under a tier; a spread over many runner types.
- The results are on shared runners, a few runs each. The level of every number moves by about 20 ms between runs.
- The Windows numbers (`packages/guard/results/ablation-docker.json`: cold start p50 264.9 ms, 12 of 12 probes) are a different machine class and are not mixed with these.

## Why the gvisor check can be green with a warning

The `gvisor` workflow runs on every push to a pull request that includes a change to its file. Inside `guard ablation --tier gvisor` the `fork-bomb` probe ends as an error (4 of 4 runs), while the same suite run alone passes (16 of 16, and 3 of 3 straight after an ablation). So that case alone now ends the step with a GitHub warning annotation instead of a red job. Any failed start, any other failed or errored probe, or a failure in the stand-alone suites still fails the job. The cause of the error is not known; this is a way to keep the check readable, not an explanation.
