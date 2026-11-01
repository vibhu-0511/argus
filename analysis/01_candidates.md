# Phase 1 — candidates

Checked 2026-10-28 against the GitHub API. Stars, licence, archived flag, and default-branch HEAD SHA and commit date come from that API. Nothing was cloned. No competitor code was installed or run.

`pushedAt` can be later than the default-branch HEAD when some other branch moved. The "last commit" column is the default-branch HEAD. Where those dates differ, the other branch was not inspected.

Approve this audit set before Phase 2. Phase 2 will `git clone --depth 1` only the kept rows into `analysis/_repos/` (gitignored) and pin every citation to the SHA below.

## T1 — Agent loop and harness

Informs P3, ADR-008, ADR-009, ADR-010, ADR-011.

| Repo | Licence | Last commit (HEAD) | Stars | SHA | Informs |
|---|---|---|---|---|---|
| [SWE-agent/SWE-agent](https://github.com/SWE-agent/SWE-agent) | MIT | 2026-07-16 (pushed 2026-10-26) | 20663 | `3ea751c087f32b16e039a2233dd6eefecef325d5` | P3-T02, P3-T06, P3-T08, P3-T21, P3-T27, ADR-008, ADR-009. Repo description says it takes a GitHub issue and tries to fix it, so it is also the T4 seed. `config/` and `trajectories/` exist at this SHA. The exact issue-mode entry point was not opened. |
| [SWE-agent/mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) | MIT | 2026-09-03 (pushed 2026-10-26) | 8906 | `04d809ceab9df28f9adaed044884180159172930` | P3-T01, P3-T17, P3-T20, P3-T25, ADR-011. This is the comparison the plan already names. |
| [Aider-AI/aider](https://github.com/Aider-AI/aider) **added** | Apache-2.0 | 2026-05-22 | 49787 | `5dc9490bb35f9729ef2c95d00a19ccd30c26339c` | P3-T02, ADR-008. Added for edit formats (search/replace and diff), which the dropped agentless repo is no longer maintained to show. Five months since HEAD: slow, not archived. |
| [OpenHands/software-agent-sdk](https://github.com/OpenHands/software-agent-sdk) **added** | MIT | 2026-10-27 | 1312 | `46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98` | P3-T02, P3-T06, P3-T08, ADR-008. Top level at this SHA is `openhands-sdk`, `openhands-tools`, `openhands-agent-server`, `examples`. This is the harness to read. Also the T4 GitHub-workflow successor (`examples/03_github_workflows`). |

**Not in the audit set**

| Repo | Licence | Last commit (HEAD) | Stars | SHA | Why |
|---|---|---|---|---|---|
| OpenHands/OpenHands (seed) | MIT | 2026-10-27 | 92068 | `6354932e87f99e1583f482f2cea49d6d573443e0` | Alive, but the default-branch root at this SHA is a TypeScript / Electron app (`package.json`, `vite.config.ts`, `electron`). No Python agent package at the top level. [CODE] contents listing. Do not spend the Phase 2 file budget here unless you say so. `All-Hands-AI/OpenHands` resolves to this same repo. |
| OpenAutoCoder/Agentless | MIT | 2024-12-22 | 2133 | `5ce5888b9f149beaace393957a55ea8ee46c9f71` | Frozen. No default-branch commit in 22 months. Edit-format role is handed to Aider. Say if you want it restored. |
| AutoCodeRoverSG/auto-code-rover | SONAR Source-Available License v1.0 (GitHub SPDX `NOASSERTION`) | 2025-04-24 (pushed 2026-10-27) | 3102 | `585d3e639aeda58ef0b6a151dd1cc2721a94d267` | Stale HEAD, and the licence file starts with "SONAR Source-Available License v1.0". Ideas only even if restored. `nus-apr/auto-code-rover` resolves to this same repo. The Oct 2026 push is not this HEAD; that branch was not inspected. |
| aorwall/moatless-tools | MIT | 2025-09-01 | 643 | `011ead57a5c81664e9c45e07e1f50b17e695cc63` | No default-branch commit in 13 months. |

`princeton-nlp/SWE-agent` resolves to `SWE-agent/SWE-agent`.

## T2 — UI repro and DOM to source

Informs P1, P2, ADR-004, ADR-005, ADR-006, ADR-007.

| Repo | Licence | Last commit (HEAD) | Stars | SHA | Informs |
|---|---|---|---|---|---|
| [microsoft/playwright](https://github.com/microsoft/playwright) | Apache-2.0 | 2026-10-27 | 98704 | `f9a841f968dd9a4e315df2ec2930da1952971667` | P1-T04, P1-T07, P1-T14, ADR-004, ADR-005. Planner / generator / healer live here, not in a separate repo. Docs: `docs/src/test-agents-js.md`. Agent definitions: `packages/playwright/src/agents/`. Phase 2 reads those paths only. |
| [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) **added** | Apache-2.0 | 2026-10-22 | 38738 | `0c4107acbecb75472b23c05c0e42471a0011874f` | P1-T01, P1-T03, P1-T15, ADR-004, P2-T00. The plan's interop spike is this server. The test-agent seed does not cover it. |
| [browser-use/browser-use](https://github.com/browser-use/browser-use) | MIT | 2026-10-26 | 119344 | `2cc71890e65056b67fdb29d98bb407749c15bb08` | P1-T04, P1-T07, P1-T14. Ticket-to-browser actions and selector failure. Phase 2 stays on the agent/DOM path, not the hosted cloud product. |
| [zh-lx/code-inspector](https://github.com/zh-lx/code-inspector) | MIT | 2026-10-09 (pushed 2026-10-13) | 3049 | `6235e8a97a484237b7308e13d7d700e5e7f3fea4` | P2-T02, P2-T03, P2-T08, ADR-006. Monorepo has a `packages/vite` package plus `code-inspector-plugin`. This is the maintained compile-time injector. |

**Not in the audit set**

| Repo | Licence | Last commit (HEAD) | Stars | SHA | Why |
|---|---|---|---|---|---|
| zthxxx/react-dev-inspector | MIT | 2025-01-05 on branch `dev` (pushed 2026-04-20) | 1322 | `3292e226597e1bafc11bbeefeded416b02c05c58` | Stale, and it still goes through `fiber._debugSource`. `packages/inspector/src/Inspector/utils/inspect.ts` exists at this SHA. Default-branch code search reports `_debugSource` in that file. React 19 removed that field (ADR-006). The Apr 2026 push is not this HEAD. |
| infi-pc/locatorjs | No licence file. GitHub licence API returned 404. `packages/runtime/package.json` says `"license": "MIT"`. | 2026-03-01 (pushed 2026-09-22) | 1827 | `ac4ed50a8f3668a3390488ea7af483fb97a58009` | Unknown licence file, so ideas only, and the same `_debugSource` approach. `packages/runtime/src/adapters/react/findDebugSource.ts` exists at this SHA; code search reports `_debugSource` there. |
| ericclemmons/click-to-component | MIT | 2025-09-23 | 2350 | `f8be09c4c1f7228168731c2d7e7dc2352f68f0b7` | No default-branch commit in 13 months, and `packages/click-to-react-component/src/getSourceForInstance.js` exists at this SHA. Code search reports `instance._debugSource` in that file. |

Considered and not added: `browserbase/stagehand` (MIT, HEAD 2026-10-27, 25845 stars) is another browser agent, not a source-location injector. `ivanstnsk/xray` (MIT, 13 stars) says it wraps `code-inspector-plugin`. `carboni-rob/carbon8r` and `mattkawczynski/click-to-source` have 0 stars. `ArnaudBarre/vite-plugin-react-click-to-component` is MIT and committed 2026-08-05, but only 87 stars; not added ahead of `code-inspector`. `webpro/click-to-react-component`, `lokalise/click-to-component`, and `ericclemmons/click-to-react-component` do not resolve.

## T3 — Verify and eval

Informs P0, P4, P5, ADR-003, ADR-012, ADR-013, ADR-014, ADR-017.

| Repo | Licence | Last commit (HEAD) | Stars | SHA | Informs |
|---|---|---|---|---|---|
| [SWE-bench/SWE-bench](https://github.com/SWE-bench/SWE-bench) | MIT | 2026-09-02 (pushed 2026-09-18) | 6099 | `02e7a74ffd0b707aab73d203fe87bdc7c76afc8e` | P0-T02, P5-T19, P5-T20, ADR-017. `princeton-nlp/SWE-bench` resolves here. Default-branch code search shows `swebench/cli/_datasets.py` mapping `multimodal` to `SWE-bench/SWE-bench_Multimodal`, and the README mentioning Multimodal. The file body was not opened. Phase 2 reads the harness and that dataset guide, not the whole repo. |
| [garris/BackstopJS](https://github.com/garris/BackstopJS) | MIT | 2026-09-08 (pushed 2026-10-10) | 7190 | `a11d3657788bbffebd7a2b2eb5212006696afbff` | P4-T02, P4-T26, ADR-012. Visual regression, masks, flake. |
| [reg-viz/reg-suit](https://github.com/reg-viz/reg-suit) | MIT | 2026-03-16 (pushed 2026-10-27) | 1303 | `5c09c8eb1e356d7e8145e5850e6de17b2b25a5a0` | P4-T02, P5-T16. Threshold / CI comparison. The Oct 2026 push is not this HEAD. |
| [argos-ci/argos](https://github.com/argos-ci/argos) | MIT | 2026-10-28 | 650 | `500420acac590b5ec0d628236e5d8c456f048ec5` | P4-T02, P8-T09. Maintained visual-review product. Phase 2 reads the diff/mask path, not the whole app. |
| [promptfoo/promptfoo](https://github.com/promptfoo/promptfoo) | MIT | 2026-10-26 (pushed 2026-10-28) | 26533 | `e48ed85e08ff8a1ca74fa7d0e41daf47cf155efb` | P7-T07, P7-T08, P4-T27. Red-team configs. Phase 2 reads the injection / CI slice, not the whole product. |
| [lm-sys/FastChat](https://github.com/lm-sys/FastChat) **added, the judge-calibration repo** | Apache-2.0 | 2025-06-02 | 39549 | `587d5cfa1609a43d192cedb8441cac3c17db105d` | P4-T01, P4-T12, P4-T14, P4-T24, ADR-013. `fastchat/llm_judge/compute_agreement.py` is in the tree at this SHA, next to `gen_judgment.py`. Stale (16 months). Kept because it is the published MT-bench agreement code, not because it is active. Phase 2 reads `fastchat/llm_judge/` only. |
| [dmtrKovalenko/odiff](https://github.com/dmtrKovalenko/odiff) **added** | MIT | 2026-10-13 | 3285 | `6dd1e9629810042c03a81fc787f37b245772970a` | P4-T02, P4-T26. Pixel-diff engine to replace archived Lost Pixel. Anti-alias options are the part to read. |

**Not in the audit set**

| Repo | Licence | Last commit (HEAD) | Stars | SHA | Why |
|---|---|---|---|---|---|
| lost-pixel/lost-pixel | MIT | 2026-04-22 | 1678 | `f08221fc2a82125df56177c2363185a886bea73a` | Archived. Replaced in the audit set by Argos (product) and odiff (diff engine). |

Considered and not added: GitHub search for "llm judge calibration" returned many small personal repos with near-duplicate descriptions. Stars were not fetched; none was adopted. `prometheus-eval/prometheus-eval` is Apache-2.0 and 1120 stars, but HEAD is 2025-04-25, and a code search for "human" returned nothing. `allenai/reward-bench` (Apache-2.0, HEAD 2026-10-14, 747 stars) evaluates reward models, not a rubric judge against human labels. `ScalerLab/JudgeBench` has no detected licence and HEAD 2024-11-07. `pln-fing-udelar/fast-krippendorff` is GPL-3.0 (ideas only) and is the statistic, not a judge study; P4-T12 stays [ME]. `mapbox/pixelmatch` is ISC, HEAD 2026-10-06, 7004 stars. Not added so the extra slot stays on odiff. Say if you want pixelmatch instead. `SWE-bench/experiments` has no detected licence (285 stars, HEAD 2026-09-03).

## T4 — Issue to PR, durability, security

Informs P6, P7, P8, ADR-020 through ADR-029.

| Repo | Licence | Last commit (HEAD) | Stars | SHA | Informs |
|---|---|---|---|---|---|
| [SWE-agent/SWE-agent](https://github.com/SWE-agent/SWE-agent) | MIT | 2026-07-16 (pushed 2026-10-26) | 20663 | `3ea751c087f32b16e039a2233dd6eefecef325d5` | P8-T08, P8-T09, P6-T05, ADR-021, ADR-026. Same SHA as T1. `.github/workflows/` at this SHA is docs and pytest only (`build-docs.yaml`, `check-links-periodic.yaml`, `check-links-pr.yaml`, `pytest.yaml`). No issue-label workflow file was found there. |
| [OpenHands/software-agent-sdk](https://github.com/OpenHands/software-agent-sdk) **added** | MIT | 2026-10-27 | 1312 | `46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98` | P8-T02, P8-T04, P8-T08, P6-T05, ADR-026. Successor to the archived resolver. `examples/03_github_workflows/` at this SHA contains `01_basic_action`, `02_pr_review`, `03_todo_management`, `04_datadog_debugging`, `05_posthog_debugging`. |
| [korthout/backport-action](https://github.com/korthout/backport-action) | MIT | 2026-10-28 | 123 | `08d2ffecdef82bdb06ea268ba07f50381440e4c4` | P8-T10, P8-T23. GitHub Action that cherry-picks a merged PR. |
| [sorenlouv/backport](https://github.com/sorenlouv/backport) | Apache-2.0 | 2026-10-07 (pushed 2026-10-22) | 286 | `f9d847e91713a58c6b8e76208241c7575569cd44` | P8-T10, P8-T23. CLI backport. `sqren/backport` resolves to this repo. |
| [dbos-inc/dbos-transact-py](https://github.com/dbos-inc/dbos-transact-py) **added** | MIT | 2026-10-27 | 1653 | `718d06613d9b7dc4c935e098e4608b6745267760` | P6-T01, P6-T03, P6-T19, ADR-020. The Python library the plan names. `dbos-inc/dbos-python` does not exist; this is the repo. Phase 2 reads step / recovery semantics, not the whole package. |
| [dbos-inc/dbos-demo-apps](https://github.com/dbos-inc/dbos-demo-apps) | None detected. Licence API 404. No root `LICENSE` in the contents listing. **Ideas only.** | 2026-10-15 | 105 | `5568fc9fdb61a91e6f7cb300ef6f1cd254d219a6` | P6-T03, P6-T05, ADR-021, ADR-022. Python demos exist under `python/` (including `dbos-app-starter`, `queue-patterns`). No snippet copying. |

**Not in the audit set**

| Repo | Licence | Last commit (HEAD) | Stars | SHA | Why |
|---|---|---|---|---|---|
| All-Hands-AI/openhands-resolver | MIT | 2024-11-18 | 133 | `baa2f4515e3a68cb5b8d1fe1eba28c03e474c798` | Archived. `OpenHands/OpenHands-resolver` does not resolve. PR [14062](https://github.com/OpenHands/OpenHands/pull/14062) is titled "Removed the V0 resolver" (merged 2026-04-23 in the search result). The diff was not opened. The app repo's top-level tree at `6354932e` has no resolver package. |
| sweepai/sweep | Sweep Enterprise Edition licence. GitHub SPDX `NOASSERTION`. The licence file begins "Sweep Enterprise Edition (EE) license". | 2025-09-18 | 7709 | `a8b8b67bda4f89faac9314d34e7c7d5a64f76046` | Not open source, and the GitHub description is now "Sweep: AI coding assistant for JetBrains", not an issue-to-PR bot. HEAD is 13 months old. Secondary write-ups of a 2026 shutdown were not used as evidence. |

Considered and not added, because the two added slots are the SDK and `dbos-transact-py`: [peter-evans/create-pull-request](https://github.com/peter-evans/create-pull-request) is MIT, HEAD 2026-10-12, 2871 stars, SHA `bd09a93810788ce61d2d5fb7d6b221b9b4a4aab7`. It is the idempotent "update the existing PR" action, relevant to P6-T21 and P8-T09. Say if you want it instead of the demo apps. `The-PR-Agent/pr-agent` (MIT, HEAD 2026-10-28, 13654 stars; `Codium-ai/pr-agent` and `qodo-ai/pr-agent` resolve there) reviews PRs. It does not turn an issue into a patch, so it was not added.

## What Phase 2 would clone

19 repos, once each. `SWE-agent/SWE-agent` and `OpenHands/software-agent-sdk` are shared by T1 and T4.

1. SWE-agent/SWE-agent
2. SWE-agent/mini-swe-agent
3. Aider-AI/aider
4. OpenHands/software-agent-sdk
5. microsoft/playwright
6. microsoft/playwright-mcp
7. browser-use/browser-use
8. zh-lx/code-inspector
9. SWE-bench/SWE-bench
10. garris/BackstopJS
11. reg-viz/reg-suit
12. argos-ci/argos
13. promptfoo/promptfoo
14. lm-sys/FastChat (`fastchat/llm_judge/` only)
15. dmtrKovalenko/odiff
16. korthout/backport-action
17. sorenlouv/backport
18. dbos-inc/dbos-transact-py
19. dbos-inc/dbos-demo-apps (ideas only)

## Approval needed

Reply with the set above, or name the swaps. The likely ones: restore Agentless; put `pixelmatch` in instead of odiff; put `peter-evans/create-pull-request` in instead of `dbos-demo-apps`; drop FastChat as too stale; add the OpenHands GUI back.
