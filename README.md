# Scout Report Kit

Two-page football scouting reports that combine video scouting with Wyscout data, built for club
recruitment meetings.

You keep one YAML file per player with your video judgement, point the generator at a Wyscout export, and
it renders the report: page 1 for the decision, page 2 for the evidence behind it. Percentiles, role score,
charts and comparison players are computed from the export, so the data side updates with every new
export while your written scouting stays in the YAML.

Output per report: one PNG per page (3840 x 2160), a two-page PDF and a self-contained HTML file.

## Contents

- [Quick start](#quick-start)
- [What the report shows](#what-the-report-shows)
- [Writing a report for your player](#writing-a-report-for-your-player)
- [What the data fills in for you](#what-the-data-fills-in-for-you)
- [Scales](#scales)
- [Methodology](#methodology)
- [Configuration](#configuration)
- [Copy budget](#copy-budget)
- [Command reference](#command-reference)
- [Project structure](#project-structure)

## Quick start

Requires Python 3.10 or newer.

```
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium        # headless browser that renders PNG and PDF

python generate_report.py reports/example_cb.yaml data/demo_wyscout_export.xlsx
```

This renders the included demo: Jonas Brandt, a fictional 17-year-old left centre-back, compared with a
fictional league. The result is in `output/jonas-brandt-lcb/`. Add `--theme paper` for the light print
version.

## What the report shows

**Page 1, the decision.** Built to work on its own for a sporting director.

- Header: photo or initials, positions, club and loan club, age and date of birth, nationality, foot,
  height, contract, market value, agent, games and minutes.
- Decision box: recommendation (Sign, Monitor, Continue scouting, Discard), current and potential rating,
  current and potential level, projection, fit, adaptation, next step and a one-line key to the scales.
- Summary, strengths, areas to develop and risks.
- Data profile: a pizza chart of percentiles against the comparison pool, coloured by tier (top 20% green,
  bottom 20% red), and the role score with rank.

**Page 2, the evidence.**

- Four-corner grades (technical, tactical, physical, psychological) with three attributes each.
- Observation log with the matches watched, live or video, and an evidence confidence rating (Low, Medium,
  High) that states what is missing to reach High.
- Two scatter plots of the pool with the player and the most relevant comparison players named.
- In and out of possession traits with clip references.
- Data and video: each interpretation line is tagged "Video + data", "Video only" or "Data only", read
  against a team context line (style, league position, possession).

## Writing a report for your player

1. **Export from Wyscout.** A player-level export (`.xlsx` or `.csv`) with all positions and the metric
   columns listed in `config/metric_templates.yaml`. One export can hold several leagues and seasons.
2. **Find candidates (optional).** Rank players by role score within each league:
   ```
   python scripts/shortlist.py data/<export>.csv --template CB --max-age 21 \
       --leagues "Austria Bundesliga 2025-26" "Poland Ekstraklasa 2025-26"
   ```
   The list shows the club in that season and the current club, because Wyscout's `Team` column is the
   current club even for past seasons.
3. **Copy the template.** Copy `reports/TEMPLATE.yaml` to `reports/<player>.yaml` and set at least:
   ```yaml
   player:
     name: Full Name
     wyscout_name: F. Name          # exactly as in the export's "Player" column
     template: CB                   # CB | FB | CM | W | AM | ST | GK
     position_code: LCB
     club: Club name
   context:
     league: League name as it should read on the report
     leagues: [Austria Bundesliga 2025-26]   # exact value(s) of the "League" column = comparison pool
   ```
4. **Render once** to see the data before you write:
   ```
   python generate_report.py reports/<player>.yaml data/<export>.csv
   ```
5. **Watch and log matches** under `observations`. Four matches including one live view reach High
   confidence with the default thresholds.
6. **Write the rest:** rating, level, grades, projection, fit, traits and interpretation. Every field in
   the template is a writing prompt. Render again and check the console for warnings.

The console lists text that overflows its block, small comparison pools, missing images and the data
drafts described below.

## What the data fills in for you

A field counts as unwritten while it is empty or still holds the prompt text from `TEMPLATE.yaml`. Where
the data supports it, an unwritten field is pre-filled and tagged "Data draft":

| Field | Draft |
|---|---|
| Strengths | Metrics in the top 20% of the pool, highest first, up to 4 |
| Areas to develop | Metrics in the bottom 20%, lowest first, up to 3 |
| Risks | Facts only: contract ending within 12 months, below the minutes threshold, small pool, market value missing, role score drop in a second pool |
| Summary | One factual first bullet: age, foot, role, height, minutes, league, role score and rank |
| Data and video | Standout metrics, clear weaknesses and the role score, while `interpretation` is empty |

Anything that needs video is never drafted: projection, fit, adaptation, next step, team context, traits
and grades. Until written, those blocks read "To be completed after video review". Written text always
replaces a draft. Every run prints the drafts as a YAML snippet you can paste into the player file and
edit; the generator never changes your YAML. Set `auto_drafts: false` under `context` to turn drafts off.

**Comparing two pools.** `compare_leagues` (with `compare_min_minutes`, default 450) recomputes the role
score in a second pool, e.g. the current season after a transfer. If it drops by 30 or more percentile
points, or by 0.5 or more in z-score, a risk line is added.

**Data proxy grades.** Before any video you can grade attributes that have a metric behind them by
percentile band and set `grades_source: data` (optional label: `grades_pool`). The grades block is then
labelled "Data proxy, not vs our level". Bands: 1 under the 10th percentile, 2 10th to 20th, 3 20th to
40th, 4 40th to 60th, 5 60th to 80th, 6 80th to 90th, 7 90th and above. Remove `grades_source` once you
have watched the player.

## Scales

Everything the scout grades uses one 1 to 7 scale, measured against the club's own level. Everything
computed from data uses 0 to 100.

| What | Scale | Reads as |
|---|---|---|
| Rating (current, potential), attribute grades, match grades | 1 to 7 | 1 well below, 2 below, 3 close to, 4 at, 5 above, 6 well above our level, 7 elite |
| Level ladder | L1 to L6 | league tier the player plays at or can reach, from L1 Elite to L6 Development |
| Pizza percentiles and role score | 0 to 100 | position in the comparison pool, 50 = pool average |

"Our level" is the club's rung on the level ladder, set as `level.club` in the report. For a club
recruiting at L3, a 4 means good enough for an L3 side. Page 1 prints this relation as a one-line key.

## Methodology

**Comparison pool.** Players in the leagues listed in `context.leagues` whose main Wyscout position
belongs to the template's position group, with at least `min_minutes` played. The player in the report is
always included and flagged if below the threshold.

**Percentiles.** Mid-rank percentile of the player's value within the pool (ties count half). For
lower-is-better metrics (`invert: true`, e.g. goals conceded) the percentile is flipped, so 100 always
means best.

**Role score.** For each metric of the position template, a z-score within the pool (distance from the pool
mean in standard deviations). The role score is the weighted mean of these z-scores, using the weights of
the role profile, e.g. "ball-playing centre-back". It is shown as a pool percentile with the rank
(e.g. 97/100, rank 2 of 53); the underlying z-score is in the small print, where 0 is the pool average and
+1 one standard deviation better. Averaging z-scores rather than percentiles keeps the distance between
players, so a clear lead counts for more than a narrow one.

**Tiers.** Green marks the top 20% (80th percentile and above), red the bottom 20%. The same cut-offs
colour the pizza and the role score and select the drafted strengths and areas to develop.

**Evidence confidence.** Low, Medium or High, from the number of matches watched, live views, data minutes
and pool size. Thresholds are in `config/grading.yaml`.

**Why a pizza, not a radar.** For one player against a pool, percentiles share one 0 to 100 scale and the
slice order does not change the impression. A radar draws raw values on per-axis ranges, so its shape
depends on the chosen ranges and axis order.

**Limitations.**

- Percentiles and the role score describe output in one league and role. They do not adjust for league
  strength, team style or possession, apart from Wyscout's possession-adjusted (PAdj) metrics. The team
  context line exists to make this explicit.
- Several leagues in one pool are compared as if they were equal in level.
- Small pools move a lot: below 20 players the report warns that one player shifts a percentile by about
  100 / n points. Early in a season, add the previous season to `leagues` or lower `min_minutes`.
- Role score weights express a playing style chosen by the scout. They are not fitted to outcomes such as
  later success at a higher level. Only the CB template has explicit weights; the others weight every
  metric equally.
- Event data only: off-ball work and physical output are covered by the video grades, not the data.

## Configuration

Behaviour is driven by config files, not code:

| What | Where |
|---|---|
| Metrics, weights, role names and default scatter pairs per position | `config/metric_templates.yaml` |
| 1 to 7 scale labels, data proxy bands, level ladder, confidence thresholds, verdicts | `config/grading.yaml` |
| Brand name, tagline, website, logo, confidentiality line, fonts, colour themes, tier cut-offs | `config/theme.yaml` |
| Layout | `templates/report.html.j2`, `templates/report.css` |

**Position templates.** Each template groups its metrics into categories, e.g. for the centre-back:
passing progression, ball carrying, ground defending and aerial ability. A metric entry looks like this:

```yaml
- {label: Progressive passes /90, column: Progressive passes per 90, weight: 3}
```

`column` must match a header in the export; matching ignores case, accents and spacing, and a missing
header stops the run with the closest headers it found. `weight` defaults to 1; 0 shows the metric on the
pizza but leaves it out of the role score.

| Template | Role profile |
|---|---|
| CB | Ball-playing centre-back |
| FB | Attacking full-back |
| CM | Progressive central midfielder |
| W | Inside forward |
| AM | Creative attacking midfielder |
| ST | Complete centre-forward |
| GK | Sweeper goalkeeper |

**Scatters per player.** Each template has two default scatter pairs, so reports for the same position
are comparable. A report can replace either pair when the player's role differs from the template. `null`
keeps the default for that slot; `label` defaults to the column header and `title` to "Y vs X".

```yaml
scatters:
  - title: Wide delivery
    x: {column: Crosses per 90, label: Crosses /90}
    y: {column: xA per 90, label: xA /90}
  - null
```

**Different export headers.** If your export names identity columns differently (e.g. `Minutes played`),
map them under `columns:` in the report YAML. The defaults are in `DEFAULT_COLUMNS` in
`scout_report/data.py`.

**Personal settings.** `config/` holds neutral defaults (brand "Your Name"). Put your own values in
`config/local/` under the same file name. They are merged over the shared file key by key, so the local
file only needs what changes:

```yaml
# config/local/theme.yaml
brand:
  name: Your Full Name
  tagline: Football Scouting & Data
  website: your-site.dev
```

An empty `context.scout` falls back to the brand name. `python scripts/export_logo.py` exports the logo
built from these settings as SVG and PNG to `assets/brand/`.

## Copy budget

Pages have a fixed size, so each text block has a length budget. Text that runs over is reported in the
console.

| Block | Budget |
|---|---|
| Summary | 3 bullets, 15 to 25 words each |
| Projection | 2 to 3 sentences |
| Strengths / areas to develop / risks | 3 to 4 items each, up to 7 words |
| Fit, adaptation, next step | 1 sentence each |
| Grades | 3 attributes per corner, names up to 22 characters |
| In / out of possession | 3 traits each, 12 to 20 words, up to 2 clip references |
| Data and video | 3 items, 15 to 25 words each; team context 1 sentence |
| Observation log | up to 4 matches |

## Command reference

```
python generate_report.py REPORT.yaml EXPORT [--theme night|paper] [--out DIR] [--scale 2] [--formats png,pdf]
```

| Option | Default | Effect |
|---|---|---|
| `--theme` | `night` | `paper` is the light print version |
| `--out` | `output/<player>-<position>/` | Output folder |
| `--scale` | `2` | PNG pixel density (2 = 3840 x 2160) |
| `--formats` | `png,pdf` | HTML is always written |

Helper scripts:

| Script | Purpose |
|---|---|
| `scripts/shortlist.py` | Rank players by role score per league (`--template`, `--leagues`, `--max-age`, `--min-minutes`, `--top`, `--out`) |
| `scripts/make_demo_data.py` | Rebuild the fictional demo export |
| `scripts/export_logo.py` | Export the logo set from the brand settings |

## Project structure

```
generate_report.py   command-line entry point
scout_report/
  data.py            load the export, match headers, build the pool, percentiles, role score
  render.py          assemble the report, render HTML, export PNG and PDF
  drafts.py          data drafts for unwritten fields
  charts.py          pizza and scatter charts
  brand.py           logo built from the brand settings
  config.py          load config files with local overrides
config/              position templates, grading model, theme and brand
templates/           report.html.j2 and report.css
reports/             TEMPLATE.yaml and the fictional example_cb.yaml
data/                fictional demo export
scripts/             shortlist, demo data, logo export
assets/fonts/        Inter font files (SIL Open Font License)
output/              generated reports
```

**Data and privacy.** Wyscout data is licensed. Real exports in `data/`, your own reports in `reports/`,
`config/local/` and `output/` are git-ignored, so only the template, the fictional demo and the shared
configuration are tracked.
