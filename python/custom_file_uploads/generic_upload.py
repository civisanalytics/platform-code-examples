"""Lightweight generalized file upload script for Civis Platform.

Uploads a CSV file to a database table based on user's group and
dropdown selection.
The script:
1. Determines user's schema from metadata table based on primary_group_id
2. Drops existing table if present and imports CSV
3. Sends email notification on completion

In order to function correctly, the following environment variables must be
  set:
- TABLE_NAME: Platform dropdown selection that maps to the table name
- DATABASE: Target Civis database name
- METADATA_TABLE: Civis table containing mapping of primary_group_id
  to schema_name
- SCRIPT_ID: Civis script ID used to send notification emails
   - this should just be a blank script configured to send success emails

The template script will also need to accept the following parameters:
- FILE: Civis file parameter
- EMAIL: Optional email address for notification
- TABLE_NAME: Platform dropdown selection that maps to the table name
- TESTING: Optional boolean to indicate testing mode (skip email)
"""

import os
import tempfile

import civis
import pandas as pd

LOG = civis.loggers.civis_logger()


def get_schema(metadata_table: str, database: str, client=None) -> str:
    client = client or civis.APIClient()

    # Get user info
    user = client.users.list_me()
    user_id = user["id"]
    user_email = user["email"]
    primary_group_id = client.users.get(user_id)["primary_group_id"]

    # Lookup schema from metadata table
    LOG.info(f"Looking up schema for primary_group_id {primary_group_id}")
    schema_query = f"""
        SELECT schema_name
        FROM {metadata_table}
        WHERE primary_group_id = {primary_group_id}
    """
    schema_result = civis.io.read_civis_sql(
        schema_query, database=database, use_pandas=True
    )

    if schema_result.empty:
        raise ValueError(
            f"No schema mapping found for primary_group_id {primary_group_id}."
            f"Please add a row to {metadata_table}."
        )

    schema = schema_result["schema_name"].iloc[0]
    LOG.info(f"Using schema: {schema}")

    # Create schema if needed
    LOG.info(f"Creating schema {schema} if needed")
    try:
        civis.io.query_civis(
            f"CREATE SCHEMA IF NOT EXISTS {schema};",
            database=database,
        ).result()
    except Exception:
        LOG.warning("""You do not have permissions to create schemas.
                    Script will continue and raise an error later
                     if the schema doesn't exist""")

    return schema, user_email


def download_data_create_table(
    file_id: int, full_table: str, database: str, client=None
):
    client = client or civis.APIClient()
    file_obj = client.files.get(file_id)
    LOG.info(f"Downloading file: {file_obj['name']}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = os.path.join(tmpdir, file_obj["name"])
        civis.io.civis_to_file(file_id, tmp_path)
        df = pd.read_csv(tmp_path)

    LOG.info(f"Read CSV with {len(df)} rows and {len(df.columns)} columns")

    # Drop existing table
    LOG.info(f"Dropping table if exists: {full_table}")
    civis.io.query_civis(
        f"DROP TABLE IF EXISTS {full_table};",
        database=database,
    ).result()

    # Import data to table
    LOG.info(f"Importing data to {full_table}")
    try:
        civis.io.dataframe_to_civis(
            df=df,
            database=database,
            table=full_table,
            existing_table_rows="fail",
        )
        LOG.info(f"Successfully uploaded {len(df)} rows to {full_table}")
    except Exception as e:
        LOG.error(f"""Failed to upload data to {full_table}: {e}
                  Please check that the schema exists and you have
                    permissions to write to it.""")


def send_email_notification(
    email_address: str,
    table_name: str,
    schema: str,
    full_table: str,
    database: str,
    user_email: str,
    file_obj: dict,
    testing: bool = False,
    client=None,
):
    client = client or civis.APIClient()
    recipient_email = email_address if email_address else user_email
    email_subject = f"Data Upload Complete"
    email_body = f"""Your data upload has been completed successfully.

File: {file_obj['name']}
Database: {database}
Schema: {schema}
Table: {table_name}
User: {user_email}

The data is now available at: {database}.{full_table}
"""

    if not testing:
        LOG.info(f"Sending notification email to {recipient_email}")
        # Use a blank script on platform to trigger email notification
        # NOTE: This requires an existing script ID that you can configure
        # to send success notification emails
        email_script_id = int(os.getenv("EMAIL_SCRIPT_ID"))

        client.scripts.patch_python3(
            id=email_script_id,
            name=f"Upload notification for {user_email}",
            notifications={
                "success_email_subject": email_subject,
                "success_email_body": email_body,
                "success_email_addresses": [recipient_email],
            },
        )
        future = civis.utils.run_job(email_script_id, client=client).result()
    else:
        LOG.info(f"Testing mode: skipping email to {recipient_email}")


def main(
    file_id: int,
    table_name: str,
    database: str,
    metadata_table: str,
    email_address: str = None,
    testing: bool = False,
):
    """Main function to upload CSV file to Civis database table."""

    client = civis.APIClient()

    schema, user_email = get_schema(
        metadata_table=metadata_table,
        database=database,
        client=client,
    )

    full_table = f"{schema}.{table_name}"
    LOG.info(f"Target table: {full_table}")

    download_data_create_table(
        file_id=file_id,
        full_table=full_table,
        database=database,
        client=client,
    )

    send_email_notification(
        email_address=email_address,
        table_name=table_name,
        schema=schema,
        full_table=full_table,
        database=database,
        user_email=user_email,
        file_obj=client.files.get(file_id),
        testing=testing,
        client=client,
    )

    LOG.info("Upload process completed successfully")


if __name__ == "__main__":
    # Get environment variables
    file_id = int(os.environ["FILE_ID"])
    table_name = os.environ["TABLE_NAME"]
    database = os.environ["DATABASE"]
    metadata_table = os.environ["METADATA_TABLE"]
    email_address = os.getenv("EMAIL")
    testing = int(os.getenv("TESTING", 0)) == 1
    main(
        file_id=file_id,
        table_name=table_name,
        database=database,
        metadata_table=metadata_table,
        email_address=email_address,
        testing=testing,
    )
