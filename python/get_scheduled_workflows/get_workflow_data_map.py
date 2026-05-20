#!/usr/bin/env python3
"""
Generate an HTML data-map report for a Civis Platform workflow.

For each step (Python, SQL, sub-workflow, etc.) the report lists which
database tables are read (inputs) and which are written/created (outputs),
then renders a Mermaid.js lineage flowchart.

This script doesn't really handle complicated workflow patterns like dynamic table names
or dbt models, but it should work reasonably well for straightforward ETL pipelines.
"""

import os
import re
import sys

try:
    import civis
except ImportError:
    print("ERROR: civis package not installed. Run: pip install civis")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
WORKFLOW_ID = int(os.environ.get("WORKFLOW_ID"))
# ─────────────────────────────────────────────────────────────────────────────

# SQL keywords that appear after FROM/JOIN but are not table names
_SQL_NON_TABLE_KEYWORDS = {
    "select", "where", "join", "on", "as", "with", "set",
    "values", "dual", "unnest", "lateral", "jsonb_each",
    "generate_series", "information_schema",
}


def safe_filename(name: str) -> str:
    return re.sub(r"[^\w\-]", "_", name).strip("_")


def fetch_script_content(client, job_id: int):
    """
    Try each known Civis script type in turn.
    Returns (content: str, extension: str, job_name: str).
    """
    attempts = [
        (client.scripts.get_python3,    "source",         "py"),
        (client.scripts.get_sql,        "sql",            "sql"),
        (client.scripts.get_r,          "source",         "r"),
        (client.scripts.get_javascript, "source",         "js"),
        (client.scripts.get_containers, "docker_command", "sh"),
    ]
    for fetch_fn, content_field, ext in attempts:
        try:
            job     = fetch_fn(job_id)
            content = getattr(job, content_field, None) or ""
            name    = getattr(job, "name", f"job_{job_id}")
            return content, ext, name
        except Exception:
            continue

    try:
        job      = client.jobs.get(job_id)
        name     = getattr(job, "name", f"job_{job_id}")
        job_type = getattr(job, "type", "unknown")
        return f"# job_type={job_type}", "txt", name
    except Exception as e:
        return f"# error: {e}", "txt", f"job_{job_id}"


# ── Table extraction ──────────────────────────────────────────────────────────

def _looks_like_table(name: str) -> bool:
    """Heuristic: reject bare keywords and subquery artifacts."""
    lower = name.lower().rstrip(")")
    if lower in _SQL_NON_TABLE_KEYWORDS:
        return False
    if "(" in name or ")" in name:
        return False
    return True


def extract_tables_from_sql(text: str):
    """Return (inputs, outputs) sets of table names from a SQL string."""
    inputs: set[str] = set()
    outputs: set[str] = set()

    # Strip line comments so they don't confuse regexes
    cleaned = re.sub(r"--[^\n]*", "", text)

    # Inputs: FROM clause — handles comma-separated table lists
    # e.g. FROM t1 alias, t2 alias WHERE ...
    for m in re.finditer(r"\bFROM\b", cleaned, re.IGNORECASE):
        rest = cleaned[m.end():]
        # Grab everything up to the next major clause keyword
        clause = re.split(
            r"\b(?:WHERE|JOIN|ON|SET|GROUP|ORDER|HAVING|LIMIT|UNION|EXCEPT|INTERSECT|INTO|VALUES)\b",
            rest, maxsplit=1, flags=re.IGNORECASE
        )[0]
        for entry in clause.split(","):
            parts = entry.strip().split()
            name = parts[0].rstrip(")") if parts else ""
            if name and _looks_like_table(name):
                inputs.add(name.lower())

    # Inputs: JOIN (always a single table name)
    for m in re.finditer(r"\bJOIN\s+([\w.]+)", cleaned, re.IGNORECASE):
        name = m.group(1)
        if _looks_like_table(name):
            inputs.add(name.lower())

    # Outputs: INSERT INTO
    for m in re.finditer(r"\bINSERT\s+(?:INTO\s+)?([\w.]+)", cleaned, re.IGNORECASE):
        outputs.add(m.group(1).lower())

    # Outputs: CREATE TABLE [OR REPLACE] [TEMP] [IF NOT EXISTS] <name>
    for m in re.finditer(
        r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:TEMP(?:ORARY)?\s+)?TABLE\s+"
        r"(?:IF\s+NOT\s+EXISTS\s+)?([\w.]+)",
        cleaned, re.IGNORECASE
    ):
        outputs.add(m.group(1).lower())

    # Outputs: UPDATE <table>
    for m in re.finditer(r"\bUPDATE\s+([\w.]+)", cleaned, re.IGNORECASE):
        name = m.group(1)
        if _looks_like_table(name):
            outputs.add(name.lower())

    # A table that is both read from and written to is an in-place update —
    # keep it in outputs only to avoid self-loops in the diagram.
    inputs -= outputs
    return inputs, outputs


def extract_tables_from_python(text: str):
    """Return (inputs, outputs) sets from a Python script."""
    inputs: set[str] = set()
    outputs: set[str] = set()

    # civis.io.read_civis(table="schema.table", ...)
    for m in re.finditer(
        r"civis\.io\.read_civis\s*\([^)]*?table\s*=\s*[\"']([^\"']+)",
        text, re.IGNORECASE | re.DOTALL
    ):
        inputs.add(m.group(1).lower())

    # civis.io.dataframe_to_civis(df, table="schema.table", ...)
    for m in re.finditer(
        r"civis\.io\.dataframe_to_civis\s*\([^)]*?table\s*=\s*[\"']([^\"']+)",
        text, re.IGNORECASE | re.DOTALL
    ):
        outputs.add(m.group(1).lower())

    # civis.io.write_civis(df, table="schema.table", ...)
    for m in re.finditer(
        r"civis\.io\.write_civis\s*\([^)]*?table\s*=\s*[\"']([^\"']+)",
        text, re.IGNORECASE | re.DOTALL
    ):
        outputs.add(m.group(1).lower())

    # Embedded SQL in triple-quoted or double-quoted strings
    for m in re.finditer(r'"""(.*?)"""|\'\'\'(.*?)\'\'\'', text, re.DOTALL):
        sql_chunk = m.group(1) or m.group(2)
        i, o = extract_tables_from_sql(sql_chunk)
        inputs |= i
        outputs |= o

    inputs -= outputs
    return inputs, outputs


def extract_tables(content: str, ext: str):
    """Dispatch to the right extractor based on file extension."""
    if ext == "sql":
        return extract_tables_from_sql(content)
    if ext == "py":
        return extract_tables_from_python(content)
    return set(), set()


# ── Step collection ───────────────────────────────────────────────────────────

def collect_steps(client, workflow_id: int, execution_id: int, depth: int = 0):
    """
    Recursively collect step data for a workflow execution.
    Returns a list of step dicts.
    """
    try:
        execution = client.workflows.get_executions(workflow_id, execution_id)
    except Exception as e:
        print(f"{'  ' * depth}⚠  Could not fetch execution {execution_id}: {e}")
        return []

    tasks = execution.tasks or []
    steps = []

    for step_num, task in enumerate(tasks, start=1):
        task_name = task.name
        indent    = "  " * depth

        # Find job_id from runs
        job_id = None
        for run in reversed(getattr(task, "runs", []) or []):
            jid = getattr(run, "job_id", None)
            if jid:
                job_id = jid
                break

        # Check for sub-workflow child executions
        child_pairs = []
        if job_id is None:
            execs = getattr(task, "executions", []) or []
            child_pairs = [
                (getattr(e, "workflow_id", None), getattr(e, "id", None))
                for e in execs
                if getattr(e, "id", None)
            ]

        # Sub-workflow
        if child_pairs:
            print(f"{indent}[{step_num:>2}] 📁 {task_name}/")
            substeps = []
            for child_wf_id, child_ex_id in child_pairs:
                substeps.extend(collect_steps(client, child_wf_id, child_ex_id, depth + 1))
            steps.append({
                "step_num": step_num,
                "name":     task_name,
                "type":     "workflow",
                "job_id":   None,
                "inputs":   [],
                "outputs":  [],
                "substeps": substeps,
                "depth":    depth,
            })
            continue

        # Skipped (no runs, no child executions)
        if job_id is None:
            print(f"{indent}[{step_num:>2}] –  {task_name}  (skipped)")
            steps.append({
                "step_num": step_num,
                "name":     task_name,
                "type":     "skipped",
                "job_id":   None,
                "inputs":   [],
                "outputs":  [],
                "substeps": [],
                "depth":    depth,
            })
            continue

        # Direct script
        try:
            content, ext, _ = fetch_script_content(client, job_id)
        except Exception as e:
            content, ext = f"# error: {e}", "txt"

        inputs, outputs = extract_tables(content, ext)
        print(f"{indent}[{step_num:>2}] ✓  {task_name} ({ext}) "
              f"→ {len(inputs)} in, {len(outputs)} out")
        steps.append({
            "step_num": step_num,
            "name":     task_name,
            "type":     ext,
            "job_id":   job_id,
            "inputs":   sorted(inputs),
            "outputs":  sorted(outputs),
            "substeps": [],
            "depth":    depth,
        })

    return steps


# ── HTML generation ───────────────────────────────────────────────────────────

_TYPE_BADGE = {
    "sql":      ("#d4edda", "#155724", "SQL"),
    "py":       ("#cce5ff", "#004085", "PY"),
    "r":        ("#fff3cd", "#856404", "R"),
    "js":       ("#ffeeba", "#856404", "JS"),
    "sh":       ("#e2e3e5", "#383d41", "SH"),
    "workflow": ("#e8d5f5", "#5a1a8a", "WF"),
    "skipped":  ("#f8f9fa", "#6c757d", "–"),
    "txt":      ("#f8f9fa", "#6c757d", "?"),
}


def _badge(ext: str) -> str:
    bg, fg, label = _TYPE_BADGE.get(ext, ("#f8f9fa", "#6c757d", ext.upper()))
    return (f'<span style="background:{bg};color:{fg};padding:1px 6px;'
            f'border-radius:3px;font-size:0.8em;font-weight:bold">{label}</span>')


def _table_rows(steps, depth=0) -> str:
    rows = []
    pad = depth * 24
    for s in steps:
        name_html = (
            f'<span style="padding-left:{pad}px">'
            f'{"📁 " if s["type"] == "workflow" else ""}'
            f'{s["name"]}'
            f'</span>'
        )
        inputs_html  = "<br>".join(f"<code>{t}</code>" for t in s["inputs"])  or "—"
        outputs_html = "<br>".join(f"<code>{t}</code>" for t in s["outputs"]) or "—"
        rows.append(
            f'<tr>'
            f'<td style="text-align:center">{s["step_num"]}</td>'
            f'<td>{name_html}</td>'
            f'<td style="text-align:center">{_badge(s["type"])}</td>'
            f'<td>{inputs_html}</td>'
            f'<td>{outputs_html}</td>'
            f'</tr>'
        )
        if s["substeps"]:
            rows.append(_table_rows(s["substeps"], depth + 1))
    return "\n".join(rows)


def _mermaid_id(label: str) -> str:
    return re.sub(r"[^\w]", "_", label)


def _mermaid_nodes(steps, prefix="") -> list[str]:
    """Recursively build Mermaid flowchart lines."""
    lines = []
    for s in steps:
        step_id = f"STEP_{prefix}{s['step_num']}"
        safe_name = s["name"].replace('"', "'")

        if s["type"] == "workflow":
            lines.append(f'  subgraph {step_id}["{s["step_num"]}. {safe_name}"]')
            lines.extend(_mermaid_nodes(s["substeps"], prefix=f"{prefix}{s['step_num']}_"))
            lines.append("  end")
        else:
            shape = f'["{s["step_num"]}. {safe_name}"]'
            lines.append(f"  {step_id}{shape}")

        for tbl in s["inputs"]:
            tbl_id = "TBL_" + _mermaid_id(tbl)
            lines.append(f'  {tbl_id}[("{tbl}")]')
            lines.append(f"  {tbl_id} --> {step_id}")

        for tbl in s["outputs"]:
            tbl_id = "TBL_" + _mermaid_id(tbl)
            lines.append(f'  {tbl_id}[("{tbl}")]')
            lines.append(f"  {step_id} --> {tbl_id}")

    return lines


def generate_html(steps: list, workflow_name: str) -> str:
    table_rows = _table_rows(steps)
    mermaid_body = "\n".join(_mermaid_nodes(steps))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Data Map: {workflow_name}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      max-width: 1200px; margin: 40px auto; padding: 0 24px;
      color: #212529; background: #fff;
    }}
    h1 {{ font-size: 1.6rem; border-bottom: 2px solid #dee2e6; padding-bottom: 8px; }}
    h2 {{ font-size: 1.2rem; margin-top: 36px; color: #495057; }}
    table {{
      width: 100%; border-collapse: collapse; font-size: 0.9rem;
      margin-top: 12px;
    }}
    th {{
      background: #343a40; color: #fff;
      padding: 8px 12px; text-align: left;
    }}
    td {{ padding: 7px 12px; border-bottom: 1px solid #dee2e6; vertical-align: top; }}
    tr:hover td {{ background: #f8f9fa; }}
    code {{
      background: #e9ecef; padding: 1px 4px; border-radius: 3px;
      font-size: 0.85em; white-space: nowrap;
    }}
    .mermaid {{ margin-top: 16px; overflow-x: auto; }}
  </style>
</head>
<body>
  <h1>Data Map: {workflow_name}</h1>
  <p style="color:#6c757d">Workflow ID: {WORKFLOW_ID}</p>

  <h2>Step Summary</h2>
  <table>
    <thead>
      <tr>
        <th style="width:40px">#</th>
        <th>Step</th>
        <th style="width:60px">Type</th>
        <th>Input Tables</th>
        <th>Output Tables</th>
      </tr>
    </thead>
    <tbody>
{table_rows}
    </tbody>
  </table>

  <h2>Data Lineage</h2>
  <div class="mermaid">
flowchart LR
{mermaid_body}
  </div>

  <script>
    mermaid.initialize({{ startOnLoad: true, theme: "default" }});
  </script>
</body>
</html>
"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not os.environ.get("CIVIS_API_KEY"):
        print("ERROR: CIVIS_API_KEY environment variable is not set.")
        sys.exit(1)

    client = civis.APIClient()

    print(f"Fetching workflow {WORKFLOW_ID}...")
    try:
        workflow = client.workflows.get(WORKFLOW_ID)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"  Name:              {workflow.name}")
    print(f"  Last execution ID: {workflow.last_execution_id}\n")

    if not workflow.last_execution_id:
        print("ERROR: No executions found for this workflow.")
        sys.exit(1)

    steps = collect_steps(client, WORKFLOW_ID, workflow.last_execution_id)
    html  = generate_html(steps, workflow.name)

    report_name        = f"Data Map: {workflow.name}"
    report_description = f"Input/output table lineage for workflow {WORKFLOW_ID}"

    # Running on Civis Platform — post/update the report there
    if os.environ.get("CIVIS_JOB_ID"):
        existing_report_id = os.environ.get("REPORT_ID")

        if existing_report_id:
            print(f"Updating existing report {existing_report_id}...")
            report = client.reports.patch(
                id=int(existing_report_id),
                name=report_name,
                code_body=html,
            )
        else:
            print("Creating new report...")
            report = client.reports.post(
                name=report_name,
                description=report_description,
                code_body=html,
            )
            client.scripts.patch_python3(
                id=int(os.environ["CIVIS_JOB_ID"]),
                arguments={
                    "WORKFLOW_ID": WORKFLOW_ID,
                    "REPORT_ID":   int(report.id),
                },
            )

        report_url = (
            f"https://platform.civisanalytics.com/spa/#/reports/{report.id}"
            f"?fullscreen=true"
        )
        print(f"\nDone. Report available at:\n  {report_url}")

    # Running locally — write to a file
    else:
        output_file = f"workflow_{WORKFLOW_ID}_data_map.html"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\nDone. Report written to ./{output_file}")


if __name__ == "__main__":
    main()
