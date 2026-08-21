# CLAUDE.md

Instructions for any agent (Claude Code, a skill, whoever) editing this
report project. See `README.md` for what this report is and how it's laid
out - this file is conventions to follow while editing, not an introduction.

## Architecture

- Model: this report's data lives in Civis Platform. Whatever built it
  (dbt, another pipeline) is out of scope here.
- Controller: `report/report_utils.py` + `report/report_builder.py` (and,
  once a report has multiple tabs, per-tab files under `report/tabs/`).
- View: `resources/templates/*.html` (Jinja). All markup lives here.

- `report_utils.py`: code reused by more than one part of this report - the
  rendering framework (`HtmlRender`/`Card`/`Section`/`Report`), `load_sql()`,
  `publish_report()`, and any other helper more than one Card/Section/tab
  in this report calls (e.g. a chart-building function used by three
  different tabs).
- `report_builder.py`: builds `Report`'s children and wires them together,
  then renders + publishes. For a small report, this also holds the
  Card/Section subclasses directly. Once a report grows past one file's
  worth of content, split by tab into `report/tabs/*.py` (each tab loads
  its own data, computes, and builds its own Cards/Sections) and let
  `report_builder.py` shrink down to importing each tab's build function
  and wiring them into `Report`.

## Rules

- Never build HTML strings in a `.py` file. If you're writing an f-string
  of markup, it belongs in a template instead.
- Never call a Python method from inside a template. Templates only ever
  receive `data`, `children` (already-rendered HTML strings from child
  components), and whatever `get_context()` returned - plain strings and
  values, nothing callable.
- Query/join/aggregate logic - anything that computes a value - runs once
  in a plain function, called from `build_report()` or from a tab's own
  build function (see `get_example_data()` for the pattern). Never put that
  kind of logic inside a `get_context()` override.
- `get_context()` on a Card/Section subclass stays cheap: pick a number,
  format it, choose a label. It formats already-computed data; it doesn't
  compute it.
- A new kind of content (a new Card or Section variant) is a new subclass,
  defined in `report_builder.py` or in that tab's own file under
  `report/tabs/` - not in `report_utils.py`.
- Add to `report_utils.py` when a helper is reused by more than one part of
  this report (a second tab needs the same chart function, say). If only
  one tab ever calls it, keep it in that tab's file instead - don't let
  single-use logic pile up in `report_utils.py` just because it's the
  "utils" file.
- Reusable Jinja fragments (a table, a badge, anything more than one
  template needs) go in `resources/templates/macros.html`, imported where
  needed. Don't duplicate markup across templates.
- If a component's default render flow doesn't fit - e.g. you need to
  mutate `self.data` before its children render - override `render()` and
  call `super().render()` rather than reimplementing the base flow.
- Every query/compute function needs a docstring stating, in plain
  language, exactly what it calculates - the filters, grouping, date
  range, and formula. Write it for someone who won't read the SQL: they
  should be able to sanity-check the number from the docstring alone. This
  is what makes it possible for someone other than the author to review
  the actual logic behind a figure before it ships.
- When a table has more than one plausible column for the same concept
  (e.g. `created_at` vs. `updated_at`, `start_date` vs. `end_date`), say
  explicitly which one is being used and why, rather than picking whichever
  name sounds right. The wrong one often still runs without error.
- Never hardcode a narrative conclusion (e.g. "attendance increased in
  July") as a literal string. The report gets rebuilt later with different
  data, and a hardcoded takeaway will eventually just be wrong while still
  looking finished. Compute the actual comparison at render time - which
  period is "current," whether a metric went up, down, or held steady
  versus the prior period - and build the sentence from that result.

## Data and publishing

- `DB_NAME`, `REPORT_NAME`, and `REPORT_DESCRIPTION` at the top of
  `report_builder.py` are placeholders. If they're still `TODO` and you're
  about to do real work, ask the user what they should be - don't guess,
  and don't assume this report's data lives in the same database as the
  last one just because that's familiar. If it's unclear where the data
  lives, look (list schemas/tables, sample rows) before writing a query
  against a guess.
- `publish_report()` (in `report_utils.py`) already handles both cases:
  writes an HTML file locally, or creates/updates a Civis Platform report
  when run as a Civis container script (`CIVIS_JOB_ID` set). Don't change
  that branching without a good reason - every report here uses it as-is.

## Running it

```
pip install -r requirements.txt
cd report
python report_builder.py
```

This is "AWS Demo Event Dates" (aws_event_html_report/).
