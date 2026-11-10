"""The quota meter of the live-run screen: used and cap per model, from the argus-core ledger, or nothing.

Two sources, nothing else, and nothing is invented. With no data the answer is an empty list and the screen shows a dash.

    quota_stop_row(text)       the ledger's own QuotaExceeded text ("{model} would exceed {limit}: {used} of {cap}",
                               argus_core.ledger.QuotaExceeded) parsed back into a row. A scripted quota run gets this
                               from a throwaway ledger the runner built, so the row is ILLUSTRATIVE.
    ledger_rows(now)           today's `tokens_per_day` per model from the machine's ledger file (env
                               ARGUS_WORKBENCH_LEDGER, default <repo>/.local/quota-ledger.json, the file the bench
                               baseline writes) against the caps of docs/quotas.md (`argus_core.ledger.load_quotas`).
                               Used is the sum over the default bucket and every tenant, the way the ledger checks the
                               shared limit. A file from another UTC day, a missing file and an unreadable one give no rows.

The ledger has no provider field; its model key is the `provider/model` name, shown as it is. A model with no row in
docs/quotas.md shows "no quota row", never 0 percent (the spec's edge case).

ponytail: reads the ledger file directly (the `argus_core.ledger` layout: day, models, tenants), because Ledger has no
public read method and argus-core is not ours to change. If that layout changes, `test_meter.py` fails first.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from argus_core.ledger import load_quotas

ENV_LEDGER = "ARGUS_WORKBENCH_LEDGER"
# the QuotaExceeded message shape of argus_core.ledger; a tenant prefix ("tenant x: ...") is allowed
_QUOTA_TEXT = re.compile(r"(?:tenant [^:]+: )?(?P<model>\S+) would exceed (?P<limit>[a-z_.]+): (?P<used>\d+) of (?P<cap>\d+)")


def _repo() -> Path:
    here = Path(__file__).resolve()
    return next((p for p in here.parents if (p / "uv.lock").exists()), Path.cwd())


def ledger_path() -> Path:
    return Path(os.environ.get(ENV_LEDGER) or _repo() / ".local" / "quota-ledger.json")


def row(model: str, limit: str, used: int, cap: int | None, *, illustrative: bool) -> dict:
    pct = None if not cap else min(100, round(used * 100 / cap))
    return {"model": model, "limit": limit, "used": used, "cap": cap, "percent": pct, "over": bool(cap) and used > cap, "illustrative": illustrative}


def quota_stop_row(text: str | None) -> dict | None:
    """The row for a QuotaExceeded message, or None when the text does not have the ledger's shape."""
    match = _QUOTA_TEXT.fullmatch((text or "").strip())
    if match is None:
        return None
    return row(match["model"], match["limit"], int(match["used"]), int(match["cap"]), illustrative=True)


def ledger_rows(now: datetime) -> tuple[list[dict], str]:
    """(rows, note). Rows are empty when there is no usable ledger for today (UTC); the note says why."""
    path = ledger_path()
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        quotas = load_quotas(_repo() / "docs" / "quotas.md")
    except FileNotFoundError:
        return [], "no ledger file on this machine"
    except (OSError, ValueError, KeyError, TypeError):
        return [], "the ledger file or docs/quotas.md could not be read"
    today = now.astimezone(UTC).date().isoformat()
    if not isinstance(state, dict) or state.get("day") != today:
        return [], f"the ledger file is from {state.get('day') if isinstance(state, dict) else 'an unknown day'}, not today ({today} UTC)"
    buckets = [state.get("models") or {}, *(state.get("tenants") or {}).values()]
    used: dict[str, int] = {}
    for models in buckets:
        for model, bucket in models.items():
            used[model] = used.get(model, 0) + int(bucket.get("tokens", 0))
    rows = [row(m, "tokens_per_day", n, quotas[m].tokens_per_day if m in quotas else None, illustrative=False) for m, n in sorted(used.items())]
    return rows, f"today's ledger on this machine ({today} UTC); not the usage of this run" if rows else "the ledger has no calls today"
