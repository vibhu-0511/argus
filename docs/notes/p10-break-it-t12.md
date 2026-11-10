# P10-T12 Break it: forged requests

Test: `packages/workbench/tests/test_break_forged.py` (104 tests). No model call, no network, no port.

## Induced failure

A web page on another site, or a DNS-rebinding page whose name now points at 127.0.0.1, sends requests to the workbench in the person's browser:

| Forgery | Sent to |
|---|---|
| no token, empty token, wrong token | every mutating route |
| `Origin: https://evil.example`, `Origin: null` (token present or not) | every mutating route |
| `Host: evil.example` and `evil.example:8765` (token present or not) | every mutating route |
| `Host: evil.example` on GET | `/`, `/api/tabs`, the review, PR, trajectory and report routes, `/static/app.js`, an unknown path |
| a request with `Origin: https://evil.example` | any route, looking for an `Access-Control-*` header |
| an OPTIONS preflight from `https://evil.example` asking for POST with `x-workbench-token` | decision, PR, review, `/api/runs`, `/api/tabs`, `/` |

"Every mutating route" is the explicit list issue create (`POST /api/runs`), start, decision approve, decision reject, retry (a decision with `request-changes`), raise PR, plus every POST, PUT, PATCH or DELETE route the routers declare. On this branch the issue-create and start routes are not merged yet (groups issue and runner); a guard answers before routing, so those two requests are refused by the guard all the same, and when the integrator merges the routes the same cases hit them without an edit.

## Expected signal

- 403 and the typed body `{"error": {"code", "field", "message"}}` with code `token_required`, `origin_not_allowed` or `host_not_allowed`.
- Nothing changes: the test reads every file under the run store root and the mock GitHub request log before the request and compares them after (bytes, not just names). A forged retry creates no new run folder.
- No `Access-Control-*` header on any response to a foreign Origin, the Origin is not echoed, and a preflight gets 403, 404 or 405, never a 200 or 204 a browser would read as "allowed". The app has no CORS middleware.
- The token never appears in an error body.
- Control: the same decision requests with the token and a good Host return 200 and do change the store, and a second app with another token refuses the first app's token.

## Observed

Clean build: `104 passed`.

Mutated builds (one change each, the original bytes written back after each run; `git status` showed the file clean afterwards):

| Mutation | File | Result | First failing assertion |
|---|---|---|---|
| token check removed (`if not sent or not hmac.compare_digest(...)` made `if False`) | `security.py` | 20 failed, 84 passed | `POST decision approve`, `no token`: `assert 200 == 403`; the decision was written |
| Host check removed | `security.py` | 52 failed, 52 passed | `POST decision approve`, `dns rebinding host`: `assert 200 == 403`; GET with a foreign Host answered 200 |
| Origin check removed | `security.py` | 19 failed, 85 passed | `POST decision approve`, `wrong origin` (token present): `assert 200 == 403` |
| permissive CORS added (`CORSMiddleware(allow_origins=["*"], ...)`) | `server.py` | 8 failed, 96 passed | `assert ['access-control-allow-origin'] == []` on a GET with a foreign Origin; every preflight case also fails; the middleware list test fails |

Each mutation is also caught by a test of the matching name, not only by luck of the shared routes: the token mutation is caught by the "no token", "empty token", "wrong token" cases and by the second-app test, the Host mutation by the GET and preflight cases, the Origin mutation by the "wrong origin" and "null origin" cases and by the forged-retry folder count, the CORS mutation by the header and preflight cases.

## Fix

None needed: the guards from T02 held. This task adds the test that keeps them holding. The defence is the per-start token in `X-Workbench-Token` (not accepted from a URL, body or cookie), the Host allow-list (127.0.0.1 or localhost, optional port) and the Origin allow-list for unsafe methods, all in `security.py`, and no CORS middleware at all.

## Not defended (said plainly)

Another program or user on the same machine can read the index, get the token and send valid requests; there is no login (ADR-031). A server bound to something other than 127.0.0.1 is outside this model.

Proof command: `uv run --all-packages python -m pytest packages/workbench/tests/test_break_forged.py -q`
