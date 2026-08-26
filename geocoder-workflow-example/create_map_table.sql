/*
Tract-level companion to historical_snap_retailer_locator_final.

Why this exists: the final retailer table is one row per store, so ACS
values only appear for tracts that happen to contain a retailer. The map
needs the opposite - one row per tract in Harris County, including the
tracts with no retailer in them at all, which are precisely the ones the
report is meant to draw attention to. Aggregating the retailer table
would silently drop them.

Produces one row per Harris County census tract with:
  - the tract's simplified boundary, ready to hand straight to a browser
  - every ACS measure for that tract
  - a count of currently authorized SNAP retailers inside it

After this runs, the report script does no joining at all. It reads this
table for the polygons and the retailer table for the dots.

Geometry notes:
  - ST_SimplifyPreserveTopology, not plain ST_Simplify. Plain simplify
    thins each polygon independently, so shared borders between
    neighbouring tracts stop matching and the map fills with slivers and
    gaps. The tolerance is in degrees; 0.0001 is roughly 11 metres, which
    is far finer than a county-wide map can show.
  - ST_AsGeoJSON's second argument caps coordinate precision at 5 decimal
    places, about 1 metre. The default is 15, which is nanometre
    precision and roughly doubles the size of the output for nothing.
  - Emitting GeoJSON rather than WKT means the browser can use it
    directly instead of parsing WKT in JavaScript.

Retailer counts:
  Tract membership comes from the geocoder's own tract assignment
  (statefp + countyfp + tractce), not from a spatial join. The geocoder
  already worked out which tract each point falls in, so re-deriving it
  with ST_Contains would be slower and could disagree with the tract
  columns sitting in the same row.

  Closed retailers are excluded from the count. This file is historical
  and includes stores whose SNAP authorization has ended; counting those
  as food access would overstate coverage in exactly the tracts this
  report exists to find.

  The open/closed rule itself is NOT defined here. It is the `is_open`
  column built by 01_build_final_retailer_table.sql, so that this count,
  the dots on the map, and the report's headline number all derive from
  one definition. If the rule needs changing, change it there and rerun
  both scripts.
*/

DROP TABLE IF EXISTS public.harris_county_tract_map_profile;

CREATE TABLE public.harris_county_tract_map_profile AS (

    WITH open_retailers AS (
        -- One row per currently authorized, successfully geocoded retailer,
        -- reduced to just the tract it sits in.
        SELECT tract_geoid
        FROM public.historical_snap_retailer_locator_final
        WHERE tract_geoid IS NOT NULL
          AND civis_latitude IS NOT NULL
          AND civis_longitude IS NOT NULL
          AND is_open
    ),

    retailer_counts AS (
        SELECT tract_geoid, COUNT(*) AS store_count
        FROM open_retailers
        GROUP BY tract_geoid
    )

    SELECT
        t.geoid          AS tract_geoid,
        t.statefp,
        t.countyfp,
        t.tractce,
        acs.tract_name,

        ST_AsGeoJSON(
            ST_SimplifyPreserveTopology(t.geom, 0.0001),
            5
        ) AS geom_json,

        COALESCE(rc.store_count, 0) AS store_count,

        acs.total_population,
        acs.median_age,
        acs.pct_under_18,
        acs.pct_65_plus,
        acs.median_household_income,
        acs.per_capita_income,
        acs.pct_below_poverty,
        acs.pct_in_labor_force,
        acs.pct_employed,
        acs.pct_unemployed,
        acs.pct_bachelors_or_higher,
        acs.pct_white_nh,
        acs.pct_black_nh,
        acs.pct_asian_nh,
        acs.pct_hispanic,
        acs.pct_other_race_nh,
        acs.total_households,
        acs.pct_family_households,
        acs.pct_families_with_children,
        acs.pct_single_parent_families,
        acs.avg_household_size,
        acs.pct_owner_occupied,
        acs.median_home_value,
        acs.median_gross_rent,
        acs.pct_housing_cost_burdened,
        acs.pct_limited_english_households,
        acs.pct_with_disability,
        acs.pct_broadband,
        acs.pct_veterans,
        acs.pct_same_house_1yr,
        acs.pct_moved_from_different_state

    FROM public.tx_2024_tiger_shapefile t

    -- LEFT so a tract with no ACS row still draws on the map, shaded as
    -- "No data", rather than leaving a hole in the county outline.
    LEFT JOIN public.acs_5yr_2024_tract_profile acs
           ON t.geoid = acs.census_tract_geoid

    -- LEFT so the 225-odd tracts containing no retailer come through with
    -- a count of zero instead of disappearing.
    LEFT JOIN retailer_counts rc
           ON t.geoid = rc.tract_geoid

    WHERE t.statefp = '48'
      AND t.countyfp = '201'
);