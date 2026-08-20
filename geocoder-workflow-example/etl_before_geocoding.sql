/*
Reformats the CASS/NCOA output into the column names and structure
the Geocoder enhancement expects: address, city, state, zip.

There is no built-in Civis Platform step that maps CASS/NCOA output
directly into Geocoder input, so this manual reformat is required
every time between the two jobs (flagged to Civis Support as a
product gap).

Uses the fnl_* columns rather than std_* because fnl_* reflects the
address AFTER any NCOA (National Change of Address) updates were
applied, which is the most current version of the address on file.
std_* would give the pre-NCOA standardized version instead.
*/

DROP TABLE IF EXISTS public.historical_snap_retailer_locator_for_geocode;

CREATE TABLE public.historical_snap_retailer_locator_for_geocode AS (
    SELECT
        primary_key,
        -- fnl_priadr (primary address: street number + name) and
        -- fnl_secadr (secondary address: suite/unit) are concatenated
        -- into one address string, since the Geocoder tool only
        -- accepts a single address field, not separate line 1/line 2
        -- columns. TIGER/Line geocoding works at the street level, so
        -- the suite/unit doesn't affect the geocode result, but it's
        -- kept here so the address string stays complete for reference.
        TRIM(
            fnl_priadr ||
            CASE WHEN NULLIF(TRIM(fnl_secadr), '') IS NOT NULL THEN ' ' || fnl_secadr ELSE '' END
        ) AS address,
        fnl_city AS city,
        fnl_state AS state,
        -- fnl_zip and fnl_zip4 are combined into a single 9-digit zip
        -- (zip+4) when the +4 extension is available, for more precise
        -- geocoding. Falls back to the 5-digit zip if no +4 is present.
        CASE
            WHEN NULLIF(TRIM(fnl_zip4), '') IS NOT NULL THEN fnl_zip || '-' || fnl_zip4
            ELSE fnl_zip
        END AS zip
    FROM public.historical_snap_retailer_locator_post_cass
)