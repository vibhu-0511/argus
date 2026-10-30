import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dom2src_mcp.locate import Ambiguous, Candidate, Location, NoSourceInfo, NotFound, locate

# Lines below are the data-src values, not the line numbers of this fixture.
PAGE = """\
<main>
  <!-- <button id="ghost" data-src="apps/canvas/src/screens/Desk.tsx:1:1">nope</button> -->
  <a id="sign-in" data-src="apps/canvas/src/screens/Landing.tsx:40:3">Sign in</a>
  <input id="auth-email" data-src="apps/canvas/src/screens/AuthModal.tsx:18:7" />
  <section id="desk-root" data-src="apps/canvas/src/screens/Desk.tsx:6:3">
    <button data-src="apps/canvas/src/desk/SaveBar.tsx:21:5" id="desk-save">Save</button>
  </section>
  <form id="user-admin" data-src="apps/canvas/src/screens/UserAdmin.tsx:55:9"></form>
  <table id="audit-table" data-src="apps/canvas/src/screens/AuditLog.tsx:22:3">
    <tr data-testid="audit-row" data-src="apps/canvas/src/screens/AuditLog.tsx:31:7"></tr>
  </table>
  <section data-src="apps/canvas/src/ops/Radar.tsx:14:5" data-testid="ops-radar"></section>
  <button data-testid="launch" data-src="apps/canvas/src/launchpad/Launchpad.tsx:9:11">Launch</button>
  <span data-testid="crew-tab" data-src="apps/canvas/src/desk/Crew.tsx:27:4">Crew</span>
</main>
"""

CASES = (
    ("#sign-in", "apps/canvas/src/screens/Landing.tsx", 40, 3),
    ("#auth-email", "apps/canvas/src/screens/AuthModal.tsx", 18, 7),
    ("#desk-root", "apps/canvas/src/screens/Desk.tsx", 6, 3),
    ("#user-admin", "apps/canvas/src/screens/UserAdmin.tsx", 55, 9),
    ("#audit-table", "apps/canvas/src/screens/AuditLog.tsx", 22, 3),
    ('[data-testid="ops-radar"]', "apps/canvas/src/ops/Radar.tsx", 14, 5),
    ('[data-testid="launch"]', "apps/canvas/src/launchpad/Launchpad.tsx", 9, 11),
    ('[data-testid="crew-tab"]', "apps/canvas/src/desk/Crew.tsx", 27, 4),
)


@pytest.mark.parametrize(("selector", "file", "line", "col"), CASES)
def test_locate_returns_file_and_line(selector: str, file: str, line: int, col: int) -> None:
    found = locate(selector, PAGE)
    assert found == Location(file, line, col)


# These hosts sit under a different data-src, so the ancestor is the call site.
NESTED = (
    (
        "#desk-save",
        "apps/canvas/src/screens/Desk.tsx",
        6,
        3,
        "apps/canvas/src/desk/SaveBar.tsx",
        21,
        5,
    ),
    (
        '[data-testid="audit-row"]',
        "apps/canvas/src/screens/AuditLog.tsx",
        22,
        3,
        "apps/canvas/src/screens/AuditLog.tsx",
        31,
        7,
    ),
)


@pytest.mark.parametrize(
    ("selector", "call_file", "call_line", "call_col", "def_file", "def_line", "def_col"),
    NESTED,
)
def test_nested_host_is_ambiguous(
    selector: str,
    call_file: str,
    call_line: int,
    call_col: int,
    def_file: str,
    def_line: int,
    def_col: int,
) -> None:
    found = locate(selector, PAGE)
    assert found == Ambiguous(
        selector,
        (
            Candidate(call_file, call_line, call_col, 1),
            Candidate(def_file, def_line, def_col, 2),
        ),
    )


@pytest.mark.parametrize("selector", ["#missing", "#desk", "#ghost", '[data-testid="missing"]'])
def test_missing_selector_is_not_found(selector: str) -> None:
    assert locate(selector, PAGE) == NotFound(selector)


# Production mode emits the same hosts and omits every data-src.
PROD = """\
<main>
  <!-- <button id="ghost">nope</button> -->
  <a id="sign-in">Sign in</a>
  <input id="auth-email" />
  <section id="desk-root">
    <button id="desk-save">Save</button>
  </section>
  <form id="user-admin"></form>
  <table id="audit-table">
    <tr data-testid="audit-row"></tr>
  </table>
  <section data-testid="ops-radar"></section>
  <button data-testid="launch">Launch</button>
  <span data-testid="crew-tab">Crew</span>
</main>
"""


@pytest.mark.parametrize("selector", [case[0] for case in CASES] + [item[0] for item in NESTED])
def test_production_build_is_no_source_info(selector: str) -> None:
    found = locate(selector, PROD)
    assert found == NoSourceInfo(selector)
    assert not isinstance(found, Location)


@pytest.mark.parametrize("selector", ["#missing", "#desk", "#ghost", '[data-testid="missing"]'])
def test_missing_selector_on_production_is_not_found(selector: str) -> None:
    assert locate(selector, PROD) == NotFound(selector)


WRAPPER = (
    '<div id="page" data-src="apps/canvas/src/screens/Page.tsx:8:5">'
    '<button id="save" data-src="apps/canvas/src/ui/Button.tsx:4:3">Save</button>'
    "</div>"
)


def test_wrapper_button_is_ambiguous() -> None:
    found = locate("#save", WRAPPER)
    assert found == Ambiguous(
        "#save",
        (
            Candidate("apps/canvas/src/screens/Page.tsx", 8, 5, 1),
            Candidate("apps/canvas/src/ui/Button.tsx", 4, 3, 2),
        ),
    )


REPEATED = """\
<span data-testid="item" data-src="apps/canvas/src/desk/Zed.tsx:4:2">Z</span>
<span data-testid="item" data-src="apps/canvas/src/desk/Able.tsx:1:1">A</span>
"""


def test_repeated_testid_is_ambiguous() -> None:
    found = locate('[data-testid="item"]', REPEATED)
    assert found == Ambiguous(
        '[data-testid="item"]',
        (
            Candidate("apps/canvas/src/desk/Zed.tsx", 4, 2, 1),
            Candidate("apps/canvas/src/desk/Able.tsx", 1, 1, 2),
        ),
    )


def test_same_ancestor_data_src_is_location() -> None:
    html = (
        '<div data-src="apps/canvas/src/screens/Page.tsx:8:5">'
        '<button id="save" data-src="apps/canvas/src/screens/Page.tsx:8:5">Save</button>'
        "</div>"
    )
    assert locate("#save", html) == Location("apps/canvas/src/screens/Page.tsx", 8, 5)


def test_unsourced_match_does_not_guess_ancestor() -> None:
    html = (
        '<div id="page" data-src="apps/canvas/src/screens/Page.tsx:8:5">'
        '<button id="save">Save</button>'
        "</div>"
    )
    assert locate("#save", html) == NoSourceInfo("#save")
