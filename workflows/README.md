# Workflows Directory

This directory contains various workflow definitions used for different data processing tasks. Each workflow is defined using YAML and is designed to be run on the Civis Platform.

## Workflows

### facebook_ad_insights_workflow

This workflow is used to run Facebook Ad Insights tasks.

- **File**: [facebook_ad_insights_workflow.yml](facebook_ad_insights_workflow/facebook_ad_insights_workflow.yml)
- **Description**: Runs a series of tasks to gather and process Facebook Ad Insights data.
- **Inputs**:
  - `SCRIPT_MODE`: Mode to run the script.
  - `DAYS`: Number of days to look back for data.
  - `START_DATE`: Start date for data collection.
  - `END_DATE`: End date for data collection.
  - `DATABASE_NAME`: Name of the database to store results.
  - `SCHEMA_NAME`: Schema name in the database.
  - `TABLE_NAME_PREFIX`: Prefix for the table names.
  - `IF_EXISTS`: Action to take if the table already exists.
  - `MAX_ERRORS`: Maximum number of errors allowed.
  - `CUSTOM_BREAKDOWNS`: Custom breakdowns for the data.
  - `FB_CREDENTIAL_ID`: Facebook credential ID.
  - `INCLUDE_ALL_ACTIVE`: Whether to include all active ads.

### van_multistate_workflow

This workflow splits a table of people records by state and sends the records to those state's VAN MyCampaign accounts.

- **File**: [van_multistate_workflow.yaml](van_multistate_workflow/van_multistate_workflow.yaml)
- **Description**: Splits people records by state and sends them to respective VAN MyCampaign accounts.
- **Inputs**:
  - `cluster`: Remote host cluster.
  - `cluster_credential`: Database credential ID.
  - `input_table`: Name of the input table containing people records.
  - `response_table`: (Optional) Name of the response table to store VAN API responses.
  - `response_table_setting`: Setting for existing response table rows (`drop` or `append`).
  - `state_field`: Name of the field by which to split people records into states.
  - `state_credentials`: List of VAN API credential IDs for each state.

### van_turf_import

This workflow imports folders from VAN, working with folders having fewer than 250 lists/turfs.

- **File**: [van_turf_import.yaml](van_turf_import/van_turf_import.yaml)
- **Description**: Imports folders from VAN and processes the lists/turfs.
- **Inputs**:
  - `ngpvan_credential`: NGPVAN credential ID.
  - `ngpvan_mode`: NGPVAN database mode (`0` for MyVoterfile, `1` for MyCampaign).
  - `cluster`: Remote host cluster.
  - `cluster_credential`: Database credential ID.
  - `metadata_table`: Output table to store turf metadata.
  - `turf_table`: Output table to store turf VAN IDs.
  - `table_setting`: Option for existing table rows (`append` or `drop`).
  - `folder_id`: ID of the folder to import.

## Getting Started

### Initial Setup

1. Clone the repository:
  ```sh
  git clone https://github.com/civisanalytics/platform-code-examples.git
  cd platform-code-examples/workflows
  ```

### Running a Workflow

1. Ensure you have the necessary credentials and access to the Civis Platform.
2. Modify the workflow YAML file to include your specific inputs and credentials.
3. Upload and run the workflow on the Civis Platform.
