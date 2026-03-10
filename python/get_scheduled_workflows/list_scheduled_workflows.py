import civis
import calendar
import os
from datetime import datetime, timedelta
import json

# ---------------------------------------------------------------------------
# Civis API client
# ---------------------------------------------------------------------------
client = civis.APIClient()

# ---------------------------------------------------------------------------
# Fetch all workflows (paginated)
# ---------------------------------------------------------------------------
def fetch_all_workflows(client):
    workflows, page = [], 1
    while True:
        page_workflows = client.workflows.list(page_num=page)
        if not page_workflows:
            break
        workflows.extend(page_workflows)
        page += 1
    return workflows

# ---------------------------------------------------------------------------
# Parse schedule into a human-readable string
# ---------------------------------------------------------------------------
def schedule_to_string(ws):
    DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    parts = []
    days          = ws.get('scheduled_days', [])
    hours         = ws.get('scheduled_hours', [])
    minutes       = ws.get('scheduled_minutes', [])
    days_of_month = ws.get('scheduled_days_of_month', [])

    if days:
        parts.append("Days: " + ', '.join(DAY_NAMES[d] for d in days if 0 <= d <= 6))
    if days_of_month:
        parts.append("Days of month: " + ', '.join(str(d) for d in days_of_month))
    if hours:
        parts.append("Hours (UTC): " + ', '.join(str(h) for h in hours))
    if minutes:
        parts.append("Minutes: " + ', '.join(str(m) for m in minutes))
    return '; '.join(parts) if parts else 'N/A'

# ---------------------------------------------------------------------------
# Build calendar events for FullCalendar
# ---------------------------------------------------------------------------
def build_calendar_events(workflows, year, month):
    month_days = [
        d for d in calendar.Calendar().itermonthdates(year, month)
        if d.month == month
    ]
    events = []
    for ws in workflows:
        workflow_url = f"https://platform.civisanalytics.com/spa/#/workflows/{ws['id']}"
        tooltip = (
            f"<b>Name:</b> <a href='{workflow_url}' target='_blank'>{ws['name']}</a><br/>"
            f"<b>Workflow ID:</b> {ws['id']}<br/>"
            f"<b>Schedule:</b> {schedule_to_string(ws)}<br/>"
            f"<b>Time zone:</b> {ws.get('time_zone') or 'UTC'}<br/>"
            f"<b>Created:</b> {ws.get('created_at', '')}<br/>"
            f"<b>Next run:</b> {ws.get('next_execution_at', '')}<br/>"
            f"<a href='{workflow_url}' target='_blank'>Open in Civis →</a>"
        )
        scheduled_days = ws.get('scheduled_days', [])
        days_of_month  = ws.get('scheduled_days_of_month', [])
        hours          = ws.get('scheduled_hours') or [0]
        minutes        = ws.get('scheduled_minutes') or [0]

        if scheduled_days:
            for day in month_days:
                civis_weekday = (day.weekday() + 1) % 7  # Civis: 0=Sun
                if civis_weekday in scheduled_days:
                    for h in hours:
                        for m in minutes:
                            event_time = datetime.combine(day, datetime.min.time()) + timedelta(hours=h, minutes=m)
                            events.append({
                                'title': ws['name'],
                                'start': event_time.strftime('%Y-%m-%dT%H:%M:%S'),
                                'description': tooltip,
                                'url': workflow_url,
                            })
        elif days_of_month:
            for dom in days_of_month:
                try:
                    event_date = datetime(year, month, dom)
                except ValueError:
                    continue
                for h in hours:
                    for m in minutes:
                        event_time = event_date + timedelta(hours=h, minutes=m)
                        events.append({
                            'title': ws['name'],
                            'start': event_time.strftime('%Y-%m-%dT%H:%M:%S'),
                            'description': tooltip,
                            'url': workflow_url,
                        })
    return events

# ---------------------------------------------------------------------------
# Build everyday workflow cards HTML
# ---------------------------------------------------------------------------
def build_everyday_cards(everyday_workflows):
    cards = []
    for ws in everyday_workflows:
        workflow_url = f"https://platform.civisanalytics.com/spa/#/workflows/{ws['id']}"
        cards.append(
            f"<div class='workflow-card' data-wfname=\"{ws['name'].lower()}\">"
            f"  <div><b>Name:</b> <a href='{workflow_url}' target='_blank'>{ws['name']}</a></div>"
            f"  <div class='workflow-meta'><b>Schedule:</b> {schedule_to_string(ws)}</div>"
            f"  <div class='workflow-meta'><b>Created:</b> {ws.get('created_at', '')}</div>"
            f"</div>"
        )
    return '\n'.join(cards)

# ---------------------------------------------------------------------------
# Build the full HTML report
# ---------------------------------------------------------------------------
def build_html(calendar_events, everyday_cards_html, job_id):
    events_json = json.dumps(calendar_events)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Civis Workflow Schedules</title>

    <!--
        CSS loads first to prevent flash of unstyled content.
        FullCalendar JS is deferred to end of <body> so the DOM is ready when it runs,
        which avoids the calendar rendering before its container has dimensions.
    -->
    <link href="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.8/index.global.min.css" rel="stylesheet" />
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet" />

    <style>
        *, *::before, *::after {{ box-sizing: border-box; }}

        body {{
            font-family: 'Roboto', Arial, sans-serif;
            background: #f4f6fa;
            color: #222;
            margin: 0;
            padding: 0 0 60px;
        }}
        h1 {{
            text-align: center;
            margin: 30px 0 0;
            font-size: 2.2em;
            color: #2a4d69;
            letter-spacing: 1px;
        }}

        /* Explanation banner */
        #explanation {{
            max-width: 900px;
            margin: 24px auto 0;
            background: #eaf1fb;
            border-radius: 8px;
            padding: 16px 24px;
            font-size: 1.05em;
            color: #234;
            box-shadow: 0 1px 6px rgba(42,77,105,0.06);
            line-height: 1.6;
        }}

        /* Search box */
        #search-box {{
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
        }}
        #search-box:focus {{
            border-color: #2a4d69;
            box-shadow: 0 0 0 2px rgba(42,77,105,0.15);
        }}

        /* Calendar container */
        #calendar {{
            max-width: 1000px;
            margin: 32px auto 0;
            padding: 16px;
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(42,77,105,0.08);
        }}
        .fc-event {{ cursor: pointer; }}

        /* Tooltip — uses position:fixed to avoid scroll-offset bugs */
        .wf-tooltip {{
            position: fixed;
            background: #fff;
            border: 1px solid #ccc;
            padding: 10px 14px;
            display: none;
            z-index: 1500;
            box-shadow: 0 2px 10px rgba(42,77,105,0.15);
            border-radius: 8px;
            font-size: 0.92em;
            max-width: 320px;
            pointer-events: none;
            line-height: 1.6;
        }}

        /* Everyday-workflows section */
        #everyday-list {{
            max-width: 1000px;
            margin: 40px auto 0;
            padding: 24px;
            background: #fff;
            border: 1px solid #e0e6ed;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(42,77,105,0.06);
        }}
        #everyday-list h2 {{
            text-align: center;
            color: #2a4d69;
            margin: 0 0 20px;
        }}
        .workflow-card {{
            background: #f9fafc;
            border: 1px solid #e0e6ed;
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 14px;
            box-shadow: 0 1px 4px rgba(42,77,105,0.04);
        }}
        .workflow-card a {{
            color: #20639b;
            text-decoration: none;
            font-weight: 500;
        }}
        .workflow-card a:hover {{ text-decoration: underline; }}
        .workflow-meta {{
            font-size: 0.95em;
            color: #555;
            margin-top: 4px;
        }}

        /* Modal */
        #event-modal {{
            display: none;
            position: fixed;
            inset: 0;
            z-index: 2000;
            background: rgba(0,0,0,0.35);
            overflow-y: auto;
        }}
        .modal-content {{
            background: #fff;
            border-radius: 10px;
            max-width: 600px;
            margin: 60px auto;
            padding: 32px 28px 24px;
            box-shadow: 0 4px 24px rgba(42,77,105,0.18);
            position: relative;
        }}
        .modal-content h3 {{
            margin-top: 0;
            color: #2a4d69;
        }}
        .modal-content ul {{ padding-left: 18px; }}
        .close-btn {{
            position: absolute;
            top: 12px;
            right: 18px;
            font-size: 1.5em;
            color: #888;
            cursor: pointer;
            line-height: 1;
        }}
        .close-btn:hover {{ color: #2a4d69; }}
    </style>
</head>
<body>

<h1>Civis Workflow Schedules Calendar</h1>

<div id="explanation">
    <b>What's in this report?</b><br>
    The calendar shows all non-archived, scheduled Civis workflows that run on specific days of
    the week or month. Workflows scheduled to run <em>every</em> day are listed separately below
    the calendar. Use the search box to filter by name in both views.<br><br>
    <b>Refreshing this report:</b>
    Navigate to <a href="https://platform.civisanalytics.com/spa/#/scripts/python3/{job_id}" target="_blank">this script</a>
    and click the blue <b>Run</b> button.
</div>

<input type="text" id="search-box" placeholder="Search workflows by name…" />

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

<script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.8/index.global.min.js"></script>
<script>
(function () {{
    var ALL_EVENTS = {events_json};

    // Single shared tooltip element
    var tooltip = document.createElement('div');
    tooltip.className = 'wf-tooltip';
    document.body.appendChild(tooltip);

    function showTooltip(e, html) {{
        tooltip.innerHTML = html;
        tooltip.style.display = 'block';
        positionTooltip(e);
    }}
    function positionTooltip(e) {{
        var x = e.clientX + 12, y = e.clientY + 12;
        if (x + 340 > window.innerWidth)  x = e.clientX - 350;
        if (y + 220 > window.innerHeight) y = e.clientY - 230;
        tooltip.style.left = x + 'px';
        tooltip.style.top  = y + 'px';
    }}
    function hideTooltip() {{ tooltip.style.display = 'none'; }}

    var cal = new FullCalendar.Calendar(document.getElementById('calendar'), {{
        initialView: 'dayGridMonth',
        height: 'auto',
        events: ALL_EVENTS,
        dayMaxEvents: true,

        eventDidMount: function (info) {{
            var desc = info.event.extendedProps.description || '';
            info.el.addEventListener('mouseenter', function (e) {{ showTooltip(e, desc); }});
            info.el.addEventListener('mousemove',  positionTooltip);
            info.el.addEventListener('mouseleave', hideTooltip);
        }},

        moreLinkClick: function (arg) {{
            var dateStr = arg.date ? arg.date.toISOString().slice(0, 10) : '';
            var body    = '<h3>Workflows on ' + dateStr + '</h3><ul>';
            (arg.allSegs || []).forEach(function (seg) {{
                var ev   = seg.event;
                var desc = (ev.extendedProps && ev.extendedProps.description) || '';
                body += '<li><b>' + ev.title + '</b><br><span style="font-size:0.95em">' + desc + '</span></li>';
            }});
            body += '</ul><span class="close-btn" id="modal-close">&times;</span>';

            var modal   = document.getElementById('event-modal');
            var content = document.getElementById('event-modal-content');
            content.innerHTML = body;
            modal.style.display = 'block';
            document.getElementById('modal-close').onclick = function () {{ modal.style.display = 'none'; }};
            modal.onclick = function (e) {{ if (e.target === modal) modal.style.display = 'none'; }};
            return false;
        }}
    }});
    cal.render();

    // Search
    var searchBox     = document.getElementById('search-box');
    var everydayCards = document.querySelectorAll('#everyday-workflows-container .workflow-card');

    searchBox.addEventListener('input', function () {{
        var q = searchBox.value.trim().toLowerCase();
        cal.getEvents().forEach(function (ev) {{ ev.remove(); }});
        ALL_EVENTS.forEach(function (ev) {{
            if (ev.title.toLowerCase().includes(q)) cal.addEvent(ev);
        }});
        everydayCards.forEach(function (card) {{
            card.style.display = card.dataset.wfname.includes(q) ? '' : 'none';
        }});
    }});
}());
</script>

</body>
</html>"""

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
all_workflows = fetch_all_workflows(client)

active_scheduled = [
    wf for wf in all_workflows
    if not wf.get('archived', False)
    and wf.get('schedule', {}).get('scheduled', False)
][:100]

workflow_schedules = []
for wf in active_scheduled:
    sched = wf.get('schedule', {})
    workflow_schedules.append({
        'id':                      wf['id'],
        'name':                    wf['name'],
        'scheduled':               sched.get('scheduled', False),
        'scheduled_days':          sched.get('scheduled_days', []),
        'scheduled_hours':         sched.get('scheduled_hours', []),
        'scheduled_minutes':       sched.get('scheduled_minutes', []),
        'scheduled_days_of_month': sched.get('scheduled_days_of_month', []),
        'created_at':              wf.get('created_at', ''),
        'next_execution_at':       wf.get('next_execution_at', ''),
        'time_zone':               wf.get('time_zone', ''),
    })

everyday_workflows = [ws for ws in workflow_schedules if sorted(ws['scheduled_days']) == list(range(7))]
main_workflows     = [ws for ws in workflow_schedules if sorted(ws['scheduled_days']) != list(range(7))]

now   = datetime.utcnow()
year  = now.year
month = now.month

calendar_events     = build_calendar_events(main_workflows, year, month)
everyday_cards_html = build_everyday_cards(everyday_workflows)
job_id              = os.environ.get("CIVIS_JOB_ID", "")
html                = build_html(calendar_events, everyday_cards_html, job_id)

with open("workflow_schedules_report.html", "w") as f:
    f.write(html)

report_name        = "Civis Workflow Schedules Calendar"
report_description = "Interactive calendar of non-archived Civis workflows and their schedules."
report_id          = os.environ.get("REPORT_ID")

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
        arguments={"REPORT_ID": int(report.id)},
    )

print(f"Report saved locally: workflow_schedules_report.html")
print(f"Civis report ID: {report['id']}")
