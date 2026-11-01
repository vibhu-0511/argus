"""Worker side of variant E. Same shape as fix_loop.turn: `show` prints the pending request, `answer` records one reply.

    mini_turn.py show <run id>                    waits up to 100 s for the next request or the verdict
    mini_turn.py answer <run id> < reply.json     reply = {"command": "<bash>", "text": "<optional reasoning>"}

`answer` prints one status line (or the verdict line when the run has ended), never the next request.
"""

import json
import os
import sys
import time
from pathlib import Path

RUNS = Path(__file__).resolve().parents[2] / "runs"
DISPLAY = 20_000  # same per-message display cut as the other variants
WAIT = 100

HEADER = """You are the model in a coding-fix loop (mini-swe-agent). One tool: bash {"command": "<string>"}. Each reply runs one command.
Reply with exactly one JSON object and nothing else: {"command": "<bash command>"}; you may add "text" with your reasoning: {"text": "...", "command": "..."}.
To finish run exactly: echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT (alone, nothing else in the command).
"""


def verdict_line(out: Path) -> str | None:
    path = out / "verdict.json"
    return json.dumps(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None


def pending(out: Path) -> int | None:
    """Index of the newest request that has no reply yet."""
    reqs = sorted((out / "mini").glob("req-*.json"), key=lambda p: int(p.stem.split("-")[1]))
    if reqs and not (out / "mini" / f"rep-{len(reqs) - 1}.json").exists():
        return len(reqs) - 1
    return None


def wait(out: Path) -> tuple[str, int | None]:
    deadline = time.time() + WAIT
    while time.time() < deadline:
        done = verdict_line(out)
        if done:
            return done, None
        n = pending(out)
        if n is not None:
            return "", n
        time.sleep(1)
    return "", None


def render(body: dict) -> str:
    parts = []
    for m in body["messages"]:
        text = str(m.get("content") or "")
        for call in m.get("tool_calls") or []:
            text += f"\n[tool call {call['function']['name']}] {call['function']['arguments']}"
        if len(text) > DISPLAY:
            text = f"{text[:DISPLAY]}\n[driver display cut: {len(text)} characters, {DISPLAY} shown]"
        parts.append(f"[{m['role']}]\n{text}")
    return HEADER + "\n" + "\n\n".join(parts)


def show(run: str) -> int:
    out = RUNS / run
    done, n = wait(out)
    if done:
        print(f"RUN FINISHED {done}")
    elif n is None:
        print("NOT READY: no request yet; run show once more")
    else:
        text = render(json.loads((out / "mini" / f"req-{n}.json").read_text(encoding="utf-8")))
        if len(text) <= DISPLAY:
            print(text)
        else:
            dest = out / "mini" / "prompt.txt"
            dest.write_text(text, encoding="utf-8", newline="\n")
            print(f"[prompt too long to print: {len(text)} characters in {dest}. Read the whole file with the Read tool, in pieces if needed, then answer.]")
    return 0


def answer(run: str, raw: str) -> int:
    out = RUNS / run
    n = pending(out)
    try:
        reply = json.loads(raw)
        ok = isinstance(reply, dict) and isinstance(reply.get("command"), str) and reply["command"].strip()
    except json.JSONDecodeError:
        ok = False
    if not ok:
        print('rejected: reply must be one JSON object with a non-empty string "command"')
        return 3
    if n is None:
        print("rejected: no request is waiting for a reply")
        return 3
    tmp = out / "mini" / f"rep-{n}.tmp"
    tmp.write_text(json.dumps(reply), encoding="utf-8")
    os.replace(tmp, out / "mini" / f"rep-{n}.json")  # the relay only sees a finished file
    done, nxt = wait(out)
    print(done if done else f"recorded reply {n}; the next request is pending" if nxt is not None else f"recorded reply {n}")
    return 0


if __name__ == "__main__":
    if sys.argv[1] == "show":
        raise SystemExit(show(sys.argv[2]))
    raise SystemExit(answer(sys.argv[2], sys.stdin.read()))
