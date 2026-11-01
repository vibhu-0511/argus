"""Context strategies. Caps drop the tail. Offload leaves a path. Summary must shrink.

ponytail: the phase cuts a 50_000-character output and does not set the cap or the head
length. 8000 and 200 are prefix sizes, not mini's head-plus-tail. ADR-009 can change them.
"""

from __future__ import annotations

from pathlib import Path

from argus_core.client import Completion
from argus_core.ledger import Ledger
from argus_core.ledger import Usage as LedgerUsage

OUTPUT_CAP = 8_000
HEAD = 200
_MARKER = "\n[truncated]"


class SummaryDidNotShrink(Exception):
    """The cheap-tier summary was not shorter than the turns it replaced."""


def cap_text(text: str) -> str:
    if len(text) <= OUTPUT_CAP:
        return text
    keep = OUTPUT_CAP - len(_MARKER)
    return text[:keep] + _MARKER


def cap_strategy(messages: list[dict], used: int, budget: int) -> list[dict]:
    del used, budget
    if not messages:
        return messages
    last = messages[-1]
    return [*messages[:-1], {**last, "content": cap_text(str(last.get("content") or ""))}]


def offload(text: str, root: Path, name: str) -> str:
    if len(text) <= OUTPUT_CAP:
        return text
    dest = root / ".argus" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8", newline="\n")
    rel = dest.relative_to(root).as_posix()
    return f"{text[:HEAD]}\n[offloaded {rel}]"


def rolling_summary(messages: list[dict], *, complete, ledger: Ledger, model: str) -> list[dict]:
    if len(messages) < 3:
        return messages
    older = "\n".join(str(item.get("content") or "") for item in messages[2:])
    held: dict[str, Completion] = {}

    def send() -> LedgerUsage:
        completion = complete(
            [
                {"role": "system", "content": "Summarize the earlier turns."},
                {"role": "user", "content": older},
            ]
        )
        held["completion"] = completion
        return LedgerUsage(
            completion.usage.tokens_in,
            completion.usage.tokens_out,
            completion.usage.tokens_cached,
        )

    ledger.call(model, send)
    summary = held["completion"].content
    updated = [messages[0], messages[1], {"role": "user", "content": "Summary:\n" + summary}]
    if _chars(updated) >= _chars(messages):
        raise SummaryDidNotShrink()
    return updated


def summary_strategy(complete, ledger: Ledger, model: str):
    def strategy(messages: list[dict], used: int, budget: int) -> list[dict]:
        del used, budget
        return rolling_summary(messages, complete=complete, ledger=ledger, model=model)

    return strategy


def _chars(messages: list[dict]) -> int:
    return sum(len(str(item.get("content") or "")) for item in messages)
