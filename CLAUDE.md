# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A generator for two-page football scouting reports (1920 x 1080 pages). Input: one report YAML per player plus one Wyscout export (.xlsx or .csv). Output in `output/<player-slug>-<position>/`: self-contained HTML, one PNG per page and a two-page PDF. `README.md` is the user-facing spec (workflow, copy budget, methodology) and should stay consistent with code changes.

## Commands

```
# setup (Windows venv already exists at .venv/)
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# render a report (the demo pair is the smoke test)
python generate_report.py reports/example_cb.yaml data/demo_wyscout_export.xlsx
python generate_report.py reports/example_cb.yaml data/demo_wyscout_export.xlsx --theme paper
#   flags: --out DIR, --scale 2 (PNG density), --formats png,pdf (HTML is always written)

# helpers
python scripts/shortlist.py <export> --template CB --leagues "<League col value>" [--max-age 21 --min-minutes 900 --top 5 --out file.csv]
python scripts/make_demo_data.py   # rebuilds the fictional data/demo_wyscout_export.xlsx
python scripts/export_logo.py      # wipes and regenerates assets/brand/ from config/theme.yaml
```

There is no test suite, linter or build step. Verify changes by rendering the demo report in both themes and checking the console: it prints auto data findings, `! text overflows in '<block>'` warnings and missing-image notices.

## Architecture

Pipeline: `generate_report.py` (CLI) → `scout_report.render.render()` → `build_context()` → Jinja2 `templates/report.html.j2` + `templates/report.css` → Playwright Chromium screenshots `.page` elements to PNG and prints the PDF.

- `scout_report/data.py`: pure data logic. `load_export` tidies headers; `resolve_column` matches headers case/accent/whitespace-insensitively and raises with the closest suggestions. `build_pool` filters by `context.leagues` (exact `League` column values), position group (`Main Position` column if present, else the first code in `Position`) and `min_minutes`; the target player is always kept and flagged if below threshold. `metric_profile` gives mid-rank percentiles (flipped for `invert: true`); `role_score` is a weighted mean of within-pool z-scores (weight 0 = shown on pizza, excluded from score); the report shows its pool percentile (0 to 100, `drafts.role_value`), with the z-score as small print.
- `scout_report/render.py`: assembles the template context. Report YAML values override export values via `pick()` (Wyscout writes 0 for unknown height/weight/market value, treated as missing). Also builds grades, level ladder verdict, evidence confidence and small-pool notes (n < 20), and validates `recommendation` against `grading.yaml` verdicts and level keys against the ladder.
- `scout_report/charts.py`: matplotlib figures exported as inline SVG with `svg.fonttype: none`, so chart text is live text rendered by the browser with the report fonts. Pizza uses mplsoccer `PyPizza` with a built-in matplotlib fallback of the same geometry, so mplsoccer is optional at runtime.
- `scout_report/config.py`: `load_config(name)` deep-merges `config/local/<name>` (git-ignored, personal brand etc.) over the shared `config/<name>`. Use it instead of reading config YAML directly.
- `scout_report/brand.py`: logo lockups with text outlined to vector paths from `assets/fonts/*.otf`. Used both by report headers and `scripts/export_logo.py`, so brand changes in `config/theme.yaml` propagate to both.
- `scripts/shortlist.py` reuses `scout_report.data` (adds the repo root to `sys.path`), computing role scores per league pool.

Config drives behaviour, not code:
- `config/metric_templates.yaml`: `position_groups` (Wyscout codes per template key CB/FB/CM/W/AM/ST/GK) and per-template categories, metrics (`column`, `label`, `weight`, `invert`), role name and the two default scatter pairs.
- `config/grading.yaml`: one 1 to 7 `scale` (4 = at our level) used by rating, attribute grades and match grades; `scale_tones` (pip colours per grades source), `data_bands` (percentile band per point for data proxy grades), four corners, level ladder (L1 to L6), confidence thresholds, verdicts. Values outside the scale raise.
- `config/theme.yaml`: brand (neutral "Your Name" default), fonts, tier cut-offs (80/20, also used for role score colour and data drafts), and the `night` / `paper` colour themes (every theme must define the same keys, e.g. `tier_colors`, `tier_ink`, `categories`, `verdict`).

Report YAML schema is defined by `reports/TEMPLATE.yaml` (`player`, `context`, `rating`, `level`, `grades`, `observations`, `highlight_players`, `scouting`, optional `scatters` (per-slot override of the template's two scatter pairs, `null` keeps a slot; see `scatter_specs` in `render.py`), optional `columns` to override Wyscout header names from `DEFAULT_COLUMNS` in `data.py`). Relative `photo` / `club_badge` paths resolve against the report file's folder. Images are embedded as data URIs.

## Conventions and gotchas

- Layout is fixed-size. Text blocks carry `data-fit="<name>"`; the renderer flags any that overflow. When adding a text block to the template, give it a `data-fit` attribute. Copy length limits are in the README "Copy budget" table.
- `scouting.interpretation`: if empty, the report shows auto-generated data findings (`data_findings` in `render.py`); written entries replace them. Entries take `evidence: both | video | data`.
- Fonts: `render()` prepends `@font-face` rules for the local OTFs in `assets/fonts/`; the template also links Google Fonts Inter.
- `templates/` contains stale copies of `README.md`, `generate_report.py`, `requirements.txt` and `.gitignore`. The root versions are canonical; only `report.html.j2` and `report.css` in `templates/` are used.
- Personal files stay local: `config/local/` and all of `reports/` except `TEMPLATE.yaml` and `example_cb.yaml` are git-ignored.
- `data/` is git-ignored except the fictional demo export: real Wyscout exports are licensed data and must not be committed. `output/` is git-ignored.
- Wyscout's `Team` column is the current club, not the club in the selected season; `Team within selected timeframe` holds the latter.
