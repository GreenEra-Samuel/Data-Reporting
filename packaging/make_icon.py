"""Generate packaging/icon.ico from the Green Era Campus mark.

The artwork is the campus logo - the leaning green trapezoid on its cream
ground - with LAB set underneath, marking this as the laboratory app.

Detail is added as the icon gets bigger, because a 16-pixel icon that tries to
carry three lines of text is just a smudge:

    16, 24 px       the cream tile and the green mark, filling the tile
    32, 48, 64 px   the mark with LAB underneath
    128 px and up   ... plus the GREEN / ERA / CAMPUS wordmark inside the mark

Every size is drawn at 4x and filtered down, so edges and type stay smooth.
Run this only when the artwork changes - the .ico it writes is committed.

Needs Pillow (pip install pillow); the app itself does not.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - only hit when regenerating
    sys.exit("This script needs Pillow. Install it with:  pip install pillow")

ROOT = Path(__file__).resolve().parent

# --------------------------------------------------------------- brand values
# Measured off the supplied logo. If the brand book gives exact values, change
# them here and re-run; nothing else needs touching.
GREEN = (13, 122, 60)
CREAM = (242, 237, 231)
WHITE = (255, 255, 255)

WORDMARK = ("GREEN", "ERA", "CAMPUS")
STRAPLINE = "LAB"          # swap for "TESTING" if that reads better

SIZES = (16, 24, 32, 48, 64, 128, 256)
SUPERSAMPLE = 4

# Thresholds, in final pixels, below which an element is dropped as unreadable.
MIN_SIZE_FOR_STRAPLINE = 32
MIN_SIZE_FOR_WORDMARK = 128

# ------------------------------------------------------------------- geometry
# All fractions of the icon's width/height, so one layout scales to every size.
TILE_RADIUS = 0.16

# The mark leans: its left edge is inset at the top and pushed out at the
# bottom, with the right edge close to vertical - as in the logo.
MARK_TOP_LEFT = 0.255
MARK_BOTTOM_LEFT = 0.145
MARK_TOP_RIGHT = 0.855
MARK_BOTTOM_RIGHT = 0.880

# With LAB underneath the mark sits in the upper two-thirds; without it (the
# smallest icons, where any lettering turns to mush) the mark fills the tile.
MARK_TOP = 0.050
MARK_BOTTOM = 0.660
MARK_TOP_ALONE = 0.105
MARK_BOTTOM_ALONE = 0.880

WORDMARK_CAP = 0.082        # cap height of each line, shrunk if it would not fit
WORDMARK_LEADING = 0.150    # baseline to baseline
WORDMARK_INSET = 0.050      # clearance from the mark's edges

STRAPLINE_CAP = 0.205
STRAPLINE_CENTRE = 0.830    # vertical centre of the LAB band

FONT_CANDIDATES = (
    ROOT / "fonts" / "Montserrat-Bold.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    Path("C:/Windows/Fonts/segoeuib.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
)


def font_path() -> Path:
    for candidate in FONT_CANDIDATES:
        if candidate.is_file():
            return candidate
    sys.exit(
        "No bold sans-serif font found. Expected packaging/fonts/Montserrat-Bold.ttf"
    )


def fitted_font(path: Path, cap_height: float) -> ImageFont.FreeTypeFont:
    """A font whose CAPITAL letters are cap_height pixels tall.

    Point size is not cap height - the ratio differs per typeface - so this
    measures a capital and scales until it matches.
    """
    probe_size = 100
    probe = ImageFont.truetype(str(path), probe_size)
    top, bottom = probe.getbbox("H")[1], probe.getbbox("H")[3]
    ratio = (bottom - top) / probe_size
    return ImageFont.truetype(str(path), max(1, round(cap_height / ratio)))


def mark_edges(y: float, top: float, bottom: float) -> tuple[float, float]:
    """Left and right edges of the leaning mark at height y (all fractions)."""
    down = (y - top) / (bottom - top)
    left = MARK_TOP_LEFT + (MARK_BOTTOM_LEFT - MARK_TOP_LEFT) * down
    right = MARK_TOP_RIGHT + (MARK_BOTTOM_RIGHT - MARK_TOP_RIGHT) * down
    return left, right


def draw_centred(draw: ImageDraw.ImageDraw, text: str, font, centre_x: float,
                 centre_y: float, fill) -> None:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text((centre_x - (right + left) / 2, centre_y - (bottom + top) / 2),
              text, font=font, fill=fill)


def draw_wordmark(draw: ImageDraw.ImageDraw, big: int, path: Path) -> None:
    """The three logo lines, left-aligned inside the mark and sized to fit.

    The mark leans, so every line has a different amount of room: the top line
    starts furthest right, while the longest word sits lower where the mark is
    wider. Each line is measured against the width available at its own height
    and the tightest of them sets the size for the block, so nothing crosses an
    edge however the wording changes.
    """
    block = (len(WORDMARK) - 1) * WORDMARK_LEADING
    centre = (MARK_TOP + MARK_BOTTOM) / 2
    first_baseline = centre - block / 2 + WORDMARK_CAP / 2
    baselines = [first_baseline + index * WORDMARK_LEADING
                 for index in range(len(WORDMARK))]

    font = fitted_font(path, WORDMARK_CAP * big)
    scale = 1.0
    for line, baseline in zip(WORDMARK, baselines):
        left, right = mark_edges(baseline - WORDMARK_CAP, MARK_TOP, MARK_BOTTOM)
        available = (right - left - 2 * WORDMARK_INSET) * big
        width = draw.textlength(line, font=font)
        if width > 0:
            scale = min(scale, available / width)
    if scale < 1.0:
        font = fitted_font(path, WORDMARK_CAP * big * scale)

    # Align the block on the tightest left edge, so the lines stay flush.
    left_edge = max(
        mark_edges(baseline - WORDMARK_CAP, MARK_TOP, MARK_BOTTOM)[0]
        for baseline in baselines
    )
    x = (left_edge + WORDMARK_INSET) * big
    for line, baseline in zip(WORDMARK, baselines):
        draw.text((x, baseline * big), line, font=font, fill=WHITE + (255,),
                  anchor="ls")


def render(size: int) -> Image.Image:
    big = size * SUPERSAMPLE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    path = font_path()

    with_strapline = size >= MIN_SIZE_FOR_STRAPLINE
    top = MARK_TOP if with_strapline else MARK_TOP_ALONE
    bottom = MARK_BOTTOM if with_strapline else MARK_BOTTOM_ALONE

    # The cream tile.
    draw.rounded_rectangle(
        (0, 0, big - 1, big - 1), radius=TILE_RADIUS * big, fill=CREAM + (255,)
    )

    # The mark itself.
    draw.polygon(
        [
            (MARK_TOP_LEFT * big, top * big),
            (MARK_TOP_RIGHT * big, top * big),
            (MARK_BOTTOM_RIGHT * big, bottom * big),
            (MARK_BOTTOM_LEFT * big, bottom * big),
        ],
        fill=GREEN + (255,),
    )

    if size >= MIN_SIZE_FOR_WORDMARK:
        draw_wordmark(draw, big, path)

    if with_strapline:
        font = fitted_font(path, STRAPLINE_CAP * big)
        draw_centred(draw, STRAPLINE, font, big / 2, STRAPLINE_CENTRE * big,
                     GREEN + (255,))

    return image.resize((size, size), Image.LANCZOS)


def build_ico(target: Path) -> Path:
    """Write a multi-size .ico, each entry a PNG (Windows Vista and later)."""
    images = []
    for size in SIZES:
        from io import BytesIO

        buffer = BytesIO()
        render(size).save(buffer, format="PNG", optimize=True)
        images.append(buffer.getvalue())

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, payload = b"", b""
    for size, data in zip(SIZES, images):
        entries += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,      # 0 means 256 in the ICO format
            0 if size >= 256 else size,
            0, 0, 1, 32, len(data), offset,
        )
        payload += data
        offset += len(data)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(header + entries + payload)
    return target


def build_preview(target: Path) -> Path:
    """A side-by-side sheet of every size, for checking the result by eye."""
    pad = 16
    width = sum(size + pad for size in SIZES) + pad
    height = max(SIZES) + 2 * pad
    sheet = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    x = pad
    for size in SIZES:
        sheet.paste(render(size), (x, height - pad - size), render(size))
        x += size + pad
    sheet.save(target)
    return target


def build_png(target: Path, size: int = 256) -> Path:
    """A plain PNG of the icon.

    Tk's iconbitmap does not reliably read PNG-compressed .ico files, so the
    running window sets its icon from this instead; the .ico stays for the
    executable's own resource, which Windows reads directly.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    render(size).save(target, format="PNG", optimize=True)
    return target


if __name__ == "__main__":
    written = build_ico(ROOT / "icon.ico")
    print(f"wrote {written} ({written.stat().st_size:,} bytes)")
    print(f"sizes: {', '.join(str(s) for s in SIZES)}")
    png = build_png(ROOT / "icon.png")
    print(f"wrote {png} ({png.stat().st_size:,} bytes)")
    if "--preview" in sys.argv:
        preview = build_preview(ROOT / "icon-preview.png")
        print(f"wrote {preview}")
