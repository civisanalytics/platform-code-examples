# This script exports data from Redshift to a CSV file with a dynamically
# generated filename that includes the current date in MMDDYYYY format.
# The file is uploaded to Civis Files and a download link is included
# in the success notification email.

import civis
import os
import json
from datetime import datetime

# Step 1: Open a new Python script in Platform, and paste this entire file
#         into the script body.
#
# Step 2: Update the database name and SQL query below to match your data.

# Swap out name of database for your own
DATABASE = 'your-database-name'

# Swap out the SQL query for your own
SQL = 'SELECT * FROM schema.your_table'

# Swap out the filename prefix for your own (date will be appended automatically)
FILENAME_PREFIX = 'your_export_'


def main():
    # Generate filename with today's date in MMDDYYYY format
    # Example output: your_export_02022026.csv
    today = datetime.now().strftime('%m%d%Y')
    filename = f"{FILENAME_PREFIX}{today}.csv"

    # Export query results to a temporary CSV file on the script's container
    # The .result() call waits for the export job to complete before continuing
    local_path = f"/tmp/{filename}"
    civis.io.civis_to_csv(local_path, SQL, DATABASE).result()

    # Upload the CSV to Civis Files with the dynamic filename
    # This returns a file_id that can be used to retrieve the file later
    file_id = civis.io.file_to_civis(local_path, name=filename)

    # Retrieve the file metadata to get the download URL
    client = civis.APIClient()
    file_info = client.files.get(file_id)
    file_url = file_info.download_url

    # Create a dictionary with the download link
    # The key 'file_link' will become the variable {{file_link}} in the email
    json_value_dict = {
        'file_link': file_url
    }

    # Upload the dictionary as a run output so it can be used in the email
    post_json_run_output(json_value_dict)

    # Print confirmation to the logs
    print(f"File uploaded with ID: {file_id}")
    print(f"Filename: {filename}")
    print(f"Download URL: {file_url}")

# Step 3: Configure the notification settings.
#
# Open the Notify pane (paper airplane icon) and set the Email Body to
# include the {{file_link}} variable. For example:
#
# Download your file here: {{file_link}}
#
# The {{file_link}} variable will be replaced with the actual download URL
# when the email is sent. Note that this link expires after 30 days by default.
#
# Step 4: Run the job, schedule it, and/or receive your email with the file link.
#
# ****
# Function below will not require editing, but
# needs to be included in the script


def post_json_run_output(json_value_dict):
    client = civis.APIClient()
    json_value_object = client.json_values.post(
        json.dumps(json_value_dict),
        name='email_outputs')
    client.scripts.post_python3_runs_outputs(
        os.environ['CIVIS_JOB_ID'],
        os.environ['CIVIS_RUN_ID'],
        'JSONValue',
        json_value_object.id)


if __name__ == '__main__':
    main()
