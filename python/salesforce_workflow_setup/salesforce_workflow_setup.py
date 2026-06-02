"""
This example is source code for the Backing Script of a template that will setup a
Civis Platform Workflow of Salesforce Imports given the required credentials and connection
information and a list of Salesforce Objects to import.

If DAYS is provided, two imports are created for each object: an incremental refresh that
appends data to the destination table, and a full refresh that runs if the incremental
import fails and drops the table. This handles field changes by dropping and recreating the
table when the incremental import fails. If DAYS is not provided, only full refresh jobs
are created.

The Backing Script must be configured to accept the following parameters:

| Display Name                 | Parameter Name      | Description                                                                                                                                                                                          | Default | Type              | Required |
|------------------------------|---------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|-------------------|----------|
| Salesforce Objects           | OBJECTS             | Comma separated list of Salesforce Objects to import e.g. "campaign, account, custom_object__c"                                                                                                      |         | String            | Yes      |
| Salesforce User Credential   | SALESFORCE          | Civis Platform Custom Credential with Salesforce username / password+token                                                                                                                           |         | Custom Credential | Yes      |
| Salesforce Client Credential | SALESFORCE_CLIENT   | Civis Platform Custom Credential with Salesforce username / password + security token.                                                                                                               |         | Custom Credential | Yes      |
| Salesforce URL               | CLIENT_INSTANCE_URL | Civis Platform Custom Credential with Consumer Key / Consumer Secret.                                                                                                                                |         | String            |          |
| Destination Database         | DB                  | Database to import to.                                                                                                                                                                               |         | Database          | Yes      |
| Destination Schema           | SCHEMA              | Schemaname to import data to. Table names will use the Salesforce Object name.                                                                                                                       |         | String            | Yes      |
| Incremental Days             | DAYS                | For the incremental import: how many days back to sync records from. The "days" value is used with incremental sync. To make sure no data is missed, days will always go backward from midnight UTC. |         | Integer           |          |
| Query All?                   | QUERY_ALL           | Boolean to apply the "Query All" parameter on the Salesforce Import. This fetches deleted records. Defaults to True.                                                                                 |         | Boolean           |          |
| Max Errors                   | MAX_ERRORS          | The maximum number of rows with errors to remove from the Civis Platform table import before failing. Defaults to 0 (i.e., no errors allowed).                                                       | 0       | Integer           |          |
| Project ID                   | PROJECT_ID          | Civis Platform Project ID to put all newly created Civis Objects into.                                                                                                                               |         | Integer           | Yes      |
| Workflow ID                  | WORKFLOW_ID         | If provided, overwrites the definition of an existing workflow instead of creating a new one.                                                                                                        |         | Integer           |          |
"""

import civis
import os
import yaml

logger = civis.civis_logger()

client = civis.APIClient()

_SALESFORCE_IMPORT_TEMPLATE_ID = 51987

_OBJECTS = [obj.strip() for obj in os.environ["OBJECTS"].split(",")]
_SF_ID = str(os.environ["SALESFORCE_ID"])
_SF_CLIENT_ID = str(os.environ["SALESFORCE_CLIENT_ID"])
_CLIENT_INSTANCE_URL = os.environ.get("CLIENT_INSTANCE_URL")
_DB_ID = int(os.environ["DB_ID"])
_DB_CREDENTIAL_ID = int(os.environ["DB_CREDENTIAL_ID"])
_DESTINATION_SCHEMA = os.environ["SCHEMA"]
_DAYS = os.environ.get("DAYS")
_QUERY_ALL = os.environ.get("QUERY_ALL", "false").lower() != "false"
_MAX_ERRORS = os.environ.get("MAX_ERRORS", 0)
_PROJECT_ID = os.environ["PROJECT_ID"]
_WORKFLOW_ID = os.environ.get("WORKFLOW_ID")

_OBJECTS_WORKFLOW_TASKS = []

for sf_object in _OBJECTS:
    full_refresh = client.scripts.post_custom(
        from_template_id=_SALESFORCE_IMPORT_TEMPLATE_ID,
        name=f"SF Import {sf_object} Full Refresh",
        arguments={
            "SCRIPT_MODE": "run",
            "SALESFORCE": _SF_ID,
            "SALESFORCE_CLIENT": _SF_CLIENT_ID,
            "CLIENT_INSTANCE_URL": _CLIENT_INSTANCE_URL,
            "SALESFORCE_OBJECTS": sf_object,
            "SALESFORCE_DATABASE": {
                "credential": _DB_CREDENTIAL_ID,
                "database": _DB_ID,
            },
            "SALESFORCE_TABLE": f"{_DESTINATION_SCHEMA}.{sf_object.lower()}",
            "IF_TABLE_EXISTS": "drop",
            "MAX_ERRORS": _MAX_ERRORS,
            "INCREMENTAL_SYNC": False,
            "QUERY_ALL": _QUERY_ALL,
        },
    )
    client.scripts.put_custom_projects(full_refresh.id, _PROJECT_ID)

    task_entry = {"name": sf_object, "jobs": {"full_refresh": full_refresh.id}}

    if _DAYS:
        incremental = client.scripts.post_custom(
            from_template_id=_SALESFORCE_IMPORT_TEMPLATE_ID,
            name=f"SF Import {sf_object} Incremental",
            arguments={
                "SCRIPT_MODE": "run",
                "SALESFORCE": _SF_ID,
                "SALESFORCE_CLIENT": _SF_CLIENT_ID,
                "CLIENT_INSTANCE_URL": _CLIENT_INSTANCE_URL,
                "SALESFORCE_OBJECTS": sf_object,
                "SALESFORCE_DATABASE": {
                    "credential": _DB_CREDENTIAL_ID,
                    "database": _DB_ID,
                },
                "SALESFORCE_TABLE": f"{_DESTINATION_SCHEMA}.{sf_object.lower()}",
                "IF_TABLE_EXISTS": "upsert",
                "MAX_ERRORS": _MAX_ERRORS,
                "INCREMENTAL_SYNC": True,
                "DAYS": _DAYS,
                "QUERY_ALL": _QUERY_ALL,
            },
        )
        client.scripts.put_custom_projects(incremental.id, _PROJECT_ID)
        task_entry["jobs"]["incremental"] = incremental.id

    _OBJECTS_WORKFLOW_TASKS.append(task_entry)


tasks = {}

for i in _OBJECTS_WORKFLOW_TASKS:
    _name = i["name"]
    _full_refresh_id = i["jobs"]["full_refresh"]

    if "incremental" in i["jobs"]:
        _incremental_id = i["jobs"]["incremental"]
        tasks.update(
            {
                f"SF_Import_{_name}_Incremental": {
                    "action": "civis.run_job",
                    "input": {"job_id": _incremental_id},
                    "on-error": f"SF_Import_{_name}_Full_Refresh",
                },
                f"SF_Import_{_name}_Full_Refresh": {
                    "action": "civis.run_job",
                    "input": {"job_id": _full_refresh_id},
                },
            }
        )
    else:
        tasks[f"SF_Import_{_name}_Full_Refresh"] = {
            "action": "civis.run_job",
            "input": {"job_id": _full_refresh_id},
        }


workflow_definition = {"version": "2.0", "workflow": {"tasks": tasks}}
workflow_yaml = yaml.dump(workflow_definition)

with open("sf_workflow.yaml", "w") as f:
    f.write(workflow_yaml)

with open("sf_workflow.yaml", "rb") as f:
    file_id = civis.io.file_to_civis(f, "sf_workflow.yaml")

client.scripts.post_custom_runs_outputs(
    os.environ["CIVIS_JOB_ID"], os.environ["CIVIS_RUN_ID"], "File", file_id
)

if _WORKFLOW_ID:
    workflow = client.workflows.patch(int(_WORKFLOW_ID), definition=workflow_yaml)
    logger.info(f"Updated workflow {workflow.id}")
else:
    workflow = client.workflows.post(
        name="Salesforce Import Workflow", definition=workflow_yaml
    )
    logger.info(f"Created workflow {workflow.id}")

execution = client.workflows.post_executions(
    workflow.id,
    included_tasks=[f"SF_Import_{sf_object}_Full_Refresh" for sf_object in _OBJECTS],
)
