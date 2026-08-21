# AWS Demo Event Dates

An MVC-style HTML report.

| Layer      | Lives in                                    | Responsibility |
|------------|----------------------------------------------|----------------|
| Model      | your modeled data source (outside this repo)  | data modeling, owned wherever that source lives (dbt, a warehouse view, an API, etc.) |
| Controller | `report/report_utils.py`, `report/report_builder.py` | load data (via `load_sql()`), compute values, assemble the object tree |
| View       | `resources/templates/*.html`                  | all HTML/Jinja markup; no markup belongs in `.py` files |

## Structure

```
aws_event_html_report/
├── README.md
├── CLAUDE.md
├── requirements.txt
├── resources/
│   ├── templates/
│   │   ├── report.html    # page shell: <head>, header, footer
│   │   ├── section.html   # generic section wrapper
│   │   ├── card.html      # generic card
│   │   └── macros.html    # reusable Jinja fragments (tables, etc.)
│   └── static/
│       └── styles.css     # Civis brand colors, house dashboard style
└── report/
    ├── report_utils.py    # this project's toolbox: HtmlRender/Card/Section/Report, load_sql(), publish_report()
    └── report_builder.py  # wires content into pages: build_report() + render + publish
```

See `CLAUDE.md` for the editing rules an agent (or you) should follow when
extending this report - this README is the orientation read; CLAUDE.md is
the standing conventions.

## How it works

Everything renderable - the whole report, a section, a card - is an
`HtmlRender` (defined once, in `report_utils.py`). Each instance holds its
own data, renders any children first (turning them into plain HTML strings),
then renders its own Jinja template with that data plus the children's HTML.
Templates only ever see strings and simple values; they never call back into
Python.

A report with one card and one text section is just:

```python
metric = MetricCard(data="--", label="Some metric")
text_section = TextSection(data="Some body text.", title="Overview")
report = Report(children=[metric, text_section], report_title="My Report")
html = report.render()
```

There's no forced tab/multi-section structure - a one-card report is just
`Report(children=[card])`. If a project needs tabbed navigation later, add a
`Tab(HtmlRender)` subclass with its own template the same way `MetricCard`
and `TextSection` are added in `report_builder.py`, and pass `Tab` instances
as `Report`'s children.

## Adding a new kind of content

Subclass `Card` or `Section` (both in `report_utils.py`), and override
`get_context()` to compute whatever values the template needs from
`self.data`. Call `super().get_context()` first so you don't lose any
constructor kwargs (label, title, etc.) already being passed through:

```python
class MetricCard(Card):
    def get_context(self) -> dict:
        context = super().get_context()
        context["value"] = self.data["amount"].sum()
        return context
```

If the default render flow doesn't fit - e.g. you need to filter or reshape
`self.data` before children render, or post-process the rendered output -
override `render()` instead and call `super().render()`.

For a small report, these subclasses live directly in `report_builder.py`
alongside `build_report()`. See "Scaling to multiple tabs" below for where
they move once a report outgrows one file.

## report_utils.py vs. report_builder.py

`report_utils.py` is for code reused by more than one part of the report:
the rendering framework (`HtmlRender`/`Card`/`Section`/`Report`),
`load_sql()`, `publish_report()`, and helpers like a chart-building function
called from more than one tab.

`report_builder.py` (and, once a report grows, each tab's own file - see
below) wires those parts together into pages: building `Report`'s children,
then rendering and publishing. If a helper is only ever called from one
tab, keep it in that tab's file rather than adding it to `report_utils.py`.

## Scaling to multiple tabs

The default scaffold is one file's worth of content, which is all most
reports need. Once a report has enough going on - say, three tabs, each
with its own query, computed table, and bar chart - split by tab instead of
cramming everything into `report_builder.py`:

```
report/
├── report_utils.py     # shared chart/table helpers used by more than one tab
├── report_builder.py   # imports each tab's build function, wires them into Report, renders + publishes
└── tabs/
    ├── overview.py      # loads its own data, computes, builds that tab's Cards/Sections
    ├── trends.py
    └── detail.py
```

Add a `Tab(HtmlRender)` subclass (with its own `resources/templates/tab.html`)
the same way `MetricCard`/`TextSection` were added, and give each tab file a
`build_overview_tab() -> Tab`-style function. `report_builder.py` then
becomes mostly:

```python
from tabs.overview import build_overview_tab
from tabs.trends import build_trends_tab

def build_report() -> Report:
    return Report(
        children=[build_overview_tab(), build_trends_tab()],
        report_title=REPORT_NAME,
    )
```

A bar-chart helper all three tabs call still goes in `report_utils.py` -
that's the "reused by more than one part of this report" case. A helper only
`trends.py` needs stays in `trends.py`.

## Running it

```
pip install -r requirements.txt   # first time only
cd aws_event_html_report/report
python report_builder.py
```

Locally, this writes `aws_event_report.html` to the project root. Run as
a Civis container script (where `CIVIS_JOB_ID` is set), it instead publishes
to Civis Platform: creating a new report on the first run, then updating that
same report on later runs (via the `REPORT_ID` argument `publish_report()`
sets on the container script - the same pattern the tourism report uses).

## Where the data comes from

This scaffold assumes the Model layer has already built whatever this report
reads from (a dbt table, a warehouse view, or anything else - however this
project's data got modeled isn't this report's concern). What every report
here has in common is *where* that modeled data lives: Civis Platform. So
`report_utils.py` ships `load_sql(sql, database)`, a thin wrapper around
`civis.io.read_civis_sql`, and `report_builder.py` has a `DB_NAME`
constant plus query functions (like `get_example_data()`) that call it.

Query/compute logic - anything that runs SQL, joins, or aggregates - belongs
in one of those query functions in `report_builder.py`, called once from
`build_report()`. `get_context()` on a Card/Section subclass should stay
limited to cheap formatting of already-computed data (picking a number,
formatting it, choosing a label) - not running a new query itself.
