import html as html_lib
import os
from datetime import datetime, timedelta, timezone
import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
EVERYDAY_SCHEDULED_DAYS = list(range(7))

# How far back to load real executions, and how far ahead to project scheduled runs.
LOOKBACK_DAYS = 60
FORWARD_DAYS = 45
# Executions that finish in seconds would be invisible slivers in the week/day views,
# so give every event at least this much height (true runtime is kept separately).
MIN_DISPLAY_DURATION = timedelta(minutes=15)
FAILURE_STATES = {"failed", "cancelled"}

PLATFORM_URL = "https://platform.civisanalytics.com/spa/#"

# Time zone the report is displayed in (calendar, event details, "generated at").
# Use any IANA name, e.g. "America/Chicago", "America/New_York", "UTC".
# Display only: each workflow's own schedule time zone is unchanged.
DISPLAY_TIME_ZONE = "America/Chicago"
DISPLAY_ZONEINFO = ZoneInfo(DISPLAY_TIME_ZONE)  # fails fast on a bad name


def workflow_url(workflow_id):
    return f"{PLATFORM_URL}/workflows/{workflow_id}"


def execution_url(workflow_id, execution_id):
    # UNVERIFIED pattern: confirm against a real execution page in platform.
    return f"{PLATFORM_URL}/workflows/{workflow_id}/executions/{execution_id}"


def job_url(job_id):
    return f"{PLATFORM_URL}/jobs/{job_id}"


# ---------------------------------------------------------------------------
# Fetch all workflows (paginated)
# ---------------------------------------------------------------------------
def fetch_all_workflows(client):
    # Every workflow, scheduled or not: unscheduled ones still have run history to show.
    workflows, page = [], 1
    while True:
        page_workflows = client.workflows.list(page_num=page, limit=50)
        if not page_workflows:
            break
        workflows.extend(page_workflows)
        page += 1
    return workflows


def fetch_all_scheduled_jobs(client):
    # Scheduled jobs only: unscheduled jobs would swamp the calendar.
    jobs, page = [], 1
    while True:
        page_jobs = client.jobs.list(page_num=page, limit=50, scheduled=True, archived="false")
        if not page_jobs:
            break
        jobs.extend(page_jobs)
        page += 1
    return jobs


# ---------------------------------------------------------------------------
# Parse schedule into a human-readable string
# ---------------------------------------------------------------------------
def schedule_to_string(ws):
    parts = []
    days = ws.get("scheduled_days", [])
    hours = ws.get("scheduled_hours", [])
    minutes = ws.get("scheduled_minutes", [])
    days_of_month = ws.get("scheduled_days_of_month", [])

    if days:
        parts.append("Days: " + ", ".join(DAY_NAMES[d] for d in days if 0 <= d <= 6))
    if days_of_month:
        parts.append("Days of month: " + ", ".join(str(d) for d in days_of_month))
    if hours or minutes:
        h_list = hours or [0]
        m_list = minutes or [0]
        times = [f"{h}:{m:02d}" for h in h_list for m in m_list]
        time_zone = getattr(get_workflow_zoneinfo(ws), "key", "UTC")
        parts.append(f"Time ({time_zone}): " + ", ".join(times))
    return "; ".join(parts) if parts else "N/A"


def get_workflow_zoneinfo(ws):
    time_zone_name = str(ws.get("time_zone") or "UTC")
    try:
        return ZoneInfo(time_zone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def normalize_schedule_values(values, min_value, max_value):
    return [v for v in values if isinstance(v, int) and min_value <= v <= max_value]


def normalize_schedule(schedule):
    schedule = schedule or {}
    return {
        "scheduled": bool(schedule.get("scheduled", False)),
        "scheduled_days": normalize_schedule_values(
            schedule.get("scheduled_days") or [],
            0,
            6,
        ),
        "scheduled_hours": normalize_schedule_values(
            schedule.get("scheduled_hours") or [],
            0,
            23,
        ),
        "scheduled_minutes": normalize_schedule_values(
            schedule.get("scheduled_minutes") or [],
            0,
            59,
        ),
        "scheduled_days_of_month": normalize_schedule_values(
            schedule.get("scheduled_days_of_month") or [],
            1,
            31,
        ),
    }


def normalize_workflow(workflow):
    return {
        "item_type": "workflow",
        "id": workflow["id"],
        "name": str(workflow.get("name", "")),
        **normalize_schedule(workflow.get("schedule")),
        "created_at": str(workflow.get("created_at", "")),
        "next_execution_at": str(workflow.get("next_execution_at", "")),
        "time_zone": getattr(get_workflow_zoneinfo(workflow), "key", "UTC"),
        "state": str(workflow.get("state", "")),
    }


def normalize_job(job):
    # The API gives jobs no time zone, so their schedules are read in the display zone.
    last_run = job.get("last_run") or {}
    return {
        "item_type": "job",
        "id": job["id"],
        "name": str(job.get("name", "")),
        "job_type": str(job.get("type", "")),
        **normalize_schedule(job.get("schedule")),
        "created_at": str(job.get("created_at", "")),
        "next_execution_at": "",
        "time_zone": DISPLAY_TIME_ZONE,
        "state": str(last_run.get("state") or ""),
    }


def event_time_pairs(ws):
    hours = ws.get("scheduled_hours") or [0]
    minutes = ws.get("scheduled_minutes") or [0]
    return [(hour, minute) for hour in hours for minute in minutes]


def parse_api_datetime(value):
    # Civis commonly returns UTC timestamps with a trailing Z.
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


def normalize_execution_state(execution):
    state = str(execution.get("state") or execution.get("mistral_state") or "").strip().lower()
    if state in {"failed", "error"}:
        return "failed"
    if state in {"succeeded", "success"}:
        return "succeeded"
    if state in {"cancelled", "canceled"}:
        return "cancelled"
    if state in {"queued", "running", "paused"}:
        return state
    return "scheduled"


def execution_reference_time(execution):
    # Prefer the earliest lifecycle timestamp we can use to line an execution
    # up with its scheduled slot.
    for key in ("started_at", "created_at", "finished_at"):
        timestamp = parse_api_datetime(execution.get(key))
        if timestamp is not None:
            return timestamp
    return None


def normalize_execution(execution):
    started_at = parse_api_datetime(execution.get("started_at"))
    finished_at = parse_api_datetime(execution.get("finished_at"))
    duration_seconds = (
        (finished_at - started_at).total_seconds() if started_at and finished_at else None
    )
    return {
        "id": execution.get("id"),
        "state": normalize_execution_state(execution),
        # Workflow executions report mistral_state_info; job runs report error.
        "state_info": str(execution.get("mistral_state_info") or execution.get("error") or ""),
        "reference_at": execution_reference_time(execution),
        "started_at": str(execution.get("started_at", "") or ""),
        "finished_at": str(execution.get("finished_at", "") or ""),
        "created_at": str(execution.get("created_at", "") or ""),
        "duration_seconds": duration_seconds,
        "tasks": [],
    }


def workflow_occurrence_times(ws, range_start, range_end):
    """Scheduled run times for every date from range_start to range_end (inclusive)."""
    days = [range_start + timedelta(days=i) for i in range((range_end - range_start).days + 1)]
    tzinfo = get_workflow_zoneinfo(ws)
    scheduled_days = set(ws.get("scheduled_days", []))
    days_of_month = ws.get("scheduled_days_of_month", [])
    occurrences = []

    if scheduled_days:
        for day in days:
            civis_weekday = (day.weekday() + 1) % 7  # Civis: 0=Sun
            if civis_weekday in scheduled_days:
                for hour, minute in event_time_pairs(ws):
                    occurrences.append(
                        datetime(day.year, day.month, day.day, hour, minute, tzinfo=tzinfo)
                    )
    elif days_of_month:
        for day in days:
            if day.day in days_of_month:
                for hour, minute in event_time_pairs(ws):
                    occurrences.append(
                        datetime(day.year, day.month, day.day, hour, minute, tzinfo=tzinfo)
                    )

    return sorted(occurrences)


def fetch_workflow_executions(client, workflow_id, window_start_utc, window_end_utc):
    limit = 50
    return collect_runs_in_window(
        lambda page_num: client.workflows.list_executions(
            workflow_id,
            limit=limit,
            page_num=page_num,
            order="created_at",
            order_dir="desc",
        ),
        limit,
        window_start_utc,
        window_end_utc,
    )


def fetch_job_runs(client, job_id, window_start_utc, window_end_utc):
    limit = 100
    return collect_runs_in_window(
        # Runs can only be ordered by id, which still tracks creation time.
        lambda page_num: client.jobs.list_runs(
            job_id,
            limit=limit,
            page_num=page_num,
            order="id",
            order_dir="desc",
        ),
        limit,
        window_start_utc,
        window_end_utc,
    )


def collect_runs_in_window(fetch_page, limit, window_start_utc, window_end_utc):
    """Page through newest-first runs, keeping those that started inside the window."""
    if window_start_utc is None or window_end_utc is None:
        return []

    executions = []
    page_num = 1
    while True:
        # Keep paging only until runs are older than the window.
        page = fetch_page(page_num)
        if not page:
            break

        oldest_in_page = None
        for execution in page:
            normalized = normalize_execution(execution)
            reference_at = normalized["reference_at"]
            created_at = parse_api_datetime(normalized["created_at"])
            if created_at is not None and (oldest_in_page is None or created_at < oldest_in_page):
                oldest_in_page = created_at
            if reference_at is None:
                continue
            if reference_at < window_start_utc or reference_at >= window_end_utc:
                continue
            executions.append(normalized)

        if len(page) < limit:
            break
        if oldest_in_page is not None and oldest_in_page < window_start_utc:
            break
        page_num += 1

    return executions


def fetch_execution_tasks(client, workflow_id, execution_id):
    # One extra API call per execution, so only used for failed/cancelled runs.
    detail = client.workflows.get_executions(workflow_id, execution_id)
    tasks = []
    for task in detail.get("tasks") or []:
        runs = task.get("runs") or []
        latest_run = runs[0] if runs else {}
        started_at = parse_api_datetime(latest_run.get("started_at"))
        finished_at = parse_api_datetime(latest_run.get("finished_at"))
        tasks.append(
            {
                "name": str(task.get("name", "")),
                "state": str(task.get("mistral_state") or ""),
                "stateInfo": str(task.get("mistral_state_info") or ""),
                "jobId": latest_run.get("job_id"),
                "jobUrl": job_url(latest_run["job_id"]) if latest_run.get("job_id") else "",
                "runId": latest_run.get("id"),
                "runState": str(latest_run.get("state") or ""),
                "durationSeconds": (
                    (finished_at - started_at).total_seconds()
                    if started_at and finished_at
                    else None
                ),
            }
        )
    return tasks


def execution_state_color(state):
    normalized_state = str(state or "").strip().lower()
    if normalized_state == "failed":
        return "#c0392b"
    if normalized_state == "succeeded":
        return "#1f7a3d"
    if normalized_state in {"running", "queued", "paused"}:
        return "#d97706"
    if normalized_state == "cancelled":
        return "#6b7280"
    return "#20639b"


def format_execution_state_label(state):
    normalized_state = str(state or "").strip().lower()
    if not normalized_state:
        return "Not run"
    if normalized_state == "succeeded":
        return "Succeeded"
    if normalized_state == "failed":
        return "Failed"
    if normalized_state == "cancelled":
        return "Cancelled"
    if normalized_state == "queued":
        return "Queued"
    if normalized_state == "running":
        return "Running"
    if normalized_state == "paused":
        return "Paused"
    if normalized_state == "scheduled":
        return "Scheduled"
    return normalized_state.title()


def item_url(item):
    if item["item_type"] == "job":
        return job_url(item["id"])
    return workflow_url(item["id"])


def item_event_metadata(item):
    metadata = {
        "itemType": item["item_type"],
        "itemId": item["id"],
        "itemUrl": item_url(item),
        "scheduleText": schedule_to_string(item),
        "timeZone": item.get("time_zone", "UTC"),
        "createdAt": item.get("created_at", ""),
        "nextExecutionAt": item.get("next_execution_at", ""),
        # Everyday items are hidden from the month grid but shown in week/day views.
        "everyday": is_everyday(item),
    }
    if item["item_type"] == "job":
        metadata["jobType"] = item.get("job_type", "")
        metadata["classNames"] = ["type-job"]
    return metadata


# ---------------------------------------------------------------------------
# Build calendar events for FullCalendar
# ---------------------------------------------------------------------------
def build_calendar_events(items, item_executions, range_start, range_end, now_utc):
    """Real runs (with true runtime/status) plus upcoming scheduled runs.

    items: normalized workflows and jobs. item_executions: {(item_type, id): [runs]}.
    """
    events = []
    for item in items:
        metadata = item_event_metadata(item)

        for execution in item_executions.get((item["item_type"], item["id"]), []):
            start = execution["reference_at"]
            finished = parse_api_datetime(execution["finished_at"])
            end = max(finished or now_utc, start + MIN_DISPLAY_DURATION)
            events.append(
                {
                    "title": item["name"],
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "color": execution_state_color(execution["state"]),
                    **metadata,
                    "kind": "execution",
                    "state": execution["state"],
                    "executionId": execution["id"],
                    "executionUrl": (
                        execution_url(item["id"], execution["id"])
                        if item["item_type"] == "workflow"
                        else ""
                    ),
                    "startedAt": execution["started_at"],
                    "finishedAt": execution["finished_at"],
                    "durationSeconds": execution["duration_seconds"],
                    "stateInfo": execution["state_info"],
                    "tasks": execution["tasks"],
                }
            )

        # Unscheduled workflows only contribute their history.
        if not item["scheduled"]:
            continue
        for occurrence_time in workflow_occurrence_times(item, range_start, range_end):
            # Past slots are represented by the executions above, not projected.
            if occurrence_time.astimezone(timezone.utc) <= now_utc:
                continue
            events.append(
                {
                    "title": item["name"],
                    "start": occurrence_time.isoformat(),
                    "color": execution_state_color("scheduled"),
                    **metadata,
                    "kind": "scheduled",
                    "state": "scheduled",
                }
            )
    return events


# ---------------------------------------------------------------------------
# Build everyday workflow cards HTML
# ---------------------------------------------------------------------------
def build_everyday_cards(everyday_workflows, most_recent_states=None):
    most_recent_states = most_recent_states or {}
    cards = []
    for ws in everyday_workflows:
        workflow_name = str(ws.get("name", ""))
        workflow_link = html_lib.escape(item_url(ws))
        workflow_name_lower = html_lib.escape(workflow_name.lower(), quote=True)
        workflow_name_html = html_lib.escape(workflow_name)
        schedule_html = html_lib.escape(schedule_to_string(ws))
        created_at_html = html_lib.escape(str(ws.get("created_at", "")))
        most_recent_state = most_recent_states.get(ws["id"], "not run")
        state_color = execution_state_color(most_recent_state)
        state_label_html = html_lib.escape(format_execution_state_label(most_recent_state))
        cards.append(
            f"<div class='workflow-card' data-wfname=\"{workflow_name_lower}\">"
            f"  <div><b>Name:</b> <a href='{workflow_link}' target='_blank' "
            f"rel='noopener noreferrer'>{workflow_name_html}</a></div>"
            f"  <div class='workflow-meta'><b>Schedule:</b> {schedule_html}</div>"
            f"  <div class='workflow-meta'><b>Most recent run state:</b> "
            f"<span class='workflow-state'><span class='workflow-state-dot' "
            f"style='background:{state_color};'></span>{state_label_html}</span></div>"
            f"  <div class='workflow-meta'><b>Created:</b> {created_at_html}</div>"
            f"</div>"
        )
    return "\n".join(cards)


# ---------------------------------------------------------------------------
# Build the full HTML report
# ---------------------------------------------------------------------------
def build_html_styles():
    return """
    <style>
        *, *::before, *::after { box-sizing: border-box; }

        body {
            font-family: 'Roboto', Arial, sans-serif;
            background: #f4f6fa;
            color: #222;
            margin: 0;
            padding: 0 0 60px;
        }
        #page-header {
            background: linear-gradient(135deg, #2a4d69, #20639b);
            color: #fff;
            padding: 28px 24px 24px;
            text-align: center;
        }
        h1 {
            margin: 0;
            font-size: 2em;
            letter-spacing: 0.5px;
        }
        .subtitle { margin: 6px 0 0; opacity: 0.85; font-size: 0.95em; }

        #summary-tiles {
            max-width: 1000px;
            margin: -18px auto 0;
            padding: 0 16px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
        }
        .tile {
            background: #fff;
            border-radius: 10px;
            padding: 12px 16px;
            box-shadow: 0 2px 10px rgba(42,77,105,0.12);
            border-top: 4px solid #b5c6d6;
        }
        .tile .tile-value { font-size: 1.7em; font-weight: 700; color: #2a4d69; }
        .tile .tile-label { font-size: 0.85em; color: #667; }

        #explanation {
            max-width: 968px;
            margin: 20px auto 0;
            background: #eaf1fb;
            border-radius: 8px;
            padding: 10px 20px;
            color: #234;
            line-height: 1.6;
        }
        #explanation summary { cursor: pointer; font-weight: 700; color: #2a4d69; }

        #controls {
            max-width: 1000px;
            margin: 20px auto 0;
            padding: 0 16px;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            align-items: center;
            justify-content: space-between;
        }
        .filter-chip {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            margin-left: 6px;
            padding: 5px 12px;
            border: 1px solid #b5c6d6;
            border-radius: 999px;
            background: #fff;
            font: inherit;
            font-size: 0.9em;
            cursor: pointer;
        }
        .filter-chip.active { border-color: #2a4d69; background: #e8f0f7; font-weight: 600; }
        .fc-event.dimmed { opacity: 0.2; }
        .fc-event.type-job { border-left: 4px solid #2a4d69; }
        .type-badge {
            display: inline-block;
            margin-right: 4px;
            padding: 0 4px;
            border-radius: 3px;
            background: rgba(255,255,255,0.3);
            font-size: 0.75em;
            font-weight: 700;
            text-transform: uppercase;
        }
        .type-toggles { display: flex; align-items: center; gap: 2px; }
        .type-toggles-label { font-size: 0.9em; color: #555; }
        .type-toggle { opacity: 0.6; }
        .type-toggle.on { opacity: 1; border-color: #2a4d69; background: #e8f0f7; font-weight: 600; }
        .everyday-section + .everyday-section { margin-top: 28px; }
        .filter-chip .dot { width: 10px; height: 10px; border-radius: 50%; }

        #search-box {
            display: block;
            flex: 1 1 260px;
            max-width: 400px;
            padding: 10px 16px;
            font-size: 1.05em;
            border: 1px solid #b5c6d6;
            border-radius: 8px;
            box-shadow: 0 1px 4px rgba(42,77,105,0.04);
            outline: none;
        }
        #search-box:focus {
            border-color: #2a4d69;
            box-shadow: 0 0 0 2px rgba(42,77,105,0.15);
        }

        #calendar {
            max-width: 1000px;
            margin: 16px auto 0;
            padding: 16px;
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(42,77,105,0.08);
        }
        .fc-event { cursor: pointer; }

        .wf-tooltip {
            position: fixed;
            background: #fff;
            border: 1px solid #ccc;
            padding: 10px 14px;
            display: none;
            z-index: 1500;
            box-shadow: 0 2px 10px rgba(42,77,105,0.15);
            border-radius: 8px;
            font-size: 0.92em;
            max-width: 360px;
            pointer-events: none;
            line-height: 1.6;
        }

        #everyday-list {
            max-width: 1000px;
            margin: 40px auto 0;
            padding: 24px;
            background: #fff;
            border: 1px solid #e0e6ed;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(42,77,105,0.06);
        }
        #everyday-list h2 {
            text-align: center;
            color: #2a4d69;
            margin: 0 0 20px;
        }
        .workflow-card {
            background: #f9fafc;
            border: 1px solid #e0e6ed;
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 14px;
            box-shadow: 0 1px 4px rgba(42,77,105,0.04);
        }
        .workflow-card a {
            color: #20639b;
            text-decoration: none;
            font-weight: 500;
        }
        .workflow-card a:hover { text-decoration: underline; }
        .workflow-meta {
            font-size: 0.95em;
            color: #555;
            margin-top: 4px;
        }
        .workflow-state {
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .workflow-state-dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            flex: 0 0 10px;
        }

        #event-modal {
            display: none;
            position: fixed;
            inset: 0;
            z-index: 2000;
            background: rgba(0,0,0,0.35);
            overflow-y: auto;
        }
        .modal-content {
            background: #fff;
            border-radius: 10px;
            max-width: 720px;
            margin: 60px auto;
            padding: 32px 28px 24px;
            box-shadow: 0 4px 24px rgba(42,77,105,0.18);
            position: relative;
        }
        .modal-content h3 {
            margin-top: 0;
            color: #2a4d69;
        }
        .modal-content ul { padding-left: 18px; }
        .modal-content:focus { outline: none; }
        .close-btn {
            position: absolute;
            top: 12px;
            right: 18px;
            padding: 0 4px;
            background: none;
            border: 0;
            font-size: 1.5em;
            color: #888;
            cursor: pointer;
            line-height: 1;
        }
        .close-btn:hover { color: #2a4d69; }
        .close-btn:focus-visible { outline: 2px solid #2a4d69; outline-offset: 2px; }

        .status-pill {
            display: inline-block;
            padding: 2px 10px;
            border-radius: 999px;
            color: #fff;
            font-size: 0.85em;
            font-weight: 700;
            vertical-align: middle;
            margin-left: 8px;
        }
        .detail-links { margin: 12px 0 4px; }
        .detail-links a {
            display: inline-block;
            margin-right: 8px;
            padding: 6px 12px;
            border: 1px solid #20639b;
            border-radius: 6px;
            color: #20639b;
            text-decoration: none;
            font-size: 0.9em;
        }
        .detail-links a:hover { background: #20639b; color: #fff; }
        .task-table a { color: #20639b; }
        .task-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.92em;
        }
        .task-table th, .task-table td {
            text-align: left;
            padding: 6px 8px;
            border-bottom: 1px solid #e0e6ed;
        }
        .task-table tr.task-failed td { background: #fdecea; color: #922b21; font-weight: 500; }
        .task-table tr.task-info td { background: #fdf6f5; }
        .task-table pre {
            margin: 0;
            white-space: pre-wrap;
            word-break: break-word;
            font-size: 0.9em;
        }
    </style>
    """


def build_client_script(calendar_time_zone=DISPLAY_TIME_ZONE):
    # Plain string (not an f-string) so the JavaScript braces don't need escaping.
    script = """
<script>
(function () {
    var eventsDataEl = document.getElementById('events-data');
    var ALL_EVENTS = JSON.parse(eventsDataEl ? eventsDataEl.textContent : '[]');
    var STATE_COLORS = __STATE_COLORS__;
    var STATE_LABELS = {
        succeeded: 'Succeeded', failed: 'Failed', running: 'Running',
        cancelled: 'Cancelled', scheduled: 'Scheduled'
    };
    var currentViewType = 'timeGridWeek';
    var searchQuery = '';
    var highlightedState = null;
    var visibleTypes = { workflow: true, job: true };

    // Queued/paused runs are grouped with running for the legend and filters.
    function stateBucket(state) {
        return (state === 'queued' || state === 'paused') ? 'running' : state;
    }

    var tooltip = document.createElement('div');
    tooltip.className = 'wf-tooltip';
    document.body.appendChild(tooltip);

    function escapeHtml(value) {
        return String(value === null || value === undefined ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function safeExternalUrl(value) {
        if (!value) return '';
        try {
            var url = new URL(String(value), window.location.origin);
            if (url.protocol === 'http:' || url.protocol === 'https:') return url.toString();
        } catch (err) {
            return '';
        }
        return '';
    }

    function formatDuration(seconds) {
        if (seconds === null || seconds === undefined || seconds === '') return 'n/a';
        var total = Math.round(Number(seconds));
        var h = Math.floor(total / 3600);
        var m = Math.floor((total % 3600) / 60);
        var s = total % 60;
        if (h) return h + 'h ' + m + 'm ' + s + 's';
        if (m) return m + 'm ' + s + 's';
        return s + 's';
    }

    function formatTimestamp(value) {
        if (!value) return 'n/a';
        var d = new Date(value);
        return isNaN(d.getTime()) ? String(value) : d.toLocaleString(undefined, {
            timeZone: '__CALENDAR_TIME_ZONE__',
            timeZoneName: 'short'
        });
    }

    function stateLabel(state) {
        var text = String(state || 'scheduled');
        return text.charAt(0).toUpperCase() + text.slice(1);
    }

    function failedTasks(props) {
        return (props.tasks || []).filter(function (t) {
            return t.state === 'error' || t.state === 'cancelled';
        });
    }

    function typeLabel(props) {
        return props.itemType === 'job' ? 'Job' : 'Workflow';
    }

    function itemLink(event, props) {
        var title = escapeHtml(event.title || '');
        var itemUrl = safeExternalUrl(props.itemUrl);
        return itemUrl
            ? "<a href='" + escapeHtml(itemUrl) +
              "' target='_blank' rel='noopener noreferrer'>" + title + "</a>"
            : title;
    }

    // Short summary used for the hover tooltip and the "+ more" list.
    function buildEventHtml(event, detailed) {
        var props = event.extendedProps || {};
        var lines = detailed ? [] : ['<b>Name:</b> ' + itemLink(event, props)];
        lines.push('<b>Type:</b> ' + typeLabel(props));
        lines.push('<b>' + typeLabel(props) + ' ID:</b> ' + escapeHtml(props.itemId));
        lines.push('<b>State:</b> ' + escapeHtml(stateLabel(props.state)));

        if (props.kind === 'execution') {
            lines.push('<b>Started:</b> ' + escapeHtml(formatTimestamp(props.startedAt)));
            lines.push('<b>Finished:</b> ' + escapeHtml(
                props.finishedAt ? formatTimestamp(props.finishedAt) : 'still running'));
            lines.push('<b>Runtime:</b> ' + escapeHtml(formatDuration(props.durationSeconds)));
            failedTasks(props).forEach(function (t) {
                lines.push('<b>Failed task:</b> ' + escapeHtml(t.name));
            });
            if (props.stateInfo) {
                lines.push('<b>Error:</b> ' + escapeHtml(props.stateInfo));
            }
            if (!detailed) lines.push('<i>Click for details</i>');
        } else {
            lines.push('<b>Scheduled for:</b> ' + escapeHtml(formatTimestamp(event.start)));
            lines.push('<b>Schedule:</b> ' + escapeHtml(props.scheduleText));
            lines.push('<b>Time zone:</b> ' + escapeHtml(props.timeZone));
        }
        return lines.join('<br/>');
    }

    // Full detail shown in the modal on click, including per-task status.
    function buildDetailHtml(event) {
        var props = event.extendedProps || {};
        var color = STATE_COLORS[stateBucket(props.state)] || '#20639b';
        var html = '<h3>' + itemLink(event, props) +
            '<span class="status-pill" style="background:' + color + '">' +
            escapeHtml(stateLabel(props.state)) + '</span></h3>' + buildEventHtml(event, true);
        html += '<br/><b>Schedule:</b> ' + escapeHtml(props.scheduleText);
        html += '<br/><b>Time zone:</b> ' + escapeHtml(props.timeZone);
        html += '<br/><b>Created:</b> ' + escapeHtml(props.createdAt);
        if (props.kind === 'execution') {
            html += '<br/><b>' + (props.itemType === 'job' ? 'Run' : 'Execution') + ' ID:</b> ' +
                escapeHtml(props.executionId);
        }

        var links = [];
        var executionUrl = safeExternalUrl(props.executionUrl);
        var itemUrl = safeExternalUrl(props.itemUrl);
        if (executionUrl) links.push([executionUrl, (props.itemType === 'job' ? 'View run' : 'View execution') + ' \u2197']);
        if (itemUrl) links.push([itemUrl, 'Open ' + typeLabel(props).toLowerCase() + ' \u2197']);
        if (links.length) {
            html += '<div class="detail-links">' + links.map(function (l) {
                return "<a href='" + escapeHtml(l[0]) +
                    "' target='_blank' rel='noopener noreferrer'>" + escapeHtml(l[1]) + '</a>';
            }).join('') + '</div>';
        }

        var tasks = props.tasks || [];
        if (tasks.length) {
            html += '<h4>Tasks</h4><table class="task-table"><thead><tr>' +
                '<th>Task</th><th>State</th><th>Runtime</th><th>Job / Run</th>' +
                '</tr></thead><tbody>';
            tasks.forEach(function (t) {
                var failed = t.state === 'error' || t.state === 'cancelled';
                html += '<tr class="' + (failed ? 'task-failed' : '') + '">' +
                    '<td>' + escapeHtml(t.name) + '</td>' +
                    '<td>' + escapeHtml(t.state) + '</td>' +
                    '<td>' + escapeHtml(formatDuration(t.durationSeconds)) + '</td>' +
                    '<td>' + taskJobHtml(t) + '</td></tr>';
                if (t.stateInfo) {
                    html += '<tr class="task-info"><td colspan="4"><pre>' +
                        escapeHtml(t.stateInfo) + '</pre></td></tr>';
                }
            });
            html += '</tbody></table>';
        }
        return html;
    }

    function taskJobHtml(task) {
        if (!task.jobId) return 'n/a';
        var label = escapeHtml('Job ' + task.jobId + ' / Run ' + task.runId);
        var url = safeExternalUrl(task.jobUrl);
        return url
            ? "<a href='" + escapeHtml(url) + "' target='_blank' rel='noopener noreferrer'>" +
              label + ' \u2197</a>'
            : label;
    }

    var modalOpener = null;

    function isModalOpen() {
        return document.getElementById('event-modal').style.display === 'block';
    }

    function closeModal() {
        document.getElementById('event-modal').style.display = 'none';
        if (modalOpener && document.contains(modalOpener) && modalOpener.focus) {
            modalOpener.focus();
        }
        modalOpener = null;
    }

    function openModal(html) {
        var modal = document.getElementById('event-modal');
        var content = document.getElementById('event-modal-content');
        var closeBtn = document.createElement('button');

        modalOpener = document.activeElement;
        content.innerHTML = html;

        var heading = content.querySelector('h3');
        if (heading) {
            heading.id = 'event-modal-title';
            content.setAttribute('aria-labelledby', 'event-modal-title');
            content.removeAttribute('aria-label');
        } else {
            content.removeAttribute('aria-labelledby');
            content.setAttribute('aria-label', 'Details');
        }

        closeBtn.type = 'button';
        closeBtn.className = 'close-btn';
        closeBtn.id = 'modal-close';
        closeBtn.setAttribute('aria-label', 'Close dialog');
        closeBtn.textContent = '\\u00d7';
        closeBtn.onclick = closeModal;
        content.insertBefore(closeBtn, content.firstChild);

        modal.style.display = 'block';
        modal.onclick = function (e) {
            if (e.target === modal) closeModal();
        };
        content.scrollTop = 0;
        closeBtn.focus();
    }

    // Escape dismisses the modal; Tab / Shift+Tab wrap inside it so focus cannot
    // land on the calendar behind the overlay.
    document.addEventListener('keydown', function (e) {
        if (!isModalOpen()) return;
        if (e.key === 'Escape') {
            e.preventDefault();
            closeModal();
            return;
        }
        if (e.key !== 'Tab') return;
        var content = document.getElementById('event-modal-content');
        var focusable = content.querySelectorAll(
            'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (!focusable.length) {
            e.preventDefault();
            content.focus();
            return;
        }
        var first = focusable[0];
        var last = focusable[focusable.length - 1];
        if (!content.contains(document.activeElement)) {
            e.preventDefault();
            first.focus();
        } else if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
        }
    });

    function showTooltip(e, event) {
        tooltip.innerHTML = buildEventHtml(event);
        tooltip.style.display = 'block';
        positionTooltip(e);
    }

    function positionTooltip(e) {
        var x = e.clientX + 12;
        var y = e.clientY + 12;
        if (x + 380 > window.innerWidth) x = e.clientX - 390;
        if (y + 300 > window.innerHeight) y = e.clientY - 310;
        tooltip.style.left = x + 'px';
        tooltip.style.top = y + 'px';
    }

    function hideTooltip() {
        tooltip.style.display = 'none';
    }

    // Everyday workflows/jobs would swamp the month grid, so they only appear in week/day views.
    function visibleEvents() {
        var monthView = currentViewType === 'dayGridMonth';
        return ALL_EVENTS.filter(function (ev) {
            if (!visibleTypes[ev.itemType]) return false;
            if (monthView && ev.everyday) return false;
            return (ev.title || '').toLowerCase().includes(searchQuery);
        });
    }

    var cal = new FullCalendar.Calendar(document.getElementById('calendar'), {
        initialView: currentViewType,
        timeZone: '__CALENDAR_TIME_ZONE__',
        height: 'auto',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay'
        },
        buttonText: { month: 'Month', week: 'Week', day: 'Day', today: 'Today' },
        nowIndicator: true,
        scrollTime: '06:00:00',
        dayMaxEvents: true,
        events: function (info, success) { success(visibleEvents()); },

        eventClassNames: function (arg) {
            var dimmed = highlightedState &&
                stateBucket(arg.event.extendedProps.state) !== highlightedState;
            return dimmed ? ['dimmed'] : [];
        },

        datesSet: function (info) {
            if (info.view.type !== currentViewType) {
                currentViewType = info.view.type;
                cal.refetchEvents();
            }
        },

        eventClick: function (info) {
            info.jsEvent.preventDefault();
            hideTooltip();
            openModal(buildDetailHtml(info.event));
        },

        eventDidMount: function (info) {
            var titleEl = info.el.querySelector('.fc-event-title');
            if (titleEl) {
                var badge = document.createElement('span');
                badge.className = 'type-badge';
                badge.textContent = info.event.extendedProps.itemType === 'job' ? 'Job' : 'WF';
                titleEl.insertBefore(badge, titleEl.firstChild);
            }
            info.el.addEventListener('mouseenter', function (e) { showTooltip(e, info.event); });
            info.el.addEventListener('mousemove', positionTooltip);
            info.el.addEventListener('mouseleave', hideTooltip);
        },

        moreLinkClick: function (arg) {
            var dateStr = arg.date ? arg.date.toISOString().slice(0, 10) : '';
            var html = '<h3>Events on ' + escapeHtml(dateStr) + '</h3><ul>';
            (arg.allSegs || []).forEach(function (seg) {
                html += '<li>' + buildEventHtml(seg.event) + '</li>';
            });
            openModal(html + '</ul>');
            return false;
        }
    });
    cal.render();

    function renderSummary() {
        var shown = ALL_EVENTS.filter(function (ev) { return visibleTypes[ev.itemType]; });
        var runs = shown.filter(function (ev) { return ev.kind === 'execution'; });
        var count = function (bucket) {
            return runs.filter(function (ev) { return stateBucket(ev.state) === bucket; }).length;
        };
        var finished = count('succeeded') + count('failed');
        var rate = finished ? Math.round(100 * count('succeeded') / finished) + '%' : 'n/a';
        var durations = runs.map(function (ev) { return ev.durationSeconds; })
            .filter(function (d) { return d !== null && d !== undefined; });
        var avg = durations.length
            ? formatDuration(durations.reduce(function (a, b) { return a + b; }, 0) /
                             durations.length)
            : 'n/a';
        var weekAhead = Date.now() + 7 * 24 * 3600 * 1000;
        var upcoming = shown.filter(function (ev) {
            return ev.kind === 'scheduled' && new Date(ev.start).getTime() <= weekAhead;
        }).length;
        var tiles = [
            ['Runs', runs.length, '#20639b'],
            ['Success rate', rate, STATE_COLORS.succeeded],
            ['Failed', count('failed'), STATE_COLORS.failed],
            ['Avg runtime', avg, '#b5c6d6'],
            ['Upcoming (7 days)', upcoming, STATE_COLORS.scheduled]
        ];
        document.getElementById('summary-tiles').innerHTML = tiles.map(function (t) {
            return '<div class="tile" style="border-top-color:' + t[2] + '">' +
                '<div class="tile-value">' + escapeHtml(t[1]) + '</div>' +
                '<div class="tile-label">' + escapeHtml(t[0]) + '</div></div>';
        }).join('');
    }

    function renderFilters() {
        var container = document.getElementById('status-filters');
        Object.keys(STATE_LABELS).forEach(function (bucket) {
            var chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'filter-chip';
            chip.innerHTML = '<span class="dot" style="background:' + STATE_COLORS[bucket] +
                '"></span>' + escapeHtml(STATE_LABELS[bucket]);
            chip.setAttribute('aria-pressed', 'false');
            chip.dataset.bucket = bucket;
            chip.onclick = function () {
                highlightedState = highlightedState === bucket ? null : bucket;
                container.querySelectorAll('.filter-chip').forEach(function (c) {
                    var on = c.dataset.bucket === highlightedState;
                    c.classList.toggle('active', on);
                    c.setAttribute('aria-pressed', String(on));
                });
                cal.refetchEvents();
            };
            container.appendChild(chip);
        });
    }

    var EVERYDAY_SECTIONS = {
        workflow: document.getElementById('everyday-workflows-section'),
        job: document.getElementById('everyday-jobs-section')
    };

    function applyTypeVisibility() {
        Object.keys(EVERYDAY_SECTIONS).forEach(function (type) {
            EVERYDAY_SECTIONS[type].style.display = visibleTypes[type] ? '' : 'none';
        });
        document.getElementById('everyday-list').style.display =
            (visibleTypes.workflow || visibleTypes.job) ? '' : 'none';
        renderSummary();
        cal.refetchEvents();
    }

    // Both types are shown by default; each toggle independently adds or removes one.
    function renderTypeToggles() {
        var container = document.getElementById('type-toggles');
        var label = document.createElement('span');
        label.className = 'type-toggles-label';
        label.textContent = 'Show:';
        container.appendChild(label);
        [['workflow', 'Workflows'], ['job', 'Jobs']].forEach(function (entry) {
            var type = entry[0];
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'filter-chip type-toggle on';
            btn.textContent = entry[1];
            btn.setAttribute('aria-pressed', 'true');
            btn.onclick = function () {
                visibleTypes[type] = !visibleTypes[type];
                btn.classList.toggle('on', visibleTypes[type]);
                btn.setAttribute('aria-pressed', String(visibleTypes[type]));
                applyTypeVisibility();
            };
            container.appendChild(btn);
        });
    }

    renderSummary();
    renderFilters();
    renderTypeToggles();

    var searchBox = document.getElementById('search-box');
    var everydayCards = document.querySelectorAll('#everyday-list .workflow-card');

    searchBox.addEventListener('input', function () {
        searchQuery = searchBox.value.trim().toLowerCase();
        cal.refetchEvents();
        everydayCards.forEach(function (card) {
            card.style.display = card.dataset.wfname.includes(searchQuery) ? '' : 'none';
        });
    });
}());
</script>
"""
    state_colors = {
        state: execution_state_color(state)
        for state in ("succeeded", "failed", "running", "cancelled", "scheduled")
    }
    return script.replace("__CALENDAR_TIME_ZONE__", calendar_time_zone).replace(
        "__STATE_COLORS__", json.dumps(state_colors)
    )


def build_html(
    calendar_events, everyday_cards_html, everyday_job_cards_html, job_id, generated_at=""
):
    events_json = json.dumps(calendar_events)
    # Prevent </script> from terminating the enclosing script tag.
    escaped_events_json = events_json.replace("</", "<\\/")
    escaped_job_id = html_lib.escape(str(job_id), quote=True)
    escaped_generated_at = html_lib.escape(generated_at)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Civis Workflow and Job Schedules</title>
    <link href="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.8/index.global.min.css"
     rel="stylesheet" />
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap"
     rel="stylesheet" />
    {build_html_styles()}
</head>
<body>

<header id="page-header">
    <h1>Scheduled Workflows and Jobs</h1>
    <p class="subtitle">Run history and upcoming schedule &middot; last {LOOKBACK_DAYS} days
        &middot; updated {escaped_generated_at}</p>
</header>

<div id="summary-tiles"></div>

<details id="explanation">
    <summary>About this report</summary>
    <p>The calendar shows the actual runs (status and runtime) of all non-archived
    Civis workflows, scheduled or not, and of scheduled jobs, plus their upcoming
    scheduled runs. Use <b>Show</b> to turn workflows or jobs on and off, and the status
    chips to highlight one status. Switch between <b>Month</b>, <b>Week</b> and
    <b>Day</b> views and use the arrows to look back. Click a run for details, including
    which task failed and why, with links back to platform. Items scheduled to run
    <em>every</em> day are left out of the month grid (they are listed below it) but
    appear in the week and day views.</p>
    <p>Platform does not record a time zone for job schedules, so upcoming job runs are
    projected in {html_lib.escape(DISPLAY_TIME_ZONE)}. Past runs are always accurate.</p>
    <p><b>Refreshing this report:</b> navigate to
    <a href="https://platform.civisanalytics.com/spa/#/scripts/python3/{escaped_job_id}"
     target="_blank" rel="noopener noreferrer">this script</a>
    and click the blue <b>Run</b> button.</p>
</details>

<div id="controls">
    <input type="text" id="search-box" aria-label="Search workflows and jobs by name" placeholder="Search workflows and jobs by name..." />
    <div id="type-toggles" class="type-toggles" role="group" aria-label="Show"></div>
    <div id="status-filters"></div>
</div>

<div id="calendar"></div>

<div id="event-modal">
    <div class="modal-content" id="event-modal-content" role="dialog" aria-modal="true" tabindex="-1"></div>
</div>

<div id="everyday-list">
    <section id="everyday-workflows-section" class="everyday-section">
        <h2>Workflows Scheduled Every Day</h2>
        <div id="everyday-workflows-container">
            {everyday_cards_html}
        </div>
    </section>
    <section id="everyday-jobs-section" class="everyday-section">
        <h2>Jobs Scheduled Every Day</h2>
        <div id="everyday-jobs-container">
            {everyday_job_cards_html}
        </div>
    </section>
</div>

<script type="application/json" id="events-data">{escaped_events_json}</script>
<script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.8/index.global.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/luxon@3.4.4/build/global/luxon.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@fullcalendar/luxon3@6.1.8/index.global.min.js"></script>
{build_client_script(calendar_time_zone=DISPLAY_TIME_ZONE)}

</body>
</html>"""


def is_everyday(item):
    return item["scheduled"] and set(item["scheduled_days"]) == set(EVERYDAY_SCHEDULED_DAYS)


def log_progress(label, index, total):
    if index % 25 == 0 or index == total:
        print(f"Loaded run history for {index}/{total} {label}")


def main():
    import civis

    client = civis.APIClient()

    normalized_workflows = [
        normalize_workflow(wf)
        for wf in fetch_all_workflows(client)
        if not wf.get("archived", False)
    ]
    normalized_jobs = [normalize_job(job) for job in fetch_all_scheduled_jobs(client)]

    everyday_workflows = [ws for ws in normalized_workflows if is_everyday(ws)]
    everyday_jobs = [job for job in normalized_jobs if is_everyday(job)]

    now = datetime.now(timezone.utc)
    window_start_utc = now - timedelta(days=LOOKBACK_DAYS)
    window_end_utc = now + timedelta(days=1)
    range_start = window_start_utc.date()
    range_end = (now + timedelta(days=FORWARD_DAYS)).date()

    item_executions = {}
    for index, workflow in enumerate(normalized_workflows, start=1):
        executions = fetch_workflow_executions(
            client,
            workflow["id"],
            window_start_utc,
            window_end_utc,
        )
        for execution in executions:
            if execution["state"] not in FAILURE_STATES:
                continue
            try:
                execution["tasks"] = fetch_execution_tasks(client, workflow["id"], execution["id"])
            except Exception as err:  # keep the report usable if one lookup fails
                print(f"Could not load tasks for execution {execution['id']}: {err}")
        item_executions[("workflow", workflow["id"])] = executions
        log_progress("workflows", index, len(normalized_workflows))

    for index, job in enumerate(normalized_jobs, start=1):
        item_executions[("job", job["id"])] = fetch_job_runs(
            client,
            job["id"],
            window_start_utc,
            window_end_utc,
        )
        log_progress("jobs", index, len(normalized_jobs))

    # Reuse state from the list calls for the "most recent run" on the everyday cards.
    everyday_workflow_states = {ws["id"]: normalize_execution_state(ws) for ws in everyday_workflows}
    everyday_job_states = {
        job["id"]: normalize_execution_state(job) if job["state"] else "not run"
        for job in everyday_jobs
    }

    calendar_events = build_calendar_events(
        normalized_workflows + normalized_jobs,
        item_executions,
        range_start,
        range_end,
        now,
    )
    everyday_cards_html = build_everyday_cards(
        everyday_workflows,
        most_recent_states=everyday_workflow_states,
    )
    everyday_job_cards_html = build_everyday_cards(
        everyday_jobs,
        most_recent_states=everyday_job_states,
    )
    job_id = os.environ.get("CIVIS_JOB_ID", "")
    html = build_html(
        calendar_events,
        everyday_cards_html,
        everyday_job_cards_html,
        job_id,
        generated_at=now.astimezone(DISPLAY_ZONEINFO).strftime("%Y-%m-%d %H:%M %Z"),
    )

    report_name = "Scheduled Workflows and Jobs"
    report_description = (
        "Interactive calendar of non-archived Civis workflows and scheduled jobs, "
        "with run history and upcoming schedules."
    )
    report_id = os.environ.get("REPORT_ID")

    if report_id:
        report = client.reports.patch(
            id=int(report_id),
            name=report_name,
            description=report_description,
            code_body=html,
        )
    else:
        report = client.reports.post(
            name=report_name,
            description=report_description,
            code_body=html,
        )
        client.scripts.patch_python3(
            id=int(os.environ["CIVIS_JOB_ID"]),
            params=[{"name": "REPORT_ID", "type": "string", "required": False}],
            arguments={"REPORT_ID": int(report.id)},
        )

    report_url = f"https://platform.civisanalytics.com/spa/#/reports/{report['id']}?fullscreen=true"
    print(f"Civis report URL: {report_url}")


if __name__ == "__main__":
    main()
