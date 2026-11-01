# T2 — UI repro and DOM-to-source

Read-only review of the pinned clones against Argus P1 and P2. No competitor code was run, imported, or tested. `locate()` and the repro loop stay [ME]. Entries below change acceptance text or an ADR. Hours are 0 unless an entry says otherwise: no new task, no library.

Pins:

| Repo | SHA | Licence |
|---|---|---|
| microsoft/playwright | `f9a841f968dd9a4e315df2ec2930da1952971667` | Apache-2.0 |
| microsoft/playwright-mcp | `0c4107acbecb75472b23c05c0e42471a0011874f` | Apache-2.0 |
| browser-use/browser-use | `2cc71890e65056b67fdb29d98bb407749c15bb08` | MIT |
| zh-lx/code-inspector | `6235e8a97a484237b7308e13d7d700e5e7f3fea4` | MIT |

Playwright tool implementations do not sit next to `packages/playwright/src/agents/`. `@playwright/mcp` `index.js` re-exports `playwright-core`. Schemas below are the generated README plus the tests that call them. This playwright-mcp tree does not contain the string `2026-07-28` (search of the clone). code-inspector `packages/core/src` does not mention `_debugSource`.

## Entries

### T2-01 Loop success is a passing script

- Topic: ticket-to-script. What the generate/revise loop treats as success.
- Their approach: The healer’s job is to make the test pass. The prompt has no fail-on-bug condition. [CODE] https://github.com/microsoft/playwright/blob/f9a841f968dd9a4e315df2ec2930da1952971667/packages/playwright/src/agents/playwright-test-healer.agent.md#L51-L55

```
You will continue this process until the test runs successfully without any failures or errors.
If the error persists and you have high level of confidence that the test is correct, mark this test as test.fixme()
so that it is skipped during the execution.
Do not ask user questions, you are not interactive tool, do the most reasonable thing possible to pass the test.
```

Docs describe the same loop, with an undefined “guardrail”: [DOCS] https://github.com/microsoft/playwright/blob/f9a841f968dd9a4e315df2ec2930da1952971667/docs/src/test-agents-js.md#L196-L213
- Argus plan: `phases/P01-repro-agent.md`, task P1-T07. “Loop stops on success, on cap or on `QuotaExceeded`, and records a stop reason.” The phase goal says the script fails on the buggy tree and passes on the golden tree, but T07 does not define success that way. T08 (the verifier) depends on T07, so the loop can ship first. P1-T14 later says to feed `passes-on-bug` back. Hours: 0. One sentence on T07: exit 0 on the buggy tree is not success, and a `test.fixme()` / skip is not success.
- Evidence: [CODE] and [DOCS].
- Licence: Apache-2.0.
- Affected: P1-T07, P1-T08, P1-T14. Not ADR-004.

### T2-02 Healer retry cap is not a number, and the escape hatch is skip

- Topic: retry caps.
- Their approach: Same healer file. Remediation includes loosening locators with regular expressions, then skip. [CODE] https://github.com/microsoft/playwright/blob/f9a841f968dd9a4e315df2ec2930da1952971667/packages/playwright/src/agents/playwright-test-healer.agent.md#L36-L56

```
- Updating selectors to match current application state
- Fixing assertions and expected values
- For inherently dynamic data, utilize regular expressions to produce resilient locators
- You will continue this process until the test runs successfully without any failures or errors.
- If the error persists ... mark this test as test.fixme()
Never wait for networkidle or use other discouraged or deprecated apis
```

No integer cap appears in that prompt or in `playwright-test-heal.prompt.md` (the prompt is “Run all my tests and fix the failing ones.”).
- Argus plan: `phases/P01-repro-agent.md`, Break it, vague ticket. “Expected signal: the retry cap is hit, stop reason `retry-cap`, no valid script.” The integer cap is not specified. P1-T08’s verdicts are `valid`, `passes-on-bug`, `fails-on-golden`, `error`. Skip is not named. A skipped script does not fail on the buggy tree. Hours: 0. Name the cap in T07. Map skip/fixme to `error` with the reason visible in the trajectory. Do not copy regex-locator healing.
- Evidence: [CODE]. Exit code of a skipped Playwright test: not verified in the allowed paths.
- Licence: Apache-2.0.
- Affected: P1-T07, P1-T08, P1-T13, P1-T14.

### T2-03 The script is a transcript of a live tool log

- Topic: ticket-to-script generation.
- Their approach: The generator runs each step, then writes the file from the log. [CODE] https://github.com/microsoft/playwright/blob/f9a841f968dd9a4e315df2ec2930da1952971667/packages/playwright/src/agents/playwright-test-generator.agent.md#L33-L47

```
- Run the `generator_setup_page` tool to set up page for the scenario
- For each step and verification in the scenario, do the following:
  - Use Playwright tool to manually execute it in real-time.
- Retrieve generator log via `generator_read_log`
- Immediately after reading the test log, invoke `generator_write_test`
- Always use best practices from the log when generating tests.
```

A click on snapshot ref `e2` is recorded as a role locator, not the ref. [CODE] https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/tests/click.spec.ts#L39-L48

```
arguments: { element: 'Submit button', target: 'e2' }
code: `await page.getByRole('button', { name: 'Submit' }).click();`,
```

Docs: the generator “verifies selectors and assertions live”. [DOCS] https://github.com/microsoft/playwright/blob/f9a841f968dd9a4e315df2ec2930da1952971667/docs/src/test-agents-js.md#L131-L134
- Argus plan: `phases/P01-repro-agent.md`, Goal. “Turn a ticket (text, optionally a screenshot) into a Playwright reproduction script that fails on the buggy tree and passes on the golden-fixed tree.” T07 says “generate script, run it, revise on error”, which is the other order. Hours: 0. T07 should say the saved script uses the logged locator (role/name), not the ephemeral ref, and that a symptom assertion is in the script before the loop can stop. Borrow the log shape. Do not replace the loop.
- Evidence: [CODE] and [DOCS].
- Licence: Apache-2.0.
- Affected: P1-T04, P1-T07, P1-T14.

### T2-04 `assert-visible` is not on the default MCP tool list

- Topic: tool schemas.
- Their approach: Default `listTools` includes `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`, `browser_take_screenshot`, and `browser_run_code_unsafe`. It does not include `browser_verify_*`. [CODE] https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/tests/capabilities.spec.ts#L19-L47

Verify tools are “opt-in via `--caps=testing`”. `browser_verify_element_visible` takes `role` and `accessibleName`, not a CSS selector. [DOCS] https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/README.md#L1604-L1625

```
Test assertions (opt-in via --caps=testing)
browser_verify_element_visible
- `role` (string)
- `accessibleName` (string)
```

The generator agent lists those verify tools; the default server does not. [CODE] https://github.com/microsoft/playwright/blob/f9a841f968dd9a4e315df2ec2930da1952971667/packages/playwright/src/agents/playwright-test-generator.agent.md#L19-L22
- Argus plan: `phases/P01-repro-agent.md`, P1-T04. “Define repro tool schemas (navigate, snapshot, click, type, assert-visible, screenshot).” `PROJECT.md` Shared types lists the same six names. Neither says the stock server hides assertions behind a capability flag, nor that visibility is role + accessible name. Hours: 0. T01’s go/no-go lists the tool names actually returned. T04’s `assert-visible` schema is role + accessible name (or an explicit unique locator), and a non-unique match is a typed error, not a click on the first node.
- Evidence: [CODE] and [DOCS].
- Licence: Apache-2.0.
- Affected: P1-T01, P1-T04, P1-T14, ADR-004.

### T2-05 Stale targets must be errors, and tool errors are markdown plus `isError`

- Topic: flaky selectors and error shapes.
- Their approach: The test client parses a markdown body. `isError` is the MCP flag; a section titled `Error` is separate. [CODE] https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/tests/fixtures.ts#L250-L265

```
const error = sections.get('Error');
const code = sections.get('Ran Playwright code');
const isError = response.isError;
```

No `*.spec.ts` under this clone asserts `isError`. A concrete error string from the server: not verified.

browser-use looks up a numeric index and, if the node is gone, returns text with no `error` field. [CODE] https://github.com/browser-use/browser-use/blob/2cc71890e65056b67fdb29d98bb407749c15bb08/browser_use/tools/service.py#L713-L718

```
node = await browser_session.get_element_by_index(params.index)
if node is None:
    msg = f'Element index {params.index} not available - page may have changed. Try refreshing browser state.'
    return ActionResult(extracted_content=msg)
```

`ActionResult.error` defaults to `None` (`browser_use/agent/views.py`). Consecutive-failure counting only increments when `last_result[-1].error` is set (`service.py` around the single-action check). A stale index can reset the failure counter.
- Argus plan: `phases/P01-repro-agent.md`, P1-T04. “Each tool has a typed schema, a description and a typed error result.” The error catalog is not specified. Hours: 0. Add `stale-target` and `not-unique` as errors. A missing element is not a successful tool result. Assertion failure on the buggy tree is not one of those errors (see T2-01).
- Evidence: [CODE]. Sample MCP error prose: not verified.
- Licence: Apache-2.0 (Playwright MCP), MIT (browser-use).
- Affected: P1-T04, P1-T07, P1-T15.

### T2-06 Snapshots are the action surface, and they blow the context window

- Topic: tool schema and quota.
- Their approach: README tells the model not to act from pixels, and warns that MCP loads large accessibility trees. [DOCS] https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/README.md#L3-L16

```
interact with web pages through structured accessibility snapshots, bypassing the need for screenshots
CLI invocations are more token-efficient: they avoid loading large tool schemas and verbose accessibility trees
Deterministic tool application. Avoids ambiguity common with screenshot-based approaches.
```

`browser_snapshot` parameters include optional `depth`. `browser_take_screenshot` says actions must use the snapshot. [DOCS] https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/README.md#L1103-L1117

The planner prompt says not to take screenshots unless necessary. [CODE] https://github.com/microsoft/playwright/blob/f9a841f968dd9a4e315df2ec2930da1952971667/packages/playwright/src/agents/playwright-test-planner.agent.md#L37-L40

browser-use caps serialized clickable elements at 40000 characters by default. [CODE] https://github.com/browser-use/browser-use/blob/2cc71890e65056b67fdb29d98bb407749c15bb08/browser_use/agent/service.py#L211
- Argus plan: `phases/P01-repro-agent.md`, P1-T04 lists `snapshot` and `screenshot` with no size cap. `PROJECT.md` Models: Groq free tier “200k tokens/day per model.” Hours: 0. T04: snapshot accepts a depth or a byte cap; screenshot is not an action input. ADR-005 stays about the ticket image, not a per-step screenshot.
- Evidence: [DOCS] and [CODE].
- Licence: Apache-2.0 and MIT.
- Affected: P1-T04, P1-T06, ADR-005.

### T2-07 Default MCP server exposes an unsafe eval tool

- Topic: what a “go” on ADR-004 actually turns on.
- Their approach: Default tool list includes `browser_run_code_unsafe` (T2-04 citation). README: “Unsafe: executes arbitrary JavaScript in the Playwright server process and is RCE-equivalent.” [DOCS] https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/README.md#L1082-L1084

“Playwright MCP is **not** a security boundary.” [DOCS] https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/README.md#L824

The planner agent’s tool list includes `playwright-test/browser_run_code_unsafe`. [CODE] https://github.com/microsoft/playwright/blob/f9a841f968dd9a4e315df2ec2930da1952971667/packages/playwright/src/agents/playwright-test-planner.agent.md#L20
- Argus plan: `phases/P01-repro-agent.md`, P1-T05. “the container cannot reach the internet.” That blocks egress. It does not allow-list tools. ADR-004 is “Playwright MCP vs direct Playwright as tool.” Hours: 0. ADR-004: a go uses an allow-list of the six repro tools. `browser_run_code_unsafe` stays off. Direct Playwright does not grow a `page.evaluate` tool in P1 either.
- Evidence: [CODE] and [DOCS].
- Licence: Apache-2.0.
- Affected: P1-T01, P1-T04, P1-T05, ADR-004.

### T2-08 This pin does not say it speaks MCP 2026-07-28

- Topic: spec currency for the P1-T01 spike.
- Their approach: Package version is `0.0.83`, dependency is Playwright `1.64.0-alpha-1790635538000`, devDependency `@modelcontextprotocol/sdk` `^1.25.2`. [CODE] https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/package.json#L2-L44

`server.json` points at the registry card schema dated 2025-12-11, which is not a protocol revision. [CODE] https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/server.json#L1-L3

`index.js` is only `createConnection: tools.createConnection` from `playwright-core`. [CODE] https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/index.js#L18-L19

The test client is constructed with name and version only. [CODE] https://github.com/microsoft/playwright-mcp/blob/0c4107acbecb75472b23c05c0e42471a0011874f/tests/fixtures.ts#L95

The Playwright clone at the review SHA reports `"version": "1.65.0-next"`. [CODE] https://github.com/microsoft/playwright/blob/f9a841f968dd9a4e315df2ec2930da1952971667/package.json#L4

Handshake `protocolVersion` returned by this server: not verified (implementation is outside this repo, in `playwright-core`).
- Argus plan: `PLAN.md` and `PROJECT.md`, versions checked on 2026-10-01. “Playwright 1.63.0 (bundles MCP)”, “`@playwright/mcp` 0.0.83”, “MCP spec **2026-07-28**”. P1-T01: “written go/no-go … with exact versions.” Risk 4 already says 2026-07-28 support is unconfirmed. Hours: 0. T01 records the `initialize` protocol version and the tool list from the spike process. Do not copy schemas from this 1.65-next / 1.64-alpha tree onto the 1.63.0 row until T00 re-checks them. The 2026-10-01 table is not what these SHAs are.
- Evidence: [CODE]. Protocol the server speaks: not verified.
- Licence: Apache-2.0.
- Affected: P1-T00, P1-T01, P1-T03, P2-T00, ADR-004.

### T2-09 Their step cap lets the model declare success on the last turn

- Topic: retry caps and stop reasons.
- Their approach: `run(max_steps: int = 500)` and `max_failures: int = 5`. On the last step the only tool is `done`, and the model sets `success`. [CODE] https://github.com/browser-use/browser-use/blob/2cc71890e65056b67fdb29d98bb407749c15bb08/browser_use/agent/service.py#L173

[CODE] https://github.com/browser-use/browser-use/blob/2cc71890e65056b67fdb29d98bb407749c15bb08/browser_use/agent/service.py#L2521-L2523

[CODE] https://github.com/browser-use/browser-use/blob/2cc71890e65056b67fdb29d98bb407749c15bb08/browser_use/agent/service.py#L1571-L1574

```
msg = 'You reached max_steps - this is your last step. Your only tool available is the "done" tool.'
msg += 'If the task is not yet fully finished as requested by the user, set success in "done" to false!'
```

The loop stops on consecutive failures or on `n_steps` past `max_steps` (`service.py` `run`, the `while self.state.n_steps <= max_steps` block). Loop detection injects a nudge. It is not the stop condition. Empty model output gets one extra LLM call, then a synthetic `done` with `success: False` (`_get_model_output_with_retry`).
- Argus plan: `phases/P01-repro-agent.md`, P1-T07. “Loop stops on success, on cap or on `QuotaExceeded`, and records a stop reason.” The cap integer is not specified. P1-T13 expects `retry-cap` and no valid script. Hours: 0. The stop reason on cap is `retry-cap`, recorded by the loop, not a `success` flag the model fills in. Empty output counts toward the cap. Do not adopt 500.
- Evidence: [CODE].
- Licence: MIT.
- Affected: P1-T07, P1-T13.

### T2-10 Element re-find takes the first accessible-name hit

- Topic: flaky selectors.
- Their approach: History replay walks exact hash, stable hash (dynamic classes removed), xpath, accessible name, then id/name/aria-label. Accessible name keeps the first node of that tag. [CODE] https://github.com/browser-use/browser-use/blob/2cc71890e65056b67fdb29d98bb407749c15bb08/browser_use/agent/service.py#L3564-L3569

[CODE] https://github.com/browser-use/browser-use/blob/2cc71890e65056b67fdb29d98bb407749c15bb08/browser_use/agent/service.py#L3643-L3652

```
# Level 4: ax_name ... Match by node type and accessible name
if elem.node_name.lower() == hist_name and elem_ax_name == hist_ax_name:
    highlight_index = idx
    break
```

Stable hash drops transient classes. [CODE] https://github.com/browser-use/browser-use/blob/2cc71890e65056b67fdb29d98bb407749c15bb08/browser_use/dom/views.py#L834-L841
- Argus plan: `phases/P01-repro-agent.md`, P1-T14. “Induced failure: a selector so loose that it matches in both trees. Expected signal: verifier verdict `passes-on-bug`.” The plan does not say a generated locator must be unique on the page. Hours: 0. T04/T14: two matches is a typed `not-unique` error during generation. The verifier still catches a locator that is unique on the page and still passes on the bug. Do not add their hash cascade to the repro loop.
- Evidence: [CODE].
- Licence: MIT.
- Affected: P1-T04, P1-T14.

### T2-11 Vision defaults on, separate from the ticket screenshot

- Topic: multimodal cost.
- Their approach: `use_vision: bool | Literal['auto'] = True`. When it is not `'auto'`, the screenshot *tool* is removed, which is not the same as omitting images from the prompt. [CODE] https://github.com/browser-use/browser-use/blob/2cc71890e65056b67fdb29d98bb407749c15bb08/browser_use/agent/service.py#L170

[CODE] https://github.com/browser-use/browser-use/blob/2cc71890e65056b67fdb29d98bb407749c15bb08/browser_use/agent/service.py#L319-L325
- Argus plan: `phases/P01-repro-agent.md`, Ablation. “A = ticket text only; B = ticket text plus screenshot.” P1-T06: “a snapshot test shows the image is attached only in image mode.” That covers the ticket image. It does not say the revise loop must not attach a fresh screenshot every step. Hours: 0. T07/T06: per-step screenshots are off unless variant B, and variant B attaches the ticket image, not a new shot each revision. ADR-005 cites that distinction.
- Evidence: [CODE].
- Licence: MIT.
- Affected: P1-T06, P1-T07, P1-T10, P1-T11, ADR-005.

### T2-12 Call site is a build-time prop, and multi-root refuses to guess

- Topic: wrapper-component ambiguity. React 19 / `_debugSource` is the plan’s reason; this repo does not mention `_debugSource`.
- Their approach: Every JSX element gets `data-insp-path` unless it is an escape tag (`fragment`, `suspense`, `script`, `style`, …). [CODE] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/core/src/server/transform/transform-jsx.ts#L101-L120

[CODE] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/core/src/shared/constant.ts#L1-L25

A component root prefers the caller’s prop and falls back to the definition. The comment in source: the call site wins, otherwise the definition. [CODE] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/core/src/server/transform/transform-jsx.ts#L153-L154

[CODE] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/core/src/server/transform/transform-jsx.ts#L858-L865

```
const addition = ` ${PathName}={${propExpression} || ${JSON.stringify(
  getNodePathValue(filePath, node, nodeName),
)}}`
```

Propagation runs only when the estimated root count is ≤ 1. A fragment with two element children returns 2 and is not rewritten. [CODE] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/core/src/server/transform/transform-jsx.ts#L636-L641

[CODE] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/core/src/server/transform/transform-jsx.ts#L723-L734

One JSX element counts as one root, including the element inside `.map()`. Repeated clones share one path. There is no runtime stack read.
- Argus plan: `phases/P02-dom2src.md`, P2-T08. “For a wrapper-rendered button, locate() returns an `ambiguous` result with at least 2 ranked candidates and the call stack hint.” P2-T15: “the DOM node's `data-src` points at the wrapper definition.” `PLAN.md` versions: “React 19.2 removed `source`/`self` from `jsxDEV`, so a build-time `data-src` attribute is the only robust route.” The plan never says the plugin records the call site. A runtime “call stack hint” is the thing ADR-006 says React 19 removed. Hours: 0. P2-T02 emits both the host definition and the JSX call site (two fields, or the element plus its caller). `locate()` stays the [ME] tool and returns `ambiguous` with those candidates. Do not copy `prop || definition`: that leaves one path and fails P2-T15. P2-T08 splits repeated elements (same `file:line`, many nodes) from a wrapper (two source locations). A single-root wrapper is still ambiguous, because the bug may be in the wrapper or at the call site.
- Evidence: [CODE]. That they did this because of React 19: not verified in this repo.
- Licence: MIT.
- Affected: P2-T02, P2-T05, P2-T08, P2-T15, ADR-006.

### T2-13 The attribute string is not `file:line:col`, and “relative” depends on git

- Topic: source locations under Vite, and what `locate()` parses.
- Their approach: Value is `filePath:line:(column + 1):nodeName`. [CODE] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/core/src/server/transform/transform-jsx.ts#L1072-L1074

```
const { line, column } = node.loc.start;
return `${filePath}:${line}:${column + 1}:${nodeName}`;
```

`transformCode` defaults `pathType` to `'relative'`. [CODE] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/core/src/server/transform/index.ts#L27-L42

Relative means strip the git toplevel, raw `git rev-parse --show-toplevel`, via string replace of `ProjectRootPath + '/'`. If git fails, the root is `''` and the path stays absolute. [CODE] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/core/src/server/server.ts#L60-L70

[CODE] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/core/src/server/server.ts#L87-L101

`normalizePath` turns `\` into `/` before that replace. Whether Windows `git rev-parse` output matches that slash: not verified (not executed). The English doc comment says the default `absolute` “means the path is relative to the project root”, which disagrees with the Chinese comment and with the `'relative'` default in `transformCode`. [DOCS] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/core/src/shared/type.ts#L497-L500
- Argus plan: `phases/P02-dom2src.md`, Done when. “a `data-src="file:line:col"` attribute”. Column base, tag suffix, and absolute vs repo-relative are not specified. Hours: 0. P2-T02’s sample transform asserts repo-relative posix `file:line:col` with no tag suffix, and no machine prefix if git toplevel lookup fails. P2-T05’s parser accepts only that shape.
- Evidence: [CODE] and [DOCS]. Windows git output: not verified.
- Licence: MIT.
- Affected: P2-T02, P2-T03, P2-T05, ADR-006.

### T2-14 Production “stripping” is “plugin does not run”, and transform errors are silent

- Topic: stripping attributes from production, and test vs dev builds.
- Their approach: The Vite plugin applies only when `isDev(options.dev, command === 'serve')` and `close` is false. [CODE] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/vite/src/index.ts#L113-L115

`isDev(true, …)` forces on, including when the command is not serve. Only an explicit `false` forces off. [CODE] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/core/src/shared/utils.ts#L115-L128

```
if (dev === false) {
  return false;
}
return dev || systemDev;
```

So `vite build` omits the plugin (attributes never exist). There is no strip pass. `dev: true` injects into a production build. `transformCode` catches errors and returns the original source. [CODE] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/core/src/server/transform/index.ts#L72-L73
- Argus plan: `phases/P02-dom2src.md`, Done when. “in test/dev builds and strips it from production builds (both asserted by tests on all 6 target-app routes).” Which Vite command is the test build is not specified. A `vite build` used as the test build would have zero attributes under their `apply` hook, and P2-T03 would fail for the wrong reason. Hours: 0. P2-T03 names the commands (dev server and the test build carry `data-src`; `vite build` for production does not). The plugin is absent from the production config, not toggled by `dev: true`. A transform exception fails the unit test. It is not swallowed into “no attribute”. P2-T16 stays `no-source-info` on a production bundle.
- Evidence: [CODE].
- Licence: MIT.
- Affected: P2-T02, P2-T03, P2-T16, ADR-006.

### T2-15 The transform must see JSX, and the plugin only warns if it is ordered wrong

- Topic: Vite plugin order, including the React oxc plugin name they know about.
- Their approach: If `code-inspector` is registered after `@vitejs/plugin-react`, `@vitejs/plugin-react-swc`, or `@vitejs/plugin-react-oxc` (`vite:react-oxc:config`), it logs a warning. It does not reorder. [CODE] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/vite/src/index.ts#L18-L31

[CODE] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/vite/src/index.ts#L80-L94

Whether Argus `target-app` uses `@vitejs/plugin-react-oxc`: not verified (that app is outside this review’s paths).
- Argus plan: `PLAN.md` versions. “Vite 8.3 (Rolldown-based).” P2-T02: “a unit test checks a sample file's transform output.” That unit test calls the transform directly, so it stays green if the Vite pipeline already compiled JSX away. The route Playwright test is P2-T03. Hours: 0. P2-T02 acceptance adds: the plugin is registered before the JSX transform, and the route test (P2-T03) is the check that the running app still has `data-src`. ADR-006 records that order, not only “attribute vs source map”.
- Evidence: [CODE]. target-app plugin id: not verified.
- Licence: MIT.
- Affected: P2-T02, P2-T03, ADR-006.

### T2-16 Their Vite plugin also injects a client and a local server

- Topic: what not to copy into `dom2src-plugin`.
- Their approach: `transformIndexHtml` injects a `<script type="module">` client. `skipSnippets` can skip `htmlScript`. [CODE] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/vite/src/index.ts#L221-L236

The options type says the server is on by default, including for “code location”, and can be closed “when building online only to view the dom path.” [DOCS] https://github.com/zh-lx/code-inspector/blob/6235e8a97a484237b7308e13d7d700e5e7f3fea4/packages/core/src/shared/type.ts#L516-L518

`getProjectRoot` shells out to git during module init (`server.ts`, T2-13).
- Argus plan: `phases/P02-dom2src.md`, Goal. “Map a rendered DOM element back to its source file and line, expose that as a `locate()` MCP tool.” No client script and no companion HTTP server are specified. Hours: 0. P2-T02 is the attribute transform only. P2-T03 asserts the production build has neither `data-src` nor that client script. `locate()` stays the Python MCP tool.
- Evidence: [CODE] and [DOCS].
- Licence: MIT.
- Affected: P2-T02, P2-T03, P2-T07, ADR-006.

## Lessons from their issue tracker

`gh search --state all` is rejected (the flag allows only `open` or `closed`). Counts below are from the GitHub search API, queried separately for open and closed, sorted by comments and by reactions. Titles and counts are from those responses. Bodies were read only where a lesson needed them.

- [Screenshot tool returns corrupted image data causing permanent API error 400](https://github.com/microsoft/playwright-mcp/issues/1211) (closed, 30 comments, 6 reactions): a `browser_take_screenshot` payload was labeled `image/jpeg` and did not match, and the caller’s next API request stayed a 400. Argus plan: not specified. P1-T06 checks that the ticket image is attached only in image mode. It does not require the bytes to match the media type, or that a bad image is a typed tool error instead of a burned model call.
- [the snapshot length is too long, add pagination to it](https://github.com/microsoft/playwright-mcp/issues/395) (closed, 8 comments, 14 reactions): a full-page snapshot hit the model token limit. Argus plan: not specified. This pin’s README adds an optional `depth` (T2-06). P1-T04 still has no cap.
- [Browser is already in use … use --isolated](https://github.com/microsoft/playwright-mcp/issues/769) (closed, 25 comments): a shared `mcp-chrome-profile` directory blocks a second instance, including after a crash. Argus plan: not specified. P1-T05 checks egress. It does not give each run its own user-data-dir, so a dead server can wedge P1-T10’s next task.
- [MCP server exits with code 1 when a page event listener throws](https://github.com/microsoft/playwright-mcp/issues/1803) (open, 2 comments; top open issue returned for this repo): an exception in client dispatch exits the server. Argus plan: `phases/P01-repro-agent.md`, P1-T15 covers an induced kill during a tool call (“tool-unavailable stop reason within the timeout”). A page listener that exits the process between calls is not specified.
- [有计划支持选择组件的层级么？](https://github.com/zh-lx/code-inspector/issues/250) (closed, 5 comments, 2 reactions): the request is to pick the hovered node or an ancestor, as click-to-react-component does. Argus plan: P2-T08 / P2-T15 already require `ambiguous` candidates and a “call stack hint”. How that chain is captured after `_debugSource` is not specified (T2-12).
- [[turbopack/next16] 插件交互注入失败](https://github.com/zh-lx/code-inspector/issues/584) (open, 5 comments) and [nextjs 15.4.5 turbopack runtime error](https://github.com/zh-lx/code-inspector/issues/366) (closed, 18 comments): the client injection breaks when the bundler changes. Argus plan: ADR-006 asks which mapping “survives React 19 and a bundler change”, which guards the attribute-vs-sourcemap decision. A client runtime is not specified as out of scope (T2-16).
- [fix(core): prevent inspector server from keeping processes alive](https://github.com/zh-lx/code-inspector/pull/590) (open, 2 comments, 2 reactions): their locator server outlives the build. Argus plan: not specified. P2 should not start that server. `locate()` is the MCP tool.
- [feat: improved navigate to URL event logic and wait mechanism](https://github.com/browser-use/browser-use/pull/3549) (merged, 46 comments; highest comment count returned for that repo): navigation waits on `networkIdle` with a load fallback. Argus plan: not specified. P1-T04’s `navigate` has no load-state. Playwright’s healer prompt forbids `networkidle` (T2-02). Do not copy this wait.
- [Too strict dependency version pinning](https://github.com/browser-use/browser-use/issues/4824) (open, 10 comments, 5 reactions; top open issue by reactions for that repo): `==` pins break consumers. Argus plan: guarded. `analysis/CONSTRAINTS.md` item 3: the repro loop and `locate()` stay [ME], so this library is not a dependency.

microsoft/playwright’s top search hits are not the test agents. Highest returned: [BDD implementation](https://github.com/microsoft/playwright/issues/11975) (closed, 180 comments, 632 reactions) and [real mobile device browsers](https://github.com/microsoft/playwright/issues/1122) (open, 75 comments, 664 reactions). Neither is a P1 or P2 task. Agent lessons are on playwright-mcp, above.

## Not verified

- The protocol version this `@playwright/mcp` build speaks (`playwright-core` is not in the allowed tree).
- A sample `### Error` body (parser only).
- Playwright’s exit code for `test.fixme()`.
- Windows `git rev-parse` slash style against `getRelativePath`.
- `target-app`’s Vite React plugin id.
- That code-inspector’s prop rewrite was written because of React 19.
