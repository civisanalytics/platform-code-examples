import civis

client = civis.APIClient()


_LOG = civis.civis_logger()

_CURRENT_USER = client.users.get_me()
_ORG_NAME = _CURRENT_USER.organization_name
_ORG_ID = client.groups.get(_CURRENT_USER.primary_group_id).organization_id

_LOG.info(f"Fetching Civis AI credit usage for {_ORG_NAME}")

_LOG.info("Checking for AI credit limit...")
limit_found = False

llm_limit = client.usage_limits.list_llm(organization_id=_ORG_ID)

for l in llm_limit:
    if l.organization_id == _ORG_ID:
        limit_found = True
        _LOG.info(f"Found limit for Organization ID {_ORG_ID}")
        _LOG.info(f"Credit usage limit: {l.hard_limit}")
        break

_LOG.info("Checking current usage...")
llm_usage = client.usage.get_llm_organization_summary(org_id=_ORG_ID)
_LOG.info(f"{llm_usage.credits} credits used so far this month.")
