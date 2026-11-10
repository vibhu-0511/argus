# P8-T02 GitHub App manifest: owner steps

Date: 2026-11-10. **Done: the App is registered (id 5699242, slug `argus-fixer`) and `P8-T02` is ticked.** The registration ran from `manifest --form` in a browser; GitHub accepted the localhost redirect. Lessons from the run: (1) sign in to GitHub before you click, or GitHub drops the manifest and shows an empty form; (2) in PowerShell use `$env:NAME = ...`, `curl.exe` and `Set-Clipboard -Value (python -c ...)`; `print | clip` adds a line break and the webhook secret then fails with 401. The text below is the original plan, written for Git Bash.

## What is built

| Item | Where |
|---|---|
| The manifest, with three `{{NAME}}` placeholders | `packages/app/src/argus_app/manifest.json` |
| Loader, validator, form page, `run` | `packages/app/src/argus_app/manifest.py` |
| Sub-command `argus-app manifest [--form]` | `packages/app/src/argus_app/cli.py` (4 lines) |
| Tests, including the comparison with ADR-026 | `packages/app/tests/test_manifest.py` |

Permissions (exactly the list in ADR-026 and `docs/notes/p7-t04-app-permissions.md`): Actions write, Contents write, Issues write, Pull requests write, Metadata read. The loader refuses the manifest unless `default_permissions` equal `flow.app_token.MINIMUM`, and a test reads the table in ADR-026 and fails if the file has one more, one less or a higher level.

Events subscribed: `issues`, `pull_request`, `pull_request_review`, `pull_request_review_comment` (the list in `packages/flow/README.md` step 6; the P6 webhook handles the last two as `/argus approve` and `/argus reject`). Installation events are sent to an App anyway.

Webhook URL: `<ARGUS_FLOW_SERVICE_URL>/webhook`, the route of the P6 flow service. **No URL is committed.** `packages/flow/README.md` says the service ran on Render at `https://argus-flow.onrender.com` on 2026-11-03 with `/health` answering; this note did not re-check it. Use the URL shown at the top of the Render service page.

Decision to confirm: the manifest sets `"public": true`, because tenants install the App on their own repositories (P8). ADR-026 and the P7 test App said "Only on this account"; that was for one repository. If you want to start private, change `public` to `false` in `manifest.json` (an App can be made public later in its settings, from memory).

## Steps

Run in Git Bash from the repository root. The `argus-app` program file is blocked by Windows Application Control on this machine (error 4551), so the commands use `python -c`, which works.

1. **Pick the three values** (no secret among them):
   - `ARGUS_FLOW_SERVICE_URL`: the Render service URL, `https://...onrender.com`, no trailing slash.
   - `ARGUS_APP_HOMEPAGE_URL`: the App homepage, an `https://` URL (the repository URL is fine).
   - `ARGUS_APP_REDIRECT_URL`: where GitHub sends you after you create the App. The loader allows `http://localhost:8765/` (nothing needs to listen there; the browser will say it cannot connect, and the address bar then holds `?code=...&state=...`). **Not verified** that GitHub accepts a localhost redirect for the manifest flow; if it refuses, use any `https://` page you control.

2. **Write the registration page** (the `state` is printed to the terminal; keep it for step 4):

   ```bash
   export ARGUS_FLOW_SERVICE_URL=https://<your-service>.onrender.com ARGUS_APP_HOMEPAGE_URL=https://github.com/<owner>/<repo> ARGUS_APP_REDIRECT_URL=http://localhost:8765/
   uv run --all-packages python -c "from argus_app.cli import main; import sys; sys.exit(main(['manifest', '--form']))" > "$TEMP/argus-app-form.html"
   ```

   To look at the JSON instead, leave out `'--form'`. A missing variable is named in the error.

3. **Register.** Sign in to GitHub in the browser as the account that should own the App, then open `$TEMP/argus-app-form.html` and click **Create the GitHub App**. GitHub shows the App name (`argus-fixer`) and the permissions. Check that the permission list is the five rows above and nothing else, then confirm. If the name is taken, edit `"name"` in `manifest.json` and redo step 2. This is GitHub's manifest step 1 (a form post to `https://github.com/settings/apps/new`).

4. **Read the code.** GitHub redirects to your redirect URL. In the address bar copy `code=` and check that `state=` is the one printed in step 2. You have **one hour** from the start of the flow to finish step 5 (docs).

5. **Convert the code** (GitHub's step 3). The answer holds the private key and the webhook secret, so it is written to a file outside the repository, nothing is printed, and the file is deleted in step 6:

   ```bash
   curl -s -X POST -H "Accept: application/vnd.github+json" "https://api.github.com/app-manifests/<CODE>/conversions" > "$TEMP/argus-app-conv.json"
   python -c "import json,os;d=json.load(open(os.environ['TEMP']+'/argus-app-conv.json'));print('app id', d['id'], 'slug', d['slug'])"
   ```

   The first call works once per code. If it prints an error, run the registration again (step 2 to 4).

6. **Put the secrets into Render only** (Render dashboard, the service, **Environment**; from memory):
   - `ARGUS_GITHUB_APP_ID`: the id printed above. Not secret.
   - `ARGUS_GITHUB_APP_PRIVATE_KEY`: copy the key to the clipboard without printing it, paste it into Render, then clear the clipboard:

     ```bash
     python -c "import json,os;print(json.load(open(os.environ['TEMP']+'/argus-app-conv.json'))['pem'])" | clip
     ```

   - `GITHUB_WEBHOOK_SECRET`: same way, with `['webhook_secret']`. The flow service holds **one** secret (ADR-026), so this replaces the secret of the old repository webhook; delete that webhook (repository Settings, Webhooks) so GitHub does not keep sending signed-with-the-old-secret events that get 401.
   - Clear the clipboard (`echo off | clip`), delete `$TEMP/argus-app-conv.json` and `$TEMP/argus-app-form.html`, and restart the service. `render.yaml` has no entries for the new variables yet (`sync: false` is needed); that edit belongs to P8-T03 or the owner.
   - Never paste the key or the secret into chat, a ticket, a commit or a command line.

7. **Check.** On the App page (GitHub, Settings, Developer settings, GitHub Apps; from memory) the permission list must equal ADR-026. After the service is up, the App's **Advanced** tab, **Recent deliveries**, should show a `ping` answered 202 (`ignored`, as the flow README says); a 401 means the secret differs from `GITHUB_WEBHOOK_SECRET`.

8. **Delete the old P7-T20 test App** (App ID 5589921, created for `docs/notes/p7-break-its.md` T20): GitHub, Settings, Developer settings, GitHub Apps, the test App, **Advanced**, **Delete GitHub App** (from memory). Also delete its downloaded `.pem` if one is left, remove any Render or local variable that holds its key, and delete the two scratch repositories `vibhu-0511/argus-p7-t20-scratch` and `vibhu-0511/argus-p7-t20-other` if you no longer need them. Do this after step 7 so the real App is working first. The P7-T20 result file in the repository stays as the record.

9. **Tick.** Tick `P8-T02` in `TASKS.md` only if step 3 registered the App from the manifest and step 7 shows the permission list equals ADR-026 and the webhook delivery is answered. Record the date and the App id (not the key) in `docs/architecture/p8.md`.

## What was not done or not verified

- The App was not registered. The manifest flow, the localhost redirect, the name `argus-fixer` being free, the `public: true` choice and GitHub's answer to the permission list are all untested.
- Which keys GitHub's manifest page accepts beyond the ones it lists: the model rejects unknown keys, and every key in the file is on the page read on 2026-11-03.
- The installation flow and token minting for tenants are P8-T03; this task only creates the App definition.
