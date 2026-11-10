"""Check `.argus.yml` when an issue arrives (P8-T22). A bad or missing config becomes a comment, never a crash or a guess.

`check_config(client, ticket_id, read_text)` is the first step of intake:

    read_text() -> the text of `.argus.yml` at the repo root, or None when the file is not there
    valid       -> the `TenantConfig` is returned and nothing is posted
    not valid   -> ONE comment on the issue names every problem (`argus_app.config` typed errors), `None` is returned,
                   and the caller starts nothing: no repro, no fix, no label, no branch

No fallback exists on purpose: a missing `test` is not replaced by `npm test` or `pytest`. Argus would run a command the
tenant never chose, on the tenant's minutes, and report a verdict about it.

The comment goes out through the flow write client's `post_comment` (P6), which finds its hidden key marker first, so a
second label event with the same problem posts nothing new. The key holds a hash of the problem text: a different
problem is a new comment. The text comes from the tenant's own file (a route, an unknown field name), so it is shown
inside a code block with backticks removed and passed through `argus_core.redact`.

ponytail: the caller reads the file (T08 intake); this module has no GitHub read of its own. Only the first 10 problems and
300 characters of each are shown.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Protocol

from argus_core.redact import redact

from argus_app.config import FILENAME, ConfigError, ConfigNotFoundError, Problem, TenantConfig, load_config_text

ONBOARDING = "docs/onboarding.md in vibhu-0511/argus"
_MAX_PROBLEMS, _MAX_LINE = 10, 300


class Commenter(Protocol):
    """The one call used from `flow.github_write.HttpGitHubClient`."""

    def post_comment(self, ticket_id: str, key: str, body: str) -> None: ...


def config_error_comment(error: ConfigError) -> str:
    """The text posted for a config error. Pure: no GitHub, no environment beyond the redactor's secret list."""
    shown = list(error.problems[:_MAX_PROBLEMS])
    lines = [f"{FILENAME}: {p.message}"[:_MAX_LINE].replace("`", "'") for p in shown]
    if len(error.problems) > len(shown):
        lines.append(f"... and {len(error.problems) - len(shown)} more")
    body = (
        f"Argus did not start on this issue: `{FILENAME}` is not usable.\n\n"
        "```text\n" + "\n".join(lines) + "\n```\n\n"
        "Nothing was run, and Argus did not guess a missing value. "
        f"Fix the file in the repository root and label the issue again. Fields and an example: {ONBOARDING}."
    )
    return redact(body)


def _key(ticket_id: str, error: ConfigError) -> str:
    digest = hashlib.sha256("\n".join(p.message for p in error.problems).encode()).hexdigest()[:12]
    return f"argus:config-error:{ticket_id}:{digest}"


def check_config(client: Commenter, ticket_id: str, read_text: Callable[[], str | None]) -> TenantConfig | None:
    """The tenant config, or None after a comment that says what is wrong. Raises only if reading or posting fails."""
    text = read_text()
    try:
        if text is None:
            raise ConfigNotFoundError([Problem("", "not-found", f"file not found (add {FILENAME} to the repository root)")])
        return load_config_text(text)
    except ConfigError as error:
        client.post_comment(ticket_id, _key(ticket_id, error), config_error_comment(error))
        return None
