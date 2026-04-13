import calendar
import html as html_lib
import os
from datetime import datetime, timedelta, timezone
import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
EVERYDAY_SCHEDULED_DAYS = list(range(7))


# ---------------------------------------------------------------------------
# Fetch all workflows (paginated)
# ---------------------------------------------------------------------------
def fetch_all_workflows(client):
    workflows, page = [], 1
    while True:
        page_workflows = client.workflows.list(page_num=page, scheduled=True)
        if not page_workflows:
            break
        workflows.extend(page_workflows)
        page += 1
    return workflows


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


def normalize_workflow(workflow):
    schedule = workflow.get("schedule", {})
    normalized = {
        "id": workflow["id"],
        "name": str(workflow.get("name", "")),
        "scheduled": bool(schedule.get("scheduled", False)),
        "scheduled_days": normalize_schedule_values(
            schedule.get("scheduled_days", []),
            0,
            6,
        ),
        "scheduled_hours": normalize_schedule_values(
            schedule.get("scheduled_hours", []),
            0,
            23,
        ),
        "scheduled_minutes": normalize_schedule_values(
            schedule.get("scheduled_minutes", []),
            0,
            59,
        ),
        "scheduled_days_of_month": normalize_schedule_values(
            schedule.get("scheduled_days_of_month", []),
            1,
            31,
        ),
        "created_at": str(workflow.get("created_at", "")),
        "next_execution_at": str(workflow.get("next_execution_at", "")),
        "time_zone": getattr(get_workflow_zoneinfo(workflow), "key", "UTC"),
        "state": str(workflow.get("state", "")),
    }
    return normalized


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
    return {
        "id": execution.get("id"),
        "state": normalize_execution_state(execution),
        "reference_at": execution_reference_time(execution),
        "started_at": str(execution.get("started_at", "") or ""),
        "finished_at": str(execution.get("finished_at", "") or ""),
        "created_at": str(execution.get("created_at", "") or ""),
    }


def workflow_occurrence_times(ws, year, month):
    month_days = [d for d in calendar.Calendar().itermonthdates(year, month) if d.month == month]
    tzinfo = get_workflow_zoneinfo(ws)
    scheduled_days = set(ws.get("scheduled_days", []))
    days_of_month = ws.get("scheduled_days_of_month", [])
    occurrences = []

    if scheduled_days:
        for day in month_days:
            civis_weekday = (day.weekday() + 1) % 7  # Civis: 0=Sun
            if civis_weekday in scheduled_days:
                for hour, minute in event_time_pairs(ws):
                    occurrences.append(
                        datetime(
                            day.year,
                            day.month,
                            day.day,
                            hour,
                            minute,
                            tzinfo=tzinfo,
                        )
                    )
    elif days_of_month:
        for dom in days_of_month:
            try:
                event_date = datetime(year, month, dom, tzinfo=tzinfo)
            except ValueError:
                continue
            for hour, minute in event_time_pairs(ws):
                occurrences.append(event_date + timedelta(hours=hour, minutes=minute))

    return sorted(occurrences)


def workflow_execution_fetch_window(occurrence_times):
    if not occurrence_times:
        return None, None
    start_utc = occurrence_times[0].astimezone(timezone.utc) - timedelta(minutes=30)
    end_utc = occurrence_times[-1].astimezone(timezone.utc) + timedelta(days=2)
    return start_utc, end_utc


def fetch_workflow_executions(client, workflow_id, window_start_utc, window_end_utc):
    if window_start_utc is None or window_end_utc is None:
        return []

    executions = []
    page_num = 1
    limit = 50
    while True:
        # Keep paging only until executions are older than the month window
        # needed for the current calendar view.
        page = client.workflows.list_executions(
            workflow_id,
            limit=limit,
            page_num=page_num,
            order="created_at",
            order_dir="desc",
        )
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


def match_executions_to_occurrences(occurrence_times, executions, now_utc):
    matched = [None] * len(occurrence_times)
    occurrence_times_utc = [occurrence.astimezone(timezone.utc) for occurrence in occurrence_times]
    grace_period = timedelta(minutes=30)

    # Attribute each execution to the most recent scheduled slot before it,
    # while leaving future occurrences uncolored until they actually run.
    for execution in sorted(
        executions,
        key=lambda item: item["reference_at"] or datetime.min.replace(tzinfo=timezone.utc),
    ):  # W503
        reference_at = execution.get("reference_at")
        if reference_at is None:
            continue
        target_index = -1
        for index, occurrence_utc in enumerate(occurrence_times_utc):
            if occurrence_utc <= reference_at + grace_period:
                target_index = index
            else:
                break
        if target_index < 0:
            continue

        next_occurrence_utc = (
            occurrence_times_utc[target_index + 1]
            if target_index + 1 < len(occurrence_times_utc)
            else occurrence_times_utc[target_index] + timedelta(days=2)
        )
        if reference_at >= next_occurrence_utc:
            continue
        if occurrence_times_utc[target_index] > now_utc:
            continue
        matched[target_index] = execution

    return matched


def workflow_event_metadata(ws, event_state, matched_execution):
    workflow_url = f"https://platform.civisanalytics.com/spa/#/workflows/{ws['id']}"
    return {
        "workflowId": ws["id"],
        "workflowUrl": workflow_url,
        "url": workflow_url,
        "scheduleText": schedule_to_string(ws),
        "timeZone": ws.get("time_zone", "UTC"),
        "createdAt": ws.get("created_at", ""),
        "nextExecutionAt": ws.get("next_execution_at", ""),
        "state": event_state,
        "matchedExecutionStartedAt": (
            matched_execution.get("started_at", "") if matched_execution else ""
        ),
        "matchedExecutionFinishedAt": (
            matched_execution.get("finished_at", "") if matched_execution else ""
        ),
    }


# ---------------------------------------------------------------------------
# Build calendar events for FullCalendar
# ---------------------------------------------------------------------------
def build_calendar_events(workflows, year, month, workflow_executions=None, now_utc=None):
    workflow_executions = workflow_executions or {}
    now_utc = now_utc or datetime.now(timezone.utc)
    events = []
    for ws in workflows:
        occurrence_times = workflow_occurrence_times(ws, year, month)
        matched_executions = match_executions_to_occurrences(
            occurrence_times,
            workflow_executions.get(ws["id"], []),
            now_utc,
        )

        for occurrence_time, matched_execution in zip(
            occurrence_times,
            matched_executions,
        ):
            occurrence_time_utc = occurrence_time.astimezone(timezone.utc)
            event_state = (
                matched_execution["state"]
                if matched_execution is not None and occurrence_time_utc <= now_utc
                else "scheduled"
            )
            events.append(
                {
                    "title": ws["name"],
                    "start": occurrence_time.isoformat(),
                    "color": execution_state_color(event_state),
                    **workflow_event_metadata(ws, event_state, matched_execution),
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
        workflow_url = html_lib.escape(
            f"https://platform.civisanalytics.com/spa/#/workflows/{ws.get('id', '')}"
        )
        workflow_name_lower = html_lib.escape(workflow_name.lower(), quote=True)
        workflow_name_html = html_lib.escape(workflow_name)
        schedule_html = html_lib.escape(schedule_to_string(ws))
        created_at_html = html_lib.escape(str(ws.get("created_at", "")))
        most_recent_state = most_recent_states.get(ws["id"], "not run")
        state_color = execution_state_color(most_recent_state)
        state_label_html = html_lib.escape(format_execution_state_label(most_recent_state))
        cards.append(
            f"<div class='workflow-card' data-wfname=\"{workflow_name_lower}\">"
            f"  <div><b>Name:</b> <a href='{workflow_url}' target='_blank' "
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
        h1 {
            text-align: center;
            margin: 30px 0 0;
            font-size: 2.2em;
            color: #2a4d69;
            letter-spacing: 1px;
        }

        #explanation {
            max-width: 900px;
            margin: 24px auto 0;
            background: #eaf1fb;
            border-radius: 8px;
            padding: 16px 24px;
            font-size: 1.05em;
            color: #234;
            box-shadow: 0 1px 6px rgba(42,77,105,0.06);
            line-height: 1.6;
        }

        #search-box {
            display: block;
            margin: 24px auto 0;
            max-width: 400px;
            width: 100%;
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
            margin: 32px auto 0;
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
            max-width: 600px;
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
        .close-btn {
            position: absolute;
            top: 12px;
            right: 18px;
            font-size: 1.5em;
            color: #888;
            cursor: pointer;
            line-height: 1;
        }
        .close-btn:hover { color: #2a4d69; }
    </style>
    """


def build_client_script(calendar_time_zone="local"):
    return f"""
<script>
(function () {{
    var eventsDataEl = document.getElementById('events-data');
    var ALL_EVENTS = JSON.parse(eventsDataEl ? eventsDataEl.textContent : '[]');

    var tooltip = document.createElement('div');
    tooltip.className = 'wf-tooltip';
    document.body.appendChild(tooltip);

    function escapeHtml(value) {{
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }}

    function safeExternalUrl(value) {{
        if (!value) return '';
        try {{
            var url = new URL(String(value), window.location.origin);
            if (url.protocol === 'http:' || url.protocol === 'https:') return url.toString();
        }} catch (err) {{
            return '';
        }}
        return '';
    }}

    function buildEventHtml(event) {{
        var props = event.extendedProps || {{}};
        var title = escapeHtml(event.title || '');
        var workflowUrl = safeExternalUrl(props.workflowUrl);
        var linkedTitle = workflowUrl
            ? "<a href='" + escapeHtml(workflowUrl) +
             "' target='_blank' rel='noopener noreferrer'>" + title + "</a>"
            : title;
        var lines = [
            '<b>Name:</b> ' + linkedTitle,
            '<b>Workflow ID:</b> ' + escapeHtml(props.workflowId),
            '<b>Schedule:</b> ' + escapeHtml(props.scheduleText),
            '<b>Time zone:</b> ' + escapeHtml(props.timeZone),
            '<b>Created:</b> ' + escapeHtml(props.createdAt),
            '<b>Next run:</b> ' + escapeHtml(props.nextExecutionAt),
            '<b>State:</b> ' + escapeHtml(props.state)
        ];

        if (props.matchedExecutionStartedAt) {{
            lines.push('<b>Matched run started:</b> '
            + escapeHtml(props.matchedExecutionStartedAt));
        }}
        if (props.matchedExecutionFinishedAt) {{
            lines.push('<b>Matched run finished:</b> '
            + escapeHtml(props.matchedExecutionFinishedAt));
        }}

        return lines.join('<br/>');
    }}

    function showTooltip(e, event) {{
        tooltip.innerHTML = buildEventHtml(event);
        tooltip.style.display = 'block';
        positionTooltip(e);
    }}

    function positionTooltip(e) {{
        var x = e.clientX + 12;
        var y = e.clientY + 12;
        if (x + 380 > window.innerWidth) x = e.clientX - 390;
        if (y + 240 > window.innerHeight) y = e.clientY - 250;
        tooltip.style.left = x + 'px';
        tooltip.style.top = y + 'px';
    }}

    function hideTooltip() {{
        tooltip.style.display = 'none';
    }}

    var cal = new FullCalendar.Calendar(document.getElementById('calendar'), {{
        initialView: 'dayGridMonth',
        timeZone: '{calendar_time_zone}',
        height: 'auto',
        events: ALL_EVENTS,
        dayMaxEvents: true,

        eventClick: function (info) {{
            var workflowUrl = safeExternalUrl(info.event.url
             || info.event.extendedProps.workflowUrl);
            if (!workflowUrl) return;
            info.jsEvent.preventDefault();
            window.open(workflowUrl, '_blank', 'noopener');
        }},

        eventDidMount: function (info) {{
            info.el.addEventListener('mouseenter', function (e) {{ showTooltip(e, info.event); }});
            info.el.addEventListener('mousemove', positionTooltip);
            info.el.addEventListener('mouseleave', hideTooltip);
        }},

        moreLinkClick: function (arg) {{
            var dateStr = arg.date ? arg.date.toISOString().slice(0, 10) : '';
            var modal = document.getElementById('event-modal');
            var content = document.getElementById('event-modal-content');
            var heading = document.createElement('h3');
            var list = document.createElement('ul');
            var closeBtn = document.createElement('span');

            content.textContent = '';
            heading.textContent = 'Workflows on ' + dateStr;
            content.appendChild(heading);

            (arg.allSegs || []).forEach(function (seg) {{
                var item = document.createElement('li');
                item.innerHTML = buildEventHtml(seg.event);
                list.appendChild(item);
            }});

            content.appendChild(list);

            closeBtn.className = 'close-btn';
            closeBtn.id = 'modal-close';
            closeBtn.textContent = '×';
            content.appendChild(closeBtn);

            modal.style.display = 'block';
            closeBtn.onclick = function () {{ modal.style.display = 'none'; }};
            modal.onclick = function (e) {{
                if (e.target === modal) modal.style.display = 'none';
            }};
            return false;
        }}
    }});
    cal.render();

    var searchBox = document.getElementById('search-box');
    var everydayCards = document.querySelectorAll('#everyday-workflows-container .workflow-card');

    searchBox.addEventListener('input', function () {{
        var q = searchBox.value.trim().toLowerCase();
        cal.batchRendering(function () {{
            cal.getEvents().forEach(function (ev) {{ ev.remove(); }});
            ALL_EVENTS.forEach(function (ev) {{
                if ((ev.title || '').toLowerCase().includes(q)) cal.addEvent(ev);
            }});
        }});
        everydayCards.forEach(function (card) {{
            card.style.display = card.dataset.wfname.includes(q) ? '' : 'none';
        }});
    }});
}}());
</script>
"""


def build_html(calendar_events, everyday_cards_html, job_id):
    events_json = json.dumps(calendar_events)
    # Prevent </script> from terminating the enclosing script tag.
    escaped_events_json = events_json.replace("</", "<\\/")
    escaped_job_id = html_lib.escape(str(job_id), quote=True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Civis Workflow Schedules</title>
    <link href="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.8/index.global.min.css"
     rel="stylesheet" />
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap"
     rel="stylesheet" />
    {build_html_styles()}
</head>
<body>

<h1>Scheduled Workflows</h1>

<div id="explanation">
    <b>What's in this report?</b><br>
    The calendar shows all non-archived, scheduled Civis workflows that run
    on specific days of the week or month. Workflows scheduled to run
    <em>every</em> day are listed separately below the calendar. Use
    the search box to filter by name in both views and click on any
    workflow name to navigate to it in platform.<br><br>
    <b>Refreshing this report:</b>
    Navigate to
    <a href="https://platform.civisanalytics.com/spa/#/scripts/python3/{escaped_job_id}"
     target="_blank" rel="noopener noreferrer">this script</a>
    and click the blue <b>Run</b> button.
</div>

<input type="text" id="search-box" placeholder="Search workflows by name..." />

<div id="calendar"></div>

<div id="event-modal">
    <div class="modal-content" id="event-modal-content"></div>
</div>

<div id="everyday-list">
    <h2>Workflows Scheduled Every Day</h2>
    <div id="everyday-workflows-container">
        {everyday_cards_html}
    </div>
</div>

<script type="application/json" id="events-data">{escaped_events_json}</script>
<script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.8/index.global.min.js"></script>
{build_client_script(calendar_time_zone="local")}

</body>
</html>"""


def main():
    import civis

    client = civis.APIClient()
    all_workflows = fetch_all_workflows(client)

    normalized_workflows = [
        normalize_workflow(wf)
        for wf in all_workflows
        if not wf.get("archived", False) and wf.get("schedule", {}).get("scheduled", False)
    ]

    everyday_workflows = [
        ws
        for ws in normalized_workflows
        if set(ws["scheduled_days"]) == set(EVERYDAY_SCHEDULED_DAYS)
    ]
    # Keep daily workflows out of the calendar grid so the month view stays readable.
    main_workflows = [
        ws
        for ws in normalized_workflows
        if set(ws["scheduled_days"]) != set(EVERYDAY_SCHEDULED_DAYS)
    ]

    now = datetime.now(timezone.utc)
    year = now.year
    month = now.month

    workflow_executions = {}
    for workflow in main_workflows:
        # Fetch only the executions needed to color the occurrences visible in
        # the current month.
        occurrence_times = workflow_occurrence_times(workflow, year, month)
        window_start_utc, window_end_utc = workflow_execution_fetch_window(occurrence_times)
        workflow_executions[workflow["id"]] = fetch_workflow_executions(
            client,
            workflow["id"],
            window_start_utc,
            window_end_utc,
        )

    # Reuse state from workflows.list to avoid one executions API call per
    # everyday workflow.
    everyday_workflow_states = {
        workflow["id"]: normalize_execution_state(workflow) for workflow in everyday_workflows
    }

    calendar_events = build_calendar_events(
        main_workflows,
        year,
        month,
        workflow_executions=workflow_executions,
        now_utc=now,
    )
    everyday_cards_html = build_everyday_cards(
        everyday_workflows,
        most_recent_states=everyday_workflow_states,
    )
    job_id = os.environ.get("CIVIS_JOB_ID", "")
    html = build_html(calendar_events, everyday_cards_html, job_id)

    report_name = "Scheduled Workflows"
    report_description = "Interactive calendar of non-archived Civis workflows and their schedules."
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
