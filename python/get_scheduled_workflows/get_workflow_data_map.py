#!/usr/bin/env python3
"""
Generate an HTML data-map report for a Civis Platform workflow.

For each step (Python, SQL, sub-workflow, etc.) the report lists which
database tables are read (inputs) and which are written/created (outputs),
then renders a Mermaid.js lineage flowchart.

SQL steps are parsed with regex (FROM/JOIN → inputs, INSERT/CREATE/UPDATE → outputs).
Python, R, JS, and shell steps use Claude via AWS Bedrock to reason about arbitrary code,
which handles dynamic table names and non-civis.io patterns that regex misses.
If Bedrock is unavailable the script falls back to the original regex extractor.
"""

import json
import os
import re
import sys

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False
import boto3
from botocore.config import Config
import civis


# ── Config ────────────────────────────────────────────────────────────────────
WORKFLOW_ID         = int(os.environ.get("WORKFLOW_ID"))
BEDROCK_MODEL_ID    = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
BEDROCK_REGION_NAME = "us-east-1"
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
        (client.scripts.get_dbt,        "name",           "dbt"),
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


def fetch_import_tables(client, job_id: int):
    """
    Try to read source/destination tables from a Civis import job.
    Returns (inputs, outputs) sets, or (None, None) if the job is not an import.
    """
    try:
        imp = client.imports.get(job_id)
    except Exception:
        return None, None

    inputs: set[str] = set()
    outputs: set[str] = set()

    for sync in getattr(imp, "syncs", []) or []:
        for side, bucket in ((getattr(sync, "source", None), inputs),
                             (getattr(sync, "destination", None), outputs)):
            if side is None:
                continue
            db_tbl = getattr(side, "database_table", None)
            if db_tbl:
                schema = getattr(db_tbl, "schema", None)
                table  = getattr(db_tbl, "table", None)
                if schema and table:
                    bucket.add(f"{schema}.{table}".lower())
                elif table:
                    bucket.add(table.lower())
            else:
                path = getattr(side, "path", None)
                if path:
                    bucket.add(path.lower())

    return inputs, outputs


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
        # Grab everything up to the next clause keyword or statement boundary
        clause = re.split(
            r"(?:\b(?:WHERE|JOIN|ON|SET|GROUP|ORDER|HAVING|LIMIT|UNION|EXCEPT|INTERSECT|INTO|VALUES)\b|;)",
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

    # Temp tables are transient — collect them so they can be excluded everywhere
    temp_tables: set[str] = set()
    for m in re.finditer(
        r"\bCREATE\s+(?:OR\s+REPLACE\s+)?TEMP(?:ORARY)?\s+TABLE\s+"
        r"(?:IF\s+NOT\s+EXISTS\s+)?([\w.]+)",
        cleaned, re.IGNORECASE
    ):
        temp_tables.add(m.group(1).lower())

    # Outputs: CREATE TABLE (non-temp only)
    for m in re.finditer(
        r"\bCREATE\s+(?:OR\s+REPLACE\s+)?TABLE\s+"
        r"(?:IF\s+NOT\s+EXISTS\s+)?([\w.]+)",
        cleaned, re.IGNORECASE
    ):
        outputs.add(m.group(1).lower())

    # Outputs: UPDATE <table>
    for m in re.finditer(r"\bUPDATE\s+([\w.]+)", cleaned, re.IGNORECASE):
        name = m.group(1)
        if _looks_like_table(name):
            outputs.add(name.lower())

    # Temp tables are internal — not real inputs or outputs
    inputs -= temp_tables
    # A table that is both read from and written to is an in-place update —
    # keep it in outputs only to avoid self-loops in the diagram.
    inputs -= outputs
    # Only keep schema-qualified names (schema.table); bare words are column
    # names, CTE aliases, or other artefacts, not real table references.
    inputs  = {t for t in inputs  if "." in t}
    outputs = {t for t in outputs if "." in t}
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


# Maps Mistral inline action names to (content_field, file_extension)
_INLINE_ACTIONS = {
    "civis.scripts.sql":        ("sql",    "sql"),
    "civis.scripts.python3":    ("source", "py"),
    "civis.scripts.r":          ("source", "r"),
    "civis.scripts.javascript": ("source", "js"),
}


def _parse_workflow_yaml(definition: str, execution_input) -> dict:
    """
    Parse a Mistral workflow YAML definition and return per-task info keyed by task name.
    Each value is a dict with:
      'action'  : str       — Mistral action name
      'job_id'  : int|None  — for civis.run_job tasks
      'content' : str|None  — YAQL-resolved inline code for civis.scripts.* tasks
      'ext'     : str|None  — 'sql', 'py', 'r', 'js' for inline tasks
    """
    if not _YAML_AVAILABLE or not definition:
        return {}
    try:
        doc = yaml.safe_load(definition)
    except Exception:
        return {}

    # Flatten execution-level inputs for YAQL resolution
    exec_inputs = {}
    if execution_input:
        items = (execution_input.items() if hasattr(execution_input, "items")
                 else vars(execution_input).items())
        exec_inputs = {str(k): str(v) for k, v in items if v is not None}

    def resolve(val):
        """Substitute <% $.varname %> YAQL expressions with their execution values."""
        if not isinstance(val, str):
            return str(val) if val is not None else ""
        return re.sub(
            r'<%\s*\$\.(\w+)\s*%>',
            lambda m: exec_inputs.get(m.group(1), m.group(0)),
            val,
        )

    workflow_body = next(
        (v for k, v in doc.items()
         if k != "version" and isinstance(v, dict) and "tasks" in v),
        None,
    )
    if not workflow_body:
        return {}

    result = {}
    for task_name, task_def in (workflow_body.get("tasks") or {}).items():
        if not isinstance(task_def, dict):
            continue
        action     = task_def.get("action", "")
        task_input = task_def.get("input") or {}
        info       = {"action": action, "job_id": None, "content": None, "ext": None}

        if action == "civis.run_job":
            raw_id = task_input.get("job_id") or task_input.get("id")
            info["job_id"] = int(raw_id) if raw_id else None
        elif action in _INLINE_ACTIONS:
            field, ext      = _INLINE_ACTIONS[action]
            info["content"] = resolve(task_input.get(field) or "")
            info["ext"]     = ext

        result[task_name] = info
    return result


def _create_bedrock_client():
    aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    cred_kwargs = {}
    if aws_access_key and aws_secret_key:
        cred_kwargs = {
            "aws_access_key_id": aws_access_key,
            "aws_secret_access_key": aws_secret_key,
        }
    return boto3.client(
        "bedrock-runtime",
        config=Config(read_timeout=120),
        region_name=BEDROCK_REGION_NAME,
        **cred_kwargs,
    )


def extract_tables_with_ai(text: str, file_type: str):
    """Return (inputs, outputs) sets by asking Claude via Bedrock to analyse the script."""

    prompt = (
        f"You are a data lineage analyst.\n"
        f"Analyse the following {file_type} script and identify every database table or file "
        f"that is READ (inputs) and every table or file that is WRITTEN or CREATED (outputs).\n\n"
        f"Guidelines:\n"
        f"- Return table names in schema.table format where visible.\n"
        f"- For Civis Platform scripts: civis.io.read_civis / read_civis_sql = input; "
        f"civis.io.dataframe_to_civis / write_civis = output.\n"
        f"- For pandas: read_sql / read_csv pointing to a table = input; to_sql = output.\n"
        f"- For dynamic table names (f-strings, variables), make a best-guess using "
        f"the surrounding context, or omit if unknowable.\n"
        f"- Exclude temporary in-memory dataframes; only include persistent storage "
        f"(databases, files written to disk/S3).\n\n"
        f"Script ({file_type}):\n{text}"
    )
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
        "tools": [{
            "name": "return_data_lineage",
            "description": "Return all input and output tables identified in the script.",
            "input_schema": {
                "type": "object",
                "required": ["inputs", "outputs"],
                "properties": {
                    "inputs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tables/files read by this script",
                    },
                    "outputs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tables/files written by this script",
                    },
                },
            },
        }],
        "tool_choice": {"type": "tool", "name": "return_data_lineage"},
    })
    bedrock = _create_bedrock_client()
    response = bedrock.invoke_model(modelId=BEDROCK_MODEL_ID, body=body)
    result = json.loads(response["body"].read())
    data = result["content"][0]["input"]
    inputs  = {t.lower() for t in data.get("inputs",  [])}
    outputs = {t.lower() for t in data.get("outputs", [])}
    inputs -= outputs  # in-place updates: keep in outputs only
    return inputs, outputs


def extract_tables(content: str, ext: str):
    """Dispatch to the right extractor based on file extension."""
    if ext == "sql":
        return extract_tables_from_sql(content)
    try:
        return extract_tables_with_ai(content, ext)
    except Exception as e:
        print(f"  ⚠  AI extraction failed ({ext}): {e}; falling back to regex")
        if ext == "py":
            return extract_tables_from_python(content)
        return set(), set()


# ── Step collection ───────────────────────────────────────────────────────────

def _task_start_time(task) -> str:
    """Return the earliest started_at across a task's runs/executions, or '' if none."""
    times = []
    for run in getattr(task, "runs", []) or []:
        t = getattr(run, "started_at", None)
        if t:
            times.append(t)
    for exc in getattr(task, "executions", []) or []:
        t = getattr(exc, "started_at", None)
        if t:
            times.append(t)
    return min(times) if times else ""


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

    # Parse YAML once — drives content source and type for each task
    yaml_task_map = _parse_workflow_yaml(
        getattr(execution, "definition", "") or "",
        getattr(execution, "input", None),
    )

    # Sort by actual start time; tasks with no timestamp (skipped) sort last.
    raw_tasks = execution.tasks or []
    ordered = sorted(
        enumerate(raw_tasks),
        key=lambda pair: (_task_start_time(pair[1]) or "\xff", pair[0]),
    )
    steps = []

    for step_num, (_, task) in enumerate(ordered, start=1):
        task_name = task.name
        yaml_info = yaml_task_map.get(task_name, {})
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

        # Determine content source: prefer YAML inline content (YAQL already resolved),
        # fall back to fetching the saved script from the API.
        if yaml_info.get("content") is not None:
            content, ext = yaml_info["content"], yaml_info["ext"]
        else:
            try:
                content, ext, _ = fetch_script_content(client, job_id)
            except Exception as e:
                content, ext = f"# error: {e}", "txt"

        if ext == "txt":
            import_inputs, import_outputs = fetch_import_tables(client, job_id)
            if import_inputs is not None:
                inputs, outputs, ext = import_inputs, import_outputs, "import"
            else:
                inputs, outputs = set(), set()
        else:
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
    "sql":      ("#0097A7", "#ffffff", "SQL"),
    "py":       ("#058DC7", "#ffffff", "PY"),
    "r":        ("#F1A137", "#0A2138", "R"),
    "js":       ("#F1A137", "#0A2138", "JS"),
    "sh":       ("#9CA3AF", "#0A2138", "SH"),
    "dbt":      ("#215470", "#ffffff", "DBT"),
    "import":   ("#0A2138", "#B0BEC5", "IMP"),
    "workflow": ("#0A2138", "#B0BEC5", "WF"),
    "skipped":  ("#E5E7EB", "#9CA3AF", "–"),
    "txt":      ("#E5E7EB", "#9CA3AF", "?"),
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


def _safe_mermaid_label(text: str) -> str:
    """Sanitize a string for use inside a Mermaid double-quoted label."""
    return (text
            .replace('"', "'")
            .replace("[", "(")
            .replace("]", ")")
            .replace("{", "(")
            .replace("}", ")")
            .replace("#", "")
            .replace(";", ","))


def _mermaid_nodes(steps, prefix="") -> list[str]:
    """Recursively build Mermaid flowchart lines."""
    lines = []
    step_ids = []
    for s in steps:
        step_id = f"STEP_{prefix}{s['step_num']}"
        step_ids.append(step_id)
        safe_name = _safe_mermaid_label(s["name"])

        if s["type"] == "workflow":
            lines.append(f'  subgraph {step_id}["{s["step_num"]}. {safe_name}"]')
            lines.extend(_mermaid_nodes(s["substeps"], prefix=f"{prefix}{s['step_num']}_"))
            lines.append("  end")
        else:
            shape = f'["{s["step_num"]}. {safe_name}"]'
            lines.append(f"  {step_id}{shape}")

        for tbl in s["inputs"]:
            tbl_id = "TBL_" + _mermaid_id(tbl)
            lines.append(f'  {tbl_id}[("{_safe_mermaid_label(tbl)}")]')
            lines.append(f"  {tbl_id} --> {step_id}")

        for tbl in s["outputs"]:
            tbl_id = "TBL_" + _mermaid_id(tbl)
            lines.append(f'  {tbl_id}[("{_safe_mermaid_label(tbl)}")]')
            lines.append(f"  {step_id} --> {tbl_id}")

    # Invisible links enforce left-to-right step ordering in the layout
    for a, b in zip(step_ids, step_ids[1:]):
        lines.append(f"  {a} ~~~ {b}")

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
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #fff;
      color: #4B5563;
    }}
    .report-header {{
      background: #0097A7;
      padding: 32px 40px 28px;
    }}
    .report-header h1 {{
      font-size: 1.6rem;
      font-weight: 700;
      color: #fff;
      margin-bottom: 6px;
    }}
    .report-header p {{
      color: #B0BEC5;
      font-size: 0.88rem;
    }}
    .content {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 32px 40px 48px;
    }}
    h2 {{
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #215470;
      margin-top: 40px;
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 2px solid #E5E7EB;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.875rem;
    }}
    th {{
      background: #215470;
      color: #fff;
      padding: 10px 14px;
      text-align: left;
      font-weight: 600;
      font-size: 0.8rem;
    }}
    td {{
      padding: 8px 14px;
      border-bottom: 1px solid #E5E7EB;
      vertical-align: top;
    }}
    tr:hover td {{ background: #f0f4f8; }}
    code {{
      background: #E5E7EB;
      color: #215470;
      padding: 1px 5px;
      border-radius: 3px;
      font-size: 0.82em;
      white-space: nowrap;
    }}
    .mermaid {{ margin-top: 8px; overflow-x: auto; }}
  </style>
</head>
<body>
  <div class="report-header">
    <h1>Data Map: {workflow_name}</h1>
    <p>Workflow ID: {WORKFLOW_ID}</p>
  </div>

  <div class="content">
    <h2>Step Summary</h2>
    <table>
      <thead>
        <tr>
          <th style="width:40px">#</th>
          <th>Step</th>
          <th style="width:64px">Type</th>
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
  </div>

  <script>
    mermaid.initialize({{ startOnLoad: true, theme: "neutral" }});
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
