# This script fetches all Jobs that the runner has at least viewer access on,
# and fetches the permission (sharing) and notification settings for each job.
# Results are saved in a Pandas dataframe, then written to a Civis database table.

import civis
import pandas as pd

_LOG = civis.civis_logger()
client = civis.APIClient()

DATABASE = "Civis Database"
TABLE = "scratch.jobs"

TYPE_TO_SHARES = {
    "JobTypes::PythonDocker": ("scripts", "list_python3_shares"),
    "JobTypes::RDocker": ("scripts", "list_r_shares"),
    "JobTypes::ContainerDocker": ("scripts", "list_containers_shares"),
    "JobTypes::SqlRunner": ("scripts", "list_sql_shares"),
    "JobTypes::Import": ("imports", "list_shares"),
    "JobTypes::IdentityResolution": ("match_targets", "list_shares"),
}

TYPE_TO_DETAIL = {
    "JobTypes::PythonDocker": ("scripts", "get_python3"),
    "JobTypes::RDocker": ("scripts", "get_r"),
    "JobTypes::ContainerDocker": ("scripts", "get_containers"),
    "JobTypes::SqlRunner": ("scripts", "get_sql"),
    "JobTypes::Import": ("imports", "get"),
    "JobTypes::IdentityResolution": ("match_targets", "get"),
}


def get_shares(job_id, job_type):
    """Return (shares, notifications) for the given job, or (None, None) for unsupported types."""
    if job_type not in TYPE_TO_SHARES:
        return None, None

    resource_name, shares_method = TYPE_TO_SHARES[job_type]
    resource = getattr(client, resource_name)

    shares = None
    try:
        shares = getattr(resource, shares_method)(job_id)
    except Exception as e:
        _LOG.warning("Could not fetch shares for job %d (%s): %s", job_id, job_type, e)

    notifications = None
    if job_type in TYPE_TO_DETAIL:
        detail_method = TYPE_TO_DETAIL[job_type][1]
        try:
            detail = getattr(resource, detail_method)(job_id)
            notifications = detail.notifications
        except Exception as e:
            _LOG.warning("Could not fetch notifications for job %d (%s): %s", job_id, job_type, e)

    return shares, notifications


def extract_names(obj, permission_level, kind):
    """Extract a list of names from a shares response for a given level (readers/writers/owners) and kind (users/groups)."""
    if obj is None:
        return None
    level = getattr(obj, permission_level, None)
    if level is None:
        return None
    items = getattr(level, kind, None)
    if not items:
        return None
    return str([i.name for i in items])


_LOG.info("Fetching jobs from API...")
jobs_iterator = client.jobs.list(iterator=True)

rows = []
for j in jobs_iterator:
    shares, notifications = get_shares(j.id, j.type)

    rows.append(
        {
            # --- Top-level fields ---
            "id": j.id,
            "name": j.name,
            "type": j.type,
            "from_template_id": j.from_template_id,
            "state": j.state,
            "created_at": j.created_at,
            "updated_at": j.updated_at,
            "archived": j.archived,
            # --- author ---
            "author_id": j.author.id if j.author else None,
            "author_name": j.author.name if j.author else None,
            "author_username": j.author.username if j.author else None,
            "author_initials": j.author.initials if j.author else None,
            "author_online": j.author.online if j.author else None,
            # --- last_run ---
            "last_run_id": j.last_run.id if j.last_run else None,
            "last_run_state": j.last_run.state if j.last_run else None,
            "last_run_created_at": j.last_run.created_at if j.last_run else None,
            "last_run_started_at": j.last_run.started_at if j.last_run else None,
            "last_run_finished_at": j.last_run.finished_at if j.last_run else None,
            "last_run_error": j.last_run.error if j.last_run else None,
            # --- schedule ---
            "scheduled": j.schedule.scheduled if j.schedule else None,
            "scheduled_days": str(j.schedule.scheduled_days) if j.schedule else None,
            "scheduled_hours": str(j.schedule.scheduled_hours) if j.schedule else None,
            "scheduled_minutes": (
                str(j.schedule.scheduled_minutes) if j.schedule else None
            ),
            "scheduled_runs_per_hour": (
                j.schedule.scheduled_runs_per_hour if j.schedule else None
            ),
            "scheduled_days_of_month": (
                str(j.schedule.scheduled_days_of_month) if j.schedule else None
            ),
            # --- shares ---
            "reader_users": extract_names(shares, "readers", "users"),
            "reader_groups": extract_names(shares, "readers", "groups"),
            "writer_users": extract_names(shares, "writers", "users"),
            "writer_groups": extract_names(shares, "writers", "groups"),
            "owner_users": extract_names(shares, "owners", "users"),
            "owner_groups": extract_names(shares, "owners", "groups"),
            # --- notifications ---
            "notification_urls": str(notifications.urls) if notifications and notifications.urls else None,
            "success_email_subject": notifications.success_email_subject if notifications else None,
            "success_email_body": notifications.success_email_body if notifications else None,
            "success_email_addresses": str(notifications.success_email_addresses) if notifications and notifications.success_email_addresses else None,
            "success_email_from_name": notifications.success_email_from_name if notifications else None,
            "failure_email_addresses": str(notifications.failure_email_addresses) if notifications and notifications.failure_email_addresses else None,
        }
    )

df = pd.DataFrame(rows)
_LOG.info(
    "Loaded %d jobs with share and notification data. Writing to %s.%s...", len(df), DATABASE, TABLE
)

fut = civis.io.dataframe_to_civis(
    df,
    database=DATABASE,
    table=TABLE,
    existing_table_rows="drop",
)
fut.result()
_LOG.info("Done.")
