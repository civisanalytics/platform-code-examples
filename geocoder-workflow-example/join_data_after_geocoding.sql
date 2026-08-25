/*
Final combined dataset: joins the original filtered record (pre_cass),
the CASS/NCOA standardized output (post_cass), the geocoded output
(post_geocode), and the ACS tract profile into a single table, one row
per retailer.

Join logic:
- pre_cass INNER JOIN post_cass: every row in pre_cass was run through
  CASS, so this should match 1:1 (confirmed earlier: no duplicate
  primary_keys in post_cass, and no unmatched primary_keys between
  the two tables).
- LEFT JOIN to post_geocode: 99 primary_keys never returned usable
  geocode data due to the intermittent geocoding service issue
  reported to Civis Support (see support email re: job 365973532).
  Using LEFT JOIN preserves those 99 retailer records in the final
  dataset, just with null values in the geocode columns, rather than
  dropping them entirely.
- LEFT JOIN to acs_5yr_2024_tract_profile: attaches demographics for the
  census tract each retailer sits in. LEFT because the 99 ungeocoded
  records have no tract, so they have no ACS row either, and they should
  survive with nulls for the same reason as above.

  The join uses the UNSUFFIXED FIPS columns (statefp, countyfp, tractce),
  not the ones ending in 20. The 20 columns are 2020 Census vintage and
  diverge from current codes in Connecticut, which replaced its counties
  with planning regions. Texas is unaffected, but this is the correct
  habit and this file is a client-facing example.

Column selection: primary_key is only pulled once (from pre_cass). The
ACS table's own statefp/countyfp/tractce/census_tract_geoid columns are
deliberately NOT selected, because the geocode output already supplies
those and duplicate column names would fail the CREATE TABLE. Every
other column from all four tables is included as-is.
*/

DROP TABLE IF EXISTS public.historical_snap_retailer_locator_final;

CREATE TABLE public.historical_snap_retailer_locator_final AS (
    SELECT
        pre.primary_key,

        -- from pre_cass: original filtered record (Harris County, TX, active retailers)
        pre.address_line_1,
        pre.address_line_2,
        pre.city,
        pre.state,
        pre.zip,
        pre.store_name,
        pre.store_type,
        pre.zip4,
        pre.county,
        pre.end_date,

        -- Is this retailer's SNAP authorization still current?
        --
        -- Defined once, here, so the map dots, the per-tract counts, and the
        -- report's headline number can never disagree about which retailers
        -- are open.
        --
        -- end_date is a TEXT column and it is not clean: some rows hold a
        -- single space rather than NULL, which is why a plain
        -- `end_date::date` errors with "invalid input syntax for type date".
        -- So each row is tested against a pattern before any cast is
        -- attempted, and anything that matches no pattern is treated as OPEN
        -- rather than dropped. Silently deleting retailers because of a
        -- formatting surprise would be far worse than keeping a few closed
        -- ones: this map is about where food access is thin, and quietly
        -- removing stores makes coverage look worse than it is.
        CASE
            -- No end date, blank, or whitespace: still authorized.
            WHEN NULLIF(TRIM(pre.end_date), '') IS NULL
                THEN TRUE
            -- ISO, e.g. 2019-06-30
            WHEN TRIM(pre.end_date) ~ '^\d{4}-\d{2}-\d{2}'
                THEN LEFT(TRIM(pre.end_date), 10)::date >= CURRENT_DATE
            -- US, e.g. 6/30/2019 or 06/30/2019
            WHEN TRIM(pre.end_date) ~ '^\d{1,2}/\d{1,2}/\d{4}$'
                THEN TO_DATE(TRIM(pre.end_date), 'MM/DD/YYYY') >= CURRENT_DATE
            -- Anything else: keep it, and surface it with the audit query
            -- at the bottom of this file.
            ELSE TRUE
        END AS is_open,

        -- from post_cass: CASS/NCOA standardized + NCOA-updated address fields
        post.std_urb,
        post.std_extadr,
        post.std_secadr,
        post.std_priadr,
        post.std_city,
        post.std_state,
        post.std_zip,
        post.std_zip4,
        post.std_crt,
        post.std_dpbc,
        post.std_lot,
        post.std_lotord,
        post.std_achkdi,
        post.std_errstt,
        post.std_rectyp,
        post.std_dpvftn,
        post.std_dpvstt,
        post.std_county,
        post.std_cntnum,
        post.std_congcd,
        post.std_fipscd,
        post.coa_name,
        post.coa_urb,
        post.coa_secadr,
        post.coa_priadr,
        post.coa_city,
        post.coa_state,
        post.coa_zip,
        post.coa_zip4,
        post.coa_crt,
        post.coa_dpbc,
        post.coa_lot,
        post.coa_lotord,
        post.coa_achkdi,
        post.coa_errstt,
        post.coa_rectyp,
        post.coa_dpvftn,
        post.coa_dpvstt,
        post.coa_county,
        post.coa_cntnum,
        post.coa_congcd,
        post.coa_fipscd,
        post.coa_eff_dt,
        post.coa_movtyp,
        post.coa_retcd,
        post.coa_desc,
        post.ankl_ret,
        post.tec_rec,
        post.tec_listid,
        post.dpv_nostat,
        post.dsf_season,
        post.dsf_vacant,
        post.dsf_busind,
        post.dsf_delvty,
        post.dsf_sequen,
        post.fnl_urb,
        post.fnl_extadr,
        post.fnl_secadr,
        post.fnl_priadr,
        post.fnl_city,
        post.fnl_state,
        post.fnl_zip,
        post.fnl_zip4,
        post.fnl_crt,
        post.fnl_dpbc,
        post.fnl_lot,
        post.fnl_lotord,
        post.fnl_achkdi,
        post.fnl_errstt,
        post.fnl_rectyp,
        post.fnl_dpvftn,
        post.fnl_dpvstt,
        post.fnl_county,
        post.fnl_cntnum,
        post.fnl_congcd,
        post.fnl_fipscd,
        post.mge_dupsta,
        post.mge_dupgro,

        -- from post_geocode: lat/long + census geography (null for the
        -- 99 records that never successfully geocoded)
        geo.civis_latitude,
        geo.civis_longitude,
        geo.civis_geocode_rating,
        geo.provider,
        geo.statefp20,
        geo.countyfp20,
        geo.tractce20,
        geo.blkgrpce20,
        geo.blockce20,
        geo.suffix1ce,
        geo.zcta5ce20,
        geo.uace20,
        geo.pumace20,
        geo.statefp,
        geo.countyfp,
        geo.tractce,
        geo.blkgrpce,
        geo.cousubfp,
        geo.submcdfp,
        geo.estatefp,
        geo.conctyfp,
        geo.placefp,
        geo.aiannhfp,
        geo.aiannhce,
        geo.comptyp,
        geo.trsubfp,
        geo.trsubce,
        geo.anrcfp,
        geo.ttractce,
        geo.tblkgpce,
        geo.elsdlea,
        geo.scsdlea,
        geo.unsdlea,
        geo.sdadmlea,
        geo.cd116fp,
        geo.cd119fp,
        geo.cd120fp,
        geo.cd_current_fp,
        geo.cd_upcoming_fp,
        geo.sldust,
        geo.sldlst,
        geo.csafp,
        geo.cbsafp,
        geo.metdivfp,
        geo.cnectafp,
        geo.nectafp,
        geo.nctadvfp,

        -- The 11-digit tract GEOID, assembled once here so nothing
        -- downstream has to concatenate and zero-pad it again. Null when
        -- the record never geocoded.
        --
        -- The LPAD is not cosmetic. In this database the geocoder's FIPS
        -- columns come back as INTEGER, which means their leading zeros are
        -- already gone: tract 000100 is stored as 100, county 011 as 11.
        -- Casting straight to text would produce '100' and match nothing.
        -- Each part is padded back to its official width - state 2, county
        -- 3, tract 6 - before being concatenated.
        CASE
            WHEN geo.statefp IS NOT NULL
             AND geo.countyfp IS NOT NULL
             AND geo.tractce IS NOT NULL
            THEN LPAD(geo.statefp::text,  2, '0')
              || LPAD(geo.countyfp::text, 3, '0')
              || LPAD(geo.tractce::text,  6, '0')
        END AS tract_geoid,

        -- from acs_5yr_2024_tract_profile: characteristics of the tract this
        -- retailer sits in. These describe the NEIGHBOURHOOD, not the store
        -- and not any individual - a tract is a few thousand residents.
        acs.tract_name,
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

    FROM public.historical_snap_retailer_locator_pre_cass pre
    INNER JOIN public.historical_snap_retailer_locator_post_cass post
        ON pre.primary_key = post.primary_key
    LEFT JOIN public.historical_snap_retailer_locator_post_geocode geo
        ON pre.primary_key = geo.primary_key
    -- The geocoder's FIPS columns are INTEGER in this database and the ACS
    -- profile's are VARCHAR, so each side has to be brought to the same
    -- type AND the same width. Padding matters more than the cast: without
    -- it, tract 000100 arrives as '100' and joins to nothing, and the
    -- failure is silent - you just get null demographics for the affected
    -- retailers rather than an error.
    LEFT JOIN public.acs_5yr_2024_tract_profile acs
        ON  LPAD(geo.statefp::text,  2, '0') = LPAD(acs.statefp::text,  2, '0')
        AND LPAD(geo.countyfp::text, 3, '0') = LPAD(acs.countyfp::text, 3, '0')
        AND LPAD(geo.tractce::text,  6, '0') = LPAD(acs.tractce::text,  6, '0')
);

/*
Check the join actually landed before moving on. If leading zeros were the
problem, this returns a large number of retailers with coordinates but no
demographics:

    SELECT
        COUNT(*)                                              AS total,
        COUNT(civis_latitude)                                 AS geocoded,
        COUNT(tract_geoid)                                    AS has_tract,
        COUNT(total_population)                               AS has_acs,
        COUNT(tract_geoid) - COUNT(total_population)          AS tract_but_no_acs
    FROM public.historical_snap_retailer_locator_final;

`tract_but_no_acs` should be 0, or very close to it. Anything large means
the FIPS columns still aren't lining up.


Also check what end_date actually contains, since is_open above treats any
unrecognized format as open. If a real format shows up here that isn't ISO
or MM/DD/YYYY, add a branch for it:

    SELECT
        CASE
            WHEN NULLIF(TRIM(end_date), '') IS NULL              THEN 'null or blank'
            WHEN TRIM(end_date) ~ '^\d{4}-\d{2}-\d{2}'           THEN 'ISO date'
            WHEN TRIM(end_date) ~ '^\d{1,2}/\d{1,2}/\d{4}$'      THEN 'US date'
            ELSE 'UNRECOGNIZED -> treated as open'
        END AS end_date_shape,
        COUNT(*),
        MIN(end_date) AS example
    FROM public.historical_snap_retailer_locator_final
    GROUP BY 1 ORDER BY 2 DESC;
*/