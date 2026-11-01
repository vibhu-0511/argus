"""pgvector holds real embeddings of the Canvas flows and ranks files offline."""

import sys
from pathlib import Path

import psycopg
import pytest
import sentence_transformers

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dom2src_mcp.embed import (
    assert_not_copa,
    canvas_files,
    dsn,
    index_canvas,
    platform_worktree,
    query_files,
)


def test_local_packages_import():
    assert sentence_transformers.__name__ == "sentence_transformers"
    assert psycopg.__name__ == "psycopg"


def test_refuses_the_copa_local_database():
    for url in (
        "postgresql://argus@127.0.0.1:5433/canvas_embed",
        "postgresql://argus@127.0.0.1:5436/copa_local",
        "postgresql://argus@db-copa-local:5432/canvas_embed",
        "host=127.0.0.1 port=5433 dbname=canvas_embed",
    ):
        try:
            assert_not_copa(url)
        except ValueError:
            continue
        raise AssertionError(url)


def _probe(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if len(text) < 80 or text.startswith(("import ", "export ", "*", "//", "/*")):
            continue
        return text
    raise AssertionError(f"no probe line in {path}")


@pytest.mark.live
def test_query_returns_ranked_canvas_files():
    files = canvas_files()
    root = platform_worktree()
    assert files
    assert all("node_modules" not in path.parts for path in files)
    assert all(path.is_relative_to(root / "apps" / "canvas") for path in files)
    assert index_canvas() == len(files)

    by_name = {path.name: path for path in files}
    for name in ("AuditLog.tsx", "UserAdmin.tsx"):
        hits = query_files(_probe(by_name[name]), limit=5)
        scores = [score for _, score in hits]
        assert scores == sorted(scores, reverse=True)
        assert hits[0][0].endswith(name)
        assert hits[0][1] > hits[-1][1]

    url = dsn()
    assert_not_copa(url)
    with psycopg.connect(url) as conn:
        database, extension, dims, rows = conn.execute(
            """
            SELECT current_database(),
                   (SELECT extversion FROM pg_extension WHERE extname = 'vector'),
                   (SELECT vector_dims(embedding) FROM canvas_embedding LIMIT 1),
                   (SELECT count(*) FROM canvas_embedding)
            """
        ).fetchone()
    assert database == "canvas_embed"
    assert database != "copa_local"
    assert extension
    assert dims == 384
    assert rows >= len(files)
