-- =============================================================================
-- QUERY: Individual Tables and Views Inventory
-- =============================================================================
-- This query returns a comprehensive list of all tables and views in the 
-- Redshift database, along with their size and row count information.
-- 
-- USE CASE: Database inventory, storage analysis, identifying large tables,
--           finding unused objects, or auditing database contents.
--
-- OUTPUT COLUMNS:
--   schema_name  - The schema containing the object
--   table_name   - The name of the table or view
--   object_type  - Either 'table' or 'view'
--   size_mb      - Size in megabytes (0 for views since they don't store data)
--   size_gb      - Size in gigabytes (0 for views)
--   row_count    - Number of rows (0 for views)
--
-- NOTE: Views show 0 for size and row_count because views are stored queries,
--       not physical data. They don't consume storage space.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- PART 1: Get all tables from svv_table_info
-- -----------------------------------------------------------------------------
-- svv_table_info is a Redshift system view that contains information about
-- all user-defined tables including their size and row counts.
-- We exclude system schemas that contain internal Redshift objects.
-- -----------------------------------------------------------------------------
SELECT 
    schema_name::VARCHAR(256),
    table_name::VARCHAR(256),
    object_type::VARCHAR(10),
    size_mb::NUMERIC(18,2),
    size_gb::NUMERIC(18,2),
    row_count::BIGINT
FROM (
    SELECT 
        "schema" AS schema_name,
        "table" AS table_name,
        'table' AS object_type,
        ROUND(size::NUMERIC, 2) AS size_mb,
        ROUND(size::NUMERIC / 1024, 2) AS size_gb,
        tbl_rows AS row_count
    FROM svv_table_info
    WHERE "schema" NOT IN (
        'pg_catalog',        -- PostgreSQL system catalog
        'information_schema', -- SQL standard metadata schema
        'pg_internal',       -- Redshift internal schema
        'pg_auto_copy',      -- Redshift auto-copy schema
        'pg_automv',         -- Redshift auto materialized views
        'pg_mv',             -- Redshift materialized views metadata
        'pg_s3'              -- Redshift Spectrum S3 schema
    )
) t

UNION ALL

-- -----------------------------------------------------------------------------
-- PART 2: Get all views from pg_views
-- -----------------------------------------------------------------------------
-- pg_views is a system catalog that lists all views in the database.
-- Views don't have size or row count since they're just stored SQL queries
-- that execute against underlying tables when called.
-- -----------------------------------------------------------------------------
SELECT 
    schema_name::VARCHAR(256),
    table_name::VARCHAR(256),
    object_type::VARCHAR(10),
    size_mb::NUMERIC(18,2),
    size_gb::NUMERIC(18,2),
    row_count::BIGINT
FROM (
    SELECT 
        schemaname AS schema_name,
        viewname AS table_name,
        'view' AS object_type,
        0 AS size_mb,
        0 AS size_gb,
        0 AS row_count
    FROM pg_views
    WHERE schemaname NOT IN (
        'pg_catalog',
        'information_schema',
        'pg_internal',
        'pg_auto_copy',
        'pg_automv',
        'pg_mv',
        'pg_s3'
    )
) v

-- -----------------------------------------------------------------------------
-- Sort by schema, then object type (tables first), then object name
-- -----------------------------------------------------------------------------
ORDER BY 1, 3, 2;
