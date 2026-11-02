# Red-team: prompt injection into the fix loop (P7-T07)

Three static cases, one each for the ticket text, a repo file and a skill file. Each plants the same attack text and a fake
canary. The grade is a deterministic check of what the model emitted and what the tools did. There is no generator and no
LLM rubric. Details: `packages/guard/src/guard/redteam.py` (docstring).

Dry run, no model call (stub):

```bash
cd packages/guard/redteam
npx --yes promptfoo@0.125.1 eval -c promptfooconfig.yaml --no-cache
```

Real run against the local Ollama (free, no quota), 5 repeats, one at a time:

```bash
ARGUS_REDTEAM_MODEL=ollama:gemma4:e4b npx --yes promptfoo@0.125.1 eval -c promptfooconfig.yaml --no-cache --repeat 5 -j 1 -o out.json
```

`ARGUS_REDTEAM_HARDENED=1` turns on the P7-T09 mitigations for the same cases. promptfoo is not a dependency of the repo:
`npx` keeps it in its own cache. Set `PROMPTFOO_DISABLE_TELEMETRY=1` to stop it sending usage data.
