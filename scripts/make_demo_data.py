"""Create a synthetic league export in Wyscout's column format for testing the template.

All players, clubs and numbers are fictional. Replace this file with a real
Wyscout export (Advanced search > export to Excel) for actual scouting work.
"""

from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
OUT = Path(__file__).resolve().parent.parent / "data" / "demo_wyscout_export.xlsx"

TEAMS = ["SV Musterstadt", "FC Beispiel", "Union Nordtal", "SC Waldau", "VfB Seeburg", "Athletic Holmen",
         "FK Rivenko", "Dinamo Verst", "Sloga Brod", "Radnik Vale", "Mladost Kern", "Jedinstvo Lis",
         "Borac Polje", "Zeleznik Ost", "Proleter Hill", "Sparta Linde"]
FIRST = ["Luka", "Marko", "Nikola", "Stefan", "Jonas", "Filip", "Milan", "David", "Petar", "Ivan", "Lazar",
         "Mateo", "Elias", "Aleksa", "Vuk", "Ognjen", "Nemanja", "Tim", "Noah", "Andrej", "Uroš", "Dušan"]
LAST = ["Kovač", "Petrov", "Lindqvist", "Horvat", "Brenner", "Vasić", "Kral", "Novak", "Stanić", "Weber",
        "Jurić", "Marić", "Hofer", "Babić", "Tadić", "Lukić", "Simić", "Ristić", "Keller", "Božić", "Arnold",
        "Pavlović", "Mitrović", "Ilić", "Kramer", "Zorić", "Radić", "Vidaković", "Đorđević", "Fischer"]

# Per-squad composition by Wyscout primary position.
SQUAD = ["GK", "GK", "LCB", "RCB", "CB", "LCB", "RCB", "LB", "RB", "LWB", "RB", "DMF", "LCMF", "RCMF",
         "RDMF", "LCMF", "AMF", "LW", "RW", "LWF", "RW", "CF", "CF", "CF"]
GROUP = {"GK": "GK", "CB": "CB", "LCB": "CB", "RCB": "CB", "LB": "FB", "RB": "FB", "LWB": "FB", "RWB": "FB",
         "DMF": "CM", "RDMF": "CM", "LCMF": "CM", "RCMF": "CM", "AMF": "AM", "LW": "W", "RW": "W",
         "LWF": "W", "RWF": "W", "CF": "ST"}

# Column -> mean by group (default under key "_"); per-90 sd = 28% of mean, % sd = 7 points.
MEANS = {
    "Progressive passes per 90": {"_": 6, "CB": 8.6, "FB": 7.5, "CM": 9, "GK": 1.5},
    "Accurate progressive passes, %": {"_": 66, "CB": 68, "CM": 70},
    "Passes to final third per 90": {"_": 5, "CB": 7, "CM": 8, "GK": 2},
    "Accurate passes to final third, %": {"_": 64, "CB": 70},
    "Progressive runs per 90": {"_": 2, "CB": 1.0, "W": 3.2, "AM": 2.6, "GK": 0.05},
    "Dribbles per 90": {"_": 2.5, "CB": 0.7, "W": 5.5, "AM": 4, "GK": 0.05},
    "Defensive duels per 90": {"_": 6, "CB": 7, "FB": 7, "CM": 7, "ST": 3, "GK": 0.3},
    "Defensive duels won, %": {"_": 60, "CB": 66},
    "PAdj Interceptions": {"_": 4, "CB": 5.7, "CM": 5.5, "W": 2.5, "ST": 1.5, "GK": 0.5},
    "Aerial duels per 90": {"_": 3, "CB": 5, "ST": 6, "GK": 1},
    "Aerial duels won, %": {"_": 45, "CB": 57, "ST": 40, "GK": 85},
    "Successful defensive actions per 90": {"_": 6, "CB": 7.8, "CM": 8, "ST": 3.5, "GK": 1},
    "Crosses per 90": {"_": 1.5, "FB": 3.2, "W": 3.5, "CB": 0.1},
    "Accurate crosses, %": {"_": 30},
    "xA per 90": {"_": 0.08, "W": 0.2, "AM": 0.22, "FB": 0.1, "CB": 0.02, "GK": 0.0},
    "Deep completions per 90": {"_": 0.8, "FB": 1.4, "W": 1.6, "AM": 1.8, "CB": 0.1},
    "Passes per 90": {"_": 35, "CB": 48, "CM": 52, "GK": 26, "ST": 18},
    "Accurate passes, %": {"_": 78, "CB": 85, "CM": 84, "ST": 70},
    "Received passes per 90": {"_": 28, "CM": 38, "ST": 16},
    "Key passes per 90": {"_": 0.4, "AM": 1.3, "W": 1.0, "CB": 0.05},
    "Non-penalty goals per 90": {"_": 0.08, "ST": 0.38, "W": 0.24, "AM": 0.2, "CB": 0.03},
    "xG per 90": {"_": 0.08, "ST": 0.42, "W": 0.26, "AM": 0.22, "CB": 0.04},
    "Shots per 90": {"_": 0.8, "ST": 2.8, "W": 2.2, "AM": 2.0},
    "Passes to penalty area per 90": {"_": 1.5, "W": 3, "AM": 3.5, "CB": 0.2},
    "Successful dribbles, %": {"_": 50},
    "Touches in box per 90": {"_": 1.2, "ST": 5.5, "W": 4, "AM": 3.5, "CB": 0.5},
    "Smart passes per 90": {"_": 0.4, "AM": 1.2},
    "Shots on target, %": {"_": 35},
    "Goal conversion, %": {"_": 12},
    "Offensive duels won, %": {"_": 40},
    "Save rate, %": {"_": 68},
    "Prevented goals per 90": {"_": 0.0},
    "Conceded goals per 90": {"_": 1.3},
    "Long passes per 90": {"_": 4, "GK": 9, "CB": 6},
    "Accurate long passes, %": {"_": 52},
    "Exits per 90": {"_": 0.9},
}


def sample(col: str, group: str) -> float:
    mean = MEANS[col].get(group, MEANS[col]["_"])
    if col.endswith("%"):
        return float(np.clip(rng.normal(mean, 7), 5, 99))
    if col == "Prevented goals per 90":
        return float(rng.normal(0, 0.18))
    return float(max(0, rng.normal(mean, max(mean * 0.28, 0.02))))


rows, used = [], set()
for team in TEAMS:
    for pos in SQUAD:
        while (name := f"{rng.choice(FIRST)[0]}. {rng.choice(LAST)}") in used:
            pass
        used.add(name)
        group = GROUP[pos]
        minutes = int(rng.integers(90, 1260))
        rows.append({
            "Player": name, "Team": team, "Position": pos, "Main Position": pos, "League": "Demo Liga 2026-27",
            "Age": int(rng.integers(17, 34)), "Market value": int(rng.choice([50, 100, 150, 250, 400, 600]) * 1000),
            "Contract expires": f"{rng.integers(2027, 2031)}-06-30",
            "Matches played": max(1, minutes // 85), "Minutes played": minutes,
            "Foot": rng.choice(["right", "right", "left"]), "Height": int(rng.normal(183, 6)),
            **{col: round(sample(col, group), 2) for col in MEANS},
        })

df = pd.DataFrame(rows)

# The fictional example target: a left-footed, ball-playing 17-year-old LCB.
target = {
    "Player": "J. Brandt", "Team": "FC Beispiel", "Position": "LCB, CB", "Main Position": "LCB", "League": "Demo Liga 2026-27", "Age": 17, "Market value": 150000,
    "Contract expires": "2029-06-30", "Matches played": 9, "Minutes played": 816, "Foot": "left", "Height": 189,
}
profile = {col: round(sample(col, "CB"), 2) for col in MEANS}
profile.update({
    "Progressive passes per 90": 12.6, "Accurate progressive passes, %": 74.1,
    "Passes to final third per 90": 7.4, "Accurate passes to final third, %": 64.0,
    "Progressive runs per 90": 1.2, "Dribbles per 90": 0.8,
    "Defensive duels per 90": 8.9, "Defensive duels won, %": 68.5, "PAdj Interceptions": 7.1,
    "Aerial duels per 90": 5.8, "Aerial duels won, %": 58.2, "Successful defensive actions per 90": 10.9,
})
df.loc[len(df)] = {**target, **profile}

OUT.parent.mkdir(parents=True, exist_ok=True)
df.to_excel(OUT, index=False)
cb = df[df["Position"].str.split(",").str[0].isin(["CB", "LCB", "RCB"]) & (df["Minutes played"] >= 600)]
print(f"Wrote {OUT} ({len(df)} players, {len(cb)} centre-backs with 600+ minutes)")
