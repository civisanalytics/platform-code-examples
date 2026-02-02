# Generic File Upload Script

This script provides a lightweight, generalized CSV upload solution for Civis Platform. It handles uploading CSV files to database tables based on a user's primary group ID and a metadata table that defines schema mappings.

## How It Works

The script performs the following operations:

1. **Schema Determination**: Looks up the user's schema from a metadata table based on their `primary_group_id`
2. **Table Creation**: Drops the existing table if present and imports the CSV data
3. **Email Notification**: Sends an email notification upon successful completion

## Key Features

- **Automatic Schema Assignment**: The script automatically determines which schema to use based on the user's primary group ID
- **Metadata-Driven Configuration**: Schema mappings are stored in a metadata table, making it easy to configure without code changes
- **Table Name Configuration**: Table names are set directly in Civis Platform using the "parameters" feature, if you set up a dropdown parameter then the "value name" will be used as the table name.
- **Email Notifications**: Optional email notifications upon successful upload

## Setup Requirements

### 1. Create a Metadata Table

Create a metadata table in your Civis database with the following structure:

```sql
CREATE TABLE your_database.your_schema.metadata_data_upload_mmk (
    primary_group_id INTEGER,
    schema_name VARCHAR
);
```

Populate this table with mappings of primary group IDs to their corresponding schemas:

```sql
INSERT INTO your_database.your_schema.metadata_data_upload_mmk 
VALUES 
    (123, 'team_a_schema'),
    (456, 'team_b_schema'),
    (789, 'team_c_schema');
```

### 2. Create a Notification Script

Create a blank Python script in Civis Platform that will be used to send notification emails. This script doesn't need to contain any code - it's only used to trigger the email notification system. Note the script ID for use in the configuration.

### 3. Set Up the Container Script in Platform

When setting up this script in Civis Platform, create a container script with the following configuration:

```bash
cd /app;
export DATABASE='redshift-general'
export TESTING=0
export EMAIL_RECIPIENTS=""
export METADATA_TABLE="metadata_data_upload_mmk"
export EMAIL_SCRIPT_ID="340695845"
python python/custom_file_uploads/generic_upload.py
```

**Configuration Variables:**

- `DATABASE`: The name of your Civis database (e.g., 'redshift-general')
- `TESTING`: Set to `1` to skip email notifications (for testing), `0` for production
- `METADATA_TABLE`: The full table name (including schema) of your metadata table
- `EMAIL_SCRIPT_ID`: The ID of the blank notification script you created in step 2

### 4. Configure Script Parameters

In the Civis Platform script configuration, add the following parameters:

- **FILE**: File parameter (required) - Users will upload their CSV file here
- **TABLE_NAME**: Dropdown or text parameter (required) - The name of the target table
- **EMAIL**: Text parameter (optional) - Email address for notification
- **TESTING**: Boolean parameter (optional) - Set to true to skip sending emails

## Usage

Once configured, users can run the script by:

1. Uploading a CSV file via the FILE parameter
2. Selecting or entering the target table name via the TABLE_NAME parameter
3. Optionally providing an email address for notification
4. Running the script

The script will:
- Automatically determine the correct schema based on the user's primary group
- Drop and recreate the table with the uploaded CSV data
- Send a notification email upon completion

## Example Metadata Table Setup

Here's a complete example for setting up your metadata table:

```sql
-- Create the metadata table
CREATE TABLE your_database.your_schema.metadata_data_upload_mmk (
    primary_group_id INTEGER,
    schema_name VARCHAR
);

-- Add your group mappings
INSERT INTO your_database.your_schema.metadata_data_upload_mmk 
    (primary_group_id, schema_name)
VALUES 
    (123, 'analytics_team'),
    (456, 'marketing_team'),
    (789, 'operations_team');
```

## Troubleshooting

- **"No schema mapping found"**: Ensure your primary group ID is added to the metadata table
- **Schema creation errors**: You may need database permissions to create schemas, or ensure the schema already exists
- **Email not received**: Check that the SCRIPT_ID points to a valid script and TESTING is set to 0

## Notes

- The script will drop and recreate the table on each run, so existing data will be replaced
- Users must have appropriate database permissions to write to their assigned schema
- The metadata table must be readable by all users who will run this script
