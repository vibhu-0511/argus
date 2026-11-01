# ADR-005: When to include the screenshot in ticket context

Status: accepted (P1-T12).

## Context

The P1 ablation asks whether attaching the ticket screenshot raises repro success enough to pay for its tokens and quota. Variant A is ticket text only. Variant B attaches the ticket image once, not a new screenshot on each revision.

Both rows are the saved batches in `packages/repro-agent/runs/text-only/` and `packages/repro-agent/runs/text-plus-image/`. The model name is `openai/gpt-oss-20b` in both. The task set is the same 30 seeded directories. `host` is `fixture`: the reply is recorded in the runner, and neither batch calls a provider. The tree outcome is that same recorded runner. It is not a browser session against each task's own UI.

One seeded ticket has a screenshot: BUG-17, `shots/radar-card.png`, 103536 bytes, media type `image/png`. The other 29 tickets have no image, so variant B attaches nothing for them.

## Decision

Text is the default. Do not attach the screenshot.

The table in `phases/P01-repro-agent.md` is the evidence. Both variants are `28/30 [0.786762, 0.981523]`. Attaching the BUG-17 image did not change a verdict. The ledger charge stayed 1 token in, 1 token out, and 0 cached per task, so the quota share stayed one request per task, which is 1/1000 of the measured daily cap. Latency was not measured. The $-equivalent stays "—" until P5-T11.

That is the cost recorded here: 103536 image bytes on the one ticket that has a shot, and no gain in valid verdicts. A later live run can overturn this rule if its valid rate rises enough to pay for those bytes.

## Alternatives

- Always attach the image. This batch shows no change in verdicts, so the bytes are spent for nothing.
- Never store a screenshot on the ticket. BUG-17 already has one. The rule is about the prompt, not about deleting the file.

## Consequences

The phase report uses the text-only row as this phase. Variant B stays in the ablation table. Image mode still exists, and it still refuses a file whose bytes do not match the declared media type before any model call.
