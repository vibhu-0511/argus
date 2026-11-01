# Scope: Canvas UI source for the five flows in config/platform.md, the same
# ceiling as the repo-map. That is sign-in (/login, /ops/login), the ops menu
# (/ops/radar, /ops/operations, /ops/launchpad, /ops/rules), the desk tabs
# (/desk?sel=console|timeline|crew|brief), user admin (/admin/users), and the
# audit table (/admin/audit). Files live under apps/canvas/src/ops,
# apps/canvas/src/desk, apps/canvas/src/launchpad, plus Landing, AuthModal,
# Desk, UserAdmin, and AuditLog. Not the rest of the monorepo. Not node_modules.
# The worktree is the Repo path in config/platform.md. Embeddings are a local
# sentence-transformers model on CPU. Postgres is local pgvector, never the
# copa-local airline database (port 5433, database copa_local, service db-copa-local).

"""Index that Canvas source in local pgvector and return ranked files."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from sentence_transformers import SentenceTransformer

from dom2src_mcp.repo_map import platform_repo

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_DSN = "postgresql://argus@127.0.0.1:5436/canvas_embed"
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 200
SOURCE_SUFFIXES = {".ts", ".tsx", ".css", ".js", ".jsx"}

# Directory trees and single files, relative to the platform worktree.
SCOPE = (
    "apps/canvas/src/ops",
    "apps/canvas/src/desk",
    "apps/canvas/src/launchpad",
    "apps/canvas/src/screens/Landing.tsx",
    "apps/canvas/src/screens/AuthModal.tsx",
    "apps/canvas/src/screens/Desk.tsx",
    "apps/canvas/src/screens/UserAdmin.tsx",
    "apps/canvas/src/screens/AuditLog.tsx",
)

_model: SentenceTransformer | None = None


def dsn() -> str:
    url = os.environ.get("ARGUS_EMBED_DSN", DEFAULT_DSN)
    assert_not_copa(url)
    return url


def assert_not_copa(url: str) -> None:
    lowered = url.lower()
    if "copa_local" in lowered or "db-copa-local" in lowered:
        raise ValueError("refusing the copa-local airline database")
    if re.search(r"(?:port=|:)\s*5433\b", lowered):
        raise ValueError("refusing port 5433")
    parsed = urlparse(url)
    if parsed.port == 5433:
        raise ValueError("refusing port 5433")
    if parsed.path.strip("/") == "copa_local":
        raise ValueError("refusing the copa-local airline database")


def platform_worktree() -> Path:
    return platform_repo()


def canvas_files() -> list[Path]:
    root = platform_worktree()
    found: list[Path] = []
    for rel in SCOPE:
        path = root / rel
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            candidates = [item for item in path.rglob("*") if item.is_file()]
        else:
            continue
        for item in candidates:
            if "node_modules" in item.parts:
                continue
            if item.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            if ".test." in item.name or ".spec." in item.name:
                continue
            found.append(item)
    return sorted(set(found))


def _chunks(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    step = CHUNK_CHARS - CHUNK_OVERLAP
    pieces = []
    start = 0
    while start < len(text):
        pieces.append(text[start : start + CHUNK_CHARS])
        if start + CHUNK_CHARS >= len(text):
            break
        start += step
    return pieces


def _model_on_cpu() -> SentenceTransformer:
    global _model
    if _model is None:
        # Weights must already be on disk. This load does not call an embedding API.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        _model = SentenceTransformer(MODEL_NAME, device="cpu")
    return _model


def _vector(values) -> str:
    return "[" + ",".join(f"{float(value):.7f}" for value in values) + "]"


def index_canvas(url: str | None = None) -> int:
    """Replace the local pgvector rows with embeddings of the scoped Canvas files."""
    target = dsn() if url is None else url
    assert_not_copa(target)
    files = canvas_files()
    if not files:
        raise FileNotFoundError("no Canvas UI source files in the platform worktree")
    root = platform_worktree()
    rows: list[tuple[str, int, str]] = []
    pending: list[tuple[str, int, str]] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for index, piece in enumerate(_chunks(text)):
            pending.append((rel, index, piece))
    encoded = _model_on_cpu().encode(
        [piece for _, _, piece in pending],
        batch_size=32,
        device="cpu",
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    for (rel, index, _), vector in zip(pending, encoded, strict=True):
        rows.append((rel, index, _vector(vector)))
    dim = int(encoded.shape[1])
    with psycopg.connect(target) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute("DROP TABLE IF EXISTS canvas_embedding")
        conn.execute(
            f"""
            CREATE TABLE canvas_embedding (
                path text NOT NULL,
                chunk_ix integer NOT NULL,
                embedding vector({dim}) NOT NULL,
                PRIMARY KEY (path, chunk_ix)
            )
            """
        )
        conn.cursor().executemany(
            "INSERT INTO canvas_embedding (path, chunk_ix, embedding) VALUES (%s, %s, %s)",
            rows,
        )
        conn.execute(
            """
            CREATE INDEX canvas_embedding_hnsw
            ON canvas_embedding USING hnsw (embedding vector_cosine_ops)
            """
        )
    return len(files)


def query_files(text: str, limit: int = 10, url: str | None = None) -> list[tuple[str, float]]:
    """Rank indexed files by cosine similarity to `text`. Best score first."""
    target = dsn() if url is None else url
    assert_not_copa(target)
    if limit < 1:
        raise ValueError("limit must be at least 1")
    vector = _model_on_cpu().encode(
        [text],
        device="cpu",
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0]
    literal = _vector(vector)
    with psycopg.connect(target) as conn:
        found = conn.execute(
            """
            SELECT path, MAX(1 - (embedding <=> %s::vector)) AS score
            FROM canvas_embedding
            GROUP BY path
            ORDER BY score DESC, path
            LIMIT %s
            """,
            (literal, limit),
        ).fetchall()
    return [(path, float(score)) for path, score in found]
