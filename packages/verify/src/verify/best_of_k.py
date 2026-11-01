"""Pick one patch from k candidates. Checks run first. The judge does not override a pass."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from verify.pipeline import Verdict


@dataclass
class UsageLedger:
    rows: list[dict] = field(default_factory=list)

    def add(self, index: int, tokens_in: int, tokens_out: int, tokens_cached: int) -> None:
        self.rows.append(
            {
                "candidate": index,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "tokens_cached": tokens_cached,
            }
        )


@dataclass(frozen=True)
class Candidate:
    index: int
    patch: str
    verdict: Verdict
    judge_label: str | None
    tokens_in: int
    tokens_out: int
    tokens_cached: int


@dataclass(frozen=True)
class Selection:
    selected: Candidate | None
    candidates: tuple[Candidate, ...]
    reason: str


def best_of_k(
    k: int,
    *,
    draw: Callable[[int], tuple[str, tuple[int, int, int]]],
    verify: Callable[[str], Verdict],
    judge: Callable[[str], str],
    ledger: UsageLedger,
) -> Selection:
    if k < 1:
        raise ValueError("k must be at least 1")
    candidates: list[Candidate] = []
    for index in range(k):
        patch, usage = draw(index)
        tokens_in, tokens_out, tokens_cached = usage
        ledger.add(index, tokens_in, tokens_out, tokens_cached)
        verdict = verify(patch)
        label = None if not verdict.ok else judge(patch)
        candidates.append(Candidate(index, patch, verdict, label, tokens_in, tokens_out, tokens_cached))
    passing = [item for item in candidates if item.verdict.ok]
    if not passing:
        return Selection(None, tuple(candidates), "checks-fail")
    preferred = next((item for item in passing if item.judge_label == "pass"), None)
    if preferred is not None and any(item.judge_label not in {None, "pass"} for item in passing):
        return Selection(preferred, tuple(candidates), "checks-pass; judge preferred pass")
    chosen = preferred or passing[0]
    if chosen.judge_label not in {None, "pass"}:
        return Selection(chosen, tuple(candidates), "checks-pass; judge did not override")
    return Selection(chosen, tuple(candidates), "checks-pass")
