import os
from tinydb import TinyDB, Query
from dotenv import load_dotenv

load_dotenv()

# Creamos o conectamos la base de datos local en un archivo json
# Este archivo aparecerá en la raíz de tu proyecto automáticamente
DB_PATH = "local_db.json"
local_db = TinyDB(DB_PATH)

# Definimos las tablas (que actúan exactamente como tus colecciones de MongoDB)
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
    """Verifica el estado de la base de datos local."""
    try:
        # En una base de datos local, si podemos leer o escribir en el archivo, está operativa
        if os.path.exists(DB_PATH) or local_db:
            print("🚀 Local JSON Database initialized successfully (Bypassed Atlas SSL restriction)!")
        else:
            raise RuntimeError("Database file could not be accessed.")
    except Exception as e:
        print(f"❌ Failed to initialize Local Database: {e}")