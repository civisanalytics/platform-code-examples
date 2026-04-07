# This script fetches all Jobs that the runner has at least viewer access on,
# and fetches the permission (sharing) information for each job. Results are saved in a Pandas dataframe,
# then written to a Civis database table.

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


def get_shares(job_id, job_type):
    if job_type not in TYPE_TO_SHARES:
        return None

    resource_name, method_name = TYPE_TO_SHARES[job_type]
    method = getattr(getattr(client, resource_name), method_name)
    try:
        return method(job_id)
    except Exception as e:
        _LOG.warning("Could not fetch shares for job %d (%s): %s", job_id, job_type, e)
        return None


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
    shares = get_shares(j.id, j.type)

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
        }
    )

df = pd.DataFrame(rows)
_LOG.info(
    "Loaded %d jobs with share data. Writing to %s.%s...", len(df), DATABASE, TABLE
)

fut = civis.io.dataframe_to_civis(
    df,
    database=DATABASE,
    table=TABLE,
    existing_table_rows="drop",
)
fut.result()
_LOG.info("Done.")
