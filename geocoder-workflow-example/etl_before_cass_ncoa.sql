/*
Prepares the pre-CASS input table for Harris County, TX SNAP retailers.

This table is scoped to CURRENTLY ACTIVE retailers only (blank/null
end_date). end_date marks the day a retailer's SNAP authorization
ended, so a blank end_date means the retailer is still authorized
today. An earlier version of this query filtered on
end_date >= '2024-01-01', which was backwards, it captured retailers
that had recently been deauthorized rather than the ones still active.

Filtering to blank end_date also resolves a duplicate primary_key
issue: Record_ID is not guaranteed unique in the raw historical table,
since some retailers have multiple rows spanning different
authorization periods (e.g. authorized, deauthorized, then
reauthorized later, each with its own end_date). Limiting to blank
end_date leaves only the one active row per retailer, since a
retailer can only have one open (blank) authorization period at a
time. Confirmed via a GROUP BY / HAVING COUNT(*) > 1 check that both
primary_key and full address are unique in the resulting table
(814 rows total).
*/

-- Drop first so this script can be rerun cleanly without erroring
-- out on "table already exists"
DROP TABLE IF EXISTS public.historical_snap_retailer_locator_pre_cass;

create table public.historical_snap_retailer_locator_pre_cass as (
SELECT DISTINCT
    "Record_ID" AS primary_key,
    -- Street_Number and Street_Name are combined into one field here
    -- because the downstream USPS/CASS address mapping expects a
    -- single "Address Line 1" field, not separate number/name columns.
    LOWER(TRIM("Street_Number" || ' ' || "Street_Name")) AS address_line_1,
    LOWER("Additional_Address") AS address_line_2,
    LOWER("City") AS city,
    LOWER("State") AS state,
    "Zip_Code" AS zip,
    LOWER("Store_Name") AS store_name,
    LOWER("Store_Type") AS store_type,
    LOWER("Zip4") AS zip4,
    LOWER("County") AS county,
    LOWER("End_Date") AS end_date
FROM public.historical_snap_retailer_locator_data_20052025
WHERE LOWER("State") = 'tx'
    AND LOWER("County") = 'harris'
    AND (
        -- Blank/null end_date = still active. Do not filter for a
        -- recent end_date here; that would select recently
        -- deauthorized retailers instead of currently active ones.
        "End_Date" IS NULL
        OR TRIM("End_Date") = ''
    )
);