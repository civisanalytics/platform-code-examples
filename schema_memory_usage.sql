-- =============================================================================
-- QUERY: Schema-Level Storage Summary
-- =============================================================================
-- This query provides a summary of each schema in the database, showing
-- the number of tables, views, total storage size, and row counts.
-- It also flags schemas that are empty or contain only views.
--
-- USE CASE: Database capacity planning, identifying unused schemas,
--           storage allocation review, schema cleanup decisions.
--
-- OUTPUT COLUMNS:
--   schema_name   - The name of the schema
--   table_count   - Number of tables in the schema
--   view_count    - Number of views in the schema
--   size_mb       - Total size of all tables in MB
--   size_gb       - Total size of all tables in GB
--   total_rows    - Sum of all rows across all tables
--   schema_status - 'empty', 'views_only', or 'has_tables'
--
-- NOTE: The schema_status column helps identify schemas that may be
--       candidates for cleanup (empty) or that only contain view definitions.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- CTE 1: all_schemas
-- -----------------------------------------------------------------------------
-- Get a complete list of all user-created schemas from pg_namespace.
-- This ensures we capture schemas that might be empty or only have views,
-- which wouldn't appear in svv_table_info.
-- -----------------------------------------------------------------------------
WITH all_schemas AS (
    SELECT nspname AS schema_name
    FROM pg_namespace
    WHERE nspname NOT IN (
        'pg_catalog',        -- PostgreSQL system catalog
        'information_schema', -- SQL standard metadata schema
        'pg_internal',       -- Redshift internal schema
        'pg_auto_copy',      -- Redshift auto-copy schema
        'pg_automv',         -- Redshift auto materialized views
        'pg_mv',             -- Redshift materialized views metadata
        'pg_s3'              -- Redshift Spectrum S3 schema
    )
    AND nspname NOT LIKE 'pg_temp%'   -- Exclude temporary schemas
    AND nspname NOT LIKE 'pg_toast%'  -- Exclude TOAST storage schemas
),

-- -----------------------------------------------------------------------------
-- CTE 2: table_sizes
-- -----------------------------------------------------------------------------
-- Aggregate table statistics by schema from svv_table_info.
-- This gives us the count of tables, total size, and total rows per schema.
-- Schemas with no tables won't appear here (handled by LEFT JOIN later).
-- -----------------------------------------------------------------------------
table_sizes AS (
    SELECT 
        "schema" AS schema_name,
        COUNT(DISTINCT "table") AS table_count,
        ROUND(SUM(size)::NUMERIC, 2) AS size_mb,
        ROUND(SUM(size)::NUMERIC / 1024, 2) AS size_gb,
        ROUND(SUM(tbl_rows)::NUMERIC, 0) AS total_rows
    FROM svv_table_info
    WHERE "schema" NOT IN ('pg_catalog', 'information_schema', 'pg_internal')
    GROUP BY "schema"
),

-- -----------------------------------------------------------------------------
-- CTE 3: view_counts
-- -----------------------------------------------------------------------------
-- Count views per schema using pg_class (relkind = 'v' indicates a view).
-- This is joined with pg_namespace to get the schema name.
-- Schemas with no views won't appear here (handled by LEFT JOIN later).
-- -----------------------------------------------------------------------------
view_counts AS (
    SELECT 
        n.nspname AS schema_name,
        COUNT(*) AS view_count
    FROM pg_class c
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE c.relkind = 'v'  -- 'v' = view in pg_class
    AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_internal')
    GROUP BY n.nspname
)

-- -----------------------------------------------------------------------------
-- Main SELECT: Join all CTEs and calculate schema_status
-- -----------------------------------------------------------------------------
-- LEFT JOINs ensure we get all schemas even if they have no tables or views.
-- COALESCE converts NULLs to 0 for schemas missing from table_sizes or view_counts.
-- The CASE statement determines the schema_status based on object counts.
-- -----------------------------------------------------------------------------
SELECT 
    s.schema_name,
    COALESCE(t.table_count, 0) AS table_count,
    COALESCE(v.view_count, 0) AS view_count,
    COALESCE(t.size_mb, 0) AS size_mb,
    COALESCE(t.size_gb, 0) AS size_gb,
    COALESCE(t.total_rows, 0) AS total_rows,
    CASE 
        WHEN COALESCE(t.table_count, 0) = 0 AND COALESCE(v.view_count, 0) = 0 THEN 'empty'
        WHEN COALESCE(t.table_count, 0) = 0 AND COALESCE(v.view_count, 0) > 0 THEN 'views_only'
        ELSE 'has_tables'
    END AS schema_status
FROM all_schemas s
LEFT JOIN table_sizes t ON s.schema_name = t.schema_name
LEFT JOIN view_counts v ON s.schema_name = v.schema_name
ORDER BY s.schema_name ASC;
