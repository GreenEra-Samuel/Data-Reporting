"""Generate packaging/icon.ico without any image libraries.

Draws the artwork at 4x and box-filters it down, so the edges stay smooth, then
writes each size as a PNG inside an ICO container (supported by Windows Vista
and later). Run it only when the artwork changes - the .ico is committed.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

SIZES = (16, 24, 32, 48, 64, 128, 256)
SUPERSAMPLE = 4

BACKGROUND = (47, 85, 151)      # the app's accent blue
BAR = (255, 255, 255)
BAR_DIM = (188, 210, 245)

Pixel = tuple[int, int, int, int]


def rounded_rect(x: float, y: float, width: float, height: float, radius: float):
    """Return a hit-test function for a rounded rectangle."""
    right, bottom = x + width, y + height

    def inside(px: float, py: float) -> bool:
        if not (x <= px <= right and y <= py <= bottom):
            return False
        for corner_x, corner_y in (
            (x + radius, y + radius), (right - radius, y + radius),
            (x + radius, bottom - radius), (right - radius, bottom - radius),
        ):
            near_x = px < x + radius if corner_x == x + radius else px > right - radius
            near_y = py < y + radius if corner_y == y + radius else py > bottom - radius
            if near_x and near_y:
                return (px - corner_x) ** 2 + (py - corner_y) ** 2 <= radius ** 2
        return True

    return inside


def render(size: int) -> list[list[Pixel]]:
    """Draw a bar chart on a rounded blue tile."""
    big = size * SUPERSAMPLE
    canvas: list[list[Pixel]] = [[(0, 0, 0, 0)] * big for _ in range(big)]

    tile = rounded_rect(0, 0, big - 1, big - 1, big * 0.22)
    inset = big * 0.18
    usable = big - 2 * inset
    bar_width = usable / 4.4
    gap = (usable - 3 * bar_width) / 2
    heights = (0.42, 0.68, 0.95)
    colours = (BAR_DIM, BAR, BAR_DIM)

    bars = []
    for index, (fraction, colour) in enumerate(zip(heights, colours)):
        left = inset + index * (bar_width + gap)
        height = usable * fraction
        top = inset + usable - height
        bars.append((rounded_rect(left, top, bar_width, height, bar_width * 0.25), colour))

    for row in range(big):
        py = row + 0.5
        for column in range(big):
            px = column + 0.5
            if not tile(px, py):
                continue
            pixel: Pixel = (*BACKGROUND, 255)
            for hit, colour in bars:
                if hit(px, py):
                    pixel = (*colour, 255)
                    break
            canvas[row][column] = pixel

    return downsample(canvas, size)


def downsample(canvas: list[list[Pixel]], size: int) -> list[list[Pixel]]:
    """Average each SUPERSAMPLE x SUPERSAMPLE block, premultiplying by alpha."""
    out: list[list[Pixel]] = []
    for row in range(size):
        line: list[Pixel] = []
        for column in range(size):
            red = green = blue = alpha = 0
            for dy in range(SUPERSAMPLE):
                for dx in range(SUPERSAMPLE):
                    r, g, b, a = canvas[row * SUPERSAMPLE + dy][column * SUPERSAMPLE + dx]
                    weight = a / 255
                    red += r * weight
                    green += g * weight
                    blue += b * weight
                    alpha += a
            count = SUPERSAMPLE * SUPERSAMPLE
            covered = alpha / 255
            if covered == 0:
                line.append((0, 0, 0, 0))
            else:
                line.append((
                    round(red / covered), round(green / covered), round(blue / covered),
                    round(alpha / count),
                ))
        out.append(line)
    return out


def png_bytes(pixels: list[list[Pixel]]) -> bytes:
    height = len(pixels)
    width = len(pixels[0])
    raw = b"".join(
        b"\x00" + b"".join(bytes(pixel) for pixel in row) for row in pixels
    )

    def chunk(tag: bytes, payload: bytes) -> bytes:
        body = tag + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def build_ico(path: Path) -> Path:
    images = [png_bytes(render(size)) for size in SIZES]

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, payload = b"", b""
    for size, image in zip(SIZES, images):
        entries += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,   # 0 means 256 in the ICO format
            0 if size >= 256 else size,
            0, 0, 1, 32, len(image), offset,
        )
        payload += image
        offset += len(image)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entries + payload)
    return path


if __name__ == "__main__":
    written = build_ico(Path(__file__).resolve().parent / "icon.ico")
    print(f"wrote {written} ({written.stat().st_size:,} bytes, sizes: "
          f"{', '.join(str(s) for s in SIZES)})")
