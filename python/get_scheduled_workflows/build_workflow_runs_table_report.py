import csv
import os
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    from backports.zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def parse_api_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def get_workflow_zoneinfo(workflow):
    time_zone_name = str(workflow.get("time_zone") or "UTC")
    try:
        return ZoneInfo(time_zone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def fetch_scheduled_workflows(client):
    workflows = []
    page_num = 1
    while True:
        page = client.workflows.list(page_num=page_num, scheduled=True)
        if not page:
            break
        workflows.extend(page)
        page_num += 1
    return [wf for wf in workflows if not wf.get("archived", False)]


def schedule_to_string(workflow):
    schedule = workflow.get("schedule", {})
    days = schedule.get("scheduled_days", []) or []
    hours = schedule.get("scheduled_hours", []) or []
    minutes = schedule.get("scheduled_minutes", []) or []
    days_of_month = schedule.get("scheduled_days_of_month", []) or []

    parts = []
    if days:
        parts.append("Days: " + ", ".join(DAY_NAMES[d] for d in days if 0 <= d <= 6))
    if days_of_month:
        parts.append("Days of month: " + ", ".join(str(d) for d in days_of_month))

    if hours or minutes:
        hour_values = hours or [0]
        minute_values = minutes or [0]
        times = [f"{hour}:{minute:02d}" for hour in hour_values for minute in minute_values]
        time_zone = getattr(get_workflow_zoneinfo(workflow), "key", "UTC")
        parts.append(f"Time ({time_zone}): " + ", ".join(times))

    return "; ".join(parts) if parts else "N/A"


def fetch_most_recent_execution(client, workflow_id):
    executions = client.workflows.list_executions(
        workflow_id,
        limit=1,
        page_num=1,
        order="created_at",
        order_dir="desc",
    )
    if not executions:
        return None
    return executions[0]


def normalize_execution_state(execution):
    if not execution:
        return "Not run"
    state = str(execution.get("state") or execution.get("mistral_state") or "").strip()
    return state or "Unknown"


def most_recent_run_time(execution):
    if not execution:
        return None
    for key in ("started_at", "created_at", "finished_at"):
        timestamp = parse_api_datetime(execution.get(key))
        if timestamp is not None:
            return timestamp
    return None


def display_run_time(timestamp):
    if timestamp is None:
        return "Never"
    return timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")


def build_workflow_rows(client, workflows):
    rows = []
    for workflow in workflows:
        execution = fetch_most_recent_execution(client, workflow["id"])
        run_time = most_recent_run_time(execution)
        rows.append(
            {
                "workflow_name": str(workflow.get("name", "")),
                "workflow_id": workflow["id"],
                "workflow_url": (
                    f"https://platform.civisanalytics.com/spa/#/workflows/{workflow['id']}"
                ),
                "most_recent_run": display_run_time(run_time),
                "most_recent_run_sort": run_time or datetime.min.replace(tzinfo=timezone.utc),
                "most_recent_run_state": normalize_execution_state(execution),
                "schedule": schedule_to_string(workflow),
            }
        )

    rows.sort(key=lambda row: row["most_recent_run_sort"], reverse=True)
    return rows


def write_csv(rows, file_path):
    fieldnames = [
        "workflow_name",
        "workflow_id",
        "workflow_url",
        "most_recent_run",
        "most_recent_run_state",
        "schedule",
    ]
    with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "workflow_name": row["workflow_name"],
                    "workflow_id": row["workflow_id"],
                    "workflow_url": row["workflow_url"],
                    "most_recent_run": row["most_recent_run"],
                    "most_recent_run_state": row["most_recent_run_state"],
                    "schedule": row["schedule"],
                }
            )


def upload_csv_as_run_output(client, local_csv_path, filename):
    import civis

    file_id = civis.io.file_to_civis(local_csv_path, name=filename)
    client.scripts.post_python3_runs_outputs(
        os.environ["CIVIS_JOB_ID"],
        os.environ["CIVIS_RUN_ID"],
        "File",
        int(file_id),
    )
    return int(file_id)


def main():
    import civis

    client = civis.APIClient()
    workflows = fetch_scheduled_workflows(client)
    rows = build_workflow_rows(client, workflows)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"workflow_runs_{timestamp}.csv"
    local_csv_path = f"/tmp/{filename}"

    write_csv(rows, local_csv_path)
    file_id = upload_csv_as_run_output(client, local_csv_path, filename)
    print(f"Attached CSV run output file ID: {file_id}")
    print(f"CSV path: {local_csv_path}")


if __name__ == "__main__":
    main()
