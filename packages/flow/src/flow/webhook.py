"""GitHub webhook endpoint: verify the HMAC signature, accept the delivery (P6-T05).

GitHub signs the raw request body with HMAC-SHA256 and sends it as
`X-Hub-Signature-256: sha256=<hex>`. The secret comes from the environment
variable `GITHUB_WEBHOOK_SECRET` and is read per request, so it is never held
in a file, a module constant or a log line. No secret configured -> the
endpoint fails closed (401 for every request).

Architecture: docs/architecture/p6.md.
"""
import hashlib
import hmac
import os

from fastapi import FastAPI, HTTPException, Request

SECRET_ENV = "GITHUB_WEBHOOK_SECRET"
SIGNATURE_HEADER = "X-Hub-Signature-256"


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


def create_app() -> FastAPI:
    app = FastAPI(title="argus-flow webhook")

    @app.post("/webhook", status_code=202)
    async def webhook(request: Request) -> dict[str, str]:
        await verified_body(request)
        return {"status": "accepted"}

    return app
