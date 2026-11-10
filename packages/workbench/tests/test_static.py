"""P10-T02: the page code never turns text into markup and loads nothing from outside. Scans every file in static/."""

import re
from pathlib import Path

from argus_workbench import server

STATIC = Path(server.__file__).parent / "static"
JS = sorted(STATIC.rglob("*.js"))
BANNED = re.compile(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|new\s+Function|setTimeout\s*\(\s*['\"`]|\.srcdoc\s*=|createContextualFragment|DOMParser|javascript:")


def test_js_files_exist():
    names = {p.relative_to(STATIC).as_posix() for p in JS}
    assert {"app.js", "api.js", "dom.js", *{f"screens/{s}.js" for s in ["issue", "run", "review", "pr", "history"]}} <= names


def test_no_markup_building_apis_in_any_script():
    for path in JS:
        match = BANNED.search(path.read_text("utf-8"))
        assert not match, f"{path.name}: {match.group(0)}"


def test_nothing_is_loaded_from_another_origin():
    for path in [*JS, STATIC / "index.html", STATIC / "style.css"]:
        text = path.read_text("utf-8")
        assert not re.search(r"(https?:)?//[a-z0-9.-]+\.[a-z]{2,}", text, re.I) or path.name == "style.css", path.name
        assert "@import" not in text and "url(" not in text


def test_dom_helper_refuses_handlers_style_and_foreign_urls():
    dom = (STATIC / "dom.js").read_text("utf-8")
    assert "BAD_ATTR" in dom and "same-origin path" in dom and "textContent" in dom


def test_scripts_are_modules_loaded_by_src_only():
    html = (STATIC / "index.html").read_text("utf-8")
    assert html.count("<script") == 1 and 'type="module" src="/static/app.js"' in html
