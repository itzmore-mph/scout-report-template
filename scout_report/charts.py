"""Scatter charts exported as inline SVG so text inherits the report's web fonts."""

from __future__ import annotations

import io
import logging
import math
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)


def configure(fonts: dict) -> None:
    """Keep SVG text as live text so the browser renders it with the report fonts."""
    plt.rcParams.update({
        "svg.fonttype": "none",
        "font.family": [fonts.get("body", "Inter"), "DejaVu Sans"],
        "axes.unicode_minus": False,
    })


def _to_svg(fig) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", transparent=True, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    svg = buf.getvalue()
    svg = svg[svg.find("<svg"):]
    # Let CSS control the rendered size: drop fixed width/height, keep viewBox.
    svg = re.sub(r'(<svg[^>]*?)\s(width|height)="[^"]*"', r"\1", svg, count=1)
    svg = re.sub(r'(<svg[^>]*?)\s(width|height)="[^"]*"', r"\1", svg, count=1)
    return svg


def fmt_metric(value: float, label: str) -> str:
    """Format a raw metric value for display: percentages as integers, small rates with 2 decimals."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    if "%" in label:
        return f"{value:.0f}%"
    return f"{value:.2f}" if abs(value) < 1 else f"{value:.1f}"


# --------------------------------------------------------------------------- scatter

# --------------------------------------------------------------------------- pizza

def _wrap(label: str, width: int = 15) -> str:
    """Wrap a metric label, keeping the unit (/90, %) attached to the last word."""
    import textwrap
    return "\n".join(textwrap.wrap(re.sub(r" (/90|%)$", " \\1", label), width))


def tier(pct: float, cuts: dict) -> str:
    """Strength tier of a percentile: strong, average or weak."""
    if pct is None or pd.isna(pct):
        return "average"
    return "strong" if pct >= cuts["strong"] else "weak" if pct <= cuts["weak"] else "average"


def pizza_chart(profile: list[dict], theme: dict, cuts: dict, size: float = 7.6) -> tuple[str, str]:
    """Percentile pizza. Slice colour = strength tier, label colour = metric category.

    Uses mplsoccer's PyPizza when installed and a matching matplotlib fallback otherwise.
    Returns the SVG and the engine name.
    """
    params = [_wrap(m["label"]) for m in profile]
    values = [0 if pd.isna(m["percentile"]) else int(round(m["percentile"])) for m in profile]
    tiers = [tier(m["percentile"], cuts) for m in profile]
    slice_colors = [theme["tier_colors"][t] for t in tiers]
    value_inks = [theme["tier_ink"][t] for t in tiers]
    label_colors = [theme["categories"][m["category_index"] % len(theme["categories"])] for m in profile]
    label_kw = dict(fontsize=10.5, fontweight="semibold", va="center", linespacing=1.05)
    value_kw = dict(fontsize=11.5, fontweight="bold", zorder=4)

    try:
        from mplsoccer import PyPizza
    except ImportError:
        PyPizza = None

    if PyPizza is not None:
        baker = PyPizza(
            params=params, background_color=theme["panel"],
            straight_line_color=theme["panel"], straight_line_lw=1.5,
            last_circle_color=theme["faint"], last_circle_lw=1.0,
            other_circle_color=theme["faint"], other_circle_lw=0.8, other_circle_ls=(0, (2, 3)),
            inner_circle_size=16)
        fig, _ = baker.make_pizza(
            values, figsize=(size, size), param_location=113,
            slice_colors=slice_colors, value_colors=value_inks, value_bck_colors=slice_colors,
            color_blank_space="same", blank_alpha=0.18,
            kwargs_slices=dict(edgecolor=theme["panel"], zorder=2, linewidth=1.5),
            kwargs_params=dict(color=theme["text"], **label_kw),
            kwargs_values=dict(**value_kw, bbox=dict(edgecolor=theme["panel"], facecolor=slice_colors[0],
                                                     boxstyle="round,pad=0.28", lw=1.2)))
        for text, color in zip(baker.get_param_texts(), label_colors):
            text.set_color(color)
        fig.patch.set_alpha(0)
        return _to_svg(fig), "mplsoccer"

    # Fallback with PyPizza's geometry: slices clockwise from 12 o'clock, tangential labels
    # flipped in the lower half so they stay readable.
    n = len(values)
    width = 2 * np.pi / n
    thetas = np.arange(n) * width + width / 2
    fig = plt.figure(figsize=(size, size))
    ax = fig.add_subplot(projection="polar")
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 100)
    ax.set_rorigin(-16)
    ax.axis("off")
    ax.bar(thetas, [100] * n, width=width, color=slice_colors, alpha=0.18, edgecolor=theme["panel"], lw=1.5, zorder=1)
    ax.bar(thetas, values, width=width, color=slice_colors, edgecolor=theme["panel"], lw=1.5, zorder=2)
    ring = np.linspace(0, 2 * np.pi, 360)
    for r in (20, 40, 60, 80):
        ax.plot(ring, [r] * ring.size, color=theme["faint"], lw=0.8, ls=(0, (2, 3)), zorder=3)
    ax.plot(ring, [100] * ring.size, color=theme["faint"], lw=1.0, zorder=3)
    for theta, v, sc, ink, lc, p in zip(thetas, values, slice_colors, value_inks, label_colors, params):
        ax.text(theta, v, str(v), ha="center", va="center", color=ink, **value_kw,
                bbox=dict(edgecolor=theme["panel"], facecolor=sc, boxstyle="round,pad=0.28", lw=1.2))
        rot = theta + np.pi if np.pi / 2 < theta < 1.5 * np.pi else theta
        ax.text(theta, 113, p, ha="center", rotation=-np.degrees(rot), rotation_mode="anchor", color=lc, **label_kw)
    return _to_svg(fig), "matplotlib"


def _overlaps(box, boxes, pad=2):
    return any(not (box.x1 + pad < b.x0 or box.x0 - pad > b.x1 or box.y1 + pad < b.y0 or box.y0 - pad > b.y1)
               for b in boxes)


def scatter_chart(pool_df: pd.DataFrame, x_col: str, y_col: str, x_label: str, y_label: str,
                  target_idx, name_col: str, theme: dict, highlight: list[str] | None = None,
                  n_labels: int = 4, reference: str = "mean") -> tuple[str, dict]:
    """Pool scatter with the target highlighted, no legend, and inline-labelled average lines."""
    data = pool_df[[name_col, x_col, y_col]].copy()
    data[x_col] = pd.to_numeric(data[x_col], errors="coerce")
    data[y_col] = pd.to_numeric(data[y_col], errors="coerce")
    data = data.dropna(subset=[x_col, y_col])
    others = data.drop(index=target_idx, errors="ignore")
    tgt = data.loc[target_idx] if target_idx in data.index else None

    agg = np.median if reference == "median" else np.mean
    ref_x, ref_y = float(agg(data[x_col])), float(agg(data[y_col]))
    ref_word = "median" if reference == "median" else "avg"

    fig, ax = plt.subplots(figsize=(5.0, 4.0))
    ax.scatter(others[x_col], others[y_col], s=40, color=theme["pool"], alpha=0.9,
               edgecolor=theme["panel"], linewidth=0.7, zorder=2)
    if tgt is not None:
        ax.scatter([tgt[x_col]], [tgt[y_col]], s=150, color=theme["target"],
                   edgecolor=theme["text"], linewidth=1.6, zorder=5)

    # Axis limits with headroom for labels.
    xs, ys = data[x_col], data[y_col]
    xpad, ypad = (xs.max() - xs.min()) * 0.08 or 1, (ys.max() - ys.min()) * 0.10 or 1
    ax.set_xlim(xs.min() - xpad, xs.max() + xpad)
    ax.set_ylim(ys.min() - ypad, ys.max() + ypad * 1.4)

    line_kw = dict(color=theme["muted"], lw=1.0, ls=(0, (4, 3)), alpha=0.8, zorder=1)
    ax.axvline(ref_x, **line_kw)
    ax.axhline(ref_y, **line_kw)

    # Inline reference labels instead of a legend.
    def _ref(v, span):
        txt = f"{v:.2f}" if span < 3 else f"{v:.1f}"
        return txt.lstrip("-") if float(txt) == 0 else txt

    ax.annotate(f"{ref_word} {_ref(ref_x, xs.max() - xs.min())}", xy=(ref_x, ax.get_ylim()[0]), xytext=(4, 4),
                textcoords="offset points", ha="left", va="bottom", fontsize=8.8, color=theme["muted"])
    ax.annotate(f"{ref_word} {_ref(ref_y, ys.max() - ys.min())}", xy=(ax.get_xlim()[0], ref_y), xytext=(4, 4),
                textcoords="offset points", ha="left", va="bottom", fontsize=8.8, color=theme["muted"])

    # Styling.
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(theme["faint"])
    ax.tick_params(colors=theme["muted"], labelsize=9.5, length=3)
    ax.grid(True, color=theme["faint"], alpha=0.25, lw=0.6, ls=":")
    ax.set_axisbelow(True)
    ax.set_xlabel(x_label, color=theme["text"], fontsize=10.5, fontweight="semibold", labelpad=6)
    ax.set_ylabel(y_label, color=theme["text"], fontsize=10.5, fontweight="semibold", labelpad=6)

    # Pick which comparison players get a name: best combined z-score plus explicit highlights.
    z = ((others[x_col] - xs.mean()) / (xs.std() or 1)) + ((others[y_col] - ys.mean()) / (ys.std() or 1))
    label_idx = list(z.sort_values(ascending=False).index[:n_labels])
    for name in highlight or []:
        label_idx += list(others.index[others[name_col].astype(str).str.casefold() == name.casefold()])
    label_idx = list(dict.fromkeys(label_idx))

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    placed = [ax.xaxis.label.get_window_extent(renderer)]
    # Treat every marker as an obstacle so names never sit on top of dots.
    from matplotlib.transforms import Bbox
    pts = ax.transData.transform(data[[x_col, y_col]].to_numpy())
    for (px, py), idx in zip(pts, data.index):
        r = 9 if idx == target_idx else 3.5
        placed.append(Bbox([[px - r, py - r], [px + r, py + r]]))
    # Reference lines are obstacles too.
    (rx, ry), (x0, y0), (x1, y1) = ax.transData.transform(
        [(ref_x, ref_y), (ax.get_xlim()[0], ax.get_ylim()[0]), (ax.get_xlim()[1], ax.get_ylim()[1])])
    placed += [Bbox([[rx - 1, y0], [rx + 1, y1]]), Bbox([[x0, ry - 1], [x1, ry + 1]])]

    def place(row, bold: bool, color: str, size: float):
        offsets = [(9, 7, "left", "bottom"), (9, -9, "left", "top"), (-9, 7, "right", "bottom"),
                   (-9, -9, "right", "top"), (0, 12, "center", "bottom"), (0, -13, "center", "top")]
        for dx, dy, ha, va in offsets:
            ann = ax.annotate(str(row[name_col]), xy=(row[x_col], row[y_col]), xytext=(dx, dy),
                              textcoords="offset points", ha=ha, va=va, fontsize=size,
                              fontweight="bold" if bold else "medium", color=color, zorder=6)
            box = ann.get_window_extent(renderer)
            inside = ax.get_window_extent(renderer)
            if not _overlaps(box, placed) and inside.x0 <= box.x0 and box.x1 <= inside.x1 \
                    and inside.y0 <= box.y0 and box.y1 <= inside.y1:
                placed.append(box)
                return
            ann.remove()

    if tgt is not None:
        place(tgt, True, theme["text"], 11)
    for idx in label_idx:
        place(others.loc[idx], False, theme["muted"], 8.8)

    return _to_svg(fig), {"ref_x": ref_x, "ref_y": ref_y, "n": len(data), "reference": ref_word}
