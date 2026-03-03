# Schema-Based Granting

## Overview

Many developed databases hold thousands of different tables and views, which makes organization and discovery of data difficult and greatly complicates questions of data sharing, granting, and access.

One remedy is to organize tables into schemas that align with different audiences and use cases, and then make and enforce sharing decisions accordingly. Even when there are exceptions, it is a significant improvement to think of dozens of schemas instead of thousands of individual tables.

However, schemas are a relatively under-supported and unintuitive database feature for sharing decisions, for a few main reasons:

- Schema and table permissions work together hierarchically in Redshift - users need **both** USAGE permission on the schema **and** SELECT permission on the tables. Granting one without the other is insufficient, making permission management more complex than simple folder-based sharing
- Schema purposes cannot always be clearly intuited from their names, requiring the use of thorough external documentation for users to know where certain kinds of data should go
- Newly created data tables inherit no permissions from their schema and are only accessible to the table owner and superusers by default, regardless of what groups have access to the schema itself

## Purpose

This script automates database sharing to work more like shared folders in collaborative file sharing software, such that:

1. Individuals primarily have access to different topic schemas based on their **group** membership, with minimal cases of person-level exceptions
2. Tables put into a schema are understood to be made **automatically** available to members of those groups (not a Redshift/SQL default behavior)
3. Behavior is documented and explained directly in context, so that users are not surprised by cases where:
   - Data is **not** shared with other users as expected, or
   - Data **is** shared with other users when it was **not** expected (data leakage)

## Configuration

### Step 1: Set Environment Variables

```bash
export DATABASE="your_database_name"  # Required: The name of your database
export DRY_RUN="True"                 # Optional: Set to False to execute changes
export GRANT_USAGE="False"            # Optional: Set to True to also grant USAGE on schemas
export GRANT_FUTURE="True"            # Optional: Set to False to skip future table grants (default: True)
```

### Step 2: Configure Schema Grants

Edit the `SCHEMA_GRANTS_CONFIG` list in `automate_schema_grants.py` to define which groups should have access to which schemas:

```python
SCHEMA_GRANTS_CONFIG = [
    {
        'schema_name': 'reporting',
        'groups': ['analysts', 'managers', 'executives'],
        'table_creators': ['etl_user', 'data_engineer_bot'],  # Users who create tables
        'notes': 'Reporting tables for business intelligence'
    },
    {
        'schema_name': 'raw_data',
        'groups': ['data_engineers', 'etl_users'],
        'table_creators': ['etl_service_account'],
        'notes': 'Raw data ingestion schema'
    },
]
```

**IMPORTANT - `table_creators` Configuration:**

In Redshift, `ALTER DEFAULT PRIVILEGES` only applies to objects created by **specific users**. You must list all users who might create tables in the `table_creators` field. Common users to include:
- Service accounts (e.g., `etl_service_account`, `airflow_user`)
- Application users that create tables
- Data engineers or analysts with CREATE privileges

If you omit `table_creators`, default privileges will only apply to tables created by the user running this script, meaning tables created by other users won't automatically inherit the correct permissions.

## Usage

### Dry Run (Preview Changes)

```bash
python automate_schema_grants.py
```

This will log the SQL GRANT statements that would be executed without actually making any changes.

### Execute Changes

```bash
export DRY_RUN="False"
python automate_schema_grants.py
```

This will execute the SQL statements to grant permissions.

### Grant USAGE Permissions

By default, the script only grants SELECT permissions on tables. To also grant USAGE permissions on the schemas themselves:

```bash
export GRANT_USAGE="True"
python automate_schema_grants.py
```

### Disable Future Object Grants

By default, the script grants permissions on both existing and future tables/views. To only grant on existing objects:

```bash
export GRANT_FUTURE="False"
python automate_schema_grants.py
```

## Tables vs Views

In Redshift, the command `GRANT SELECT ON ALL TABLES IN SCHEMA` covers:
- Regular tables
- Views
- External tables
- Late-binding views

Similarly, `ALTER DEFAULT PRIVILEGES` applies to both tables and views created in the future. This means you don't need separate commands for views - they're automatically included.

## How It Works

1. **Reads Configuration**: Loads the schema-to-groups mapping from `SCHEMA_GRANTS_CONFIG`
2. **Generates GRANT Statements**: Creates SQL statements to grant SELECT (and optionally USAGE) permissions
   - Grants SELECT on all existing tables and views in each schema
   - Optionally grants USAGE on the schema itself (required for accessing tables/views)
   - Sets default privileges for future tables and views created by specified users
3. **Executes or Logs**: Either executes the changes (when `DRY_RUN=False`) or logs them for review

**Note**: In Redshift, "ALL TABLES" includes tables, views, and external tables that currently exist in the schema. 

**Critical Limitation**: The `ALTER DEFAULT PRIVILEGES` command only applies to objects created by specific users. The script uses `FOR USER <username>` to grant privileges on future objects created by each user in the `table_creators` list. If a user not in this list creates a table, the permissions will **not** be automatically applied, and you'll need to either:
- Re-run this script to grant on the newly created tables
- Add that user to the `table_creators` list and re-run the script

## Requirements

- Python 3.x
- `civis` Python package
- Superuser/admin access to the target database
- Appropriate Civis Platform API credentials
