"""Shared fixtures. Every test uses a fake token and a tmp_path run store; no model is called."""

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from argus_workbench.server import create_app

TOKEN = "test-token-not-secret"


@pytest.fixture(autouse=True)
def runs_root(tmp_path, monkeypatch):
    root = tmp_path / "runs"
    monkeypatch.setenv("ARGUS_WORKBENCH_RUNS", str(root))
    return root


@pytest.fixture
def app():
    app = create_app(token=TOKEN)
    app.state.calls = []

    # Routes that change something, to prove a refused request never reaches them.
    @app.post("/__probe")
    @app.put("/__probe")
    @app.patch("/__probe")
    @app.delete("/__probe")
    def probe(request: Request):
        app.state.calls.append(request.method)
        return {"ok": True}

    return app


@pytest.fixture
def client(app):
    return TestClient(app, base_url="http://127.0.0.1")
