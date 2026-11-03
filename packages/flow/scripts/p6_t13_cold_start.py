"""P6-T13: time a signed `ping` webhook against the Render service after it has gone to sleep.

For each idle gap the script waits (or, with `--confirm`, waits for the owner to say the dashboard
shows the service suspended), sends one correctly signed `ping` to `<url>/webhook`, and records the
seconds until the response. A ping names no ticket, so the handler answers 202 `ignored` at once
(`flow.webhook`); the time measured is therefore the cold start of the web service, not of Neon or
DBOS. Right after, a second ping on the now-warm service gives a baseline. The verdict per try is
about GitHub's 10 s delivery timeout: `ok` (202 in under 10 s), `slow` (202, 10 s or more), `error`
(any other status) or `no-answer` (connection error or the client timeout).

Run, with the owner's service:

    ARGUS_FLOW_SERVICE_URL=https://<name>.onrender.com GITHUB_WEBHOOK_SECRET=<same as on Render> \\
        uv run --all-packages python packages/flow/scripts/p6_t13_cold_start.py --gaps 1200,1200,1200,1800,3600

Writes `packages/flow/results/p6-t13/results.json` (raw timings plus a summary) and prints the markdown
table for `docs/notes/p6-render.md`. Steps and what to copy back: docs/notes/p6-t13.md.

The secret is read from the environment and used only to sign; it is never printed or written. Nothing
here has been run against a real service: the unit tests use a fake transport (`test_cold_start.py`).

ponytail: whether the service is really asleep is not observable from outside. The gap defaults to
20 minutes (Render's documented sleep is after 15 minutes without inbound traffic, p6-t00-versions.md);
a fast "cold" try (a few hundred ms) means the service was still awake, so read the table with the
Render dashboard's events beside it, or use `--confirm`.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import statistics
import sys
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

URL_ENV = "ARGUS_FLOW_SERVICE_URL"
SECRET_ENV = "GITHUB_WEBHOOK_SECRET"
WEBHOOK_TIMEOUT_SECONDS = 10.0  # GitHub gives up on a delivery after this long (phase file, P6-T13)
CLIENT_TIMEOUT_SECONDS = 90.0  # longer than Render's documented "about one minute" cold start, so a slow wake is a number, not an error
DEFAULT_GAP_SECONDS = 1200.0
RESULTS = Path(__file__).resolve().parent.parent / "results" / "p6-t13" / "results.json"
PING_BODY = json.dumps({"zen": "Keep it logically awesome.", "hook_id": 0}).encode()

# (url, headers, body, timeout_seconds) -> HTTP status; raises TransportError when there is no answer.
Transport = Callable[[str, dict[str, str], bytes, float], int]


class TransportError(Exception):
    """No HTTP answer: connection failed, reset, or the client timeout ran out."""


def sign(secret: str, body: bytes) -> str:
    """`X-Hub-Signature-256` value for `body`, the same HMAC `flow.webhook.verify_signature` checks."""
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def ping_headers(secret: str, body: bytes = PING_BODY) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-GitHub-Event": "ping",
        "X-GitHub-Delivery": str(uuid.uuid4()),
        "X-Hub-Signature-256": sign(secret, body),
    }


def httpx_transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> int:
    try:
        return httpx.post(url, headers=headers, content=body, timeout=timeout).status_code
    except httpx.HTTPError as e:
        raise TransportError(type(e).__name__) from None


def verdict(status: int | None, seconds: float) -> str:
    if status is None:
        return "no-answer"
    if status != 202:
        return "error"
    return "ok" if seconds < WEBHOOK_TIMEOUT_SECONDS else "slow"


def timed_ping(
    transport: Transport, webhook_url: str, secret: str, *, clock: Callable[[], float] = time.perf_counter, timeout: float = CLIENT_TIMEOUT_SECONDS
) -> dict:
    """One signed ping: `{status, seconds, verdict[, error]}`. `seconds` is the time until the answer or the failure."""
    status, error = None, None
    start = clock()
    try:
        status = transport(webhook_url, ping_headers(secret), PING_BODY, timeout)
    except TransportError as e:
        error = str(e)
    seconds = clock() - start
    row = {"status": status, "seconds": round(seconds, 3), "verdict": verdict(status, seconds)}
    if error:
        row["error"] = error
    return row


def run_tries(
    transport: Transport,
    base_url: str,
    secret: str,
    gaps: list[float],
    *,
    wait: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.perf_counter,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    on_try: Callable[[int, dict], None] = lambda i, row: None,
) -> list[dict]:
    """For each gap: `wait(gap)`, a cold ping, then a warm ping. `wait` is `time.sleep` or the owner prompt."""
    webhook_url = base_url.rstrip("/") + "/webhook"
    tries = []
    for i, gap in enumerate(gaps, 1):
        wait(gap)
        started = now().isoformat(timespec="seconds")
        cold = timed_ping(transport, webhook_url, secret, clock=clock)
        warm = timed_ping(transport, webhook_url, secret, clock=clock)
        tries.append({"try": i, "idle_gap_seconds": gap, "started_at": started, "cold": cold, "warm": warm})
        on_try(i, tries[-1])
    return tries


def summarize(tries: list[dict]) -> dict:
    """Counts of each verdict and the spread of the cold times. Medians and maxima are over the cold pings that got an answer."""
    cold = [t["cold"] for t in tries]
    answered = [c["seconds"] for c in cold if c["status"] is not None]
    verdicts = {v: sum(c["verdict"] == v for c in cold) for v in ("ok", "slow", "error", "no-answer")}
    return {
        "tries": len(tries),
        "cold_verdicts": verdicts,
        "cold_seconds_min": min(answered, default=None),
        "cold_seconds_median": round(statistics.median(answered), 3) if answered else None,
        "cold_seconds_max": max(answered, default=None),
        "gaps_over_10s": sorted({t["idle_gap_seconds"] for t in tries if t["cold"]["verdict"] != "ok"}),
        "all_within_10s": bool(tries) and all(c["verdict"] == "ok" for c in cold),
    }


def markdown_table(tries: list[dict]) -> str:
    rows = ["| Try | Idle gap (s) | Cold: HTTP | Cold: seconds | Cold: verdict | Warm: seconds |", "|---|---|---|---|---|---|"]
    for t in tries:
        c, w = t["cold"], t["warm"]
        rows.append(f"| {t['try']} | {t['idle_gap_seconds']:g} | {c['status'] or c.get('error', '-')} | {c['seconds']:g} | {c['verdict']} | {w['seconds']:g} |")
    return "\n".join(rows)


def build_results(tries: list[dict], base_url: str, started_at: str) -> dict:
    return {
        "task": "P6-T13",
        "started_at": started_at,
        "service_host": urlsplit(base_url).netloc,
        "webhook_timeout_seconds": WEBHOOK_TIMEOUT_SECONDS,
        "client_timeout_seconds": CLIENT_TIMEOUT_SECONDS,
        "event": "ping",
        "summary": summarize(tries),
        "tries": tries,
    }


def owner_confirms(gap: float) -> None:
    input(f"Render dashboard shows argus-flow as suspended/sleeping (idle >= {gap:g} s)? Press Enter to send the ping. ")


def sleep_for(gap: float) -> None:
    print(f"waiting {gap:g} s ...", flush=True)
    time.sleep(gap)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--gaps", default=",".join([f"{DEFAULT_GAP_SECONDS:g}"] * 5), help="comma separated idle gaps in seconds, one try each")
    p.add_argument("--confirm", action="store_true", help="instead of sleeping for each gap, wait for Enter once the owner sees the service asleep")
    p.add_argument("--out", type=Path, default=RESULTS)
    args = p.parse_args(argv)
    base_url, secret = os.environ.get(URL_ENV, ""), os.environ.get(SECRET_ENV, "")
    if not base_url.startswith("https://") or not secret:
        print(f"set {URL_ENV} (https://...) and {SECRET_ENV}", file=sys.stderr)
        return 2
    gaps = [float(g) for g in args.gaps.split(",") if g.strip()]
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    tries = run_tries(
        httpx_transport, base_url, secret, gaps,
        wait=owner_confirms if args.confirm else sleep_for,
        on_try=lambda i, t: print(f"try {i}: cold {t['cold']['seconds']:g} s {t['cold']['verdict']}, warm {t['warm']['seconds']:g} s", flush=True),
    )
    results = build_results(tries, base_url, started_at)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(markdown_table(tries))
    print(json.dumps(results["summary"], indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
