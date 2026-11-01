"""Four deterministic checks. Each one returns pass or fail on its own."""

from __future__ import annotations

from dataclasses import dataclass

from verify.png import Image

# Unit: changed pixels / unmasked pixels.
CHANGED_PIXEL_RATIO = 0.02

# A changed pixel within this Chebyshev distance of an unchanged pixel is fringe.
# A 4 px shift leaves a band thicker than this, so it is not fringe.
FRINGE_PX = 1

# Unit: fringe pixels / unmasked pixels.
FRINGE_RATIO = 0.10

FINGERPRINT_MIN_PX = 4

Rect = tuple[int, int, int, int]


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    hard: bool
    reason: str


@dataclass(frozen=True)
class Element:
    id: str
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class OverflowReport:
    viewport_width: int
    viewport_height: int
    scroll_width: int
    client_width: int
    elements: tuple[Element, ...]


@dataclass(frozen=True)
class ConsoleMessage:
    level: str
    text: str


def pixel_diff(golden: Image, actual: Image, mask: tuple[Rect, ...] = ()) -> CheckResult:
    """Compare screenshots. The mask is in golden pixels and is not scaled. A size change fails."""
    if golden.width != actual.width or golden.height != actual.height:
        return CheckResult(
            "pixel",
            False,
            True,
            f"size {actual.width}x{actual.height} vs {golden.width}x{golden.height}",
        )
    changed: list[tuple[int, int]] = []
    unchanged: set[int] = set()  # y * width + x of every unmasked, unchanged pixel
    unmasked = 0
    for y in range(golden.height):
        for x in range(golden.width):
            if _inside(x, y, mask):
                continue
            unmasked += 1
            i = (y * golden.width + x) * 3
            if golden.rgb[i : i + 3] != actual.rgb[i : i + 3]:
                changed.append((x, y))
            else:
                unchanged.add(y * golden.width + x)
    if unmasked == 0 or not changed:
        return CheckResult("pixel", True, True, "clean")
    fringe = [point for point in changed if _near(point, unchanged, golden.width, FRINGE_PX)]
    real = len(changed) - len(fringe)
    real_ratio = real / unmasked
    fringe_ratio = len(fringe) / unmasked
    if real_ratio > CHANGED_PIXEL_RATIO:
        return CheckResult(
            "pixel",
            False,
            True,
            f"changed ratio {real_ratio:.4f} exceeds {CHANGED_PIXEL_RATIO} "
            f"(changed pixels / unmasked pixels); pixels beyond fringe cap {FRINGE_PX} px",
        )
    if _repeated(changed):
        return CheckResult("pixel", False, True, "repeated fingerprint")
    if fringe_ratio > FRINGE_RATIO:
        return CheckResult(
            "pixel",
            False,
            True,
            f"fringe ratio {fringe_ratio:.4f} exceeds {FRINGE_RATIO} (fringe pixels / unmasked pixels)",
        )
    return CheckResult("pixel", True, True, f"fringe ratio {fringe_ratio:.4f} within {FRINGE_RATIO}")


def overflow_check(report: OverflowReport) -> CheckResult:
    reasons: list[str] = []
    if report.scroll_width > report.client_width:
        reasons.append(f"scroll width {report.scroll_width} > client {report.client_width}")
    for element in report.elements:
        right = element.x + element.width
        bottom = element.y + element.height
        if element.x < 0 or element.y < 0 or right > report.viewport_width or bottom > report.viewport_height:
            reasons.append(f"{element.id} clipped at {report.viewport_width} px")
    if reasons:
        return CheckResult("overflow", False, True, "; ".join(reasons))
    return CheckResult("overflow", True, True, "in view")


def axe_check(baseline: tuple[str, ...] | list[str], current: tuple[str, ...] | list[str]) -> CheckResult:
    known = set(baseline)
    new: list[str] = []
    for rule_id in current:
        if rule_id not in known and rule_id not in new:
            new.append(rule_id)
    if not new:
        return CheckResult("axe", True, True, "no new violations")
    return CheckResult("axe", False, True, "new violations: " + ", ".join(new))


def console_check(
    baseline: tuple[ConsoleMessage, ...] | list[ConsoleMessage],
    current: tuple[ConsoleMessage, ...] | list[ConsoleMessage],
) -> CheckResult:
    known = {(item.level, item.text) for item in baseline if item.level in {"error", "warning"}}
    fresh = [
        item
        for item in current
        if item.level in {"error", "warning"} and (item.level, item.text) not in known
    ]
    if not fresh:
        return CheckResult("console", True, True, "no new errors")
    shown = ", ".join(f"{item.level}: {item.text}" for item in fresh)
    return CheckResult("console", False, True, shown)


def _inside(x: int, y: int, mask: tuple[Rect, ...]) -> bool:
    return any(rx <= x < rx + rw and ry <= y < ry + rh for rx, ry, rw, rh in mask)


def _near(point: tuple[int, int], anchors: set[int], width: int, limit: int) -> bool:
    """True when an anchor (an index y * width + x) lies within Chebyshev distance `limit`. Looks only at the window."""
    x, y = point
    for ay in range(y - limit, y + limit + 1):
        for ax in range(max(0, x - limit), min(width, x + limit + 1)):
            if ay * width + ax in anchors:
                return True
    return False


def _repeated(changed: list[tuple[int, int]]) -> bool:
    remaining = set(changed)
    seen: dict[tuple[tuple[int, int], ...], int] = {}
    while remaining:
        start = remaining.pop()
        stack = [start]
        comp = [start]
        while stack:
            x, y = stack.pop()
            for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nxt in remaining:
                    remaining.remove(nxt)
                    stack.append(nxt)
                    comp.append(nxt)
        if len(comp) < FINGERPRINT_MIN_PX:
            continue
        min_x = min(p[0] for p in comp)
        min_y = min(p[1] for p in comp)
        shape = tuple(sorted((px - min_x, py - min_y) for px, py in comp))
        seen[shape] = seen.get(shape, 0) + 1
        if seen[shape] >= 2:
            return True
    return False
