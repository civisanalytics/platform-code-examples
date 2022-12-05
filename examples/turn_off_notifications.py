# Python script that handles turning off notifications for all jobs, imports,
# and workflows (optionally) owned by the running user
# This script will request a page of 50 objects at a time and turn off their
# notifications sequentially. Any erros that occurred during the run of the
# script will be collected and printed out towards the end

import civis
import os
import sys

failed_to_update = []


def paginated_processing(api_method, user_id, process_method):
    page_num = 1

    while True:
        results = api_method(author=user_id, page_num=page_num)
        if len(results) == 0:
            break
        process_method(results)
        page_num += 1


def process_jobs(jobs):
    jobs_to_skip = ['JobTypes::Query', 'JobTypes::SingleTableScanner',
                    'JobTypes::Snapshot', 'JobTypes::Import']

    for job in jobs:
        if job.type in jobs_to_skip:
            continue
        try:
            if job.from_template_id is not None:
                client.scripts.patch_custom(job.id, notifications=notifications)
            elif job.type == 'JobTypes::ContainerDocker':
                client.scripts.patch_containers(job.id, notifications=notifications)

            elif job.type == 'JobTypes::PythonDocker':
                client.scripts.patch_python3(job.id, notifications=notifications)

            elif job.type == 'JobTypes::RDocker':
                client.scripts.patch_r(job.id, notifications=notifications)

            elif job.type == 'JobTypes::SqlRunner':
                client.scripts.patch_sql(job.id, notifications=notifications)

            elif job.type == 'JobTypes::ScriptedSql':
                client.scripts.patch_javascript(job.id, notifications=notifications)
            else:
                raise Exception('Unknown job type')

        except Exception as err:
            failed_to_update.append(f" ({job.type} ID {job.id}) - Unexpected error {err}")


def process_imports(imports):
    for import_job in imports:
        try:
            client.imports.put(import_job.id, import_job.name, import_job.sync_type,
                               import_job.is_outbound, notifications=notifications)
        except Exception as err:
            failed_to_update.append(f" (Import ID {import_job.id}) - Unexpected error {err}")


def process_workflows(workflows):
    for workflow in workflows:
        try:
            client.workflows.patch(workflow.id, notifications=notifications)
        except Exception as err:
            failed_to_update.append(f" (Workflow ID {workflow.id}) - Unexpected error {err}")


client = civis.APIClient()
user = client.users.list_me()
user_id = f'{user.id}'

success_off = os.getenv('success_off', 'false') == 'true'
failure_off = os.getenv('failure_off', 'false') == 'true'
handle_workflows = os.getenv('handle_workflows', 'false') == 'true'

if success_off is False and failure_off is False:
    raise Exception("Either success_off or failure_off, or both, must be selected")

notifications = {}
turning_off_notifs_str = None
if success_off is True and failure_off is True:
    turning_off_notifs_str = "success and failure"
    notifications.update({'success_on': not success_off})
    notifications.update({'failure_on': not failure_off})
if success_off is True and failure_off is False:
    turning_off_notifs_str = "success"
    notifications.update({'success_on': not success_off})
else:
    turning_off_notifs_str = "failure"
    notifications.update({'failure_on': not success_off})


print(f'Turning off {turning_off_notifs_str} notifications for scripts owned by user id {user_id}')
paginated_processing(client.jobs.list, user_id, process_jobs)

# IMPORTS
print(f'Turning off {turning_off_notifs_str} notifications for imports owned by user id {user_id}')
paginated_processing(client.imports.list, user_id, process_imports)

# WORKFLOWS
if handle_workflows is True:
    print(f'Turning off {turning_off_notifs_str} notifications for workflows owned by user id {user_id}')  # noqa: E501
    paginated_processing(client.workflows.list, user_id, process_workflows)


# Print Failed Jobs
print(f"Failed to turn off notifications for {len(failed_to_update)} jobs")
for failed_job in failed_to_update:
    sys.stderr.write(failed_job + '\n')
