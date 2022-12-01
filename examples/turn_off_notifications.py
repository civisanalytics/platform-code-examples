import civis
import os
import sys

def bulk_fetch(api_method, user_id):
  page_num = 1
  jobs = []
  # LM: Collecting all the user's jobs up front won't be the most memory efficient, not sure if that's a large enough concern to refactor this or not.
  # Maybe we should check how many jobs some of our power users have? What was the memory usage of this script when you were running it?
  while True:
    results = api_method(author=user_id, page_num=page_num)
    if len(results) == 0:
        break
    jobs += results
    page_num+=1

  return jobs

client = civis.APIClient()
user = client.users.list_me()
user_id = f'{user.id}'

success_off = os.getenv('success_off', 'false') == 'true'
failure_off = os.getenv('failure_off', 'false') == 'true'
handle_workflows = os.getenv('handle_workflows', 'false') == 'true'

if success_off == False and failure_off == False:
    raise Exception("Either success_off or failure_off, or both, must be selected")

notifications = {}
turning_off_notifs_str = None
if success_off == True and failure_off == True:
    turning_off_notifs_str = "success and failure"
    notifications.update({'success_on': not success_off})
    notifications.update({'failure_on': not failure_off})
if success_off == True and failure_off == False:
    turning_off_notifs_str = "success"
    notifications.update({'success_on': not success_off})
else:
    turning_off_notifs_str = "failure"
    notifications.update({'failure_on': not success_off})

print(f'Turning off {turning_off_notifs_str} notifications for scripts owned by user id {user_id}')
jobs = bulk_fetch(client.jobs.list, user_id)

failed_to_update = []
jobs_to_skip = ['JobTypes::Query', 'JobTypes::SingleTableScanner', 'JobTypes::Snapshot', 'JobTypes::Import']
for job in jobs:
  if job.type in jobs_to_skip:
    continue
  try:
    if job.from_template_id is not None:
      client.scripts.patch_custom(job.id, notifications=notifications)

    # I think this should also be an elif?
    if job.type == 'JobTypes::ContainerDocker':
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
      raise Exception(f"Unknown job type")

  except Exception as err:
      failed_to_update.append(f" ({job.type} ID {job.id}) - Unexpected error {err}")


# IMPORTS
print(f'Turning off {turning_off_notifs_str} notifications for imports owned by user id {user_id}')
imports = bulk_fetch(client.imports.list, user_id)
for import_job in imports:
  try:
    client.imports.put(import_job.id, import_job.name, import_job.sync_type, import_job.is_outbound, notifications=notifications)
  except Exception as err:
    failed_to_update.append(f" (Import ID {import_job.id}) - Unexpected error {err}")


if handle_workflows == True:
  # WORKFLOWS
  print(f'Turning off {turning_off_notifs_str} notifications for workflows owned by user id {user_id}')
  workflows = bulk_fetch(client.workflows.list, user_id)
  for workflow in workflows:
    try:
      client.workflows.patch(workflow.id, notifications=notifications)
    except Exception as err:
      failed_to_update.append(f" (Workflow ID {workflow.id}) - Unexpected error {err}")


# Print Failed Jobs
print(f"Failed to turn off notifications for {len(failed_to_update)} jobs")
for failed_job in failed_to_update:
  sys.stderr.write(failed_job + '\n')
