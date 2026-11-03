# P7-T01 OWASP agentic top 10 and Firecracker paper notes

Written by Claude on the owner's behalf (T01 is an [ME] task; owner to read). Read on 2026-11-03:

- the OWASP launch post [OWASP Top 10 for Agentic Applications: the benchmark for agentic security in the age of autonomous AI](https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/) (dated 2025-12-09) and the [resource page](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) for the edition "OWASP Top 10 for Agentic Applications for 2026",
- the paper [Firecracker: Lightweight Virtualization for Serverless Applications](https://www.usenix.org/conference/nsdi20/presentation/agache) (NSDI '20, Agache, Brooker, Florescu, Iordache, Liguori, Neugebauer, Piwonka, Popa), the full PDF at `usenix.org/system/files/nsdi20-paper-agache.pdf`.

Later tasks read this note: T02 (threat model rows), T10 to T13 (sandbox tiers), T15 (ADR-025). The edition and version facts are in `p7-t00-versions.md`.

## 1. What could not be read

The OWASP resource page links the PDF of the list itself, but a plain HTTP request to that link returned an HTML "No Access" page, so the per-risk text of the PDF was **not read**. Everything in section 2 comes from the launch post, which names all ten risks in one paragraph and gives one real incident for most of them. The one-line descriptions in section 2 are the ones the post's wording supports; where I add context it is marked as mine. **Owner step:** open the PDF in a browser, check the ten names below against its table of contents, and fix any difference here and in `packages/guard/threat-model.md`.

## 2. ASI01 to ASI10 as the OWASP post names them

The post writes each as "ASIxx - Name". The name column is copied from the post. The third column is what the post says about that risk, in short.

| ID | Name (OWASP launch post) | What the post says | Other spellings seen in write-ups, not confirmed against the PDF |
|---|---|---|---|
| ASI01 | Agent Goal Hijack | Hidden prompts turned copilots into "silent exfiltration engines"; example named: EchoLeak | |
| ASI02 | Tool Misuse | Agents "bent legitimate tools into destructive outputs"; example named: Amazon Q | "Tool Misuse and Exploitation" |
| ASI03 | Identity & Privilege Abuse | Leaked credentials let agents "operate far beyond their intended scope" | "Identity and Privilege Abuse" |
| ASI04 | Agentic Supply Chain Vulnerabilities | Dynamic MCP and A2A ecosystems let runtime components be poisoned; example named: a GitHub MCP exploit | "Agentic Supply Chain" |
| ASI05 | Unexpected Code Execution | Natural-language execution paths opened new routes to remote code execution; example named: AutoGPT RCE | |
| ASI06 | Memory & Context Poisoning | Memory poisoning "reshaped behaviour long after the initial interaction"; example named: the Gemini memory attack | "Memory and Context Poisoning" |
| ASI07 | Insecure Inter-Agent Communication | Spoofed inter-agent messages misdirected "entire clusters" | |
| ASI08 | Cascading Failures | False signals cascaded through automated pipelines with escalating impact | "Cascading Agent Failures" |
| ASI09 | Human-Agent Trust Exploitation | Confident, polished explanations misled human operators into approving harmful actions | |
| ASI10 | Rogue Agents | Agents showing "misalignment, concealment, and self-directed action"; example named: the Replit incident | |

The post also says a "Threat and Mitigations 1.1" taxonomy was released with the list. It was not read.

The threat model uses the names in the second column. The `&` is kept as written.

## 3. What the Firecracker paper claims about isolation

All numbers and quotes are from the NSDI '20 PDF (Firecracker v0.20.0 was its baseline). The paper is from 2020; the current release is v1.17.0 (`p7-t00-versions.md`), so the claims below are the paper's, not a check of today's code.

### Why a microVM and not a container (section 2)

- Containers rely on cgroups, namespaces and seccomp-bpf over **one shared kernel**, so there is "a fundamental tradeoff between security and code compatibility": restrict syscalls and some programs break.
- A trivial Linux program needs 15 unique syscalls; the paper cites a typical Ubuntu 15.04 install needing 224 syscalls and 52 unique ioctls.
- User-space kernels such as Google's gVisor are named as a different approach: provide OS functionality in user space so less of the host kernel is exposed. The paper still points out that rich interfaces like `/proc` made information-leak and covert-channel prevention hard (it cites CVE-2018-17972 and CVE-2017-18344).
- Virtualization "moves the security-critical interface from the OS boundary to a boundary supported in hardware and comparatively simpler software", and "removes the need to trade off between kernel features and security". VMMs are "much smaller than general-purpose OS kernels".

### The isolation properties the paper claims for Firecracker

| Property | Claim in the paper | Section |
|---|---|---|
| Hardware boundary | Built on Linux KVM; each workload runs in its own guest kernel inside a MicroVM | 1, 2.1.3 |
| One process per VM | "One Firecracker process runs per MicroVM, providing a simple model for security isolation." The whole VM stops if the process is killed | 2.1.3, 3.2 |
| Small device model | Only virtio network and block devices, serial ports and partial i8042 keyboard support, against more than 40 emulated devices in QEMU. USB, GPU and 9p were removed from the code taken from crosvm. The virtio block code is about 1,400 lines of Rust; the serial driver about 250 | 1, 3.1 |
| Block devices, not filesystem passthrough | Chosen "as a security consideration": passing only block IO "protects a substantial part of the host kernel surface area" | 3.1 |
| Memory-safe VMM | Written in Rust; "implementation in Rust, extensive testing and validation" is part of its stated confidence | 5.4 |
| Jailer | A wrapper that puts Firecracker "into a restrictive sandbox before it boots the guest": chroot, pid and network namespaces, privileges dropped, seccomp-bpf profile. The chroot holds only the Firecracker binary, `/dev/net/tun`, cgroup control files and the VM's own resources. The seccomp profile allows 24 syscalls (each with argument filtering) and 30 ioctls, 22 of them needed by KVM | 3.4.1 |
| Rate limiters in the device layer | Token buckets on IOPS, packets per second and bandwidth per device, enforced in emulation because "we do not trust the guest to implement its own limits" | 3.3 |
| Side channels | Guidance, not a guarantee: disable SMT, keep host kernel mitigations on, disable swap and samepage merging, avoid sharing files. "Other side-channel attacks, such as power and temperature, are not addressed by Firecracker" | 3.4 |
| Stated overall confidence | "The use of virtualization, along with side-channel hardening, implementation in Rust, extensive testing and validation makes us confident to run multiple workloads from multiple tenants on the same hardware" | 5.4 |

### Numbers the paper gives for cost

| Item | Paper's figure | Section |
|---|---|---|
| Memory overhead | "less than 5MB per container" with the minimal guest kernel | 1 |
| Boot to application code | "less than 125ms" | 1 |
| Creation rate | "up to 150 MicroVMs per second per host" | 1 |
| Where it ran | AWS Lambda and Fargate on EC2 bare-metal instances, in production since 2018 | 1, 4 |

These are the paper's numbers on bare metal. **They are not Argus numbers.** Argus's cold start comes from its own runs in P7-T13, and a hosted GitHub runner may have no `/dev/kvm` at all (`p7-t00-versions.md`).

### Limits the paper states (what Firecracker does not give)

- The paper says Firecracker "does sacrifice portability between host operating systems, and inherits a larger trusted compute base" because it relies on the Linux kernel and KVM.
- It supports "modern Linux hosts, and Linux and OSv guests" only.
- It was built for serverless; "the performance, density, and isolation goals of Firecracker were set by its intended use for serverless and containers".
- Side-channel protection depends on how the host is set up. A hosted CI runner that is itself a VM (nested virtualization) is not the setup the paper describes.

## 4. How this feeds P7

| Use | Where |
|---|---|
| The ten names | `packages/guard/threat-model.md` (T02), one row each |
| Container versus gVisor versus microVM: what is shared with the host | ADR-025 (T15); the three tiers in the ablation (T13) |
| "A sandbox with no network route" is a container control, not a hardware one: the paper's point is that the kernel is shared | T05, T12 escape probes (docker socket, host filesystem, fork bomb) |
| Jailer-style hardening (privileges dropped, restricted syscalls, no extra files in the root) | design reference for the Firecracker tier if T11 is built |

## 5. Not confirmed

- The OWASP PDF's own text, names and descriptions (section 1).
- Whether the post's short forms ("Tool Misuse", "Identity & Privilege Abuse") match the PDF's headings.
- Anything in the Firecracker paper newer than v0.20.0; the current repository docs were only skimmed in `p7-t00-versions.md`.
