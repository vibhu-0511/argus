# dom2src-mcp

`locate()` on MCP spec 2026-07-28, plus the repo-map and pgvector file retrievers.

The Postgres this package uses is `canvas_embed` on port 5436. It is not the copa-local database.

## Install

From the repo root, with Python 3.12:

```
uv sync
```

## Commands

```
uv run --package dom2src-mcp python -m dom2src_mcp.server --html-file page.html
uv run pytest packages/dom2src-mcp/tests/test_server.py -q
uv run pytest packages/dom2src-mcp/tests/test_harness.py -q
```

The server speaks stdio and accepts protocol `2026-07-28` only. `--html-file` is the document. The tool argument is the selector.

The file-accuracy numbers are in the ablation table in `phases/P02-dom2src.md`.
