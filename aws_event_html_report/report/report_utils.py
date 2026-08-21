"""
report/report_utils.py - this report's toolbox: code reused by more than
one part of this report. That's the rendering framework below, plus
helpers like load_sql() and publish_report(), and, as this report grows,
things like a chart-building function called from more than one tab. If a
helper is only ever called from one tab/Card/Section, keep it there instead
of adding it here.

HtmlRender is the base class for any renderable piece of the report (Report,
Section, Card, or anything else added later). Each instance holds its own
data and any child HtmlRender instances. render() renders children first
(bottom-up), turning them into plain HTML strings in Python, then renders
this instance's own Jinja template with its data, computed context, and the
already-rendered children. Templates never call back into Python - they
receive strings and simple values only.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import civis
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "resources" / "templates"
_ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def load_sql(sql: str, database: str) -> pd.DataFrame:
    """Run `sql` against a Civis Platform database and return the result as
    a DataFrame.

    Every report's Model layer is expected to live in Civis Platform, so
    this is the one shared way any report pulls data - a thin wrapper around
    civis.io.read_civis_sql. `database` is project-specific (see DB_NAME in
    report_builder.py); this function stays generic."""
    return civis.io.read_civis_sql(sql, database=database, return_as="pandas")


def ensure_report_id_param(client: civis.APIClient, job_id: int) -> None:
    """Make sure this Container Script has a REPORT_ID parameter defined,
    adding it if it's missing. Civis Platform requires a parameter to be
    declared via `params` before an `arguments` value for that key is
    recognized - passing arguments={"REPORT_ID": ...} to patch_containers
    without REPORT_ID ever appearing in `params` does not create a usable
    script parameter (see Civis's Script Parameters docs: `params` defines
    the parameter, `arguments` sets its value for a parameter that already
    exists). Without this, the REPORT_ID argument set below never turns
    into an environment variable on the next run, so publish_report() would
    take the "create new report" branch every run instead of updating the
    same report. This only ensures the parameter definition exists; it does
    not set a value - the patch_containers(arguments=...) call right after
    it still does that."""
    script = client.scripts.get_containers(job_id)
    existing_params = [dict(p) for p in (script.params or [])]
    if any(p.get("name") == "REPORT_ID" for p in existing_params):
        return
    client.scripts.patch_containers(
        id=job_id,
        params=existing_params + [
            {"name": "REPORT_ID", "type": "integer", "required": False}
        ],
    )


def publish_report(
    html: str,
    report_name: str,
    report_desc: str,
    local_filename: str,
) -> None:
    """Publish `html` as a Civis Platform report if running inside a Civis
    container script (CIVIS_JOB_ID is set), updating the existing report if
    REPORT_ID is also set, else creating a new one. Outside a Civis job (e.g.
    local development), just write `html` to `local_filename` instead.

    This is the shared publish step every report uses unmodified - per-report
    values (name, description, output filename) come from report_builder.py."""
    job_id = os.environ.get("CIVIS_JOB_ID")
    if job_id:
        client = civis.APIClient()
        job_id = int(job_id)
        run_id = int(os.environ["CIVIS_RUN_ID"])
        existing_id = os.environ.get("REPORT_ID")

        if existing_id:
            print(f"Updating existing Civis report {existing_id}...")
            report = client.reports.patch(
                id=int(existing_id), name=report_name, code_body=html
            )
        else:
            print("Creating new Civis report...")
            report = client.reports.post(
                name=report_name, description=report_desc, code_body=html
            )
            ensure_report_id_param(client, job_id)
            client.scripts.patch_containers(
                id=job_id, arguments={"REPORT_ID": int(report.id)}
            )

        client.scripts.post_containers_runs_outputs(job_id, run_id, "Report", report.id)
        print(f"Done. Report id: {report.id}")
    else:
        with open(local_filename, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Done. Written to {local_filename}")


class HtmlRender:
    """Base class for anything that renders itself to an HTML string."""

    template_name: str = ""

    def __init__(
        self,
        data: Any = None,
        children: list["HtmlRender"] | None = None,
        template_name: str | None = None,
        **context: Any,
    ) -> None:
        self.data = data
        self.children = children or []
        self.template_name = template_name or self.template_name
        self.context = context

    def get_context(self) -> dict:
        """Return the template variables for this instance, on top of
        data/children. Default: just pass through whatever kwargs were
        given at construction time. Override and call
        super().get_context() first, then add/override keys computed from
        self.data - this is the hook to reach for first, and it covers most
        cases."""
        return dict(self.context)

    def render(self) -> str:
        """Render children (bottom-up), then render this instance's own
        template with data + children + get_context()'s output.

        Override this instead of get_context() if the default flow doesn't
        fit - e.g. filtering/reordering self.data before children render, or
        post-processing the output. Call super().render() to fall back to
        the default behavior for the rest."""
        rendered_children = [child.render() for child in self.children]
        template = _ENV.get_template(self.template_name)
        return template.render(
            data=self.data,
            children=rendered_children,
            **self.get_context(),
        )


class Card(HtmlRender):
    """Smallest building block - a single stat, chart, or short block of
    content. Paired with resources/templates/card.html by default."""

    template_name = "card.html"


class Section(HtmlRender):
    """A block of text and/or a group of cards (or nested sections), under
    an optional heading. Paired with resources/templates/section.html by
    default."""

    template_name = "section.html"


class Report(HtmlRender):
    """The whole page. Takes report_title/report_subtitle plus a list of
    children (Sections, Cards, or a mix) rendered in order. Paired with
    resources/templates/report.html by default.

    There's no separate Tab class here - most reports don't need one. A
    single-card report is just Report(children=[card]). If a project
    genuinely needs tabbed navigation later, add a Tab(HtmlRender) subclass
    with its own template the same way MetricCard/TextSection are added in
    report_builder.py, and pass Tab instances as Report's children."""

    template_name = "report.html"
