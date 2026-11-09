"""Rank players by role score within each league, to pick who to write a report on.

Usage:
    python scripts/shortlist.py EXPORT --template CB --max-age 21 \
        --leagues "Austria Bundesliga 2025-26" "Poland Ekstraklasa 2025-26"

Role scores are computed within each league's own pool (same method as the report).
`role_pct` is the 0 to 100 pool percentile shown on the report; `role_z` is the weighted
z-score behind it (+1.0 = one standard deviation above that league's average for the role).
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scout_report import data  # noqa: E402
from scout_report.config import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # player names with accents on Windows consoles
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export")
    ap.add_argument("--template", default="CB")
    ap.add_argument("--leagues", nargs="+", required=True)
    ap.add_argument("--min-minutes", type=int, default=900)
    ap.add_argument("--max-age", type=int, default=99)
    ap.add_argument("--top", type=int, default=5, help="players listed per league")
    ap.add_argument("--out", default=None, help="optional CSV path")
    args = ap.parse_args()

    cfg = load_config("metric_templates.yaml")
    template, codes = cfg["templates"][args.template], cfg["position_groups"][args.template]
    df = data.load_export(args.export)

    rows = []
    for league in args.leagues:
        scoped = data.filter_leagues(df, [league], "League")
        pos = scoped["Main Position"].astype(str).str.upper() if "Main Position" in scoped else scoped["Position"].map(data.primary_position)
        pool_df = scoped[pos.isin(codes) & (scoped["Minutes played"] >= args.min_minutes)]
        if len(pool_df) < 8:
            print(f"! {league}: only {len(pool_df)} players at {args.min_minutes}+ min, skipped")
            continue
        for idx, r in pool_df.iterrows():
            pool = data.Pool(df=pool_df, target=r, group=args.template, min_minutes=args.min_minutes,
                             leagues=[league], target_below_threshold=False)
            prof = data.metric_profile(pool, template, df)
            rs = data.role_score(pool, prof)
            rows.append({"league": league, "player": r["Player"], "team_in_season": r.get("Team within selected timeframe", r["Team"]), "team_now": r["Team"], "pos": r.get("Main Position"),
                         "age": r["Age"], "minutes": r["Minutes played"], "market_value": r.get("Market value"),
                         "contract": r.get("Contract expires"), "role_pct": round(rs["percentile"]), "role_z": round(rs["score"], 2),
                         "rank": f"{rs['rank']}/{rs['n']}"})

    out = pd.DataFrame(rows)
    if out.empty:
        return
    out = out[out["age"] <= args.max_age].sort_values(["league", "role_z"], ascending=[True, False])
    top = out.groupby("league").head(args.top)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(f"{template.get('role', args.template)}, {args.min_minutes}+ min, age <= {args.max_age}\n")
        print(top.to_string(index=False))
    if args.out:
        top.to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
