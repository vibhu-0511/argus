"""One test per check: clean passes, the matching break fails."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from verify.checks import (
    CHANGED_PIXEL_RATIO,
    ConsoleMessage,
    Element,
    OverflowReport,
    axe_check,
    console_check,
    overflow_check,
    pixel_diff,
)
from verify.png import fill, solid

W, H = 40, 30
GRAY = (180, 180, 180)
RED = (200, 40, 40)


def _base():
    return solid(W, H, GRAY)


def test_clean_tree_passes():
    image = _base()
    assert pixel_diff(image, image).ok


def test_difference_inside_the_mask_passes_and_outside_fails():
    golden = _base()
    inside = fill(golden, 1, 1, 6, 6, RED)
    outside = fill(golden, 16, 8, 12, 12, RED)
    mask = ((0, 0, 10, 10),)
    assert pixel_diff(golden, inside, mask).ok
    failed = pixel_diff(golden, outside, mask)
    assert not failed.ok


def test_mask_uses_source_coordinates():
    golden = _base()
    changed = fill(golden, 2, 2, 8, 8, RED)
    assert pixel_diff(golden, changed, ((0, 0, 12, 12),)).ok
    assert not pixel_diff(golden, changed, ((20, 20, 5, 5),)).ok


def test_four_px_shift_outside_the_mask_exceeds_the_fringe_cap():
    golden = fill(_base(), 4, 4, 12, 12, RED)
    shifted = fill(_base(), 8, 4, 12, 12, RED)
    result = pixel_diff(golden, shifted, ((0, 0, 2, 2),))
    assert not result.ok
    assert "fringe cap" in result.reason
    assert str(CHANGED_PIXEL_RATIO) in result.reason


def test_size_change_fails_without_scaling():
    golden = fill(solid(2, 2, GRAY), 0, 0, 1, 1, RED)
    scaled = fill(solid(4, 4, GRAY), 0, 0, 2, 2, RED)
    result = pixel_diff(golden, scaled)
    assert not result.ok
    assert result.reason.startswith("size ")


def test_repeated_fingerprint_is_a_hard_failure():
    golden = _base()
    actual = fill(fill(golden, 2, 2, 3, 3, RED), 30, 20, 3, 3, RED)
    result = pixel_diff(golden, actual)
    assert not result.ok
    assert result.hard
    assert result.reason == "repeated fingerprint"


def test_ratio_constant_is_written_next_to_its_unit():
    text = Path(__file__).resolve().parents[1].joinpath("src", "verify", "checks.py").read_text(encoding="utf-8")
    assert "Unit: changed pixels / unmasked pixels.\nCHANGED_PIXEL_RATIO" in text


def test_fringe_under_the_cap_passes_and_a_different_font_fails():
    golden = _base()
    fringe = fill(golden, 0, 0, W, 1, RED)
    passed = pixel_diff(golden, fringe)
    assert passed.ok
    assert (W / (W * H)) > CHANGED_PIXEL_RATIO
    font = fill(golden, 10, 8, 16, 16, RED)
    failed = pixel_diff(golden, font)
    assert not failed.ok
    assert failed.reason != "repeated fingerprint"


def test_font_wait_stays_in_the_capture():
    text = Path(__file__).resolve().parents[1].joinpath("src", "capture.ts").read_text(encoding="utf-8")
    assert "document.fonts.ready" in text
    assert "networkidle" in text


def test_overflow_fails_on_a_clipped_button_at_375_and_passes_clean():
    clean = OverflowReport(375, 812, 375, 375, (Element("submit", 10, 10, 100, 40),))
    clipped = OverflowReport(375, 812, 420, 375, (Element("submit", 340, 10, 80, 40),))
    assert overflow_check(clean).ok
    failed = overflow_check(clipped)
    assert not failed.ok
    assert "submit" in failed.reason
    assert "375" in failed.reason


def test_axe_reports_only_new_rule_ids():
    assert axe_check(("color-contrast",), ("color-contrast",)).ok
    failed = axe_check(("color-contrast",), ("color-contrast", "label"))
    assert not failed.ok
    assert "label" in failed.reason


def test_console_fails_on_a_new_error_and_passes_clean():
    assert console_check((), ()).ok
    assert console_check((), [ConsoleMessage("log", "ready")]).ok
    failed = console_check((), [ConsoleMessage("error", "Error: boom")])
    assert not failed.ok
    assert "boom" in failed.reason
    assert not console_check((), [ConsoleMessage("warning", "deprecated")]).ok


def _near_slow(point, anchors, limit):
    """The original all-pairs rule, kept here as the reference the windowed lookup must agree with."""
    x, y = point
    return any(max(abs(x - ax), abs(y - ay)) <= limit for ax, ay in anchors)


def test_fringe_lookup_agrees_with_the_all_pairs_rule():
    import random

    from verify.checks import _near

    rng = random.Random(3)
    for _ in range(40):
        width, height = rng.randrange(1, 14), rng.randrange(1, 14)
        pixels = [(x, y) for y in range(height) for x in range(width)]
        anchors = [p for p in pixels if rng.random() < rng.choice((0.1, 0.5, 0.9))]
        indexes = {y * width + x for x, y in anchors}
        for limit in (0, 1, 2):
            for point in pixels:
                assert _near(point, indexes, width, limit) == _near_slow(point, anchors, limit)


def test_pixel_diff_is_usable_at_screenshot_size():
    import time

    big_w, big_h = 1280, 720
    golden = solid(big_w, big_h, GRAY)
    shifted = fill(golden, 100, 100, 160, 100, RED)  # 16000 px, about 1.7% of the frame: under the ratio
    clean = pixel_diff(golden, golden)
    started = time.perf_counter()
    verdict = pixel_diff(golden, shifted)
    elapsed = time.perf_counter() - started
    assert clean.ok
    assert verdict.ok and "fringe ratio" in verdict.reason
    assert elapsed < 30  # it was hours with the all-pairs scan
