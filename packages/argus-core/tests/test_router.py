import httpx
import pytest

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota, QuotaExceeded
from argus_core.prices import load_prices
from argus_core.router import ROUTING_PATH, Policy, Router, UnknownStage, load_policy
from argus_core.types import TrajectoryStep


class StubClient:
    def __init__(self, name: str, fail: Exception | None = None):
        self.name = name
        self.fail = fail
        self.calls: list[str] = []

    def complete(self, model: str, messages: list[dict]) -> Completion:
        self.calls.append(model)
        if self.fail is not None:
            raise self.fail
        return Completion(f"from {self.name}", Usage(10, 2, 0), {})


def _quota(**overrides) -> ModelQuota:
    fields = dict(requests_per_day=10, tokens_per_day=1000, requests_per_minute=10, tokens_per_minute=1000, cached_counts=False)
    fields.update(overrides)
    return ModelQuota(**fields)


def _router(tmp_path, quotas, clients):
    return Router(load_policy(), Ledger(tmp_path / "ledger.json", quotas), clients)


def _all_quotas(**overrides):
    policy = load_policy()
    models = {r.model for t in policy.tiers.values() for r in (t.primary, t.fallback) if r}
    return {m: _quota(**overrides) for m in models}


def test_policy_is_read_from_the_data_file():
    policy = load_policy()
    assert policy.stages == {"repro": "cheap", "localize": "cheap", "fix": "strong"}
    assert policy.tiers["cheap"].primary.model != policy.tiers["strong"].primary.model
    assert ROUTING_PATH.suffix == ".yaml"


def test_editing_the_file_moves_a_stage_without_code_change(tmp_path):
    path = tmp_path / "routing.yaml"
    path.write_text(ROUTING_PATH.read_text(encoding="utf-8").replace("fix: strong", "fix: cheap"), encoding="utf-8")
    assert load_policy(path).stages["fix"] == "cheap"


def test_stage_naming_a_missing_tier_is_refused_at_load():
    with pytest.raises(ValueError, match="not in tiers"):
        Policy.model_validate({"stages": {"fix": "huge"}, "tiers": {"cheap": {"primary": {"host": "h", "model": "m"}}}})


def test_primary_routes_are_priced():
    prices = load_prices()
    for tier in load_policy().tiers.values():
        assert tier.primary.model in prices


def test_tier_and_host_are_recorded_per_call(tmp_path):
    clients = {"groq": StubClient("groq"), "ollama": StubClient("ollama"), "mistral": StubClient("mistral")}
    router = _router(tmp_path, _all_quotas(), clients)
    policy = router.policy
    cheap = router.complete("repro", [{"role": "user", "content": "x"}])
    strong = router.complete("fix", [{"role": "user", "content": "x"}])
    assert (cheap.tier, cheap.host, cheap.model, cheap.fell_back) == ("cheap", "groq", policy.tiers["cheap"].primary.model, False)
    assert (strong.tier, strong.host, strong.model) == ("strong", "groq", policy.tiers["strong"].primary.model)
    assert clients["groq"].calls == [cheap.model, strong.model]
    step = TrajectoryStep(index=0, **cheap.trace())
    assert TrajectoryStep.model_validate_json(step.model_dump_json()).tier == "cheap"


def test_quota_refusal_falls_back_to_the_other_host(tmp_path):
    policy = load_policy()
    primary = policy.tiers["strong"].primary.model
    quotas = _all_quotas()
    quotas[primary] = _quota(requests_per_day=1)
    clients = {"groq": StubClient("groq"), "mistral": StubClient("mistral")}
    router = _router(tmp_path, quotas, clients)
    first = router.complete("fix", [])
    second = router.complete("fix", [])
    assert (first.host, first.fell_back) == ("groq", False)
    assert (second.tier, second.host, second.fell_back) == ("strong", "mistral", True)
    assert second.completion.content == "from mistral"


def test_http_429_falls_back_and_other_errors_do_not(tmp_path):
    request = httpx.Request("POST", "http://x")
    too_many = httpx.HTTPStatusError("429", request=request, response=httpx.Response(429, request=request))
    broken = httpx.HTTPStatusError("500", request=request, response=httpx.Response(500, request=request))
    router = _router(tmp_path, _all_quotas(), {"groq": StubClient("groq", too_many), "ollama": StubClient("ollama")})
    assert router.complete("repro", []).host == "ollama"
    router = _router(tmp_path, _all_quotas(), {"groq": StubClient("groq", broken), "ollama": StubClient("ollama")})
    with pytest.raises(httpx.HTTPStatusError):
        router.complete("repro", [])


def test_both_hosts_refused_raises_quota_exceeded(tmp_path):
    router = _router(tmp_path, {}, {"groq": StubClient("groq"), "ollama": StubClient("ollama")})
    with pytest.raises(QuotaExceeded):
        router.complete("repro", [])


def test_unknown_stage_is_an_explicit_error(tmp_path):
    stub = StubClient("groq")
    router = _router(tmp_path, _all_quotas(), {"groq": stub})
    with pytest.raises(UnknownStage):
        router.complete("review", [])
    assert stub.calls == []


def test_old_step_records_without_tier_still_load():
    step = TrajectoryStep.model_validate({"index": 0, "kind": "step", "tokens_in": 3})
    assert (step.tier, step.host, step.model) == (None, None, None)
