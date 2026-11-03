"""Exit 1 if a workflow file names a model-provider secret, a tracked file holds a token, or a git remote carries one.

Standard library only: the CI job runs it with a bare Python, no uv sync. The token shapes are the ones the redactor uses
(`packages/argus-core/src/argus_core/redact.py`, loaded by path), so the scan and the redaction cannot drift apart. P7-T03.
"""

import importlib.util
import re
import subprocess
from pathlib import Path
import sys

DIR = Path(__file__).resolve().parent
ROOT = DIR.parents[1]
FAKE = "FAKE"  # a line that says so is a test value, never a credential
# Made-up values in tests of earlier phases and one stored trajectory (a model quoting the code under test). Matched by text, not
# by path, so a real token added to the same file still fails.
ALLOWED_MATCHES = frozenset(
    {
        "Bearer secretKey",
        "Bearer sk-secret-for-the-test",
        "ghp_SECRET_TOKEN_VALUE_123",
        "ghp_0123456789abcdefghijklmnopqrstuv",
        "gsk_abcdefghijklmnopqrstuvwxyz0123",
        "ghp_write-token-not-real-7c1e",
        "Bearer s3cret-token",
    }
)
REMOTE_WITH_USERINFO = re.compile(r"^https?://[^/\s@]+@", re.IGNORECASE)
MARKERS = (
    "ARGUS_MODEL_API_KEY",
    "GROQ_",
    "MISTRAL_",
    "OPENAI_",
    "secrets.",
)


# agent-job.yml runs the agent on dispatch only (never on push or pull_request) and names the one
# model secret it needs; nothing else is allowed there. P6-T04.
# golden.yml (manual dispatch only) checks out the private platform repo with the read-only token PLATFORM_REPO_TOKEN. P0.
ALLOWED = {"agent-job.yml": ("ARGUS_MODEL_API_KEY", "secrets."), "golden.yml": ("secrets.",)}


def markers_in(text: str, name: str = "") -> list[str]:
    text = text.replace(Path(__file__).stem, "")  # a workflow that runs this script names it; that is not a secret
    return [m for m in MARKERS if m in text and m not in ALLOWED.get(name, ())]


def self_check() -> bool:
    dirty = "GROQ_API_KEY"
    clean = "uv run bench golden --all"
    planted = "token ghp_" + "A" * 36  # built at run time so this file holds no token shape
    return (
        markers_in(dirty) == ["GROQ_"]
        and markers_in(clean) == []
        and len(leaks_in(planted)) == 1
        and len(leaks_in("remote https://x-access-token:abc" + "@github.com/o/r.git")) == 1
        and leaks_in(planted + " FAKE") == []
    )


def _shapes() -> tuple[re.Pattern[str], ...]:
    path = ROOT / "packages" / "argus-core" / "src" / "argus_core" / "redact.py"
    spec = importlib.util.spec_from_file_location("argus_redact", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return (*module.TOKEN_SHAPES, module.URL_USERINFO)


def leaks_in(text: str) -> list[tuple[int, str]]:
    """(line number, matched text) for every token shape or `user:token@` URL in `text`, except FAKE lines and ALLOWED_MATCHES."""
    shapes = _shapes()
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        if FAKE in line:
            continue
        for shape in shapes:
            found += [(number, m.group(0)) for m in shape.finditer(line) if m.group(0) not in ALLOWED_MATCHES]
    return found


def remote_leaks(root: Path = ROOT) -> list[str]:
    """Remotes of the repository at `root` whose URL has a user or token in it (user:token before the host)."""
    out = subprocess.run(
        ["git", "-C", str(root), "config", "--get-regexp", r"^remote\..*\.(pushurl|url)$"],
        capture_output=True,
        text=True,
    ).stdout  # exit 1 with no output when there is no remote
    return [line.split()[0] for line in out.splitlines() if REMOTE_WITH_USERINFO.match(line.split(maxsplit=1)[-1])]


def tracked_leaks(root: Path = ROOT) -> list[str]:
    """`path:line: <first 4 characters>...` for every leak in a tracked text file. The value itself is never printed."""
    names = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"], capture_output=True, text=True, check=True
    ).stdout.split("\0")
    found = []
    for name in filter(None, names):
        try:
            text = (root / name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # a binary file or a path that is gone
        found += [f"{name}:{n}: {value[:4]}..." for n, value in leaks_in(text)]
    return found


def main(root: Path = ROOT) -> int:
    if not self_check():
        print("self-check failed", file=sys.stderr)
        return 1
    failed = False
    for hit in remote_leaks(root):
        failed = True
        print(f"git config {hit}: a remote URL must not carry a user or token", file=sys.stderr)
    for hit in tracked_leaks(root):
        failed = True
        print(hit, file=sys.stderr)
    for pattern in ("*.yml", "*.yaml"):
        for path in sorted((root / ".github" / "workflows").glob(pattern)):
            hit = markers_in(path.read_text(encoding="utf-8"), path.name)
            if hit:
                failed = True
                print(f"{path.name}: {', '.join(hit)}", file=sys.stderr)
    if failed:
        return 1
    print("clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT))  # an argument scans that repository (tests plant a secret in a temp one)
