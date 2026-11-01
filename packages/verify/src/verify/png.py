"""8-bit RGB PNG write; read of 8-bit RGB and RGBA, every scanline filter, not interlaced. No scaling."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

PNG_SIGNATURE = bytes([137, 80, 78, 71, 13, 10, 26, 10])


@dataclass(frozen=True)
class Image:
    width: int
    height: int
    rgb: bytes


def solid(width: int, height: int, color: tuple[int, int, int]) -> Image:
    return Image(width, height, bytes(color) * (width * height))


def fill(image: Image, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> Image:
    px = bytearray(image.rgb)
    paint = bytes(color)
    for yy in range(y, y + height):
        for xx in range(x, x + width):
            i = (yy * image.width + xx) * 3
            px[i : i + 3] = paint
    return Image(image.width, image.height, bytes(px))


def encode_png(image: Image) -> bytes:
    raw = b"".join(
        b"\x00" + image.rgb[y * image.width * 3 : (y + 1) * image.width * 3] for y in range(image.height)
    )

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", image.width, image.height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def decode_png(blob: bytes) -> Image:
    """Decode an 8-bit, non-interlaced RGB or RGBA PNG (what Chromium screenshots are). Alpha is dropped."""
    if blob[:8] != PNG_SIGNATURE:
        raise ValueError("not a png")
    pos = 8
    width = height = None
    channels = 0
    idat = b""
    while pos + 8 <= len(blob):
        length = struct.unpack(">I", blob[pos : pos + 4])[0]
        tag = blob[pos + 4 : pos + 8]
        data = blob[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            width, height, bit, color, comp, filt, inter = struct.unpack(">IIBBBBB", data)
            if (bit, comp, filt, inter) != (8, 0, 0, 0) or color not in (2, 6):
                raise ValueError("unsupported png")
            channels = 3 if color == 2 else 4
        elif tag == b"IDAT":
            idat += data
        elif tag == b"IEND":
            break
    if width is None or height is None:
        raise ValueError("png missing header")
    raw = zlib.decompress(idat)
    stride = width * channels
    if len(raw) != height * (stride + 1):
        raise ValueError("png size")
    rows: list[bytes] = []
    prev = bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        kind = raw[start]
        row = bytearray(raw[start + 1 : start + 1 + stride])
        _unfilter(kind, row, prev, channels)
        rows.append(bytes(row))
        prev = row
    if channels == 4:
        rows = [b"".join(r[x : x + 3] for x in range(0, stride, 4)) for r in rows]
    return Image(width, height, b"".join(rows))


def _unfilter(kind: int, row: bytearray, prev: bytearray, bpp: int) -> None:
    """In place, as in the PNG spec section 9. `bpp` is bytes per pixel."""
    n = len(row)
    if kind == 0:
        return
    if kind == 1:  # Sub
        for i in range(bpp, n):
            row[i] = (row[i] + row[i - bpp]) & 255
    elif kind == 2:  # Up
        for i in range(n):
            row[i] = (row[i] + prev[i]) & 255
    elif kind == 3:  # Average
        for i in range(n):
            left = row[i - bpp] if i >= bpp else 0
            row[i] = (row[i] + ((left + prev[i]) >> 1)) & 255
    elif kind == 4:  # Paeth
        for i in range(n):
            a = row[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
            pred = a if pa <= pb and pa <= pc else b if pb <= pc else c
            row[i] = (row[i] + pred) & 255
    else:
        raise ValueError("png filter")
