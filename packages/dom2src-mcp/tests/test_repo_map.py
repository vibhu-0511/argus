import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dom2src_mcp.repo_map import INDEX_PATH, StaleIndex, _stale_files, platform_repo, query

USER_ADMIN = "apps/canvas/src/screens/UserAdmin.tsx"


@pytest.mark.live
def test_query_returns_definition_and_references_from_language_server():
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    files = index["files"]
    assert index["indexed_dir"] == "apps/canvas/src"
    assert index["language_server"] == "tsserver"
    assert len(files) > 50
    assert sum(len(symbols) for symbols in files.values()) > 100
    for rel, symbols in files.items():
        assert rel.startswith("apps/canvas/src/")
        assert "node_modules" not in rel.split("/")
        assert all(item["name"] and item["line"] >= 1 and item["offset"] >= 1 for item in symbols)

    indexed = next(item for item in files[USER_ADMIN] if item["name"] == "UserAdmin")
    found = query("UserAdmin")
    assert found["symbol"] == "UserAdmin"
    assert found["definitions"]
    assert found["references"]
    assert any(
        loc["file"] == USER_ADMIN and loc["line"] == indexed["line"] and loc["offset"] == indexed["offset"]
        for loc in found["definitions"]
    )
    assert any(not loc["is_definition"] for loc in found["references"])
    for loc in found["definitions"] + found["references"]:
        assert loc["file"]
        assert loc["line"] >= 1
        assert loc["offset"] >= 1


def test_query_refuses_when_a_named_file_changes_after_its_hash_was_stored(tmp_path):
    rel = "apps/canvas/src/Widget.tsx"
    source = tmp_path / rel
    source.parent.mkdir(parents=True)
    original = b"export function Widget() { return null }\n"
    source.write_bytes(original)
    index = {
        "files": {rel: [{"name": "Widget", "kind": "function", "line": 1, "offset": 1}]},
        "content_hashes": {rel: hashlib.sha256(original).hexdigest()},
    }
    source.write_bytes(original + b"// edited after the repo-map was built\n")
    with pytest.raises(StaleIndex) as caught:
        query("Widget", index=index, root=tmp_path)
    assert caught.value.files == [rel]


def test_committed_index_is_checked_for_staleness(tmp_path):
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    assert set(index["content_hashes"]) == set(index["files"])
    # Against a tree where none of the indexed files exist, every one of them is stale.
    with pytest.raises(StaleIndex) as caught:
        query("UserAdmin", index=index, root=tmp_path)
    assert sorted(caught.value.files) == sorted(index["files"])
    # One edited byte in one file is reported, and only that file.
    rel = USER_ADMIN
    source = tmp_path / rel
    source.parent.mkdir(parents=True)
    source.write_bytes(b"x")
    index["content_hashes"][rel] = hashlib.sha256(b"x").hexdigest()
    assert _stale_files(index, tmp_path) == sorted_without(index["files"], rel)
    source.write_bytes(b"y")
    assert rel in _stale_files(index, tmp_path)


@pytest.mark.live
def test_committed_index_matches_the_platform_checkout():
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    assert _stale_files(index, platform_repo()) == []


def sorted_without(files, rel):
    return [name for name in files if name != rel]
