"""
Load the Olist e-commerce CSVs into a Postgres OLTP database.

Loads tables in dependency order so foreign keys resolve correctly:
product_category_translation -> products -> sellers -> customers ->
geolocation -> orders -> order_items -> order_payments -> order_reviews

Usage:
    python oltp/load_data.py                       # uses .env (local Docker Postgres)
    python oltp/load_data.py --env-file .env.supabase   # loads into Supabase instead
"""

import argparse
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / "raw_data"

# Each entry describes how to load one CSV into its matching table.
# Order matters: parents must load before children (FK dependencies).
LOAD_PLAN = [
    {
        "csv": "product_category_name_translation.csv",
        "table": "product_category_translation",
        "parse_dates": None,
        "rename": None,
    },
    {
        "csv": "olist_products_dataset.csv",
        "table": "products",
        "parse_dates": None,
        # Fix the typos ("lenght") present in the raw Olist column names
        "rename": {
            "product_name_lenght": "product_name_length",
            "product_description_lenght": "product_description_length",
        },
    },
    {
        "csv": "olist_sellers_dataset.csv",
        "table": "sellers",
        "parse_dates": None,
        "rename": None,
    },
    {
        "csv": "olist_customers_dataset.csv",
        "table": "customers",
        "parse_dates": None,
        "rename": None,
    },
    {
        "csv": "olist_geolocation_dataset.csv",
        "table": "geolocation",
        "parse_dates": None,
        "rename": None,
    },
    {
        "csv": "olist_orders_dataset.csv",
        "table": "orders",
        "parse_dates": [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
        "rename": None,
    },
    {
        "csv": "olist_order_items_dataset.csv",
        "table": "order_items",
        "parse_dates": ["shipping_limit_date"],
        "rename": None,
    },
    {
        "csv": "olist_order_payments_dataset.csv",
        "table": "order_payments",
        "parse_dates": None,
        "rename": None,
    },
    {
        "csv": "olist_order_reviews_dataset.csv",
        "table": "order_reviews",
        "parse_dates": ["review_creation_date", "review_answer_timestamp"],
        "rename": None,
        # The raw Olist file has duplicate review_id values (a handful of
        # reviews got recorded twice); keep the last occurrence so the
        # primary key constraint doesn't reject the second insert.
        "dedup_subset": ["review_id"],
    },
]


def load_csv_to_table(engine, plan: dict, chunksize: int = 5000) -> int:
    """Read one CSV and append it into its matching Postgres table.

    Returns the number of rows loaded.
    """
    csv_path = DATA_DIR / plan["csv"]
    if not csv_path.exists():
        raise FileNotFoundError(f"Expected CSV not found: {csv_path}")

    df = pd.read_csv(csv_path, parse_dates=plan["parse_dates"])

    if plan["rename"]:
        df = df.rename(columns=plan["rename"])

    # Postgres rejects NaN in integer columns (e.g. product_name_length) and
    # NaT in timestamp columns (e.g. orders without an approval date yet).
    # Converting to None lets psycopg2 send a proper SQL NULL instead.
    df = df.astype(object).where(pd.notnull(df), None)

    if plan.get("dedup_subset"):
        before = len(df)
        df = df.drop_duplicates(subset=plan["dedup_subset"], keep="last")
        dropped = before - len(df)
        if dropped:
            print(f"[dropped {dropped} duplicate rows] ", end="")

    df.to_sql(
        plan["table"],
        engine,
        if_exists="append",  # tables already exist from schema.sql, just insert
        index=False,
        method="multi",
        chunksize=chunksize,
    )
    return len(df)


def reset_tables(engine) -> None:
    """Truncate all tables so the script can be re-run safely from scratch.

    RESTART IDENTITY resets the geolocation_id sequence; CASCADE lets us list
    tables in any order regardless of FK dependencies.
    """
    tables = [plan["table"] for plan in LOAD_PLAN]
    with engine.begin() as conn:
        conn.exec_driver_sql(
            f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE;"
        )


def patch_missing_categories(engine) -> None:
    """Insert product categories that exist in products.csv but are missing
    from product_category_name_translation.csv (a known gap in the Olist
    dataset, e.g. 'pc_gamer' has no official English translation).

    Without this, loading `products` fails with a ForeignKeyViolation.
    """
    products_path = DATA_DIR / "olist_products_dataset.csv"
    products_df = pd.read_csv(products_path, usecols=["product_category_name"])

    with engine.connect() as conn:
        existing = pd.read_sql(
            "SELECT product_category_name FROM product_category_translation", conn
        )["product_category_name"]

    all_categories = set(products_df["product_category_name"].dropna())
    missing = sorted(all_categories - set(existing))

    if not missing:
        return

    print(f"  (patching {len(missing)} categories missing from translation table: {missing})")
    missing_df = pd.DataFrame(
        {
            "product_category_name": missing,
            # No official English translation exists for these; reuse the
            # Portuguese name as a placeholder so the FK constraint is satisfied.
            "product_category_name_english": missing,
        }
    )
    missing_df.to_sql(
        "product_category_translation", engine, if_exists="append", index=False
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path (relative to project root) to the .env file with DB credentials. "
        "Use --env-file .env.supabase to load into Supabase instead of local Docker.",
    )
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / args.env_file, override=True)

    db_user = os.environ["POSTGRES_USER"]
    db_password = os.environ["POSTGRES_PASSWORD"]
    db_name = os.environ["POSTGRES_DB"]
    db_port = os.environ["POSTGRES_PORT"]
    # Defaults to localhost for local Docker Postgres; set POSTGRES_HOST in
    # .env.supabase (or similar) to point at a remote host instead.
    db_host = os.environ.get("POSTGRES_HOST", "localhost")
    # Supabase requires SSL; local Docker Postgres doesn't need it.
    sslmode = os.environ.get("POSTGRES_SSLMODE")

    connection_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    if sslmode:
        connection_url += f"?sslmode={sslmode}"

    engine = create_engine(connection_url)

    print(f"Target: {db_host}:{db_port}/{db_name} (env file: {args.env_file})")
    print("Resetting tables...")
    reset_tables(engine)

    print(f"Loading data from {DATA_DIR} into database '{db_name}'...\n")

    for plan in LOAD_PLAN:
        table = plan["table"]
        print(f"  -> loading {table} ...", end=" ", flush=True)
        rows = load_csv_to_table(engine, plan)
        print(f"{rows:,} rows")

        if table == "product_category_translation":
            patch_missing_categories(engine)

    print("\nDone. Row counts per table:")
    with engine.connect() as conn:
        for plan in LOAD_PLAN:
            table = plan["table"]
            count = conn.exec_driver_sql(f"SELECT COUNT(*) FROM {table}").scalar()
            print(f"  {table:<30} {count:>10,}")


if __name__ == "__main__":
    main()