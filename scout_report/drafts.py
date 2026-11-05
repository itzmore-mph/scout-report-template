"""Data drafts for unwritten report fields and detection of unedited TEMPLATE.yaml prompts.

Drafts state facts from the export and the report YAML only. Nothing here claims a video observation:
projection, fit, traits, grades, rating, level and recommendation are never drafted.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from . import charts, data

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = ROOT / "reports" / "TEMPLATE.yaml"


# --------------------------------------------------------------------------- placeholders

def load_template(path: Path = TEMPLATE_PATH) -> dict:
    """The blank report whose text fields are writing prompts. Empty dict if it is missing."""
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _norm(text) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def _prompts(template_value) -> set[str]:
    """All prompt strings of a template field: the string itself, list items, or `text` of dict items."""
    if template_value in (None, ""):
        return set()
    if isinstance(template_value, str):
        return {_norm(template_value)}
    if isinstance(template_value, dict):
        return {_norm(template_value["text"])} if template_value.get("text") else set()
    if isinstance(template_value, list):
        return set().union(*(_prompts(v) for v in template_value)) if template_value else set()
    return set()


def is_unwritten(value, template_value=None) -> bool:
    """True if `value` is empty, missing or still equal to the template prompt (string or list item)."""
    if value is None or (isinstance(value, (str, list, dict)) and not value):
        return True
    if isinstance(value, list):
        return all(is_unwritten(v, template_value) for v in value)
    if isinstance(value, dict):
        return is_unwritten(value.get("text"), template_value)
    if isinstance(value, str):
        return not value.strip() or _norm(value) in _prompts(template_value)
    return False


def clean_list(values: list | None, template_values=None) -> list:
    """Drop prompt items, keep written ones."""
    return [v for v in values or [] if not is_unwritten(v, template_values)]


# --------------------------------------------------------------------------- formatting

def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def metric_line(m: dict) -> str:
    """'Defensive duels won % 78% (99th pct)'."""
    return f"{m['label']} {charts.fmt_metric(m['raw'], m['label'])} ({ordinal(round(m['percentile']))} pct)"


def _draft(text: str) -> dict:
    return {"text": text, "draft": True}


def _ranked(profile: list[dict]) -> list[dict]:
    return sorted([m for m in profile if not pd.isna(m["percentile"])], key=lambda m: -m["percentile"])


def league_name(value: str) -> str:
    """'Poland Ekstraklasa 2026-27' -> 'Poland Ekstraklasa'."""
    return re.sub(r"\s+\d{4}(-\d{2,4})?$", "", str(value)).strip()


# --------------------------------------------------------------------------- drafts

def draft_strengths(profile: list[dict]) -> list[dict]:
    """Metrics at or above the 80th percentile, highest first, max 4."""
    return [_draft(metric_line(m)) for m in _ranked(profile) if m["percentile"] >= 80][:4]


def draft_development(profile: list[dict]) -> list[dict]:
    """Metrics at or below the 25th percentile, lowest first, max 3. Empty if none."""
    return [_draft(metric_line(m)) for m in reversed(_ranked(profile)) if m["percentile"] <= 25][:3]


def compare_role(df: pd.DataFrame, player: dict, ctx: dict, template_key: str, codes: list[str],
                 template: dict, column_overrides: dict | None, fallback_team: str | None) -> dict | None:
    """Role score and rank of the target in the `compare_leagues` pool, or None if not available."""
    leagues = ctx.get("compare_leagues") or []
    if not leagues:
        return None
    try:
        pool = data.build_pool(df, player.get("wyscout_name", player["name"]),
                               player.get("wyscout_team") or fallback_team, template_key, codes,
                               int(ctx.get("compare_min_minutes", 450)), leagues, column_overrides)
        role = data.role_score(pool, data.metric_profile(pool, template, df))
    except (LookupError, KeyError):
        return None
    return {**role, "leagues": leagues}


def draft_risks(contract: date | None, report_date: date, pool: data.Pool, minutes, market_value_missing: bool,
                role: dict, compare: dict | None) -> list[dict]:
    """Risk lines that are facts in the data or the YAML."""
    out = []
    if contract and 0 <= (contract - report_date).days <= 365:
        out.append(f"Contract expires {contract.strftime('%m/%Y')}, within 12 months")
    if pool.target_below_threshold:
        mins = f" ({int(minutes):,} min)" if minutes is not None else ""
        out.append(f"Below the {pool.min_minutes}-minute threshold{mins}")
    if pool.n < 20:
        out.append(f"Small comparison pool (n = {pool.n})")
    if market_value_missing:
        out.append("Market value missing in Wyscout, check Transfermarkt")
    if compare:
        pct_drop = role["percentile"] - compare["percentile"]
        score_drop = role["score"] - compare["score"]
        if pct_drop >= 30 or score_drop >= 0.5:
            target = ", ".join(league_name(l) for l in compare["leagues"])
            out.append(f"Role score fell from {role['score']:+.2f} ({role['rank']}/{role['n']}) to "
                       f"{compare['score']:+.2f} ({compare['rank']}/{compare['n']}) after the move to {target}")
    return [_draft(t) for t in out]


def draft_summary(age, foot, role_name: str, position_code: str, height, minutes, league: str, season,
                  role: dict) -> list[dict]:
    """One factual first bullet. Parts with missing data are left out."""
    who = []
    if age is not None and not pd.isna(age):
        who.append(f"{int(age)}-year-old")
    if foot and str(foot).strip() not in ("", "-"):
        who.append(f"{str(foot).lower()}-footed")
    if role_name:
        who.append(role_name[0].lower() + role_name[1:])
    first = " ".join(who) or "Player"
    first = first[0].upper() + first[1:]
    if position_code:
        first += f" ({position_code})"
    if height:
        first += f", {int(height)} cm"
    where = " ".join(str(x) for x in (league, season) if x)
    second = f"{int(minutes):,} minutes in {where}, " if minutes is not None and where else ""
    second += f"role score {role['score']:+.2f}, rank {role['rank']} of {role['n']}"
    second = second[0].upper() + second[1:]
    return [_draft(f"{first}. {second}.")]


def yaml_snippet(drafts: dict[str, list[dict]]) -> str:
    """Drafted fields as YAML under `scouting:`, ready to paste into the player file."""
    body = {}
    for key, entries in drafts.items():
        if key == "interpretation":
            body[key] = [{"text": e["text"], "evidence": e.get("evidence", "data")} for e in entries]
        else:
            body[key] = [e["text"] for e in entries]
    return yaml.safe_dump({"scouting": body}, allow_unicode=True, sort_keys=False, width=200)
