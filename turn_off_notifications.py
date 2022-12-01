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

# LM: I'd recommend moving these statements to the top of the file and adding a readme of how to change the success & failure_off variables.
# This looks like it expects env variables to change those params; that's clean for turning this into a reusable script (we could provide one with those vars for CS, make user id a var too?),
# but I'm guessing that it'd be easier for most client users simply change a "true" string to a "false" string.
# Oh, now I see that there are actually variables at the top - cool! Those probably won't transfer to Zendesk though.
client = civis.APIClient()
user = client.users.list_me()
user_id = f'{user.id}'

success_off = os.getenv('success_off', 'false') == 'true'
failure_off = os.getenv('failure_off', 'false') == 'true'

# LM: Oh, interesting! We expect people to use this script to turn off notifications, but I wonder if anyone will want to use it in reverse.
# Might discover this later, but now I'm also wondering if this script could end up turning on notifications for some jobs,
# if say, only success_off is selected, will failure emails then be enabled for all jobs, even if they had been selectively disabled previously?
# Preventing that situation could be a good reason to say that this script only supports turning off notifications.
if success_off == False and failure_off == False:
    raise Exception("Either success_off or failure_off, or both, must be selected")

turning_off_notifs_str = None
if success_off == True and failure_off == True:
    turning_off_notifs_str = "success and failure"
if success_off == True and failure_off == False:
    turning_off_notifs_str = "success"
else:
    turning_off_notifs_str = "failure"

# LM: Hm, so I think this will have the effect which I mentioned previously: we could end up affecting notification which we're not trying to change.
# Preserving the original setting for one or the other might make the logic more complex though, since this is a hash.
# It looks like success_email_addresses, etc are also part of that same hash. Can we simply leave out items we don't wish to modify?
# Ideally, platform would merge the items in the patch request with the existing settings for the unspecified items; I'm not sure if that's how it works or not though.
notifications = {'success_on': not success_off, 'failure_on': not failure_off}


# JOBS
# LM: Could probably say "scripts" instead of "jobs" in this log here I think.
# Hm, I wonder if we could use the list scripts endpoint instead since it looks like those are the only types of job which this particular section handles.
# From the API docs, I'm not positive if that would return custom scripts too though.
# If we can use it, that would get us away from the possibility of users having jobs of other types though.
# (e.g. I expect that some Civis users will still have Media Optimizer jobs; don't think we need to/should modify deprecated job types, but they could muck up the script)
# Might be better to explicitly modify just scripts and imports, rather than try to collect an exhaustive list of different job types to put in client visible code?
# Oh wait, I didn't see the error handling on L92. This might be fine after all, since additional job types won't crash the script.
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

# LM: I wonder if it would be worthwhile to make processing of jobs/workflows configurable via a variable. e.g. HANDLE_WORKFLOWS = true
# Users could just comment out the section they don't want, but it might be a bit friendlier to include that as a top level option.
# WORKFLOWS
print(f'Turning off {turning_off_notifs_str} notifications for workflows owned by user id {user_id}')
workflows = bulk_fetch(client.workflows.list, user_id)
for workflow in workflows:
  try:
    client.workflows.patch(workflow.id, notifications=notifications)
  except Exception as err:
    failed_to_update.append(f" (Workflow ID {workflow.id}) - Unexpected error {err}")

# Print Failed Jobs
print(f"Failed to turn off notifications for {len(failed_to_update) jobs}")
for failed_job in failed_to_update:
  sys.stderr.write(failed_job + '\n')
