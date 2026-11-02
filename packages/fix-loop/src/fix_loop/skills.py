"""Agent Skills for the fix loop, with progressive disclosure (P5.5-T02).

Level 1: the system message lists each loadable skill's name and description, nothing else.
Level 2: the model calls `load_skill {"name"}` and gets the body wrapped as `<skill_content name="...">`.
The format and the numbers are fixed in `docs/notes/p5.5-t01-skills-spec.md`.

`load_skills` reads `<directory>/<name>/SKILL.md` and returns `(loadable skills, refusals)`. A skill that fails a check
is left out of the catalog and logged with a typed `Reason`, so the model cannot be steered toward it.

The format checks live in `_parse`. The trust checks (P5.5-T10) live in `trust_refusal`, the one place that decides
loadable vs refused on trust. The trust anchor is the lock file `skills.lock.json` (next to the skills directory, in
`packages/skills`), not the SKILL.md itself: the owner's sign-off is writing `reviewed: true` and the SHA-256 there
(`python -m skills.pin`). A skill passes only when its lock entry says reviewed, pins a hash, the file still has that
hash, and every name in its `allowed-tools` is a loop tool. At run time `tool_denied` keeps the agent inside the
`allowed-tools` of the skills it has loaded.

ponytail: the loop has no native tool-calling API, a reply is one JSON `{"tool", "arguments"}` object and the tool list
is text in the system message. So the `name` enum is both in that text and in `tool_spec` (a JSON schema for clients
that do send tools) and is enforced again when the call arrives.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

from fix_loop.tools import ALLOW, ToolError, ToolResult

log = logging.getLogger(__name__)

MAX_BODY_CHARS = 8000  # 2,000 tokens by the repo's len // 4 estimate; the T12 lint reads this constant too
NAME_MAX = 64
DESCRIPTION_MAX = 1024
COMPATIBILITY_MAX = 500
FIELDS = frozenset({"name", "description", "license", "compatibility", "metadata", "allowed-tools"})
LOAD_SKILL = "load_skill"
MAX_LOADED_SKILLS = 3  # per run: a skill that matches every ticket cannot pull the whole catalog into the context (P5.5-T15)
_NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")  # no leading or trailing hyphen, no `--`
LOCK_NAME = "skills.lock.json"
LOCK_VERSION = 1
READ_ONLY = frozenset({"read_file", "list_dir", "search", "ast_grep"})  # the tools of a loaded skill with no `allowed-tools`
_SHA256 = re.compile(r"[0-9a-f]{64}")
_WRAPPER = re.compile(r'<skill_content name="([^"]+)">')


class Reason(StrEnum):
    """Typed refusal reasons shared with the T12 lint. T10 may add reasons; it does not rename these."""

    unreviewed = "unreviewed"
    not_pinned = "not-pinned"
    hash_mismatch = "hash-mismatch"
    too_large = "too-large"
    bad_frontmatter = "bad-frontmatter"
    tool_not_allowed = "tool-not-allowed"
    vague_description = "vague-description"  # raised by the lint only (P5.5-T15); the loader never refuses on it


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    path: Path
    tools: frozenset[str] = READ_ONLY  # the skill's `allowed-tools`, a ceiling while it is loaded


@dataclass(frozen=True)
class Refusal:
    name: str  # the directory name: a skill that fails to parse has no trusted name of its own
    reason: Reason
    detail: str


def content_hash(raw: bytes) -> str:
    """The pin: SHA-256 of the whole SKILL.md with CRLF read as LF (the T01 notes). The lint (T12) uses this too."""
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def lock_skills(path: Path) -> tuple[dict[str, dict], str | None]:
    """The `skills` map of the lock file and, when the file exists but cannot be trusted, what is wrong with it. A missing,
    unreadable or wrong-version file gives an empty map. The T12 lint reads the problem; `read_lock` logs it."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, None
    except (OSError, ValueError) as exc:
        return {}, f"is unreadable ({exc})"
    skills = doc.get("skills") if isinstance(doc, dict) else None
    if not isinstance(doc, dict) or doc.get("version") != LOCK_VERSION or not isinstance(skills, dict):
        return {}, f"is not version {LOCK_VERSION} with a skills map"
    return skills, None


def read_lock(path: Path) -> dict[str, dict]:
    """The `skills` map of the lock file. A missing, unreadable or wrong-version file gives an empty map, so every skill
    is refused as unreviewed: a broken lock never trusts anything."""
    skills, problem = lock_skills(path)
    if problem:
        log.error("skill lock %s %s; no skill is trusted", path, problem)
    return skills


def load_skills(directory: Path, lock: Path | None = None) -> tuple[list[Skill], list[Refusal]]:
    """Every skill directory under `directory`, split into loadable skills and refusals. Each refusal is logged.

    `lock` defaults to `skills.lock.json` in the parent of `directory`."""
    if not directory.is_dir():
        raise FileNotFoundError(f"skills directory {directory} does not exist")
    pins = read_lock(lock if lock is not None else directory.parent / LOCK_NAME)
    loadable: list[Skill] = []
    refusals: list[Refusal] = []
    for folder in sorted(item for item in directory.iterdir() if item.is_dir() and not item.name.startswith(".")):
        outcome = _load_one(folder, pins)
        if isinstance(outcome, Skill):
            loadable.append(outcome)
        else:
            refusals.append(outcome)
            log.warning("skill refused: %s (%s): %s", outcome.name, outcome.reason.value, outcome.detail)
    return loadable, refusals


def trust_refusal(name: str, raw: bytes, fields: dict, pins: dict[str, dict]) -> tuple[Reason, str] | None:
    """The trust checks, in this order. None means trusted.

    1. `unreviewed`: no lock entry, or its `reviewed` is not `true`. (A draft has no entry.)
    2. `not-pinned`: a reviewed entry with no valid `sha256`.
    3. `hash-mismatch`: the file no longer has the pinned hash. The hash covers the frontmatter, so a changed
       `allowed-tools` or `argus-status` needs a new pin.
    4. `tool-not-allowed`: `allowed-tools` names something that is not a loop tool (`ALLOW`), such as `Bash(curl:*)`.

    `raw` is the whole SKILL.md as read from disk; `pins` is the lock's `skills` map."""
    entry = pins.get(name)
    if not isinstance(entry, dict) or entry.get("reviewed") is not True:
        return Reason.unreviewed, "the lock file has no reviewed entry for this skill"
    pinned = entry.get("sha256")
    if not isinstance(pinned, str) or not _SHA256.fullmatch(pinned):
        return Reason.not_pinned, "the lock entry has no valid sha256"
    actual = content_hash(raw)
    if actual != pinned:
        return Reason.hash_mismatch, f"SKILL.md hashes to {actual[:12]}, the lock pins {pinned[:12]}"
    unknown = [tool for tool in fields.get("allowed-tools", "").split() if tool not in ALLOW]
    if unknown:
        return Reason.tool_not_allowed, f"allowed-tools names {', '.join(unknown)}; the loop tools are {' '.join(ALLOW)}"
    return None


def tool_denied(skills: list[Skill], loaded: set[str], name: str) -> ToolError | None:
    """The run-time allowlist. While skills are loaded the agent may call only the tools every loaded skill allows, so a
    skill can narrow the loop's tools and never widen them. `submit` always passes (a run must be able to end) and so does
    `load_skill`. With nothing loaded there is no limit, and the run is the same as one with no skills."""
    if not loaded or name in (LOAD_SKILL, "submit"):
        return None
    allowed = frozenset(ALLOW).intersection(*(skill.tools for skill in skills if skill.name in loaded))
    if name in allowed:
        return None
    return ToolError(
        error="not-allowed",
        message=f"{Reason.tool_not_allowed.value}: {name} is outside the allowed-tools of the loaded skills ({', '.join(sorted(loaded))})",
    )


def catalog(skills: list[Skill]) -> str:
    """The level-1 block appended to the system message. Empty when nothing is loadable, so the prompt is unchanged."""
    if not skills:
        return ""
    lines = [
        "Skills: short playbooks for known bug types. Only the name and description are loaded.",
        f'When the ticket matches a skill, call {LOAD_SKILL} {{"name"}} with that name before you edit; skip it if none match.',
        *(f"- {skill.name}: {' '.join(skill.description.split())}" for skill in sorted(skills, key=lambda s: s.name)),
    ]
    return "\n".join(lines)


def tool_spec(skills: list[Skill]) -> dict | None:
    """JSON schema of `load_skill`: `name` is an enum of the loadable names. None when nothing is loadable."""
    if not skills:
        return None
    return {
        "name": LOAD_SKILL,
        "description": "Return the full instructions of one skill.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "enum": sorted(skill.name for skill in skills)}},
            "required": ["name"],
            "additionalProperties": False,
        },
    }


def load_skill(skills: list[Skill], payload: dict, loaded: set[str]) -> ToolResult | ToolError:
    """Answer one `load_skill` call. `loaded` is the per-run set; a second call for a name returns a short note."""
    if set(payload) - {"name"}:
        return ToolError(error="failed", message="unexpected " + ", ".join(sorted(set(payload) - {"name"})))
    name = payload.get("name")
    if not isinstance(name, str) or not name:
        return ToolError(error="failed", message="missing name")
    by_name = {skill.name: skill for skill in skills}
    if name not in by_name:
        return ToolError(error="not-found", message=f"{name} is not a skill; choose one of: {', '.join(sorted(by_name))}")
    if name in loaded:
        return ToolResult(tool=LOAD_SKILL, text=f"skill {name} is already loaded; use the instructions above")
    if len(loaded) >= MAX_LOADED_SKILLS:
        return ToolError(error="failed", message=f"at most {MAX_LOADED_SKILLS} skills per run; {name} was not loaded")
    loaded.add(name)
    return ToolResult(tool=LOAD_SKILL, text=f'<skill_content name="{name}">\n{by_name[name].body}\n</skill_content>')


def loaded_names(steps) -> list[str]:
    """Skills loaded in a run, in order, from its trajectory steps. A repeat call and an unknown name do not count."""
    names: list[str] = []
    for step in steps:
        text = (step.message or {}).get("text") or ""
        found = _WRAPPER.match(text)
        if step.tool_name == LOAD_SKILL and step.tool_error is None and found and found.group(1) not in names:
            names.append(found.group(1))
    return names


def _load_one(folder: Path, pins: dict[str, dict]) -> Skill | Refusal:
    file = folder / "SKILL.md"
    if not file.is_file():
        return Refusal(folder.name, Reason.bad_frontmatter, "no SKILL.md")
    raw = file.read_bytes()
    parsed = _parse(folder.name, raw)
    if isinstance(parsed, Refusal):
        return parsed
    fields, body = parsed
    if len(body) > MAX_BODY_CHARS:
        return Refusal(folder.name, Reason.too_large, f"body is {len(body)} characters, the limit is {MAX_BODY_CHARS}")
    trust = trust_refusal(folder.name, raw, fields, pins)
    if trust is not None:
        return Refusal(folder.name, *trust)
    tools = frozenset(fields["allowed-tools"].split()) if "allowed-tools" in fields else READ_ONLY
    return Skill(name=fields["name"], description=fields["description"], body=body, path=file, tools=tools)


def _parse(folder_name: str, raw: bytes) -> tuple[dict, str] | Refusal:
    def bad(detail: str) -> Refusal:
        return Refusal(folder_name, Reason.bad_frontmatter, detail)

    try:
        text = raw.decode("utf-8").replace("\r\n", "\n")
    except UnicodeDecodeError:
        return bad("not UTF-8 text")
    lines = text.split("\n")
    if lines[0].rstrip() != "---":
        return bad("the file does not start with ---")
    close = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
    if close is None:
        return bad("no closing --- line")
    try:
        fields = yaml.load("\n".join(lines[1:close]), Loader=_StrictLoader)  # noqa: S506 - SafeLoader subclass
    except yaml.YAMLError as exc:
        return bad(f"not valid YAML: {str(exc).splitlines()[0]}")
    problem = _check_fields(folder_name, fields)
    if problem is not None:
        return bad(problem)
    return fields, "\n".join(lines[close + 1 :]).strip()


def _check_fields(folder_name: str, fields: object) -> str | None:
    if not isinstance(fields, dict):
        return "the frontmatter is not a mapping"
    unknown = sorted(str(key) for key in fields if key not in FIELDS)
    if unknown:
        return "unknown field " + ", ".join(unknown)
    for required in ("name", "description"):
        if required not in fields:
            return f"missing {required}"
    name, description = fields["name"], fields["description"]
    if not isinstance(name, str) or not 1 <= len(name) <= NAME_MAX or not _NAME.fullmatch(name):
        return f"name must be 1 to {NAME_MAX} lowercase letters, digits and single hyphens"
    if name != folder_name:
        return f"name {name} is not the directory name {folder_name}"
    if not isinstance(description, str) or not description.strip() or len(description) > DESCRIPTION_MAX:
        return f"description must be 1 to {DESCRIPTION_MAX} characters"
    for key in ("license", "compatibility", "allowed-tools"):
        if key in fields and (not isinstance(fields[key], str) or not fields[key].strip()):
            return f"{key} must be a non-empty string"
    if "compatibility" in fields and len(fields["compatibility"]) > COMPATIBILITY_MAX:
        return f"compatibility is over {COMPATIBILITY_MAX} characters"
    if "metadata" in fields:
        meta = fields["metadata"]
        if not isinstance(meta, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in meta.items()):
            return "metadata must map strings to strings; quote values such as \"true\" and \"1.0\""
    return None


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects a repeated key. Plain PyYAML keeps the last one without a word."""

    def construct_mapping(self, node, deep=False):
        seen: set = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=True)
            try:
                repeated = key in seen
            except TypeError:
                raise yaml.YAMLError("a mapping key is not a plain value") from None
            if repeated:
                raise yaml.YAMLError(f"duplicate key {key!r}")
            seen.add(key)
        return super().construct_mapping(node, deep)
