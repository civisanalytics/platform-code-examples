"""
This script automates granting SELECT access (and optionally USAGE) on database schemas to specified groups.
For each configured schema, it grants permissions to all associated groups on all tables and views within that schema.

This script must be run with authorized superuser account credential on the affected database.

Configuration:
- Set the DATABASE environment variable to specify which database to use
- Edit the SCHEMA_GRANTS_CONFIG list below to map schemas to their authorized groups
- Set DRY_RUN=True to preview changes without executing them
- Set GRANT_USAGE=True to also grant USAGE permissions on schemas
- Set GRANT_FUTURE=True to grant permissions on future tables/views (default: True)

IMPORTANT: ALTER DEFAULT PRIVILEGES in Redshift only applies to objects created by specific users.
You must specify the 'table_creators' list for each schema to include all users who might create tables.
Otherwise, default privileges will only apply to tables created by the user running this script.

Note: In Redshift, "ALL TABLES" includes tables, views, and external tables.
"""

import civis
import os
import logging
from distutils.util import strtobool

# Setting up logging
LOG = logging.getLogger(__name__)
FORMAT = "%(asctime)-15s %(levelname)s:%(name)s.%(funcName)s:%(lineno)s %(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT)

# ========================================
# CONFIGURATION: Edit this list for your specific use case
# ========================================
SCHEMA_GRANTS_CONFIG = [
    {
        'schema_name': 'example_schema',
        'groups': ['example_group_1', 'example_group_2', 'read_only_users'],
        'table_creators': [],  # Optional: usernames who can create tables in this schema
        'notes': 'Example schema - replace with your actual schemas and groups'
    },
    # Add more schema-to-groups mappings here as needed
    # {
    #     'schema_name': 'analytics_schema',
    #     'groups': ['analysts', 'data_engineers', 'reporting_users'],
    #     'table_creators': ['etl_user', 'data_engineer_bot'],  # Users who create tables
    #     'notes': 'Analytics schema for reporting team'
    # },
]


def get_schema_grants_config():
    """
    Returns the schema grants configuration from the code-based SCHEMA_GRANTS_CONFIG.
    Returns a dict mapping schema names to their authorized groups:
        {
            'schema_name': {
                'schema': 'schema_name',
                'groups': ['group1', 'group2', ...],
                'table_creators': ['user1', 'user2', ...]
            },
            ...
        }
    """
    mapping = {}
    
    for config in SCHEMA_GRANTS_CONFIG:
        schema = config.get('schema_name')
        groups = config.get('groups', [])
        table_creators = config.get('table_creators', [])
        
        if schema and groups:
            mapping[schema] = {
                "schema": schema,
                "groups": tuple(groups),
                "table_creators": table_creators,
            }
    
    return mapping


def main(database, dry_run=True, grant_usage=False, grant_future=True):
    grant_commands = []
    schema_grants = get_schema_grants_config()
    
    for schema_name in schema_grants:
        schema = schema_grants[schema_name]["schema"]
        groups = schema_grants[schema_name]["groups"]

        if grant_usage:
            usage_command = f"GRANT USAGE ON SCHEMA {schema} TO GROUP {', GROUP '.join(groups)};"
            grant_commands.append(usage_command)

        # Grant on existing tables and views
        # Note: In Redshift, "ALL TABLES" includes tables, views, and external tables
        select_command = f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO GROUP {', GROUP '.join(groups)};"
        grant_commands.append(select_command)
        
        # Grant on future tables and views (if enabled)
        # IMPORTANT: ALTER DEFAULT PRIVILEGES only applies to objects created by specific users
        if grant_future:
            table_creators = schema_grants[schema_name].get("table_creators", [])
            
            if table_creators:
                # Grant for each specified table creator
                for creator in table_creators:
                    for group in groups:
                        future_command = f"ALTER DEFAULT PRIVILEGES FOR USER {creator} IN SCHEMA {schema} GRANT SELECT ON TABLES TO GROUP {group};"
                        grant_commands.append(future_command)
            else:
                # No table_creators specified - grant for the current user running the script
                # This will only apply to tables created by this user!
                for group in groups:
                    future_command = f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT SELECT ON TABLES TO GROUP {group};"
                    grant_commands.append(future_command)
                LOG.warning(f"No table_creators specified for schema '{schema}'. Default privileges will only apply to tables created by the user running this script.")

    query = "\n".join(grant_commands)

    if dry_run:
        LOG.info(
            "Running in dry run mode. The following SQL generated but not executed:\n\n"
        )
        LOG.info(query)
    else:
        LOG.info("Running in full mode. The following SQL will be executed:\n\n")
        LOG.info(query)
        future = civis.io.query_civis(query, database=database, hidden=False)
        LOG.info(future.result())


if __name__ == "__main__":
    # Different Platform/cloud environments use slightly different formats for Boolean parameters;
    # This provides some assurance that "truthy" values are assigned properly.
    DRY_RUN_PARAM = strtobool(str(os.environ.get('DRY_RUN', 'True')))
    GRANT_USAGE = strtobool(str(os.environ.get('GRANT_USAGE', 'False')))
    GRANT_FUTURE = strtobool(str(os.environ.get('GRANT_FUTURE', 'True')))
    DATABASE = os.environ.get('DATABASE')
    
    if not DATABASE:
        raise ValueError("DATABASE environment variable must be set")
    
    main(database=DATABASE, dry_run=DRY_RUN_PARAM, grant_usage=GRANT_USAGE, grant_future=GRANT_FUTURE)
