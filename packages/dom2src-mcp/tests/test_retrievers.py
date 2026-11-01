import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dom2src_mcp.retrievers import locate_files, repo_map_files

GOLDEN = "apps/canvas/src/styles/landing.css"


def _task(root: Path, text: str, html: str | None = None) -> Path:
    task = root / "task"
    task.mkdir()
    (task / "ticket.json").write_text(json.dumps({"text": text}), encoding="utf-8")
    (task / "golden.patch").write_text(f"+++ b/{GOLDEN}\n", encoding="utf-8")
    if html is not None:
        (task / "page.html").write_text(html, encoding="utf-8")
    return task


def test_repo_map_ranks_the_symbol_file_not_the_golden_patch(tmp_path: Path) -> None:
    task = _task(tmp_path, "The landing brand uses LandingMark.")
    index = {
        "files": {
            "apps/canvas/src/screens/Landing.tsx": [{"name": "LandingMark"}],
            "apps/canvas/src/screens/Other.tsx": [{"name": "OtherMark"}],
        }
    }
    assert repo_map_files(task, index) == ["apps/canvas/src/screens/Landing.tsx"]


def test_locate_returns_no_file_without_a_selector_and_html(tmp_path: Path) -> None:
    task = _task(tmp_path, "The landing brand is drawn at 8 px instead of 20 px.")
    assert locate_files(task) == []


def test_locate_reads_data_src_when_the_task_has_both(tmp_path: Path) -> None:
    task = _task(
        tmp_path,
        "The mark #brand is the wrong size.",
        '<a id="brand" data-src="apps/canvas/src/screens/Landing.tsx:4:1">A</a>',
    )
    assert locate_files(task) == ["apps/canvas/src/screens/Landing.tsx"]
