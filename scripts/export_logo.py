"""Export the personal logo set (SVG and PNG, light and dark) to assets/brand/.

Usage: python scripts/export_logo.py
Name and tagline come from config/theme.yaml. All text is outlined, so the SVGs
render identically without the font installed.

Files:
  logo-<theme>.svg/.png              primary logo: reports, website, title slides
  logo-line-<theme>.svg/.png         single line for email signatures and narrow spaces
  avatar-<theme>.png (800 px)        LinkedIn, X, GitHub profile picture
  favicon.svg, favicon-32.png, favicon-180.png   itzmore.dev
  brand-sheet.png                    overview of the full set
"""

import sys
from pathlib import Path

import yaml
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scout_report import brand  # noqa: E402

OUT = ROOT / "assets" / "brand"


def sized(svg_src: str, width: int) -> str:
    return svg_src.replace("<svg ", f'<svg width="{width}" ', 1)


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config" / "theme.yaml").read_text(encoding="utf-8"))
    name, tag = cfg["brand"]["name"], cfg["brand"]["tagline"]
    themes = {"paper": cfg["themes"]["paper"], "night": cfg["themes"]["night"]}
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        old.unlink()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def png(svg_src: str, path: Path, width: int) -> None:
            page.set_content(f'<html><body style="margin:0">{sized(svg_src, width)}</body></html>')
            page.locator("svg").screenshot(path=str(path), omit_background=True)

        for key, th in themes.items():
            for layout, stem in (("stacked", f"logo-{key}"), ("line", f"logo-line-{key}")):
                inner, w, h = brand.lockup(name, tag, th["text"], th["muted"], th["target"], layout)
                (OUT / f"{stem}.svg").write_text(brand.svg(inner, w, h), encoding="utf-8")
                png(brand.svg(inner, w, h, pad=h * 0.35, background=th["bg"]), OUT / f"{stem}.png", 1600)
            # Full-bleed square: LinkedIn, X and GitHub crop avatars to a circle themselves.
            avatar = brand.svg(brand.tile(name, th["bg"], th["text"], th["target"], radius=0), 64, 64)
            png(avatar, OUT / f"avatar-{key}.png", 800)

        night = themes["night"]
        favicon = brand.svg(brand.tile(name, night["bg"], night["text"], night["target"]), 64, 64)
        (OUT / "favicon.svg").write_text(favicon, encoding="utf-8")
        for size in (32, 180):
            png(favicon, OUT / f"favicon-{size}.png", size)

        def lock(th, layout, px):
            i, w, h = brand.lockup(name, tag, th["text"], th["muted"], th["target"], layout)
            return brand.svg(i, w, h, px_height=px)

        def tiles(th):
            return "".join(brand.svg(brand.tile(name, th["bg"], th["text"], th["target"]), 64, 64, px_height=s)
                           for s in (128, 64, 32))

        sheet = "".join(
            f'<section style="background:{th["bg"]};padding:60px 64px;display:flex;flex-direction:column;gap:52px">'
            f'<div style="display:flex;gap:72px;align-items:flex-end">{lock(th, "stacked", 120)}'
            f'<div style="display:flex;gap:28px;align-items:flex-end;outline:1px solid {th["panel_line"]};outline-offset:12px">{tiles(th)}</div></div>'
            f'<div style="display:flex;gap:56px;align-items:flex-end">{lock(th, "stacked", 60)}{lock(th, "line", 30)}</div></section>'
            for th in themes.values())
        page.set_viewport_size({"width": 1100, "height": 800})
        page.set_content(f'<html><body style="margin:0">{sheet}</body></html>')
        page.screenshot(path=str(OUT / "brand-sheet.png"), full_page=True)
        browser.close()
    print(f"Wrote {len(list(OUT.iterdir()))} files to {OUT}")


if __name__ == "__main__":
    main()
