"""decode_png reads what Chromium writes: every scanline filter, RGB and RGBA. Unsupported files are refused."""

from __future__ import annotations

import hashlib
import random
import struct
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from verify.png import PNG_SIGNATURE, Image, decode_png  # noqa: E402

CAL = Path(__file__).resolve().parents[1] / "fixtures" / "calibration"


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def _forward(kind: int, row: bytes, prev: bytes, bpp: int) -> bytes:
    out = bytearray(len(row))
    for i, x in enumerate(row):
        a = row[i - bpp] if i >= bpp else 0
        b = prev[i]
        c = prev[i - bpp] if i >= bpp else 0
        pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
        pred = (0, a, b, (a + b) >> 1, a if pa <= pb and pa <= pc else b if pb <= pc else c)[kind]
        out[i] = (x - pred) & 255
    return bytes(out)


def _png(width: int, height: int, color: int, pixels: bytes, *, bit: int = 8, interlace: int = 0) -> bytes:
    """Row y uses filter y % 5, so every filter kind is written."""
    bpp = {2: 3, 6: 4}[color]
    stride = width * bpp
    raw, prev = b"", bytes(stride)
    for y in range(height):
        row = pixels[y * stride : (y + 1) * stride]
        raw += bytes([y % 5]) + _forward(y % 5, row, prev, bpp)
        prev = row
    ihdr = struct.pack(">IIBBBBB", width, height, bit, color, 0, 0, interlace)
    return PNG_SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b"")


def test_every_filter_round_trips_rgb_and_rgba():
    rng = random.Random(7)
    width, height = 11, 15  # 15 rows: each of the 5 filters is used 3 times
    rgb = bytes(rng.randrange(256) for _ in range(width * height * 3))
    assert decode_png(_png(width, height, 2, rgb)) == Image(width, height, rgb)
    rgba = bytes(rng.randrange(256) for _ in range(width * height * 4))
    dropped = b"".join(rgba[i : i + 3] for i in range(0, len(rgba), 4))
    assert decode_png(_png(width, height, 6, rgba)) == Image(width, height, dropped)


@pytest.mark.parametrize("kwargs", [{"bit": 16}, {"interlace": 1}])
def test_unsupported_png_is_refused(kwargs):
    with pytest.raises(ValueError, match="unsupported png"):
        decode_png(_png(2, 2, 2, bytes(12), **kwargs))
    with pytest.raises(ValueError, match="not a png"):
        decode_png(b"GIF89a")


def test_real_chromium_screenshot_matches_an_independent_decoder():
    # sha256 of the RGB bytes of fixtures/calibration/000/before.png as decoded by pngjs (the bench's PNG library)
    image = decode_png((CAL / "000" / "before.png").read_bytes())
    assert (image.width, image.height) == (1280, 800)
    assert hashlib.sha256(image.rgb).hexdigest() == "cc9aa83fa36b655ad6bd284bdda58a93d1e1ce691fc50d65c52beeb7913ceebc"
