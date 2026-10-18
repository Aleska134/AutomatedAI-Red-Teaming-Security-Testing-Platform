import os
from tinydb import TinyDB, Query
from dotenv import load_dotenv

load_dotenv()

# Local JSON database. Configurable so tests and deployments never share (or
# wipe) the developer's working data.
DB_PATH = os.getenv("DB_PATH", "local_db.json")
local_db = TinyDB(DB_PATH)

# Tables (equivalent to document collections).
sessions_collection = local_db.table("test_sessions")
products_collection = local_db.table("products")
customers_collection = local_db.table("customers")
orders_collection = local_db.table("orders")
carts_collection = local_db.table("carts")

# Multi-tenant platform tables: registered companies (tenants), their user
# accounts, and the external chatbot targets each company has onboarded.
companies_collection = local_db.table("companies")
users_collection = local_db.table("users")
targets_collection = local_db.table("targets")

async def ping_database():
    """Check that the local database is reachable."""
    try:
        if os.path.exists(DB_PATH) or local_db:
            print(f"🚀 Local JSON database ready at {DB_PATH}")
        else:
            raise RuntimeError("Database file could not be accessed.")
    except Exception as e:
        print(f"❌ Failed to initialize Local Database: {e}")