"""One-off import of a legacy TinyDB ``local_db.json`` into the SQL database.

Usage: python -m scripts.import_tinydb [path/to/local_db.json]
Targets whatever ``DATABASE_URL`` points to. Run it once on an empty database.
"""

import json
import sys

from app.database import (
    carts_collection,
    companies_collection,
    customers_collection,
    init_database,
    orders_collection,
    products_collection,
    sessions_collection,
    targets_collection,
    users_collection,
)

TABLES = {
    "test_sessions": sessions_collection,
    "products": products_collection,
    "customers": customers_collection,
    "orders": orders_collection,
    "carts": carts_collection,
    "companies": companies_collection,
    "users": users_collection,
    "targets": targets_collection,
}


def main(path: str) -> None:
    init_database()
    with open(path, encoding="utf-8") as handle:
        legacy = json.load(handle)
    for table, collection in TABLES.items():
        records = list(legacy.get(table, {}).values())
        if records:
            collection.insert_multiple(records)
        print(f"{table}: {len(records)} records imported")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "local_db.json")
