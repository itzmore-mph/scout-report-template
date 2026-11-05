"""Load a Wyscout export, build a positional comparison pool, compute percentiles and a role score."""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

# Default Wyscout export headers for identity and context columns.
# Override them in the report YAML under `columns:` if your export differs.
DEFAULT_COLUMNS = {
    "name": "Player",
    "team": "Team",
    "position": "Position",
    "main_position": "Main Position",
    "league": "League",
    "minutes": "Minutes played",
    "matches": "Matches played",
    "age": "Age",
    "height": "Height",
    "weight": "Weight",
    "foot": "Foot",
    "market_value": "Market value",
    "contract_expires": "Contract expires",
    "passport": "Passport country",
    "on_loan": "On loan",
}
REQUIRED = {"name", "team", "position", "minutes"}


def _norm(text: str) -> str:
    """Normalise a header or name for tolerant matching (case, accents, spacing)."""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().casefold()


def load_export(path: str | Path) -> pd.DataFrame:
    """Read a Wyscout export (.xlsx, .xls or .csv) and tidy its headers."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    elif suffix == ".csv":
        df = pd.read_csv(path, low_memory=False)
    else:
        raise ValueError(f"Unsupported export format: {path.suffix}")
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
    return df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")])


def resolve_column(df: pd.DataFrame, wanted: str, required: bool = True) -> str | None:
    """Return the actual header in `df` that matches `wanted`, tolerant to case and spacing."""
    if wanted in df.columns:
        return wanted
    lookup = {_norm(c): c for c in df.columns}
    if _norm(wanted) in lookup:
        return lookup[_norm(wanted)]
    if not required:
        return None
    suggestions = difflib.get_close_matches(wanted, list(df.columns), n=3, cutoff=0.5)
    hint = f" Closest headers: {suggestions}" if suggestions else ""
    raise KeyError(f"Column '{wanted}' not found in export.{hint}")


def primary_position(value) -> str:
    """Wyscout lists positions as 'LCB, CB'. The first entry is the primary role."""
    if pd.isna(value):
        return ""
    return str(value).split(",")[0].strip().upper()


@dataclass
class Pool:
    """Comparison pool for one target player."""

    df: pd.DataFrame
    target: pd.Series
    group: str
    min_minutes: int
    leagues: list[str]
    target_below_threshold: bool
    columns: dict = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.df)


def filter_leagues(df: pd.DataFrame, leagues: list[str] | None, league_col: str | None) -> pd.DataFrame:
    """Restrict a multi-league export to the competitions named in the report."""
    if not leagues:
        return df
    if not league_col:
        raise KeyError("`leagues` is set in the report but the export has no 'League' column.")
    wanted = {_norm(l) for l in leagues}
    out = df[df[league_col].map(_norm).isin(wanted)]
    if out.empty:
        options = difflib.get_close_matches(leagues[0], df[league_col].dropna().unique().tolist(), n=5, cutoff=0.4)
        raise LookupError(f"No rows for leagues {leagues}. Similar league names: {options}")
    return out


def find_player(df: pd.DataFrame, name: str, team: str | None, cols: dict) -> pd.Series:
    """Locate the target row by Wyscout name, optionally disambiguated by team."""
    name_col = cols["name"]
    hits = df[df[name_col].map(_norm) == _norm(name)]
    if team and len(hits) > 1:
        hits = hits[hits[cols["team"]].map(_norm) == _norm(team)]
    if hits.empty:
        candidates = difflib.get_close_matches(name, df[name_col].astype(str).tolist(), n=5, cutoff=0.6)
        raise LookupError(f"Player '{name}' not found in the selected leagues. Similar names: {candidates}")
    if len(hits) > 1:
        teams = hits[cols["team"]].tolist()
        raise LookupError(f"Player '{name}' is ambiguous ({teams}). Set `wyscout_team` in the report YAML.")
    return hits.iloc[0]


def build_pool(df: pd.DataFrame, player_name: str, team: str | None, group: str, group_codes: list[str],
               min_minutes: int, leagues: list[str] | None = None,
               column_overrides: dict | None = None) -> Pool:
    """Players of the same position group, in the selected leagues, above the minutes threshold.

    The target player is always kept in the pool, even below the threshold, and flagged.
    """
    wanted = {**DEFAULT_COLUMNS, **(column_overrides or {})}
    cols = {key: resolve_column(df, header, required=key in REQUIRED) for key, header in wanted.items()}

    scoped = filter_leagues(df, leagues, cols.get("league"))
    target = find_player(scoped, player_name, team, cols)

    codes = {c.upper() for c in group_codes}
    if cols.get("main_position"):
        positions = scoped[cols["main_position"]].astype(str).str.strip().str.upper()
    else:
        positions = scoped[cols["position"]].map(primary_position)
    minutes = pd.to_numeric(scoped[cols["minutes"]], errors="coerce").fillna(0)
    keep = (positions.isin(codes) & (minutes >= min_minutes)) | (scoped.index == target.name)

    below = float(target[cols["minutes"]] or 0) < min_minutes
    return Pool(df=scoped[keep].copy(), target=target, group=group, min_minutes=min_minutes,
                leagues=list(leagues or []), target_below_threshold=below, columns=cols)


def percentile_rank(values: pd.Series, value: float, invert: bool = False) -> float:
    """Percentile of `value` within `values` (mid-rank for ties), scaled 0 to 100."""
    arr = pd.to_numeric(values, errors="coerce").dropna().to_numpy()
    if arr.size == 0 or value is None or np.isnan(value):
        return float("nan")
    below = np.sum(arr < value)
    equal = np.sum(arr == value)
    pct = 100.0 * (below + 0.5 * equal) / arr.size
    return 100.0 - pct if invert else pct


def metric_profile(pool: Pool, template: dict, df_full: pd.DataFrame) -> list[dict]:
    """Raw values and percentiles for every metric in a position template."""
    rows = []
    for cat_idx, category in enumerate(template["categories"]):
        for metric in category["metrics"]:
            col = resolve_column(df_full, metric["column"])
            raw = pd.to_numeric(pd.Series([pool.target[col]]), errors="coerce").iloc[0]
            rows.append({
                "label": metric["label"],
                "column": col,
                "category": category["name"],
                "category_index": cat_idx,
                "raw": raw,
                "percentile": percentile_rank(pool.df[col], raw, metric.get("invert", False)),
                "invert": metric.get("invert", False),
                "weight": float(metric.get("weight", 1.0)),
            })
    return rows


def role_score(pool: Pool, profile: list[dict]) -> dict:
    """Weighted mean of z-scores across the template metrics, ranked within the pool.

    z-scores keep the distance between players (unlike percentiles), so one standout metric
    and a large gap to the field both show up. Weights come from the positional profile.
    """
    total, weights = pd.Series(0.0, index=pool.df.index), 0.0
    for m in profile:
        if m["weight"] <= 0:
            continue
        x = pd.to_numeric(pool.df[m["column"]], errors="coerce")
        sd = x.std(ddof=0)
        z = ((x - x.mean()) / sd).fillna(0) if sd and not np.isnan(sd) else x * 0
        total += (-z if m["invert"] else z) * m["weight"]
        weights += m["weight"]
    score = total / (weights or 1)
    target = float(score.loc[pool.target.name])
    rank = int((score > target).sum()) + 1
    return {"score": target, "rank": rank, "n": len(score),
            "percentile": percentile_rank(score, target)}
