"""GitHub webhook endpoint: verify the HMAC signature, treat the event as a hint (P6-T05, P6-T06).

GitHub signs the raw request body with HMAC-SHA256 and sends it as
`X-Hub-Signature-256: sha256=<hex>`. The secret comes from the environment
variable `GITHUB_WEBHOOK_SECRET` and is read per request, so it is never held
in a file, a module constant or a log line. No secret configured -> the
endpoint fails closed (401 for every request).

After the signature check the event is only a hint: the handler reads the
event type and delivery id from the headers, derives the ticket id from the
payload, schedules `enqueue_reconcile(ticket_id)` to run after the response is
sent, and returns 202. It makes no GitHub call and waits for nothing, so it
answers well inside GitHub's 10 s timeout. See `flow.enqueue` for the workflow
id contract. Architecture: docs/architecture/p6.md.
"""
import hashlib
import hmac
import json
import logging
import os

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from flow.enqueue import Enqueuer, HintDedup

SECRET_ENV = "GITHUB_WEBHOOK_SECRET"
SIGNATURE_HEADER = "X-Hub-Signature-256"
EVENT_HEADER = "X-GitHub-Event"
DELIVERY_HEADER = "X-GitHub-Delivery"

log = logging.getLogger("flow.webhook")


def verify_signature(secret: str | None, body: bytes, header: str | None) -> bool:
    """True only for a configured secret and a header that matches the body's HMAC."""
    if not secret or not header:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


async def verified_body(request: Request) -> bytes:
    """Read the raw body and return it only if the signature holds, else raise 401."""
    body = await request.body()
    if not verify_signature(os.environ.get(SECRET_ENV), body, request.headers.get(SIGNATURE_HEADER)):
        raise HTTPException(status_code=401, detail="invalid signature")
    return body


def ticket_id_of(payload: dict) -> str | None:
    """`owner/repo#number` from an issue or pull-request payload, else None.

    ponytail: an event with no issue or PR number (ping, push, workflow_run) names
    no ticket, so it is acknowledged and not enqueued; the poller (P6-T07) covers
    it. A PR number is used as given; mapping a PR back to its ticket is the poller's job.
    """
    repo = (payload.get("repository") or {}).get("full_name")
    number = (payload.get("issue") or payload.get("pull_request") or {}).get("number")
    return f"{repo}#{number}" if repo and number else None


def create_app(enqueuer: Enqueuer, dedup: HintDedup | None = None) -> FastAPI:
    app = FastAPI(title="argus-flow webhook")
    dedup = dedup if dedup is not None else HintDedup()

    def enqueue(ticket_id: str, delivery_id: str | None) -> None:
        try:
            enqueuer.enqueue_reconcile(ticket_id)
        except Exception:
            if delivery_id:
                dedup.forget(delivery_id)  # let GitHub's redelivery through
            log.exception("enqueue failed for %s", ticket_id)

    @app.post("/webhook", status_code=202)
    async def webhook(request: Request, background: BackgroundTasks) -> dict[str, str]:
        body = await verified_body(request)
        event = request.headers.get(EVENT_HEADER, "")
        delivery_id = request.headers.get(DELIVERY_HEADER)
        try:
            payload = json.loads(body)
        except ValueError:
            raise HTTPException(status_code=400, detail="body is not JSON")
        ticket_id = ticket_id_of(payload) if isinstance(payload, dict) else None
        if ticket_id is None:
            return {"status": "ignored", "event": event}
        if delivery_id and not dedup.first_time(delivery_id):
            return {"status": "duplicate", "event": event, "ticket": ticket_id}
        background.add_task(enqueue, ticket_id, delivery_id)
        return {"status": "accepted", "event": event, "ticket": ticket_id}

    return app
