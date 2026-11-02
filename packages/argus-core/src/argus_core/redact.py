"""P7-T03: mask secrets in text that is about to be written (a trajectory line, a span attribute).

Two things are masked: the value of every secret-named environment variable (`KEY`, `TOKEN`, `SECRET`, `PASSWORD`,
`CREDENTIAL` in the name) and every string that has the shape of a token (`TOKEN_SHAPES`). Standard library only, so the
CI scan (`.github/workflows/check_no_secrets.py`) loads this file by path and uses the same shapes.

`guard.redact` re-exports this module. The code lives here because `guard` depends on `fix-loop` and `argus-core`;
`argus_core.types` and `argus_core.telemetry` cannot import `guard` without a cycle.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping

MASK = "***"
MIN_SECRET_LEN = 6  # ponytail: a shorter env value ("ci", "1") would mask ordinary words; same floor as flow.agent_job.scrub
SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", re.IGNORECASE)

# One pattern per shape. GitHub: classic and OAuth/server/refresh tokens, fine-grained PATs, and installation tokens in the
# `ghs_<APPID>_<JWT>` form (the JWT part has `.` and `-`, so it is not covered by the plain `gh[pousr]_` run).
TOKEN_SHAPES = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_.-]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}"),
)
# A URL with a user and token before the host (user:token@host, or token@host): all of it is masked, the host stays.
URL_USERINFO = re.compile(r"(https?://)[^/\s@\"'\\]+@", re.IGNORECASE)


def redact(text: str, env: Mapping[str, str] | None = None) -> str:
    """`text` with every secret-named env value (default `os.environ`) and every token-shaped string replaced by `***`."""
    env = os.environ if env is None else env
    for name, value in env.items():
        if len(value) >= MIN_SECRET_LEN and SECRET_NAME.search(name):
            text = text.replace(value, MASK)
            escaped = json.dumps(value)[1:-1]  # the same value inside a JSON string (a trajectory line)
            if escaped != value:
                text = text.replace(escaped, MASK)
    for shape in TOKEN_SHAPES:
        text = shape.sub(MASK, text)
    return URL_USERINFO.sub(rf"\1{MASK}@", text)
