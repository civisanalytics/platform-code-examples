#!/usr/bin/env python3
"""
Download all scripts from a Civis Platform workflow, including sub-workflows.

When a task is a sub-workflow, a subdirectory is created and that workflow's
scripts are downloaded recursively into it.

Usage:
    pip install civis
    export CIVIS_API_KEY="your_api_key"
    python download_workflow_scripts.py

Output:
    workflow_4742_scripts/
        step_01_<name>/          ← sub-workflow → becomes a folder
            step_01_<name>.sql
            step_02_<name>.py
            ...
        step_02_<name>.sql       ← direct script → single file
        step_03_<name>.py
        ...
"""

import os
import re
import sys

try:
    import civis
except ImportError:
    print("ERROR: civis package not installed. Run: pip install civis")
    sys.exit(1)

# ── Config ───────────────────────────────────────────────────────────────────
WORKFLOW_ID = 4742
OUTPUT_DIR  = f"workflow_{WORKFLOW_ID}_scripts"
# ─────────────────────────────────────────────────────────────────────────────


def safe_filename(name: str) -> str:
    return re.sub(r"[^\w\-]", "_", name).strip("_")


def fetch_script_content(client, job_id: int):
    """
    Try each known Civis script type in turn.
    Returns (content: str, extension: str, job_name: str).
    """
    attempts = [
        (client.scripts.get_python3,    "source",        "py"),
        (client.scripts.get_sql,        "sql",           "sql"),
        (client.scripts.get_r,          "source",        "r"),
        (client.scripts.get_javascript, "source",        "js"),
        (client.scripts.get_containers, "docker_command","sh"),
    ]
    for fetch_fn, content_field, ext in attempts:
        try:
            job     = fetch_fn(job_id)
            content = getattr(job, content_field, None) or ""
            name    = getattr(job, "name", f"job_{job_id}")
            return content, ext, name
        except Exception:
            continue  # wrong type — try next

    # Generic fallback
    try:
        job      = client.jobs.get(job_id)
        name     = getattr(job, "name", f"job_{job_id}")
        job_type = getattr(job, "type", "unknown")
        content  = (
            f"# Could not retrieve source automatically.\n"
            f"# Job type: {job_type}  |  Job name: {name}\n"
            f"# Visit: https://platform.civisanalytics.com/spa/#/scripts/{job_id}\n"
        )
        return content, "txt", name
    except Exception as e:
        return (
            f"# Could not retrieve source for job_id {job_id}\n# Error: {e}\n",
            "txt",
            f"job_{job_id}",
        )


def process_execution(client, workflow_id: int, execution_id: int, output_dir: str, depth: int = 0):
    """
    Recursively download all scripts for a workflow execution.

    Direct script tasks  → saved as individual files in output_dir.
    Sub-workflow tasks   → saved into a subdirectory named after the step,
                           then this function is called recursively.

    depth controls indentation in console output.
    """
    indent = "  " * depth

    try:
        execution = client.workflows.get_executions(workflow_id, execution_id)
    except Exception as e:
        print(f"{indent}⚠  Could not fetch execution {execution_id} "
              f"for workflow {workflow_id}: {e}")
        return

    tasks = execution.tasks or []
    if not tasks:
        print(f"{indent}⚠  No tasks in this execution.")
        return

    os.makedirs(output_dir, exist_ok=True)

    for step_num, task in enumerate(tasks, start=1):
        task_name  = task.name
        safe_name  = safe_filename(task_name)
        step_label = f"step_{step_num:02d}_{safe_name}"

        # ── Find job_id from runs ────────────────────────────────────────────
        job_id = None
        runs   = getattr(task, "runs", []) or []
        for run in reversed(runs):           # most recent first
            jid = getattr(run, "job_id", None)
            if jid:
                job_id = jid
                break

        # ── Check for sub-workflow executions ────────────────────────────────
        child_pairs = []
        if job_id is None:
            execs = getattr(task, "executions", []) or []
            child_pairs = [
                (getattr(e, "workflow_id", None), getattr(e, "id", None))
                for e in execs
                if getattr(e, "id", None)
            ]

        # ── Sub-workflow: recurse into a subdirectory ────────────────────────
        if child_pairs:
            subdir = os.path.join(output_dir, step_label)
            print(f"{indent}[{step_num:>2}] 📁 {task_name}/")
            for child_wf_id, child_ex_id in child_pairs:
                process_execution(client, child_wf_id, child_ex_id, subdir, depth + 1)
            continue

        # ── Skipped task (no runs, no child executions) ──────────────────────
        if job_id is None:
            filename = f"{step_label}_skipped.txt"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(
                    f"# Step {step_num}: {task_name}\n"
                    f"# No runs recorded — task may have been skipped.\n"
                )
            print(f"{indent}[{step_num:>2}] –  {filename}  (skipped)")
            continue

        # ── Direct script: fetch and save ────────────────────────────────────
        try:
            content, ext, job_name = fetch_script_content(client, job_id)
        except Exception as e:
            content  = f"# Unexpected error fetching script: {e}\n"
            ext      = "txt"
            job_name = task_name

        header = (
            f"# Step {step_num}: {task_name}\n"
            f"# Workflow ID: {workflow_id}  |  Execution ID: {execution_id}\n"
            f"# Job ID: {job_id}  |  Job name: {job_name}\n"
            + "#" + "─" * 68 + "\n\n"
        )

        filename = f"{step_label}.{ext}"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(header + (content or "# (empty source)\n"))

        print(f"{indent}[{step_num:>2}] ✓  {filename}")


def main():
    if not os.environ.get("CIVIS_API_KEY"):
        print("ERROR: CIVIS_API_KEY environment variable is not set.")
        sys.exit(1)

    client = civis.APIClient()

    # ── Get workflow ─────────────────────────────────────────────────────────
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

    # ── Recursively download everything ──────────────────────────────────────
    print(f"Downloading to ./{OUTPUT_DIR}/\n")
    process_execution(
        client,
        workflow_id  = WORKFLOW_ID,
        execution_id = workflow.last_execution_id,
        output_dir   = OUTPUT_DIR,
        depth        = 0,
    )

    print(f"\nDone. Output is in ./{OUTPUT_DIR}/")


if __name__ == "__main__":
    main()