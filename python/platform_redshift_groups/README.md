# Automated Management of Redshift/Database User Groups

## Overview

The permissions and account management of Civis Platform is entirely separate from the management of specific databases (such as Redshift). This presents a challenge for managing and implementing best practices to govern data access, especially in complex environments with many users and tables.

This script addresses one specific challenge: **user group management**. User (permission) groups are a powerful tool for managing permissions en masse, bringing clarity and reducing the risk of missing key individuals when permissions need to change. Even though Redshift and Platform both have the concept of user groups, the two implementations are completely independent -- nothing enforces that the same groups exist in both places, or that they have the same members. This creates a significant manual burden on database admins to maintain consistent lists, or risk having to track multiple "sources of truth".

## Solution

This automation addresses the problem by:

1. Assuming that all Platform users have a corresponding user in the target database
2. Ensuring that all included Platform user groups have a corresponding user group in the target database (unless consciously excluded)
3. Pulling the list of user group membership for all included Platform user groups
4. Assigning database users to corresponding database user groups to **match what is set for their Platform counterparts**

Platform users and groups, with their better existing User Interface, are treated as the **Source of Truth**.

## Configuration

### Step 1: Set Environment Variables

```bash
export DATABASE="your_database_name"  # Required: The name of your database
export DRY_RUN="True"                 # Optional: Set to False to execute changes
```

### Step 2: Update the Groups Crosswalk

Edit the `GROUPS_CROSSWALK` list in `automate_groups.py` to map your Platform groups to Redshift groups:

```python
GROUPS_CROSSWALK = [
    {
        'platform_group_name': 'Data Analysts',
        'platform_group_id': None,  # Optional: for reference
        'redshift_group_name': 'data_analysts_group',
        'redshift_group_id': None,  # Optional: for reference
        'notes': 'Standard read access for analysts'
    },
    {
        'platform_group_name': 'Data Engineers',
        'platform_group_id': None,
        'redshift_group_name': 'data_engineers_group',
        'redshift_group_id': None,
        'notes': 'Write access for engineers'
    },
]
```

### Step 3: Customize Ignored Users (Optional)

Edit the `ignore_users_list` in the `main()` function to specify users that should be ignored during synchronization (e.g., service accounts, admin users).

## Usage

### Dry Run (Preview Changes)

```bash
python automate_groups.py
```

This will log the SQL statements that would be executed without actually making any changes.

### Execute Changes

```bash
export DRY_RUN="False"
python automate_groups.py
```

This will execute the SQL statements to synchronize database group membership with Platform groups.

## How It Works

1. **Fetches Platform Groups**: Retrieves all group memberships from Civis Platform API
2. **Fetches Redshift Groups**: Queries the database for current group memberships
3. **Compares Memberships**: Identifies users that need to be added or removed from database groups
4. **Generates SQL**: Creates `ALTER GROUP` statements to synchronize memberships
5. **Executes or Logs**: Either executes the changes (when `DRY_RUN=False`) or logs them for review

## Requirements

- Python 3.x
- `civis` Python package
- Superuser/admin access to the target database
- Appropriate Civis Platform API credentials
