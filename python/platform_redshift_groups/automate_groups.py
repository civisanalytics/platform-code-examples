"""
This script checks the current users and groups configured in both an instance of Civis Platform and a corresponding
(Redshift) database, determines where these users and groups correspond across the two lists, and then updates
the database group membership to match the membership specified in Platform.

As this script generates and executes SQL statements that alter database group membership, it must be executed
with an authorized superuser account credential on the affected database. This access and privilege should be
closely managed, ideally through a secured Platform robot/service account.

Configuration:
- Set the DATABASE environment variable to specify which database to use
- Edit the GROUPS_CROSSWALK list below to map Platform groups to Redshift groups for your use case
- Set DRY_RUN=True to preview changes without executing them
"""
import civis
import pandas as pd
import os
import logging
from collections import defaultdict
from distutils.util import strtobool

# Setting up logging
LOG = logging.getLogger(__name__)
FORMAT = "%(asctime)-15s %(levelname)s:%(name)s.%(funcName)s:%(lineno)s %(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT)

# ========================================
# CONFIGURATION: Edit this crosswalk for your specific use case
# ========================================
GROUPS_CROSSWALK = [
    {
        'platform_group_name': 'Example Platform Group',
        'platform_group_id': None,  # Optional: Platform group ID for reference
        'redshift_group_name': 'example_redshift_group',
        'redshift_group_id': None,  # Optional: Redshift group ID for reference
        'notes': 'Example mapping - replace with your actual groups'
    },
    # Add more group mappings here as needed
    # {
    #     'platform_group_name': 'Another Platform Group',
    #     'platform_group_id': None,
    #     'redshift_group_name': 'another_redshift_group',
    #     'redshift_group_id': None,
    #     'notes': 'Additional notes'
    # },
]

def create_valid_database_users_list(database):
    """
    Return a list of strings for every Redshift/Postgres account name within the database.
    This will be used to check and ensure a user account exists before attempting to add
    or remove it from a database user group.
    """
    redshift_sql = f"""SELECT
    usename as redshift_username
    from pg_user"""
    result = civis.io.read_civis_sql(sql=redshift_sql,
                            database=database,
                            use_pandas=False)
    
    # Extract strings from sublists (length 1) and omit header element
    flattened_result = [x[0] for x in result[1:]]
    
    return(flattened_result)

def create_redshift_groups_dictionary(database):
    """
    Creating a list from redshift platform table data import
    """
    redshift_sql = f"""SELECT
    usename as redshift_username,
    usesysid as redshift_user_id,
    groname as redshift_group_name,
    grosysid as redshift_group_id
    FROM pg_user, pg_group
    WHERE pg_user.usesysid = ANY(pg_group.grolist)"""

    LOG.info("Creating the redshift dictionary")
    redshift = civis.io.read_civis_sql(sql=redshift_sql,
                                       database=database)
    LOG.debug(f"The redshift SQL executed: {redshift_sql}")

    header = None
    redshift_temp_list = []
    for item in redshift:
        if not header:
            header = item
        else:
            redshift_temp_list.append(dict(zip(header, item)))

    redshift_dict = defaultdict(set)

    for item in redshift_temp_list:
        redshift_dict[item['redshift_group_name']].add(item['redshift_username'])

    return redshift_dict


def create_group_names_crosswalk():
    """
    Creating the Redshift <> Platform group crosswalk as a list of tuples for iteration.
    Output tuples: (Platform group name, Corresponding Redshift group name)
    Uses the code-based GROUPS_CROSSWALK configuration defined at the top of this file.
    """
    LOG.info("Creating the crosswalk from code-based configuration")

    # Omit any rows that are missing a mapping for either name
    valid_crosswalk = [
        (entry['platform_group_name'].strip(), entry['redshift_group_name'].strip())
        for entry in GROUPS_CROSSWALK
        if entry['platform_group_name'] and entry['redshift_group_name']
    ]

    return valid_crosswalk


def create_platform_groups_dictionary():
    """
    Creating platform groups dictionary from API response. Note that this response will filter out any Platform user accounts
    that are inactive, in the event that the account running this script has privileges to see any such users.
    """

    # Instantiate API connection
    client = civis.APIClient()

    LOG.info("Creating platform group dictionary")
    group_results = [client.groups.get(result['id']) for result in client.groups.list(limit = 1000)]

    # String matching in the crosswalk is fragile to whitespaces
    # Recommend converting to use unique group ids from Redshift and Platform instead
    platform_group_members = {
        result['name'].strip(): [
            member['username'].strip() for member in result['members'] if member['active']
        ] for result in group_results
    }

    return platform_group_members


def main(database, dry_run = True):
    """
    Main function that produces and executes the SQL query to align the redshift and platform groups
    """

    # constants and empty lists for the loop
    full_add_list = []
    full_drop_list = []
    full_platform_group_change_list = []
    full_query_text = ""

    # creating the dictionaries and lists we need
    group_names_crosswalk = create_group_names_crosswalk()
    platform_group_members_dict = create_platform_groups_dictionary()
    redshift_group_members_dict = create_redshift_groups_dictionary(database=database)

    redshift_valid_users_list = create_valid_database_users_list(database=database)
    # Edit this list to specify users that should be ignored during group synchronization
    ignore_users_list = ["dbadmin", "console"]
    # ignore_groups_list =
    
    for platform_group, redshift_group in group_names_crosswalk:
        platform_group_members = platform_group_members_dict[platform_group]
        platform_group_members = [x for x in platform_group_members if x in redshift_valid_users_list]

        redshift_group_members = redshift_group_members_dict[redshift_group]
        redshift_group_members = [x for x in redshift_group_members if x not in ignore_users_list]
        
        to_add_to_redshift = set(platform_group_members) - set(redshift_group_members)
        to_drop_from_redshift = set(redshift_group_members) - set(platform_group_members)
        
        full_add_list.append((platform_group, to_add_to_redshift))
        full_drop_list.append((platform_group, to_drop_from_redshift))
        
        if to_add_to_redshift:
            add_query = f"\nALTER GROUP {redshift_group} ADD USER {', '.join(to_add_to_redshift)};"
        else:
            add_query = f"\n--No users to add to {redshift_group}"
            
        if to_drop_from_redshift:
            drop_query = f"\nALTER GROUP {redshift_group} DROP USER {', '.join(to_drop_from_redshift)};"
        else:
            drop_query = f"\n--No users to drop from {redshift_group}"
        
        full_query_text = full_query_text + f"\n\n--Platform group name: {platform_group}" + \
            f"\n--Corresponding Redshift group name: {redshift_group}" + \
            f"\n--Users to add: {add_query}" + f"\n--Users to drop: {drop_query}"
    
    LOG.info(f"Full Platform Group change list: {full_platform_group_change_list}")
    LOG.info(f"Full add list: {full_add_list}")
    LOG.info(f"Full drop list: {full_drop_list}")
    
    if dry_run:
        LOG.info("Running in dry run mode. The following SQL generated but not executed:\n\n")
        LOG.info(full_query_text)
    else:
        LOG.info("Running in full mode. The following SQL will be executed:\n\n")
        LOG.info(full_query_text)
        future = civis.io.query_civis(full_query_text, database = database, hidden = False)
        LOG.info(future.result())

   

if __name__ == "__main__":
    # Different Platform/cloud environments use slightly different formats for Boolean parameters;
    # This provides some assurance that "truthy" values are assigned properly.
    DRY_RUN_PARAM = strtobool(str(os.environ.get('DRY_RUN', 'True')))
    DATABASE = os.environ.get('DATABASE')
    
    if not DATABASE:
        raise ValueError("DATABASE environment variable must be set")
    
    main(database=DATABASE, dry_run=DRY_RUN_PARAM)