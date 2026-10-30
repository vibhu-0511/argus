"""Same seed hashes the same. A different patch does not reuse a cached verdict."""

from pathlib import Path

from argus_bench.mutate import mutate_all, task_set_hash


def test_same_seed_hash_and_cache_miss_on_new_patch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.css").write_bytes(b".a { font-size: 20px; }\n")
    out = tmp_path / "mutated"
    cache = tmp_path / "verdicts.json"
    calls: list[str] = []

    def score(task: str, tree: Path) -> int:
        calls.append(Path(task).name)
        return 1 if len(calls) % 2 == 1 else 0

    row = {
        "path": "a.css",
        "operatorId": "change-unit",
        "archetype": "font-size",
        "patch": "--- a/a.css\n+++ b/a.css\n@@ -1,1 +1,1 @@\n-.a { font-size: 20px; }\n+.a { font-size: 24px; }\n",
        "selector": ".a",
        "property": "font-size",
        "expected": "20px",
    }

    def rows(_seed: int, _repo: Path):
        yield row

    code = mutate_all(1, repo=repo, out=out, cache_path=cache, candidates=rows, score=score, limit=1)
    assert code == 0
    assert len(calls) == 2
    first = task_set_hash(out)
    calls.clear()
    code = mutate_all(1, repo=repo, out=out, cache_path=cache, candidates=rows, score=score, limit=1)
    assert code == 0
    assert calls == []
    assert task_set_hash(out) == first

    other = dict(row)
    other["patch"] = row["patch"].replace("24px", "28px")

    def changed(_seed: int, _repo: Path):
        yield other

    code = mutate_all(1, repo=repo, out=out, cache_path=cache, candidates=changed, score=score, limit=1)
    assert code == 0
    assert len(calls) == 2

    calls.clear()
    code = mutate_all(2, repo=repo, out=out, cache_path=cache, candidates=rows, score=score, limit=1)
    assert code == 0
    assert len(calls) == 2
