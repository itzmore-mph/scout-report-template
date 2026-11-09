"""Assemble report context, render the HTML template and export PNG/PDF with Playwright."""

from __future__ import annotations

import base64
import mimetypes
import numbers
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import brand as brand_mark, charts, data, drafts
from .config import load_config
from .drafts import ordinal

ROOT = Path(__file__).resolve().parent.parent
PAGE_W, PAGE_H = 1920, 1080


# --------------------------------------------------------------------------- helpers

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def data_uri(path: str | Path | None, base: Path) -> str | None:
    """Embed an image file so the HTML stays self-contained."""
    if not path:
        return None
    p = Path(path)
    p = p if p.is_absolute() else (base / p)
    if not p.exists():
        print(f"  ! image not found, using placeholder: {p}")
        return None
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def to_date(value) -> date | None:
    if value in (None, "", "-") or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        return value.date()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(str(value).split(" ")[0], fmt).date()
        except ValueError:
            continue
    return None


def age_on(dob: date | None, ref: date) -> int | None:
    if not dob:
        return None
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))


def fmt_value(value) -> str:
    """Format Wyscout market values (plain euros) as €100K / €1.2M."""
    if value is None or (isinstance(value, float) and pd.isna(value)) or value in ("", 0):
        return "-"
    if isinstance(value, str):
        return value
    v = float(value)
    if v >= 1_000_000:
        return f"€{v / 1_000_000:.1f}M".replace(".0M", "M")
    if v >= 1_000:
        return f"€{v / 1_000:.0f}K"
    return f"€{v:.0f}"


def initials(text: str) -> str:
    parts = [p for p in re.split(r"[\s\-]+", text) if p and p[0].isalpha()]
    return "".join(p[0] for p in parts[:2]).upper()


def pick(override, row: pd.Series, col: str | None, zero_missing: bool = False):
    """YAML value wins; otherwise fall back to the export.

    Wyscout writes 0 for unknown height, weight and market value, so those treat 0 as missing.
    """
    if override not in (None, ""):
        return override
    if col and col in row.index and not pd.isna(row[col]):
        value = row[col]
        if zero_missing and isinstance(value, numbers.Number) and value == 0:
            return None
        if isinstance(value, str) and value.strip().lower() in {"", "unknown", "-"}:
            return None
        return value
    return None


# --------------------------------------------------------------------------- context

def scale_max(grading: dict) -> int:
    return max(int(k) for k in grading["scale"])


def check_scale(value, what: str, grading: dict) -> int | None:
    """Validate a value on the unified scale (1 to max). Empty stays None."""
    if value in (None, ""):
        return None
    top = scale_max(grading)
    if not (isinstance(value, numbers.Number) and 1 <= value <= top and float(value).is_integer()):
        raise ValueError(f"{what} = {value!r} must be a whole number from 1 to {top} (config/grading.yaml `scale`)")
    return int(value)


def tone(grade: int | None, source: str, grading: dict) -> str:
    """'good', 'mid' or 'bad' for pip and grade colours."""
    if not grade:
        return ""
    cuts = grading["scale_tones"][source]
    return "good" if grade >= cuts["good"] else "bad" if grade <= cuts["bad"] else "mid"


def build_grades(raw: dict, grading: dict, source: str) -> list[dict]:
    """Four-corner attribute grades on the unified scale, relative to the club's level."""
    corners = []
    for corner in grading["corners"]:
        attrs = []
        for name, value in ((raw or {}).get(corner) or {}).items():
            grade = check_scale(value, f"grades.{corner}.{name}", grading)
            attrs.append({"name": name, "grade": grade or 0, "tone": tone(grade, source, grading)})
        graded = [a["grade"] for a in attrs if a["grade"]]
        avg = sum(graded) / len(graded) if graded else None
        corners.append({"name": corner, "attributes": attrs, "avg": avg})
    return corners


def scale_key(grading: dict, club_level: dict | None) -> str:
    """One line on how the rating, grades and level ladder relate."""
    top, levels = scale_max(grading), grading["levels"]
    at = next((int(k) for k, v in grading["scale"].items() if str(v).lower() == "at our level"), None)
    our = f" ({club_level['key']}, {club_level['label']})" if club_level else ""
    anchor = f", {at} = at our level{our}" if at else ""
    return (f"Scales: rating and grades 1 to {top} vs our level{anchor}. "
            f"Levels from {levels[0]['key']} {levels[0]['label']} to {levels[-1]['key']} {levels[-1]['label']}.")


def build_ladder(level: dict, grading: dict) -> dict:
    """Level ladder rungs with current, potential and club markers."""
    keys = [lv["key"] for lv in grading["levels"]]
    cur, pot, club = level.get("current"), level.get("potential"), level.get("club")
    for key in (cur, pot, club):
        if key and key not in keys:
            raise KeyError(f"Level '{key}' not defined in config/grading.yaml ({keys})")
    idx = {k: i for i, k in enumerate(keys)}
    span = sorted([idx[cur], idx[pot]]) if cur and pot else None
    rungs = [{**lv,
              "current": lv["key"] == cur, "potential": lv["key"] == pot, "club": lv["key"] == club,
              "in_span": bool(span) and span[0] <= i <= span[1]} for i, lv in enumerate(grading["levels"])]
    if not (cur and pot):
        verdict = "Set current and potential level"
    elif club and idx[cur] <= idx[club]:
        verdict = "Already at our level"
    elif pot and club and idx[pot] <= idx[club]:
        verdict = f"Projected to reach our level{', ' + level['horizon'] if level.get('horizon') else ''}"
    else:
        verdict = "Not projected to reach our level"
    by_key = {lv["key"]: lv for lv in grading["levels"]}
    line = None
    if cur and pot:
        rel = ""
        if club:
            rel = (", our level" if idx[pot] == idx[club] else ", above our level" if idx[pot] < idx[club]
                   else f", below our level ({club})")
        when = f", in {level['horizon']}" if level.get("horizon") else ""
        line = (f"Level now: {by_key[cur]['label']} ({cur}). "
                f"Potential: {by_key[pot]['label']} ({pot}){rel}{when}.")
    return {"rungs": rungs, "verdict": verdict, "horizon": level.get("horizon"), "line": line}


def data_findings(profile: list[dict], role: dict, role_name: str, group_label: str, cuts: dict) -> list[dict]:
    """Factual data statements for a new player: standout metrics, clear weaknesses, role score.

    They describe output only. The scout adds the video view and the context.
    """
    ranked = sorted([m for m in profile if not pd.isna(m["percentile"])], key=lambda m: -m["percentile"])
    out = []
    top = [m for m in ranked if m["percentile"] >= cuts["strong"]][:3]
    if top:
        parts = [f"{m['label']} {charts.fmt_metric(m['raw'], m['label'])} ({ordinal(round(m['percentile']))})" for m in top]
        out.append(f"Standout output against {group_label}: {', '.join(parts)}.")
    weak = [m for m in reversed(ranked) if m["percentile"] <= cuts["weak"]][:2]
    if weak:
        parts = [f"{m['label']} {charts.fmt_metric(m['raw'], m['label'])} ({ordinal(round(m['percentile']))})" for m in weak]
        out.append(f"Below the pool on {', '.join(parts)}.")
    out.append(f"Role score {drafts.role_value(role)} for the {role_name.lower()} profile, rank {role['rank']} of {role['n']}.")
    return [{"text": t, "evidence": "data"} for t in out]


def scatter_specs(defaults: list[dict], overrides: list | None) -> list[dict]:
    """The two scatter pairs: the position template's, replaced slot by slot by the report's `scatters`.

    An empty slot (null or missing) keeps the template pair. Axis labels default to the column header,
    the title to 'Y vs X'.
    """
    overrides = overrides or []
    if not isinstance(overrides, list):
        raise ValueError("`scatters` in the report YAML must be a list of up to two pairs")
    specs = []
    for i, default in enumerate(defaults[:2]):
        spec = overrides[i] if i < len(overrides) and overrides[i] else default
        axes = {}
        for axis in ("x", "y"):
            a = spec.get(axis) if isinstance(spec, dict) else None
            if not (isinstance(a, dict) and a.get("column")):
                raise ValueError(f"scatters[{i}].{axis} needs a `column` (Wyscout header), e.g. "
                                 f"{{column: Progressive passes per 90, label: Progressive passes /90}}")
            axes[axis] = {"column": a["column"], "label": a.get("label") or a["column"]}
        title = spec.get("title") or f"{axes['y']['label']} vs {axes['x']['label']}"
        specs.append({"title": title, **axes})
    return specs


def build_confidence(observations: list[dict], minutes: float, pool_n: int, grading: dict) -> dict:
    """Evidence confidence from matches watched, live views, data minutes and pool size."""
    matches = len(observations)
    live = sum(1 for o in observations if str(o.get("mode", "")).lower() == "live")
    have = {"matches": matches, "live": live, "data_minutes": minutes or 0, "pool": pool_n}
    rules = grading["confidence"]
    level = "Low"
    for name in ("Medium", "High"):
        if all(have[k] >= v for k, v in rules[name].items()):
            level = name
    gaps = []
    if level != "High":
        need = rules["High"]
        if matches < need["matches"]:
            gaps.append(f"{need['matches'] - matches} more match{'es' if need['matches'] - matches > 1 else ''} watched")
        if live < need["live"]:
            gaps.append(f"{need['live'] - live} live view{'s' if need['live'] - live > 1 else ''}")
        if have["data_minutes"] < need["data_minutes"]:
            gaps.append(f"{int(need['data_minutes'] - have['data_minutes'])} more data minutes")
        if pool_n < need["pool"]:
            gaps.append(f"a larger comparison pool (n < {need['pool']})")
    return {"level": level, "score": {"Low": 1, "Medium": 2, "High": 3}[level], "matches": matches,
            "live": live, "video": matches - live, "minutes": int(have["data_minutes"]), "gaps": gaps}


def build_context(report_path: Path, export_path: Path, theme_name: str) -> dict:
    report = yaml.safe_load(report_path.read_text(encoding="utf-8"))
    templates = load_config("metric_templates.yaml")
    theme_cfg = load_config("theme.yaml")
    grading = load_config("grading.yaml")
    theme = theme_cfg["themes"][theme_name]
    charts.configure(theme_cfg["fonts"])

    player, ctx = report["player"], report["context"]
    scouting = report.get("scouting", {}) or {}
    template_key = player["template"]
    template = templates["templates"][template_key]
    codes = templates["position_groups"][template_key]
    leagues = ctx.get("leagues") or []

    df = data.load_export(export_path)
    pool = data.build_pool(df, player.get("wyscout_name", player["name"]), player.get("wyscout_team"),
                           template_key, codes, int(ctx.get("min_minutes", 600)), leagues, report.get("columns"))
    profile = data.metric_profile(pool, template, df)
    role = data.role_score(pool, profile)
    cols, row = pool.columns, pool.target

    cuts = theme_cfg.get("tiers", {"strong": 80, "weak": 20})
    pizza_svg, pizza_engine = charts.pizza_chart(profile, theme, cuts)
    categories = [{"name": c["name"], "color": theme["categories"][i % len(theme["categories"])]}
                  for i, c in enumerate(template["categories"])]

    scatters = []
    for spec in scatter_specs(template["scatters"], report.get("scatters")):
        x_col = data.resolve_column(df, spec["x"]["column"])
        y_col = data.resolve_column(df, spec["y"]["column"])
        svg, meta = charts.scatter_chart(
            pool.df, x_col, y_col, spec["x"]["label"], spec["y"]["label"], row.name, cols["name"],
            theme, highlight=report.get("highlight_players"), n_labels=ctx.get("scatter_labels", 4),
            reference=ctx.get("reference_line", "mean"))
        scatters.append({"title": spec["title"], "svg": svg, **meta})

    base = report_path.parent
    data_date = to_date(ctx.get("data_date")) or date.today()
    report_date = to_date(ctx.get("report_date")) or date.today()
    dob = to_date(player.get("date_of_birth"))
    contract = to_date(pick(player.get("contract_expires"), row, cols.get("contract_expires")))
    height = pick(player.get("height_cm"), row, cols.get("height"), zero_missing=True)
    weight = pick(player.get("weight_kg"), row, cols.get("weight"), zero_missing=True)
    minutes = pick(None, row, cols["minutes"])
    matches = pick(None, row, cols.get("matches"))
    age = age_on(dob, report_date) if dob else pick(None, row, cols.get("age"))
    foot = pick(player.get("foot"), row, cols.get("foot"))
    market_value = pick(player.get("market_value"), row, cols.get("market_value"), zero_missing=True)
    physical = " / ".join(x for x in [f"{int(height)} cm" if height else None,
                                       f"{int(weight)} kg" if weight else None] if x) or "-"

    observations = []
    for o in report.get("observations", []) or []:
        d = to_date(o.get("date"))
        grade = check_scale(o.get("grade"), f"observations[{o.get('date')}].grade", grading)
        observations.append({**o, "grade": grade, "tone": tone(grade, "video", grading),
                             "date_str": d.strftime("%d/%m/%y") if d else "-",
                             "mode": str(o.get("mode", "video")).capitalize()})

    verdict = ctx.get("recommendation", "Monitor")
    if verdict not in grading["verdicts"]:
        raise ValueError(f"Recommendation '{verdict}' must be one of {grading['verdicts']}")
    level = report.get("level", {}) or {}
    club_level = next((lv for lv in grading["levels"] if lv["key"] == level.get("club")), None)
    rating = {k: check_scale((report.get("rating") or {}).get(k), f"rating.{k}", grading)
              for k in ("current", "potential")}
    grades_source = report.get("grades_source") or "video"
    if grades_source not in ("video", "data"):
        raise ValueError(f"grades_source '{grades_source}' must be 'video' or 'data'")

    notes = []
    if pool.n < 20:
        notes.append(f"Small comparison pool (n = {pool.n}): one player moves a percentile by about {100 / pool.n:.0f} points.")
    if pool.target_below_threshold:
        notes.append(f"Below the {pool.min_minutes}-minute threshold: treat the data as indicative.")

    # Unedited TEMPLATE.yaml prompts count as unwritten: they are hidden or replaced by data drafts.
    tpl = drafts.load_template()
    tpl_player, tpl_ctx, tpl_scouting = (tpl.get(k) or {} for k in ("player", "context", "scouting"))
    auto = ctx.get("auto_drafts", True) is not False

    def written(value, tpl_value):
        return None if drafts.is_unwritten(value, tpl_value) else value

    def items(key):
        raw = [i if isinstance(i, dict) else {"text": i} for i in scouting.get(key, []) or []]
        return drafts.clean_list(raw, tpl_scouting.get(key))

    for key in ("name", "club"):
        if drafts.is_unwritten(player.get(key), tpl_player.get(key)):
            print(f"  ! player.{key} is empty or still the TEMPLATE prompt")
    pool_label = ", ".join(leagues) if leagues else ctx.get("league", "")
    role_written = written(player.get("role"), tpl_player.get("role"))
    league_label = written(ctx.get("league"), tpl_ctx.get("league")) or pool_label
    fit = {k: written(ctx.get(k), tpl_ctx.get(k)) for k in ("suitability", "adaptation", "next_action", "team_context")}
    projection = written(scouting.get("projection"), tpl_scouting.get("projection"))

    keys = ("summary", "strengths", "development", "risks", "in_possession", "out_of_possession", "interpretation")
    lists = {k: items(k) for k in keys}
    drafted: dict[str, list[dict]] = {}
    if auto:
        makers = {
            "summary": lambda: drafts.draft_summary(
                age, foot, role_written or template.get("role", template["label"]), player.get("position_code"),
                height, minutes, league_label, ctx.get("season"), role),
            "strengths": lambda: drafts.draft_strengths(profile, cuts),
            "development": lambda: drafts.draft_development(profile, cuts),
            "risks": lambda: drafts.draft_risks(
                contract, report_date, pool, minutes, market_value is None, role,
                drafts.compare_role(df, player, ctx, template_key, codes, template, report.get("columns"),
                                    row.get(cols["team"]))),
        }
        for key, make in makers.items():
            if not lists[key]:
                lists[key] = make()
                if lists[key]:
                    drafted[key] = lists[key]

    evidence_labels = {"both": "Video + data", "video": "Video only", "data": "Data only"}
    findings = data_findings(profile, role, template.get("role", template["label"]), template["label"].lower() + "s",
                             cuts)
    interpretation_auto = auto and not lists["interpretation"]
    if interpretation_auto:
        lists["interpretation"] = drafted["interpretation"] = [{**f, "draft": True} for f in findings]
    else:
        print("  data findings (paste into `interpretation` and add your video view):")
        for f in findings:
            print(f"    - {f['text']}")
    interpretation = [{**i, "evidence_label": evidence_labels.get(i.get("evidence"))} for i in lists["interpretation"]]
    if drafted:
        print(f"  data drafts (paste into {report_path.name} under `scouting:`, then edit):")
        for line in drafts.yaml_snippet(drafted).splitlines():
            print(f"    {line}")
    brand = theme_cfg["brand"]
    logo_inner, logo_w, logo_h = brand_mark.lockup(brand["name"], brand.get("tagline"), theme["text"],
                                                   theme["muted"], theme["target"])
    logo_svg = brand_mark.svg(logo_inner, logo_w, logo_h)
    st_inner, st_w, st_h = brand_mark.lockup(brand["name"], brand.get("tagline"), theme["text"],
                                             theme["muted"], theme["target"], "stacked")
    logo_svg_stacked = brand_mark.svg(st_inner, st_w, st_h)

    return {
        "theme": theme,
        "theme_name": theme_name,
        "fonts": theme_cfg["fonts"],
        "brand": {**brand, "logo_uri": data_uri(brand.get("logo"), ROOT), "logo_svg": logo_svg, "logo_svg_stacked": logo_svg_stacked},
        "player": {
            **player,
            "initials": initials(player["name"]),
            "dob": dob.strftime("%d/%m/%Y") if dob else "-",
            "age": int(age) if age is not None and not pd.isna(age) else None,
            "role": role_written,
            "foot": str(foot or "-").capitalize(),
            "physical": physical,
            "nationality": player.get("nationality") or pick(None, row, cols.get("passport")) or "-",
            "market_value": fmt_value(market_value),
            "contract": contract.strftime("%m/%Y") if contract else "-",
            "agent": player.get("agent") or "-",
            "secondary_positions": player.get("secondary_positions") or [],
            "photo_uri": data_uri(player.get("photo"), base),
            "badge_uri": data_uri(player.get("club_badge"), base),
        },
        "ctx": {
            **ctx,
            **fit,
            "scout": ctx.get("scout") or brand["name"],
            "league": league_label,
            "data_date_str": data_date.strftime("%d %b %Y").lstrip("0"),
            "report_date_str": report_date.strftime("%d %b %Y").lstrip("0"),
            "minutes": int(minutes) if minutes is not None else "-",
            "matches": int(matches) if matches is not None else "-",
            "verdict": verdict,
            "verdict_color": theme["verdict"][verdict],
            "position_label": template["label"],
            "pool_label": pool_label,
        },
        "rating": {**rating, "max": scale_max(grading)},
        "grades": build_grades(report.get("grades"), grading, grades_source),
        "grade_scale": grading["scale"],
        "scale_max": scale_max(grading),
        "data_bands": grading["data_bands"],
        "scale_key": scale_key(grading, club_level),
        "grades_source": grades_source,
        "grades_pool": report.get("grades_pool"),
        "club_level": club_level,
        "ladder": build_ladder(level, grading) if level else None,
        "confidence": build_confidence(report.get("observations", []) or [], minutes, pool.n, grading),
        "observations": observations,
        "scouting": {**scouting, **lists, "projection": projection, "interpretation": interpretation},
        "pizza_svg": pizza_svg,
        "pizza_engine": pizza_engine,
        "categories": categories,
        "tiers": [{"label": f"Top {100 - cuts['strong']}%", "color": theme["tier_colors"]["strong"]},
                  {"label": "Middle", "color": theme["tier_colors"]["average"]},
                  {"label": f"Bottom {cuts['weak']}%", "color": theme["tier_colors"]["weak"]}],
        "role": {**role, "name": template.get("role", template["label"]), "value": drafts.role_value(role),
                 "tone": charts.tier(role["percentile"], cuts)},
        "scatters": scatters,
        "pool_n": pool.n,
        "min_minutes": pool.min_minutes,
        "group_label": template["label"].lower() + "s",
        "notes": notes,
        "interpretation_auto": interpretation_auto,
        "pages": 2,
    }


# --------------------------------------------------------------------------- output

OVERFLOW_JS = """
() => [...document.querySelectorAll('[data-fit]')]
  .filter(el => el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1)
  .map(el => el.getAttribute('data-fit'))
"""


def render(report_path: str | Path, export_path: str | Path, out_dir: str | Path | None = None,
           theme_name: str = "night", scale: float = 2.0, formats: tuple[str, ...] = ("png", "pdf")) -> Path:
    report_path, export_path = Path(report_path).resolve(), Path(export_path).resolve()
    context = build_context(report_path, export_path, theme_name)

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html", "j2"]))
    css = (ROOT / "templates" / "report.css").read_text(encoding="utf-8")
    faces = []
    for f in sorted((ROOT / "assets" / "fonts").glob("*.otf")):
        family = "Inter Display" if f.stem.startswith("InterDisplay") else "Inter"
        weight = {"Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700, "ExtraBold": 800}[f.stem.split("-")[1]]
        faces.append(f'@font-face {{ font-family: "{family}"; font-weight: {weight}; src: local("{family} {f.stem.split("-")[1]}"), url("{f.as_uri()}"); }}')
    css = "\n".join(faces) + "\n" + css
    html = env.get_template("report.html.j2").render(**context, css=css)

    slug = slugify(f"{context['player']['name']} {context['player'].get('position_code', '')}")
    out = Path(out_dir).resolve() if out_dir else ROOT / "output" / slug
    out.mkdir(parents=True, exist_ok=True)
    html_path = out / f"{slug}.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"  html  {html_path}")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": PAGE_W, "height": PAGE_H}, device_scale_factor=scale)
        page.goto(html_path.as_uri())
        page.wait_for_load_state("networkidle")
        page.evaluate("document.fonts.ready")

        overflowing = page.evaluate(OVERFLOW_JS)
        for block in overflowing:
            print(f"  ! text overflows in '{block}'. Shorten the copy for that block.")

        if "png" in formats:
            for i, el in enumerate(page.query_selector_all(".page"), start=1):
                png = out / f"{slug}-p{i}.png"
                el.screenshot(path=str(png))
                print(f"  png   {png}")
        if "pdf" in formats:
            pdf = out / f"{slug}.pdf"
            page.pdf(path=str(pdf), width=f"{PAGE_W}px", height=f"{PAGE_H}px", print_background=True,
                     margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
            print(f"  pdf   {pdf}")
        browser.close()
    return out
