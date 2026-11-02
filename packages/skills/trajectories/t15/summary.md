Computed from the stored trajectory.jsonl files in this folder (tokens are chars/4 estimates of the messages). `scorer` is rescore.json; verdict.json says excluded for all 8 because node modules were missing in the run worktree (see docs/notes/p5.5-break-its.md).

| arm | task | scorer | steps | tokens in | tokens out | skills loaded | T04 no-skills steps / in |
|---|---|---|---|---|---|---|---|
| real5 | mut-0190 | resolved | 4 | 5836 | 98 | 1: css-value-changed-in-existing-rule | 3 / 2442 |
| real5 | mut-0206 | resolved | 4 | 6122 | 111 | 1: css-value-changed-in-existing-rule | 3 / 2471 |
| real5 | mut-0001 | resolved | 5 | 9555 | 144 | 1: svg-transform-box-missing | 5 / 8204 |
| real5 | mut-0005 | resolved | 5 | 13687 | 155 | 1: svg-transform-box-missing | 4 / 9474 |
| plus-any | mut-0190 | resolved | 4 | 5968 | 98 | 1: css-value-changed-in-existing-rule | 3 / 2442 |
| plus-any | mut-0206 | resolved | 4 | 6244 | 108 | 1: css-value-changed-in-existing-rule | 3 / 2471 |
| plus-any | mut-0001 | resolved | 5 | 9718 | 144 | 1: svg-transform-box-missing | 5 / 8204 |
| plus-any | mut-0005 | resolved | 5 | 13850 | 155 | 1: svg-transform-box-missing | 4 / 9474 |

| arm | steps | tokens in | tokens out | skills loaded (sum over 4 runs) |
|---|---|---|---|---|
| real5 | 18 | 35200 | 508 | 4 |
| plus-any | 18 | 35780 | 505 | 4 |
| T04, no skills | 15 | 22591 | 457 | 0 |
