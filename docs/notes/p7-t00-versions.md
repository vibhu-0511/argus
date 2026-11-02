# P7-T00 version re-check

Checked on 2026-11-03. Every row has the page or API it came from. "not confirmed" means the source did not say, or could not be read. No number below is from memory. Format follows `docs/notes/p6-t00-versions.md`.

Dependency waived: P7-T00 lists `P6-T25` as its dependency. P6 is still open (7 tasks, draft PR), so that dependency is waived and this check stands on its own date (see `docs/notes/p7-waves.md`).

How the checks were made: version and date facts come from the registries' own JSON (`registry.npmjs.org`, the GitHub releases API) because the web-search tool returned stale snippets (it reported promptfoo 0.117.5 and Firecracker v1.15.1; the registries say 0.125.1 and v1.17.0). Prose facts come from the vendor docs pages named in each row.

## promptfoo

| Item | Value | Source | Notes |
|---|---|---|---|
| Latest version | npm `promptfoo` dist-tag `latest` is 0.125.1, published 2026-10-25T02:12:24Z. GitHub release `0.125.1` (not draft, not prerelease) published 2026-10-25T01:53:11Z | [npm registry](https://registry.npmjs.org/promptfoo), [GitHub release](https://github.com/promptfoo/promptfoo/releases/tag/0.125.1) | The only dist-tag is `latest`. Not yet a dependency in any file of this repo |
| Licence | MIT | [npm registry, latest](https://registry.npmjs.org/promptfoo/latest) | |
| Runtime | `engines.node` is `>=22.22.0` | npm registry, latest | This machine has Node v24.16.0 (`node --version`, 2026-11-03), so it fits. A Python-only CI job would need Node set up |
| Use in Argus | Run with a pinned version, `npx promptfoo@0.125.1`, from T07; keep the three static cases deterministic with no LLM rubric | | Pin in the config file, not `@latest` |

## gVisor (`runsc`)

| Item | Value | Source | Notes |
|---|---|---|---|
| Latest release | `release-20261026.0` ("gVisor 20261026.0"), published 2026-10-28T00:10:59Z, not prerelease. Previous: `release-20261019.0` (2026-10-22), `release-20261012.0` (2026-10-16) | [GitHub releases API](https://api.github.com/repos/google/gvisor/releases?per_page=3), [release page](https://github.com/google/gvisor/releases/tag/release-20261026.0) | gVisor ships a new release about weekly, so T10 records the exact release it installs |
| Release assets | `gvisor-x86_64.tar.bz2`, `.tar.zstd`, `gvisor-aarch64.tar.bz2`, `.tar.zstd`, `SHA256SUMS`, `SHA512SUMS` | releases API | Verify the checksum when installing |
| Platform | "gVisor supports x86_64 and ARM64, and requires Linux 5.6+" | [install guide](https://gvisor.dev/docs/user_guide/install/) | Linux only. This dev machine is Windows 11 (Docker 29.5.3 via Docker Desktop). Whether `runsc` can be installed inside Docker Desktop's Linux VM: not confirmed, T10 tests it or leaves it to a Linux/Actions run |
| Docker runtime | `sudo /usr/local/bin/runsc install`, `sudo systemctl reload docker`, then `docker run --rm --runtime=runsc hello-world` | install guide | Also installable from an apt repository (the guide's first option) |
| Install change | The guide says `runsc install` auto-download of missing binaries "will be dropped at the end of September 2026"; use the apt package or the tarball | install guide | That date has passed, so T10 installs from the tarball or apt, not from `runsc install` alone |
| KVM platform | Optional. "If you intend to run the KVM platform, you will also need to have KVM installed" | [platforms guide](https://gvisor.dev/docs/user_guide/platforms/) | The default platform is not read here; T10 records which one it uses |

## Firecracker

| Item | Value | Source | Notes |
|---|---|---|---|
| Latest release | `v1.17.0`, published 2026-09-10T14:19:40Z, not prerelease | [GitHub releases API](https://api.github.com/repos/firecracker-microvm/firecracker/releases/latest), [release page](https://github.com/firecracker-microvm/firecracker/releases/tag/v1.17.0) | Assets: `firecracker-v1.17.0-x86_64.tgz` and `-aarch64.tgz`, each with a `.sha256.txt` |
| Licence | Apache 2.0 | [README at v1.17.0](https://github.com/firecracker-microvm/firecracker/blob/v1.17.0/README.md) | |
| Host requirement | "Firecracker requires read/write access to `/dev/kvm` exposed by the KVM module." Check with `lsmod \| grep kvm`; some distributions use the `kvm` group, otherwise `setfacl -m u:${USER}:rw /dev/kvm` | [getting-started.md at v1.17.0](https://github.com/firecracker-microvm/firecracker/blob/v1.17.0/docs/getting-started.md) | The project's own CI uses `.metal` instance types "because EC2 only supports KVM on specific supported kernels" (same page) |
| Guest kernel | v1.17.0 notes: "official support for 6.18 microVM guest kernels"; `bzImage` guest kernels now boot on x86_64 | release notes | The exact host and guest kernel support table was not read. T11 reads `docs/kernel-policy.md` |
| Isolation features | README: KVM-based, "thread-specific seccomp filters", and a jailer that "applies a cgroup/namespace isolation barrier and then drops" privileges | README at v1.17.0 | Detail goes in `p7-t01-owasp-firecracker.md` |

## GitHub-hosted runner KVM availability

**Answer: not confirmed for standard hosted runners, and the claim in `PROJECT.md` ("Linux runners have exposed `/dev/kvm` since October 2025") was not found in any source read.** Nothing below can be proved without a real Actions run, which this session cannot do. The Firecracker and gVisor-on-KVM tiers must start with a step that prints `ls -l /dev/kvm` (T11's acceptance already asks for this) and treat a missing device as "tier cut".

| Item | What the source says | Source |
|---|---|---|
| Official position | "While nested virtualization is technically possible while using runners, it is not officially supported. Any use of nested VMs is experimental and done at your own risk, we offer no guarantees regarding stability, performance, or compatibility." | [GitHub-hosted runners concepts](https://docs.github.com/en/actions/concepts/runners/github-hosted-runners) |
| What is documented | "GitHub-hosted Linux runners support hardware acceleration for Android SDK tools" | [runners reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) |
| Origin of that | April 2024 changelog: 2-vCPU Linux runners got hardware acceleration for Android emulators; the workflow must add the runner user to the KVM group with a udev rule | [changelog 2024-04-02](https://github.blog/changelog/2024-04-02-github-actions-hardware-accelerated-android-virtualization-now-available/) |
| Standard public-repo Linux x64 runner | 4 vCPU, 16 GB RAM, 14 GB SSD, labels `ubuntu-latest`, `ubuntu-24.04`, `ubuntu-22.04`, `ubuntu-26.04`. Free and unlimited on public repositories | runners reference |
| Arm | `ubuntu-24.04-arm` has `/dev/kvm` per a user report; `ubuntu-26.04-arm` does not (closed issue). A GitHub reply on a related issue says the Arm fleet "doesn't surface a nested KVM device" and "nested virtualization isn't officially supported on GitHub-hosted runners in general". The two statements conflict, and neither is a GitHub statement about x64 | [runner-images#14549](https://github.com/actions/runner-images/issues/14549), [runner-images#14062](https://github.com/actions/runner-images/issues/14062) |
| Older reports | A 2020 community thread reported no `/dev/kvm` and no `vmx`/`svm` flags on x64 runners then | [community discussion 160591](https://github.com/orgs/community/discussions/160591) |
| Image moving | `ubuntu-latest` moves to Ubuntu 26.04 over several weeks from 2026-10-19, to finish by 2026-11-19. The 24.04 image seen on 2026-11-03 has kernel `7.0.0-1017-azure`, image `20261026.354.1` | [runner-images#14748](https://github.com/actions/runner-images/issues/14748), [Ubuntu 24.04 readme](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md) |

So: a probe step on a real run is the only evidence that counts. Use a pinned label (`ubuntu-24.04`) for the probe so the `ubuntu-latest` move does not change the result silently. Larger hosted runners are paid; not read, not used.

## GitHub App installation token

| Item | Value | Source | Notes |
|---|---|---|---|
| Lifetime | "Installation tokens expire one hour from the time you create them." An expired token gives 401 | [REST: create an installation access token](https://docs.github.com/en/rest/apps/apps#create-an-installation-access-token-for-an-app) | One hour is fixed; T04 cannot make it shorter, only mint per run |
| Default scope | "By default the installation token has access to all repositories that the installation can access" | same | |
| Narrowing | Body parameter `repositories` or `repository_ids` (up to 500) limits the repos; body parameter `permissions` limits permissions. A token "cannot be granted access to repositories that the installation was not granted access to" | same | The minimum permission list for the workflow is T04's job and is not decided here |
| JWT to mint it | `exp` must be no more than 10 minutes in the future; set `iat` 60 s in the past for clock drift; `iss` is the client ID or app ID; signed RS256 with the App's private key | [generating a JWT](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app) | The private key is a secret: env var only |
| Token format change | "Starting April 27, 2026, GitHub began a staged rollout of a stateless format (`ghs_APPID_JWT`) to all newly minted GitHub App installation tokens." Code that expects a 40-character token may break | REST page above | **Matters for T03:** the secret redactor must match a prefix (`ghs_`) and a length range, not 40 characters |

## OWASP agentic top 10 edition

| Item | Value | Source | Notes |
|---|---|---|---|
| Name and edition | "OWASP Top 10 for Agentic Applications for 2026", resource page dated December 9, 2025. Ids ASI01 to ASI10 | [resource page](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/), [launch post](https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/) | The page describes it as peer reviewed with "more than 100" experts. The launch post also mentions a "Threat and Mitigations 1.1" taxonomy released with it. No newer edition was found on the OWASP site on 2026-11-03 |
| Full text | Not read. The resource page's download link returned an HTML "No Access" page to a plain HTTP request, so the PDF text could not be read here | resource page | The ten names in `p7-t01-owasp-firecracker.md` come from the launch post; two are spelled differently in other write-ups (see that note). **Owner step:** open the PDF in a browser and check names and the per-risk text |

## Result

- New pins: promptfoo 0.125.1 (MIT, Node >= 22.22.0), gVisor release 20261026.0, Firecracker v1.17.0, OWASP Top 10 for Agentic Applications for 2026 (ASI01 to ASI10).
- Changed: the `PLAN.md` and `PROJECT.md` statement that Linux runners have exposed `/dev/kvm` since October 2025 is not supported by any source read; GitHub calls nested virtualization unsupported. Both files are corrected.
- New fact for T03: installation tokens may now be `ghs_<APPID>_<JWT>`, not 40 characters.
- Not confirmed, carried forward: `/dev/kvm` on `ubuntu-24.04` / `ubuntu-26.04` x64 hosted runners (T11, a real run); `runsc` inside Docker Desktop on Windows (T10); Firecracker host-kernel table (T11); the OWASP PDF text (owner).
