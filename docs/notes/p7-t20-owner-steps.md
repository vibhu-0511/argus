# P7-T20 owner steps: use the App token to push to the default branch, for real

Only you can do these. They create a GitHub App, which needs your GitHub login, and a private key, which must never go in a file in the repo, a chat or a commit. The script that does the actual test is built and tested against a mock (`packages/flow/src/flow/app_push_check.py`, `packages/flow/tests/test_app_push_check.py`, 6 tests). It has **not** been run against GitHub.

The task is done when the real refusal is recorded: the push to the default branch is refused with a 403 or a protection error. Until then the box in `TASKS.md` stays unticked.

Screen names below are from the GitHub docs and from memory; GitHub changes them. If a name differs, follow the docs link, not this page.

## What you need

- A **throwaway repository** `OWNER/argus-p7-t20-scratch` with at least one commit on `main`. If protection turns out to be off, the test adds one empty commit to `main`; that is why it must be a throwaway.
- A second repository `OWNER/argus-p7-t20-other` (private is best) on which the App will **not** be installed.
- 15 minutes.

## 1. Create the App

GitHub, Settings, Developer settings, GitHub Apps, New GitHub App ([docs](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)).

| Field | Value |
|---|---|
| Name | anything unique, for example `argus-p7-t20-test` |
| Homepage URL | any URL (the repo URL is fine) |
| Webhook | untick Active (no webhook is needed for this test) |
| Repository permissions | Metadata: Read-only (GitHub sets this itself). Contents: Read and write. Pull requests: Read and write. Issues: Read and write. **Nothing else.** This is the list in `docs/notes/p7-t04-app-permissions.md`, section 1 |
| Account and organization permissions | none |
| Where can this GitHub App be installed | Only on this account |

Create it. Note the **App ID** (a number on the App's page). Under "Private keys", generate a private key: a `.pem` file downloads. Keep it out of the repo.

## 2. Install it on the throwaway repository only

On the App's page, Install App, choose your account, then "Only select repositories" and pick `argus-p7-t20-scratch`. After installing, the address bar shows `.../settings/installations/<NUMBER>`: that number is the **installation ID**.

## 3. Turn on protection for `main` of the throwaway repository

Settings of that repository, Rules (rulesets) or Branches ([docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)). Protect `main` so that it cannot be updated directly: "require a pull request before merging" (classic rule), or in a ruleset the rules "Restrict updates" and "Require a pull request before merging". Do **not** add the App, and do not add yourself as a bypass actor. Whether a repository admin is also bound ("Do not allow bypassing" / "Include administrators") does not matter for the App's token, but the note should say which you chose.

Write down which kind you used (classic branch protection or ruleset), because the status and text of the refusal may differ.

## 4. Run the test

PowerShell, from the repo root. The three variables are the only place the key is held; nothing is written to disk.

```powershell
$env:ARGUS_GITHUB_APP_ID = "<the App ID>"
$env:ARGUS_GITHUB_APP_INSTALLATION_ID = "<the installation ID>"
$env:ARGUS_GITHUB_APP_PRIVATE_KEY = Get-Content -Raw "C:\path\to\the-key.pem"
uv run --all-packages python -m flow.app_push_check --repo OWNER/argus-p7-t20-scratch --other-repo OWNER/argus-p7-t20-other --throwaway-repo --out packages/guard/results/app-push-real.json
```

What it does (it prints every request and GitHub's answer, never the token):

1. lists the repositories the token sees: expected exactly the scratch repo;
2. makes an empty commit object on top of `main`;
3. tries to move `main` to it with a normal (not force) ref update: **expected 403 or 422 with a protection message**;
4. control: creates a probe branch (expected 201) and deletes it (expected 204), to show the token works;
5. tries a write on the other repository (a ref with a made-up sha that creates nothing): expected 403 or 404.

The last line of the result is `verdict`. Exit code 0 means `as expected`.

If the verdict says `NOT PROTECTED`, step 3 moved `main` (one empty commit) and your protection is not working: fix the rule, remove the extra commit if you care, and run it again.

## 5. Record it

- Commit `packages/guard/results/app-push-real.json` (it holds status codes and GitHub's messages, no token). Check it with `grep -i ghs_ packages/guard/results/app-push-real.json` first: it must print nothing.
- Add the real status and message to the T20 section of `docs/notes/p7-break-its.md` (replace "MOCK ONLY"), say which protection kind you used, and note that the mock's guess (403 or 422) was or was not right.
- Tick `P7-T20` in `TASKS.md` and remove "Mock only" from the guard README row.
- Optional, once: run it with protection switched off on the scratch repo, to see the control (`NOT PROTECTED`, `main` moves). It shows that only protection, not the token, keeps `main` safe.

## 6. Clean up

Delete the key file. On the App's page, delete the private key, then uninstall the App or delete it. Delete the two scratch repositories if you do not need them. Nothing in this test is needed afterwards.

## What this will and will not show

- Shows: GitHub's real answer to a non-force ref update on a protected `main` with a token that has Contents: write; that the token sees one repository only; that a write on a repository outside the installation is refused.
- Does not show: the real App for the pipeline (the production App can reuse the same manifest later); that every protection style behaves the same; the token's behaviour after its hour is up.
