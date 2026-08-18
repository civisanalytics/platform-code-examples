"""Drop tables in a Redshift schema that are older than N days.

TABLE AGE SOURCE
Age is determined entirely via the Civis Platform API's table catalog
(client.tables.get -> schema_updated_at / data_updated_at), the newer of
which is used as a "last touched" date. This is NOT a creation date -- Civis
only knows about a table from whenever it first scanned/refreshed it, and a
table can be touched long after it's created -- but it's a real signal that
doesn't require querying Redshift's own system catalog. If Civis has never
captured either timestamp for a table (e.g. it hasn't scanned the table
yet), that table's age is unknown and it is skipped rather than guessed at --
see the final summary log for a count.

Before reading the table catalog, the script kicks off a Civis Platform
schema scan (client.databases.post_schemas_scan) and waits for it to finish,
so tables created or dropped since Civis's last scheduled scan are reflected.
Then, for every candidate table (after REGEX filtering), it kicks off a
per-table scan (client.tables.post_scan) and waits for that to finish too, so
schema_updated_at / data_updated_at reflect the table's current state rather
than whatever Civis last happened to observe.

Because "last touched" is not a creation date, a table created long ago but
never touched since will show up as "old" and be dropped, while a table
touched recently is protected from being dropped even if it's actually
older than DAYS -- the dry-run output below lists each candidate so it can
be reviewed before setting DRY_RUN=false.

Requires a superuser (or schema-owning) Redshift credential, since it drops
tables outright.

Parameters (env vars):
  SCHEMA        (str, required)  - schema to clean up
  DAYS          (int, required)  - drop tables not touched (per Civis
                                    Platform's schema_updated_at /
                                    data_updated_at) in more than this many
                                    days
  REGEX         (str, optional)  - if set, only tables whose name matches
                                    this regex (re.search) are considered
  DATABASE_ID   (int, required)  - Civis database ID the schema lives in
  CREDENTIAL_ID (int, optional)  - Civis credential ID to run as; defaults
                                    to the account's default database
                                    credential
  DRY_RUN       (bool, optional) - default true. Logs what would be dropped
                                    without dropping anything. Set to
                                    "false" to actually drop tables.
  SKIP_SCANS    (bool, optional)
"""

import os
import re
from datetime import datetime, timezone

import civis
from civis.futures import CivisFuture

logger = civis.civis_logger()


def scan_schema(client, database_id, schema):
    """Trigger a Civis Platform schema scan and wait for it to finish, so
    the table catalog (list_schema_tables) reflects tables that were
    created or dropped outside of Civis's normal refresh cadence."""
    response = client.databases.post_schemas_scan(database_id, schema)
    CivisFuture(
        client.jobs.get_runs, (response.job_id, response.run_id), client=client
    ).result()


def scan_table(client, database_id, schema, table_name):
    """Trigger a Civis Platform scan of a single table and wait for it to
    finish, so its schema_updated_at / data_updated_at reflect the table's
    current state before we use them to judge age."""
    response = client.tables.post_scan(
        database_id=database_id, schema=schema, table_name=table_name
    )
    CivisFuture(
        client.jobs.get_runs, (response.job_id, response.run_id), client=client
    ).result()


def list_schema_tables(client, database_id, schema, credential_id):
    tables = []
    page_num = 1
    while True:
        page = client.tables.list(
            database_id=database_id,
            schema=schema,
            credential_id=credential_id,
            limit=1000,
            page_num=page_num,
        )
        if not page:
            break
        # the API does substring matching on `schema`, so filter to an exact match
        tables.extend(t for t in page if t.schema == schema)
        page_num += 1
    return tables


def civis_last_touched(client, table_id):
    """Newer of Civis's schema_updated_at / data_updated_at for a table, or
    None if Civis has never captured either (e.g. it hasn't scanned the
    table yet)."""
    detail = client.tables.get(table_id)
    candidates = [
        ts
        for ts in (detail.schema_updated_at, detail.data_updated_at)
        if ts is not None
    ]
    if not candidates:
        return None
    return max(datetime.fromisoformat(ts.replace("Z", "+00:00")) for ts in candidates)


def main():
    schema = os.environ["SCHEMA"]
    days = int(os.environ["DAYS"])
    regex = os.getenv("REGEX") or None
    database_id = int(os.environ["DB_ID"])
    credential_id = int(os.environ["DB_CREDENTIAL_ID"])
    dry_run = os.environ["DRY_RUN"] == "true"
    skip_scans = os.environ["SKIP_SCANS"] == "true"

    try:
        pattern = re.compile(regex) if regex else None
    except re.error as exc:
        raise ValueError(f"Invalid REGEX {regex!r}: {exc}") from exc
    cutoff = datetime.now(timezone.utc)

    if dry_run:
        logger.info("DRY_RUN is enabled: no tables will actually be dropped.")

    client = civis.APIClient()
    if skip_scans:
        logger.info("Skip scans option enabled, bypassing schema and table scans")
    else:
        logger.info(f"Scanning schema {schema!r} for up-to-date table metadata...")
        scan_schema(client, database_id, schema)

    tables = list_schema_tables(client, database_id, schema, credential_id)
    logger.info(f"Found {len(tables)} tables/views in schema {schema!r}.")

    to_drop = []
    skipped_unknown_age = []
    for table in tables:
        if table.is_view:
            continue
        if pattern and not pattern.search(table.name):
            continue

        if not skip_scans:
            logger.info(f"Scanning {schema}.{table.name} for up-to-date metadata...")
            scan_table(client, database_id, schema, table.name)

        last_touched = civis_last_touched(client, table.id)
        if last_touched is None:
            skipped_unknown_age.append(table.name)
            continue

        age_days = (cutoff - last_touched).days
        if age_days > days:
            to_drop.append((table, age_days))

    if skipped_unknown_age:
        logger.warning(
            f"Skipping {len(skipped_unknown_age)} table(s) with no last-touched "
            f"value tables API : {', '.join(skipped_unknown_age)}"
        )

    logger.info(f"{len(to_drop)} table(s) are older than {days} day(s):")
    for table, age_days in to_drop:
        logger.info(f"  {schema}.{table.name} (last touched {age_days} days ago)")

    if dry_run:
        logger.info("DRY_RUN is enabled -- exiting without dropping anything.")
        return

    dropped, failed = 0, []
    for table, _ in to_drop:
        full_name = '"{}"."{}"'.format(
            schema.replace('"', '""'), table.name.replace('"', '""')
        )
        try:
            civis.io.query_civis(
                f"DROP TABLE {full_name}",
                database=database_id,
                credential_id=credential_id,
                client=client,
                hidden=True,
            ).result()
            dropped += 1
            logger.info(f"Dropped {schema}.{table.name}")
        except Exception as err:
            failed.append(table.name)
            logger.error(f"Failed to drop {schema}.{table.name}: {err}")

    logger.info(f"Dropped {dropped} table(s); {len(failed)} failure(s)")
    if failed:
        logger.warning(f"Failed to drop: {', '.join(failed)}")


if __name__ == "__main__":
    main()
