"""P10 rule 7: no model call in code or tests. No key, URL or model name is read at import."""

import importlib
import pkgutil
import re
import sys
from pathlib import Path

import argus_workbench

SRC = Path(argus_workbench.__file__).parent


def test_importing_every_module_reads_no_secret_env(monkeypatch):
    seen = []
    real_get = __import__("os").environ.get
    monkeypatch.setattr("os.environ.get", lambda k, *a: seen.append(k) or real_get(k, *a), raising=False)
    for name in [m for m in sys.modules if m.startswith("argus_workbench")]:
        monkeypatch.delitem(sys.modules, name)  # so the imports below really run the module bodies again
    for info in pkgutil.walk_packages(argus_workbench.__path__, "argus_workbench."):
        importlib.import_module(info.name)
    assert not [k for k in seen if re.search(r"KEY|TOKEN|SECRET|MODEL|URL|OPENAI|ANTHROPIC|OLLAMA", k.upper())]


def test_package_source_has_no_model_client():
    banned = re.compile(r"\b(openai|anthropic|ollama|ModelClient|argus_core\.client|chat\.completions)\b", re.I)
    for path in SRC.rglob("*.py"):
        assert not banned.search(path.read_text("utf-8")), path
