DROP TABLE IF EXISTS public.historical_snap_retailer_locator_for_geocode;
CREATE TABLE public.historical_snap_retailer_locator_for_geocode AS (
    SELECT
        primary_key,
        TRIM(
            fnl_priadr ||
            CASE WHEN NULLIF(TRIM(fnl_secadr), '') IS NOT NULL THEN ' ' || fnl_secadr ELSE '' END
        ) AS address,
        fnl_city AS city,
        fnl_state AS state,
        CASE
            WHEN NULLIF(TRIM(fnl_zip4), '') IS NOT NULL THEN fnl_zip || '-' || fnl_zip4
            ELSE fnl_zip
        END AS zip
    FROM public.historical_snap_retailer_locator_post_cass
)