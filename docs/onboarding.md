# Use Argus on your repo

Argus fixes an issue by opening a pull request. The work runs in your repo, on your GitHub Actions minutes, with your own model key. Nothing runs on Argus servers except opening the pull request.

## 1. Add the workflow

Save this as `.github/workflows/argus.yml` (five lines):

```yaml
on: {issues: {types: [labeled]}}
jobs:
  argus:
    uses: vibhu-0511/argus/.github/workflows/argus-reusable.yml@main
    secrets: {ARGUS_MODEL_API_KEY: "${{ secrets.ARGUS_MODEL_API_KEY }}"}
```

Pin `@main` to a tag or a commit once you trust a version.

## 2. Add `.argus.yml` to the repo root

```yaml
start: npm run dev
test: npm test
routes:
  - /
  - /login
budget:
  max_tokens: 200000
  max_steps: 20
```

| Field | Meaning |
|---|---|
| `start` | Command that starts the app. Run in the repo root |
| `test` | Command that runs your tests. Exit 0 means pass |
| `routes` | Paths that must answer once the app is up |
| `budget` | Most model tokens and agent steps one issue may use |
| `base_url` | Optional. Where the app listens, localhost only. Default `http://127.0.0.1:3000` |

Every field is required except `base_url`. An unknown field or a wrong type is refused, and the error names the field.

Your commands run on a bare Ubuntu runner: Node and Python are there, your dependencies are not. Put the install in the command, for example `npm ci && npm test`.

## 3. Add the secret and install the App

- Repository secret `ARGUS_MODEL_API_KEY`: your own model key.
- Install the Argus GitHub App on the repo (it opens the branch and the pull request).

## 4. Label an issue `argus`

The workflow runs repro, fix and verify. The fix step is the only one that sees your key. Read the run log under Actions.
