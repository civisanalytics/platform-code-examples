"""
report_builder.py - Controller entry point.

Defines this project's specific content (subclasses of Card/Section from
report_utils.py), the queries this report runs, and the object tree they
assemble into - then renders it and publishes it via
report_utils.publish_report() (writes locally outside a Civis job, updates/
creates a Civis Platform report when run as one).

If this report grows past one file's worth of content (multiple tabs, each
with their own query + chart), split by tab into report/tabs/*.py instead of
letting this file grow indefinitely - see README.md's "Scaling to multiple
tabs" section. Helpers reused by more than one tab go in report_utils.py;
helpers only one tab needs stay in that tab's file.
"""

from __future__ import annotations

import calendar
from datetime import date
from pathlib import Path

import pandas as pd

from report_utils import Card, Report, Section, load_sql, publish_report

REPORT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = REPORT_DIR.parent
OUTPUT_FILENAME = "aws_event_report.html"

REPORT_NAME = "AWS Demo Event Dates"
REPORT_DESCRIPTION = (
    "A calendar of when events were hosted in the AWS sample (tickit) "
    "dataset, shaded by how many events started on each day."
)

# The Civis Platform database this report's data lives in - the AWS sample
# (tickit) schema aws_sample_data.
DB_NAME = "redshift-general"

# Sunday-first weekday labels, to match the calendar grid layout in
# resources/templates/calendar_section.html.
WEEKDAY_LABELS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]


class MetricCard(Card):
    """A single labeled number. self.data is the already-formatted display
    value (a string, e.g. "8,797") - any rounding/formatting happens where
    the value is computed, not here."""

    def get_context(self) -> dict:
        context = super().get_context()
        context.setdefault("label", "TODO label")
        context["value"] = self.data
        return context


class CalendarSection(Section):
    """A GitHub-style heatmap calendar for one year, paired with
    resources/templates/calendar_section.html. self.data is the list of
    month dicts from build_calendar_months() - each month's day/week grid,
    already computed - so this class and its template only format and loop
    over that structure; no counting or bucketing happens here or in Jinja.
    """

    template_name = "calendar_section.html"

    def get_context(self) -> dict:
        context = super().get_context()
        context.setdefault("weekday_labels", WEEKDAY_LABELS)
        return context


def get_daily_event_counts() -> pd.DataFrame:
    """Counts events per calendar day in aws_sample_data.event (the AWS/
    Redshift "tickit" sample dataset). Groups every row by DATE(starttime) -
    the event's own start timestamp - rather than joining to the
    aws_sample_data.date lookup table, since starttime already carries the
    full date and no other column on `date` (week/qtr/holiday) is used by
    this report. Returns one row per day that had at least one event, with
    columns event_date (a Python date) and n_events (count of events that
    started that day). Days with zero events are simply absent from the
    result; the calendar treats any date missing from this table as 0."""
    df = load_sql(
        """
        SELECT
            DATE(starttime) AS event_date,
            COUNT(*) AS n_events
        FROM aws_sample_data.event
        GROUP BY DATE(starttime)
        ORDER BY event_date
        """,
        database=DB_NAME,
    )
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    df["n_events"] = df["n_events"].astype(int)
    return df


def get_event_summary(daily_counts: pd.DataFrame) -> dict:
    """Summarizes the daily_counts DataFrame (from get_daily_event_counts)
    into the totals shown in the metric cards: total_events is the sum of
    n_events across all days; days_with_events is the count of distinct
    days that had at least one event; year is the calendar year covered,
    read from the first row's event_date (this dataset covers a single
    year, 2008)."""
    total_events = int(daily_counts["n_events"].sum())
    days_with_events = int(len(daily_counts))
    year = daily_counts["event_date"].iloc[0].year if not daily_counts.empty else None
    return {
        "total_events": total_events,
        "days_with_events": days_with_events,
        "year": year,
    }


def _intensity_level(count: int) -> int:
    """Buckets a day's event count into a 0-4 shading level for the
    calendar heatmap: 0 = no events that day, 1 = 1-15, 2 = 16-30,
    3 = 31-60, 4 = 60+. Thresholds are set for this dataset's distribution
    (most days in aws_sample_data.event run 11-40 events; a handful of
    outlier days run into the hundreds), purely to pick a shade - it does
    not affect any number shown elsewhere in the report."""
    if count <= 0:
        return 0
    if count <= 15:
        return 1
    if count <= 30:
        return 2
    if count <= 60:
        return 3
    return 4


def build_calendar_months(counts_by_date: dict, year: int) -> list[dict]:
    """Builds the calendar heatmap's row/column structure for
    calendar_section.html to loop over - no day-count math happens in the
    template itself. Returns one dict per month with a "label" (e.g. "Jan")
    and "weeks": a list of weeks, each a list of exactly 7 day-cells
    (Sunday-first, matching WEEKDAY_LABELS). Each day-cell is either None
    (a blank leading/trailing cell outside the month) or a dict with "day",
    "count" (from counts_by_date, defaulting to 0 for days absent from it),
    and "level" (0-4, from _intensity_level). This is formatting of
    already-computed counts_by_date (from get_daily_event_counts /
    get_event_summary); it runs no query itself."""
    months = []
    for month in range(1, 13):
        first_weekday, n_days = calendar.monthrange(year, month)
        # calendar.monthrange's weekday is 0=Monday..6=Sunday; convert to a
        # Sunday-first offset to match WEEKDAY_LABELS.
        lead_blank = (first_weekday + 1) % 7

        cells: list[dict | None] = [None] * lead_blank
        for day in range(1, n_days + 1):
            count = counts_by_date.get(date(year, month, day), 0)
            cells.append({"day": day, "count": count, "level": _intensity_level(count)})
        while len(cells) % 7 != 0:
            cells.append(None)

        weeks = [cells[i : i + 7] for i in range(0, len(cells), 7)]
        months.append({"label": calendar.month_abbr[month], "weeks": weeks})
    return months


def build_report() -> Report:
    """Assemble the report's object tree: three summary metric cards
    (total events, days with an event, year covered) followed by the
    heatmap calendar, all built from get_daily_event_counts()."""
    daily_counts_df = get_daily_event_counts()
    summary = get_event_summary(daily_counts_df)
    counts_by_date = dict(
        zip(daily_counts_df["event_date"], daily_counts_df["n_events"])
    )
    days_in_year = 366 if calendar.isleap(summary["year"]) else 365

    total_card = MetricCard(
        data=f"{summary['total_events']:,}", label="Total events"
    )
    days_card = MetricCard(
        data=f"{summary['days_with_events']} of {days_in_year}",
        label="Days with an event",
    )
    year_card = MetricCard(data=str(summary["year"]), label="Year covered")

    calendar_section = CalendarSection(
        data=build_calendar_months(counts_by_date, summary["year"]),
        title=f"Event Calendar — {summary['year']}",
    )

    return Report(
        children=[total_card, days_card, year_card, calendar_section],
        report_title=REPORT_NAME,
        report_subtitle=(
            "Daily event counts from the AWS sample (tickit) dataset, "
            "aws_sample_data.event."
        ),
    )


def main() -> None:
    report = build_report()
    html = report.render()
    publish_report(
        html,
        report_name=REPORT_NAME,
        report_desc=REPORT_DESCRIPTION,
        local_filename=str(PROJECT_ROOT / OUTPUT_FILENAME),
    )


if __name__ == "__main__":
    main()
