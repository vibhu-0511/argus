"""The four history metrics, from REAL result files only (P10-T09).

Resolve rate with its Wilson 95% interval, tokens per bug (in, out and cached apart), latency (p50, p95) and quota
share per tenant. A number comes from a file or it is a dash with the reason; nothing is estimated or filled in.
The workbench's own runs (SIMULATED, REPLAY) are never read here: this module does not know the run store.

Reuse, nothing copied: the list of result files is the P5 dashboard's (`packages/dashboard/build.py` DEFAULT_FILES,
oldest first; its "made up" fixtures are skipped the way it skips them), each file is checked with
`eval.results.Results`, the interval is `eval.stats.wilson`, and the ledger tenant dimension is the one of
`argus_core.ledger` (`models` is the default tenant, `tenants` holds the others).

Which file backs which metric: the LAST file in the list that has a value for it (the dashboard's "this phase"
rule). Each metric names its file, run id and the number of tasks behind it. Two files are never pooled: they can
be different task sets and different hosts.

ponytail: a metric reads one file, not a merge. The quota share is the tenant's part of the tokens on the ledger's
day; the tenant budgets of P8-T07 are an argument of `Ledger`, not stored in a file, so a share of a budget needs a
budget file first. The ledger file holds one day only (it rolls at UTC midnight).
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from typing import Any

from argus_core.ledger import DEFAULT_TENANT
from eval.results import Results
from eval.stats import wilson
from pydantic import ValidationError

ENV_RESULTS = "ARGUS_WORKBENCH_RESULTS"  # result files separated by os.pathsep; "" means none; unset means the dashboard's list
ENV_LEDGER = "ARGUS_WORKBENCH_LEDGER"  # default .local/quota-ledger.json under the repo root, where the P0 bench writes it
NO_NUMBER_BANNER = "No run id backs any number yet."


def repo_root() -> Path:
    here = Path(__file__).resolve()
    return next((p for p in here.parents if (p / "uv.lock").exists()), Path.cwd())


def default_result_files() -> list[Path]:
    """The dashboard's DEFAULT_FILES, oldest first. Empty if the dashboard module is not in this checkout."""
    build = repo_root() / "packages" / "dashboard" / "build.py"
    if not build.is_file():
        return []
    spec = importlib.util.spec_from_file_location("argus_dashboard_build", build)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # only defines names; its main block is guarded
    return [repo_root() / f for f in module.DEFAULT_FILES]


def result_files() -> list[Path]:
    raw = os.environ.get(ENV_RESULTS)
    if raw is None:
        return default_result_files()
    return [Path(p) for p in raw.split(os.pathsep) if p]


def ledger_path() -> Path:
    raw = os.environ.get(ENV_LEDGER)
    return Path(raw) if raw else repo_root() / ".local" / "quota-ledger.json"


def _label(path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root()).as_posix()
    except ValueError:
        return path.name  # a file outside the repo: the name only, never an absolute path


def load_results(files: list[Path]) -> tuple[list[tuple[str, Results]], list[dict]]:
    """(label, Results) for each file that validates and is not made up; and why each other file was left out."""
    loaded, skipped = [], []
    for path in files:
        label = _label(path)
        try:
            r = Results.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, ValidationError):  # a pydantic error is a ValueError; file missing or not UTF-8 too
            skipped.append({"file": label, "reason": "missing, unreadable or not a results file (schema_version 1)"})
            continue
        if "made up" in (r.run_id + json.dumps(r.agent.model_dump())).lower().replace("made-up", "made up"):
            skipped.append({"file": label, "reason": "labelled made up"})
            continue
        loaded.append((label, r))
    return loaded, skipped


def _dash(reason: str) -> dict:
    return {"value": None, "reason": reason}


def _source(label: str, r: Results, n: int) -> dict:
    return {"file": label, "run_id": r.run_id, "host": r.agent.host, "n": n}


def _last(loaded: list[tuple[str, Results]], has_value) -> tuple[str, Results] | None:
    return next(((label, r) for label, r in reversed(loaded) if has_value(r)), None)


def resolve_rate(loaded: list[tuple[str, Results]]) -> dict:
    hit = _last(loaded, lambda r: r.resolve_rate.total > 0)
    if hit is None:
        return _dash("no result file with scored tasks" if loaded else "no result file")
    label, r = hit
    rr = r.resolve_rate
    low, high = wilson(rr.successes, rr.total)  # eval.stats.wilson, clamped to [0, 1]
    return {
        "value": round(rr.successes / rr.total, 6), "ci_low": round(low, 6), "ci_high": round(high, 6),
        "interval": "wilson95", "successes": rr.successes, "total": rr.total, "source": _source(label, r, rr.total),
    }


def tokens_per_bug(loaded: list[tuple[str, Results]]) -> dict:
    hit = _last(loaded, lambda r: r.tokens.per_task is not None)
    if hit is None:
        return _dash("no result file with scored tasks" if loaded else "no result file")
    label, r = hit
    per = r.tokens.per_task
    return {
        "value": per.tokens_in + per.tokens_out, "tokens_in": per.tokens_in, "tokens_out": per.tokens_out,
        "tokens_cached": per.tokens_cached, "source": _source(label, r, r.resolve_rate.total),
    }


def latency(loaded: list[tuple[str, Results]]) -> dict:
    hit = _last(loaded, lambda r: r.latency_s.p50 is not None)
    if hit is None:
        return _dash("no result file records a latency" if loaded else "no result file")
    label, r = hit
    return {"value": r.latency_s.p50, "p50": r.latency_s.p50, "p95": r.latency_s.p95, "source": _source(label, r, r.latency_s.n)}


def quota_share(path: Path) -> dict:
    """Each tenant's part of the tokens charged on the ledger's day. Needs a tenant other than the default one."""
    if not path.is_file():
        return _dash("no ledger file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        tenants = data.get("tenants") or {}
        if not tenants:
            return _dash("the ledger has no tenant dimension (default tenant only)")
        buckets = {DEFAULT_TENANT: data.get("models") or {}, **tenants}
        rows = [
            {
                "tenant": str(name)[:80],
                "tokens": sum(int(b.get("tokens", 0)) for b in models.values()),
                "requests": sum(int(b.get("requests", 0)) for b in models.values()),
            }
            for name, models in buckets.items()
            if models or name != DEFAULT_TENANT  # no default row when the default tenant made no call
        ]
        day = str(data.get("day"))[:10]
    except (OSError, ValueError, TypeError, AttributeError):
        return _dash("the ledger file could not be read")
    total = sum(r["tokens"] for r in rows)
    if total <= 0:
        return _dash("the ledger has no tokens charged on its day")
    for r in rows:
        r["share"] = round(r["tokens"] / total, 6)
    rows.sort(key=lambda r: (-r["tokens"], r["tenant"]))
    return {"value": total, "day": day, "tenants": rows, "total_tokens": total, "source": {"file": _label(path)}}


def history_metrics() -> dict[str, Any]:
    loaded, skipped = load_results(result_files())
    metrics = {
        "resolve_rate": resolve_rate(loaded), "tokens_per_bug": tokens_per_bug(loaded),
        "latency": latency(loaded), "quota_share": quota_share(ledger_path()),
    }
    backed = any(m["value"] is not None for m in metrics.values())
    return {
        "metrics": metrics,
        "files": [{"file": label, "run_id": r.run_id, "host": r.agent.host, "tasks": r.resolve_rate.total} for label, r in loaded],
        "skipped": skipped,
        "banner": None if backed else NO_NUMBER_BANNER,
    }
