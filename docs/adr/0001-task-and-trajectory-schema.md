# ADR-001: Task and Trajectory schema

Status: accepted (P0-T04).

## Context

A bench item has to be reproducible, and a run has to be replayable with no model call. Later phases add tools, stop reasons, and a JSONL recorder. The fields have to be fixed before those phases, or each one will invent its own file.

## Decision

`argus-core` defines three pydantic models, and the JSON Schema files under `packages/argus-core/schemas/` are exported from those models. A test fails if a file drifts from the model.

- **Ticket.** `id`, `text`, and an optional screenshot. The screenshot is a media type plus a relative path. The path cannot be absolute and cannot contain `..`. Bytes stay in the task directory.
- **Task.** `id`, the ticket, `bug_patch`, `golden_patch`, a non-empty `checks` list, and `meta`. `meta.source` is `seeded` or `mutated`. `meta.tier` is `easy`, `medium`, or `hard`. `meta.archetype` stays an open string until the six names in `docs/bug-archetypes.md` are worth closing. `meta.seed` is set for a mutated task. A check type is `pixel_diff`, `bounding_box`, or `computed_style`, with a free `params` object.
- **Trajectory.** `meta` (run id, task id, model, host, seed, prompt hash, git commit) plus `steps`. Each step has `tokens_in`, `tokens_out`, and `tokens_cached`. An omitted cache field parses as 0. `raw_response` and `message` are stored on the step, so replay reads the file. A rejected tool call is still a step. The JSONL form starts with `{"kind":"meta",...}` and then one step per line.

`stop_reason` is a closed enum: `submit`, `step-cap`, `token-cap`, `QuotaExceeded`, `stuck`, `consecutive-timeout`, `retry-cap`. Those are the reasons P1 and P3 already name. Unknown fields are rejected.

## Alternatives

- Hand-written JSON Schema, separate from the parser. The file and the code would drift the first time a field is added.
- An open string for `stop_reason`. A typo would become a new reason and split the counts.
- Screenshot bytes inside the ticket JSON. The file is already on disk, and a bad image is checked when it is used (P1-T06).
- One JSON document per trajectory and no JSONL. P3-T08 writes one JSONL record per step, including a rejected tool call.

## Consequences

Adding a check type or a stop reason is a change to this schema and its test. Cached tokens are their own field and are never added into `tokens_in`. A task directory (P0-T10) is valid against this Task schema only after the checks fail on the buggy tree and pass on the golden tree. The schema does not prove that. The scorer does.
