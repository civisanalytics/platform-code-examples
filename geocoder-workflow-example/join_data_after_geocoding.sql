/*
Final combined dataset: joins the original filtered record (pre_cass),
the CASS/NCOA standardized output (post_cass), and the geocoded
output (post_geocode) into a single table, one row per retailer.

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

Column selection: primary_key is only pulled once (from pre_cass).
There are no other overlapping column names across the three tables,
so every remaining column from all three is included as-is.
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
        geo.nctadvfp

    FROM public.historical_snap_retailer_locator_pre_cass pre
    INNER JOIN public.historical_snap_retailer_locator_post_cass post
        ON pre.primary_key = post.primary_key
    LEFT JOIN public.historical_snap_retailer_locator_post_geocode geo
        ON pre.primary_key = geo.primary_key
);