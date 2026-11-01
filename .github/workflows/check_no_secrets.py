"""Exit 1 if a workflow file in this directory names a model-provider secret."""

from pathlib import Path
import sys

DIR = Path(__file__).resolve().parent
MARKERS = (
    "ARGUS_MODEL_API_KEY",
    "GROQ_",
    "MISTRAL_",
    "OPENAI_",
    "secrets.",
)


# agent-job.yml runs the agent on dispatch only (never on push or pull_request) and names the one
# model secret it needs; nothing else is allowed there. P6-T04.
ALLOWED = {"agent-job.yml": ("ARGUS_MODEL_API_KEY", "secrets.")}


def markers_in(text: str, name: str = "") -> list[str]:
    return [m for m in MARKERS if m in text and m not in ALLOWED.get(name, ())]


def self_check() -> bool:
    dirty = "GROQ_API_KEY"
    clean = "uv run bench golden --all"
    return markers_in(dirty) == ["GROQ_"] and markers_in(clean) == []


def main() -> int:
    if not self_check():
        print("self-check failed", file=sys.stderr)
        return 1
    failed = False
    for pattern in ("*.yml", "*.yaml"):
        for path in sorted(DIR.glob(pattern)):
            hit = markers_in(path.read_text(encoding="utf-8"), path.name)
            if hit:
                failed = True
                print(f"{path.name}: {', '.join(hit)}", file=sys.stderr)
    if failed:
        return 1
    print("clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
