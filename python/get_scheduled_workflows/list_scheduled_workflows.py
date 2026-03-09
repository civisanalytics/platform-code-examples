import civis

# Authenticate using your Civis API key (set CIVIS_API_KEY env variable)
client = civis.APIClient()

# Get all workflows (paginated)
workflows = []
page = 1
while True:
    page_workflows = client.workflows.list(page_num=page)
    if not page_workflows:
        break
    workflows.extend(page_workflows)
    page += 1

# Filter non-archived workflows
non_archived = [wf for wf in workflows if not wf.get('archived', False)]


# Collect schedule details for each non-archived workflow
workflow_schedules = []
for wf in non_archived:
    schedules = client.schedules.list(workflow_id=wf['id'])
    for sched in schedules:
        workflow_schedules.append({
            'id': wf['id'],
            'name': wf['name'],
            'schedule_id': sched['id'],
            'active': sched.get('active', False),
            'crontab': sched.get('crontab', ''),
            'next_run_time': sched.get('next_run_time', ''),
            'created_at': sched.get('created_at', ''),
        })

# Generate calendar events for FullCalendar
import json

calendar_events = []
for ws in workflow_schedules:
    # Only add event if next_run_time is available
    if ws['next_run_time']:
        # Tooltip content
        tooltip = f"""
        <b>Name:</b> {ws['name']}<br/>
        <b>Workflow ID:</b> {ws['id']}<br/>
        <b>Schedule ID:</b> {ws['schedule_id']}<br/>
        <b>Active:</b> {'Yes' if ws['active'] else 'No'}<br/>
        <b>Crontab:</b> {ws['crontab']}<br/>
        <b>Created At:</b> {ws['created_at']}<br/>
        <b>Next Run Time:</b> {ws['next_run_time']}<br/>
        """
        calendar_events.append({
            'title': ws['name'],
            'start': ws['next_run_time'],
            'description': tooltip,
        })

html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset='utf-8' />
    <title>Civis Workflow Schedules Calendar</title>
    <link href='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.8/index.global.min.css' rel='stylesheet' />
    <script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.8/index.global.min.js'></script>
    <script src='https://cdn.jsdelivr.net/npm/@popperjs/core@2'></script>
    <style>
        #calendar {{
            max-width: 900px;
            margin: 40px auto;
            padding: 0 10px;
        }}
        .fc-event-title {{
            cursor: pointer;
        }}
    </style>
</head>
<body>
    <h1 style='text-align:center;'>Civis Workflow Schedules Calendar</h1>
    <div id='calendar'></div>
    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            var calendarEl = document.getElementById('calendar');
            var calendar = new FullCalendar.Calendar(calendarEl, {{
                initialView: 'dayGridMonth',
                height: 'auto',
                events: {json.dumps(calendar_events)},
                eventDidMount: function(info) {{
                    var tooltip = document.createElement('div');
                    tooltip.innerHTML = info.event.extendedProps.description;
                    tooltip.style.position = 'absolute';
                    tooltip.style.background = '#fff';
                    tooltip.style.border = '1px solid #ccc';
                    tooltip.style.padding = '8px';
                    tooltip.style.display = 'none';
                    tooltip.style.zIndex = 1000;
                    document.body.appendChild(tooltip);

                    info.el.addEventListener('mouseenter', function(e) {{
                        tooltip.style.display = 'block';
                        tooltip.style.left = (e.pageX + 10) + 'px';
                        tooltip.style.top = (e.pageY + 10) + 'px';
                    }});
                    info.el.addEventListener('mousemove', function(e) {{
                        tooltip.style.left = (e.pageX + 10) + 'px';
                        tooltip.style.top = (e.pageY + 10) + 'px';
                    }});
                    info.el.addEventListener('mouseleave', function() {{
                        tooltip.style.display = 'none';
                    }});
                }}
            }});
            calendar.render();
        }});
    </script>
</body>
</html>
"""

# Save HTML report locally
with open("workflow_schedules_report.html", "w") as f:
    f.write(html)

# Post HTML report to Civis Platform
report_name = "Civis Workflow Schedules Calendar"
report_description = "Interactive calendar of non-archived Civis workflows and their schedules."
report = client.reports.post_html(name=report_name, description=report_description, body=html)
print(f"Calendar-style HTML report generated: workflow_schedules_report.html\nCivis report created: {report['id']}")
