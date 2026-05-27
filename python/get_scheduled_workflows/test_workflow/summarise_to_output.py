import os

import civis

TABLE_NAME = os.environ["TABLE_NAME"]
DATABASE = "redshift-general"

customers = civis.io.read_civis(
    table="scratch.test_customers",
    database=DATABASE,
    use_pandas=True,
)
orders = civis.io.read_civis(
    table="scratch.test_orders",
    database=DATABASE,
    use_pandas=True,
)

merged = orders.merge(customers, on="customer_id")
summary = (
    merged.groupby(["customer_id", "name", "email"])
    .agg(total_amount=("amount", "sum"), order_count=("order_id", "count"))
    .reset_index()
)

civis.io.dataframe_to_civis(
    summary,
    database=DATABASE,
    table=f"scratch.{TABLE_NAME}",
    existing_table_rows="drop",
)

print(f"Written {len(summary)} rows to scratch.{TABLE_NAME}")
