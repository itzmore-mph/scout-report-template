# Scout Report Kit

A two-page detailed player report that combines video scouting with Wyscout data, built for club
recruitment meetings. One YAML file per player, one Wyscout export, one command.

```
python generate_report.py reports/example_cb.yaml data/demo_wyscout_export.xlsx
python generate_report.py reports/my_player.yaml exports/Wyscout_League_Export.csv --theme paper
```

Output in `output/<player>-<position>/`: one PNG per page (3840 x 2160 at `--scale 2`), a two-page PDF and a
self-contained HTML file.

## The two pages

**Page 1, decision.** Two columns, read left to right and top to bottom. Left: the recommendation with
current and potential rating, level and projection, fit, adaptation and next step, then the summary and the
strengths, areas to develop and risks. Right: the data that backs it, a pizza and the role score.

**Page 2, detail.** Four-corner grades and the observation log with evidence confidence, two legend-free
scatters, in and out of possession observations with clip references, and the data and video section read
against team context.

## What updates automatically

Everything computed from the export: pizza, percentiles, role score and rank, scatters and named players,
pool size and warnings, facts the YAML leaves empty, the level line and the confidence rating.

Written scouting text does not: summary, projection, strengths, observations and fit come from your video
work and stay in the YAML. The one exception is the data and video section: while `interpretation` is empty
it shows auto-generated data findings (standout metrics, clear weaknesses, role score), and every run prints
them in the console so you can paste them into the YAML and add the video view.

Page 1 works on its own for a sporting director. The two-page limit follows standard practice for detailed
reports: longer reports get skimmed.

## What makes it different

- **Graded against the club, not in the abstract.** Grades and the level ladder refer to the level you
  recruit for, set once in `config/grading.yaml`.
- **Projection, not only observation.** Clubs buy the player in two years. The report states what he can
  become, by when, and what has to happen.
- **Evidence is visible.** Confidence comes from matches watched, live views, data minutes and pool size, and
  the report states what is missing to reach High.
- **Data and video reconciled.** Each interpretation line is tagged, so agreement and disagreement between
  sources is explicit.
- **Strength-coloured pizza.** Slices are coloured by tier (top 30%, middle, bottom 30%), not by
  category, so strengths and weaknesses read at first sight. Label colour shows the category.
- **Role score.** A weighted mean of z-scores across the template metrics, using the weights of your
  positional profile, ranked within the pool. Percentiles show rank, z-scores show distance.

## Pizza or radar?

The pizza stays. For one player against a pool, percentiles on a pizza are the clearer read: every metric
shares the same 0 to 100 scale and the slice order does not change the impression. A radar (mplsoccer
`Radar`) draws raw values on per-axis ranges, so the polygon's shape and area depend on the chosen ranges
and axis order. Its real strength is overlaying two players, e.g. a target against the current starter,
which is a useful later addition for shortlist reports.

## Setup

```
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
python scripts/make_demo_data.py                     # optional: rebuilds the fictional demo export
```

The pizza uses mplsoccer's `PyPizza`. If mplsoccer is missing, a built-in matplotlib version with the same
geometry is drawn instead, so reports always render. Inter loads from Google Fonts at render time; install it
locally for offline use.

## Finding a player to report on

```
python scripts/shortlist.py exports/Wyscout_League_Export.csv --template CB --max-age 21 \
    --leagues "Austria Bundesliga 2025-26" "Poland Ekstraklasa 2025-26" "Spain Segunda 2025-26"
```

Ranks players by role score within each league, showing both the club in that season and the current club.
For past seasons Wyscout's `Team` column is the current club, so use `Team within selected timeframe` to
see where the minutes were played.

## Report erzeugen

```
python generate_report.py reports/<player>.yaml data/<wyscout_export>.csv [--theme paper]
```

- `reports/<player>.yaml`: eine Kopie von `reports/TEMPLATE.yaml` pro Spieler
- `data/<wyscout_export>.csv`: dein Wyscout-Export (.csv oder .xlsx); `leagues` in der YAML bestimmt die Vergleichsgruppe
- `--theme paper`: helle Druckversion; ohne den Parameter kommt die dunkle

Beispiel:

```
python generate_report.py reports/krzyzanowski.yaml data/Wyscout_League_Export_15102026.csv --theme paper
```

Ausgabe in `output/<spieler>-<position>/`: PDF, PNG pro Seite und HTML.

## Workflow per player

1. **Export from Wyscout.** All positions, the metric columns in `config/metric_templates.yaml`. Multi-league
   exports work: the pool is set by `context.leagues` (exact values of the `League` column).
2. **Copy `reports/TEMPLATE.yaml`** to `reports/<player>.yaml`. Set `wyscout_name` as spelled in the export
   (e.g. `V. Marinkovic`), the `template` (`CB`, `FB`, `CM`, `W`, `AM`, `ST`, `GK`) and `leagues`.
3. **Render once** to see the data before writing. The template text is a writing prompt for every field.
4. **Watch and log matches** under `observations`. Three to four matches are usually enough for a detailed
   report; the confidence rating shows where you stand.
5. **Write grades and notes**, render again, check the console for overflow and pool warnings.

## Copy budget

| Block | Budget |
|---|---|
| Summary | 3 bullets, 15 to 25 words each |
| Projection | 2 to 3 sentences |
| Strengths / areas to develop / risks | 3 to 4 items each, up to 7 words |
| Fit, adaptation, next action | 1 sentence each |
| Grades | 3 attributes per corner, names up to 22 characters |
| In / out of possession | 3 traits each, 12 to 20 words, up to 2 clip references |
| Data and video | 3 items, 15 to 25 words each; team context 1 sentence |
| Observation log | up to 4 matches |

## Methodology

- **Pool:** players in the selected leagues whose main Wyscout position is in the template's position group,
  with at least `min_minutes`. The target is always included and flagged if below the threshold.
- **Percentile:** mid-rank percentile within the pool; lower-is-better metrics (`invert: true`) are flipped.
- **Role score:** z-score per metric within the pool, sign flipped for inverted metrics, weighted mean using
  `weight` from the template. 0 is the pool average; +1 is one standard deviation better.
- **Early season:** pools are small in October (a 2. Bundesliga AM pool can be 2 players). Add the previous
  season to `leagues`, or lower `min_minutes`, and say so in the report. The report warns below n = 20.
- **Limits:** percentiles and z-scores describe output in one league and role. They do not adjust for team
  style, possession or league strength. That is what the team context line is for.

## Customising

| What | Where |
|---|---|
| Metrics, weights, role names and scatter pairs per position | `config/metric_templates.yaml` |
| Grade scale, level ladder, confidence rules, verdicts, rating scale | `config/grading.yaml` |
| Name, tagline, website, logo, confidentiality line, colours, tier cut-offs | `config/theme.yaml` |
| Logo set: lockups, avatar, favicon (SVG, PNG, light and dark) | `python scripts/export_logo.py` writes to `assets/brand/` |
| Layout | `templates/report.html.j2`, `templates/report.css` |

If a metric header does not exist in your export, the error lists the closest headers it found.

## Structure

```
config/            metric templates, grading model, theme and brand
reports/           TEMPLATE.yaml, a fictional example and a real-data example
data/              Wyscout exports (demo file is fictional, real exports are git-ignored)
scout_report/      data.py (pools, percentiles, role score), charts.py (pizza, scatters), render.py
templates/         HTML template and CSS
scripts/           demo data generator, logo export, shortlist
assets/brand/      exported logo files
output/            generated reports
```

## Logo

Bold stacked wordmark: given names over surname in Inter Display ExtraBold, a green rule, and the tagline
in tracked capitals bottom-aligned with the surname. Avatar and favicon use the initials with the same
rule (M | H). All text is outlined to vector paths, so files render identically without fonts installed.
Built in `scout_report/brand.py`; the report headers and every exported file use the same code, so a name,
tagline or colour change in `config/theme.yaml` updates everything. `logo-line` is a single-line version for
email signatures. Minimum size: primary logo 40 px high, line version 24 px, initials tile 24 px.
