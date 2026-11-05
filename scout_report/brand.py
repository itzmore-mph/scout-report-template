"""Personal logo, variant F: bold stacked name, green rule, tracked tagline.

    Moritz Philipp |  FOOTBALL
    Haaf           |  SCOUTING
                   |  & DATA

Small mark (avatar, favicon): M | H in the same weight.
All text is converted to vector paths, so the logo renders identically everywhere,
with or without the font installed.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from matplotlib import ft2font
from matplotlib.font_manager import FontProperties
from matplotlib.path import Path as MplPath
from matplotlib.textpath import TextPath

FONT_DIRS = [Path(__file__).resolve().parent.parent / "assets" / "fonts",
             Path("/usr/share/fonts/opentype/inter")]
FONT_NAME = "InterDisplay-ExtraBold.otf"
FONT_TAG = "Inter-SemiBold.otf"

NAME_SIZE = 40.0
NAME_LEADING = 0.94      # baseline distance as a share of the name size
NAME_TRACKING = -0.022   # em, display type set tight
TAG_SIZE = 11.5
TAG_TRACKING = 0.20      # em
TAG_LEADING = 1.7        # baseline distance as a share of the tag size
RULE_W = 3.0
GAP = 18.0


def _font_path(name: str) -> str:
    for folder in FONT_DIRS:
        if (folder / name).exists():
            return str(folder / name)
    raise FileNotFoundError(f"Logo font missing: {name}. Expected in assets/fonts/.")


def _to_d(tp: TextPath, dx: float = 0.0) -> str:
    """Convert a matplotlib text path to SVG path data (y flipped, baseline at 0)."""
    d, verts, codes, i = [], tp.vertices, tp.codes, 0
    while i < len(verts):
        code = codes[i]
        if code == MplPath.MOVETO:
            d.append(f"M{verts[i][0] + dx:.2f} {-verts[i][1]:.2f}"); i += 1
        elif code == MplPath.LINETO:
            d.append(f"L{verts[i][0] + dx:.2f} {-verts[i][1]:.2f}"); i += 1
        elif code == MplPath.CURVE3:
            (x1, y1), (x2, y2) = verts[i], verts[i + 1]
            d.append(f"Q{x1 + dx:.2f} {-y1:.2f} {x2 + dx:.2f} {-y2:.2f}"); i += 2
        elif code == MplPath.CURVE4:
            (x1, y1), (x2, y2), (x3, y3) = verts[i], verts[i + 1], verts[i + 2]
            d.append(f"C{x1 + dx:.2f} {-y1:.2f} {x2 + dx:.2f} {-y2:.2f} {x3 + dx:.2f} {-y3:.2f}"); i += 3
        elif code == MplPath.CLOSEPOLY:
            d.append("Z"); i += 1
        else:
            i += 1
    return " ".join(d)


@lru_cache(maxsize=128)
def text_path(text: str, font_file: str, size: float, tracking: float = 0.0) -> tuple[str, float, float, float]:
    """Outline text. Returns (d, width, cap height, descent), baseline at y = 0.

    Without tracking the whole string is outlined at once; with tracking each glyph is
    placed at its font advance plus tracking (used for the capitalised tagline).
    """
    path = _font_path(font_file)
    fp = FontProperties(fname=path)
    cap = TextPath((0, 0), "H", size=size, prop=fp).get_extents().y1
    if not tracking:
        tp = TextPath((0, 0), text, size=size, prop=fp)
        ext = tp.get_extents()
        return _to_d(tp), float(ext.x1), float(cap), float(max(0.0, -ext.y0))

    face = ft2font.FT2Font(path)
    face.set_size(size, 72)
    parts, x, low = [], 0.0, 0.0
    for ch in text:
        advance = face.load_char(ord(ch)).linearHoriAdvance / 65536
        if not ch.isspace():
            tp = TextPath((0, 0), ch, size=size, prop=fp)
            parts.append(_to_d(tp, dx=x))
            low = min(low, tp.get_extents().y0)
        x += advance + tracking * size
    return " ".join(parts), x - tracking * size, float(cap), float(max(0.0, -low))


def _path(d: str, x: float, y: float, fill: str) -> str:
    return f'<path transform="translate({x:.2f} {y:.2f})" d="{d}" fill="{fill}"/>'


def _tag_lines(tagline: str) -> list[str]:
    """'Football Scouting & Data' -> ['FOOTBALL', 'SCOUTING', '& DATA']."""
    words = tagline.upper().split()
    lines, i = [], 0
    while i < len(words):
        if words[i] == "&" and i + 1 < len(words):
            lines.append(f"& {words[i + 1]}"); i += 2
        else:
            lines.append(words[i]); i += 1
    return lines


def _split_name(name: str) -> list[str]:
    """Given names on the first line, surname on the second."""
    parts = name.split()
    return [" ".join(parts[:-1]), parts[-1]] if len(parts) > 1 else [name]


def lockup(name: str, tagline: str | None, ink: str, muted: str, accent: str,
           layout: str = "stacked") -> tuple[str, float, float]:
    """Logo lockup. 'stacked' is the primary logo, 'line' a single-line version for tight spaces.

    Returns (svg inner markup, width, height) in user units.
    """
    if layout == "line":
        d, w, cap, desc = text_path(name, FONT_NAME, NAME_SIZE * 0.75, NAME_TRACKING)
        parts = [_path(d, 0, cap + 4, ink)]
        rule_x = w + GAP * 0.8
        parts.append(f'<rect x="{rule_x:.2f}" y="0" width="{RULE_W * 0.8:.2f}" height="{cap + 8:.2f}" fill="{accent}"/>')
        width = rule_x + RULE_W
        if tagline:
            td, tw, tcap, _ = text_path(tagline.upper(), FONT_TAG, TAG_SIZE, TAG_TRACKING)
            tx = rule_x + RULE_W * 0.8 + GAP * 0.8
            parts.append(_path(td, tx, (cap + 8 + tcap) / 2, muted))
            width = tx + tw
        return "".join(parts), width + 1, cap + 8 + desc

    lines = _split_name(name)
    leading = NAME_SIZE * NAME_LEADING
    outlined = [text_path(t, FONT_NAME, NAME_SIZE, NAME_TRACKING) for t in lines]
    cap = outlined[0][2]
    top = 2.0
    first_base = top + cap
    last_base = first_base + leading * (len(lines) - 1)
    parts = [_path(d, 0, first_base + k * leading, ink) for k, (d, _, _, _) in enumerate(outlined)]
    name_w = max(w for _, w, _, _ in outlined)

    rule_x = name_w + GAP
    rule_top, rule_bottom = top, last_base
    parts.append(f'<rect x="{rule_x:.2f}" y="{rule_top:.2f}" width="{RULE_W}" '
                 f'height="{rule_bottom - rule_top:.2f}" fill="{accent}"/>')
    width = rule_x + RULE_W

    if tagline:
        tags = [text_path(t, FONT_TAG, TAG_SIZE, TAG_TRACKING) for t in _tag_lines(tagline)]
        step = TAG_SIZE * TAG_LEADING
        tx = rule_x + RULE_W + GAP
        # Bottom-align the tagline with the surname's baseline.
        for k, (d, _, _, _) in enumerate(tags):
            parts.append(_path(d, tx, last_base - step * (len(tags) - 1 - k), muted))
        width = tx + max(w for _, w, _, _ in tags)

    height = last_base + outlined[-1][3] + top
    return "".join(parts), width + 1, height


def initials(name: str) -> tuple[str, str]:
    """First and last initial, e.g. 'Moritz Philipp Haaf' -> ('M', 'H')."""
    parts = [p for p in name.split() if p[:1].isalpha()]
    return parts[0][0].upper(), parts[-1][0].upper()


def mark(name: str, ink: str, accent: str, size: float = 64) -> str:
    """Initials with the accent rule between them, centred in a size x size square."""
    first, last = initials(name)
    fs = size * 0.36
    d1, w1, cap, _ = text_path(first, FONT_NAME, fs)
    d2, w2, _, _ = text_path(last, FONT_NAME, fs)
    gap = 0.30 * cap
    rule_w = size * 0.045
    rule_h = cap * 1.45
    total = w1 + gap + rule_w + gap + w2
    x0 = (size - total) / 2
    base = (size + cap) / 2
    return (_path(d1, x0, base, ink)
            + f'<rect x="{x0 + w1 + gap:.2f}" y="{(size - rule_h) / 2:.2f}" width="{rule_w:.2f}" '
              f'height="{rule_h:.2f}" fill="{accent}"/>'
            + _path(d2, x0 + w1 + gap + rule_w + gap, base, ink))


def tile(name: str, background: str, ink: str, accent: str, size: float = 64, radius: float = 0.22) -> str:
    """Avatar / favicon: the initials mark on a filled square (radius as share of size, 0 = square)."""
    return (f'<rect width="{size}" height="{size}" rx="{size * radius:.2f}" fill="{background}"/>'
            + mark(name, ink, accent, size))


def svg(inner: str, width: float, height: float, pad: float = 0, px_height: float | None = None,
        background: str | None = None) -> str:
    """Wrap markup in a standalone SVG element."""
    w, h = width + 2 * pad, height + 2 * pad
    size = f' height="{px_height}" width="{px_height * w / h:.1f}"' if px_height else ""
    bg = f'<rect x="{-pad}" y="{-pad}" width="{w}" height="{h}" fill="{background}"/>' if background else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} {w:.2f} {h:.2f}"{size} '
            f'role="img" aria-label="logo">{bg}{inner}</svg>')
