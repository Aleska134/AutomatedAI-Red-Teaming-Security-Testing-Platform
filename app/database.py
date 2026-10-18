"""SQL persistence layer (SQLModel).

``DATABASE_URL`` selects the backend: SQLite locally (default ``local.db``)
and Postgres in production (e.g. Neon). Each table stores the full record as
JSON in ``data`` plus the fields we look records up by as real, indexed
columns. Services keep working with plain dicts through the small
``Collection`` API below, and every write runs in its own transaction, so
concurrent requests can no longer corrupt the store.
"""

import os
from typing import Any, Optional

from dotenv import load_dotenv
from sqlalchemy import JSON, Column, delete
from sqlmodel import Field, Session, SQLModel, create_engine, select

load_dotenv()


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///local.db")
    # Heroku still exposes the legacy scheme, which SQLAlchemy rejects.
    # SQLAlchemy now defaults plain "postgresql://" to psycopg 3; we ship psycopg2.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


DATABASE_URL = _database_url()
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)


def _json_column() -> Any:
    return Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class SessionRecord(SQLModel, table=True):
    __tablename__ = "test_sessions"
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: Optional[str] = Field(default=None, index=True)
    session_id: Optional[str] = Field(default=None, index=True)
    company_id: Optional[str] = Field(default=None, index=True)
    data: dict = _json_column()


class ProductRecord(SQLModel, table=True):
    __tablename__ = "products"
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: str = Field(unique=True, index=True)
    data: dict = _json_column()


class CustomerRecord(SQLModel, table=True):
    __tablename__ = "customers"
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: str = Field(unique=True, index=True)
    data: dict = _json_column()


class OrderRecord(SQLModel, table=True):
    __tablename__ = "orders"
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: str = Field(index=True)
    customer_id: str = Field(index=True)
    data: dict = _json_column()


class CartRecord(SQLModel, table=True):
    __tablename__ = "carts"
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: str = Field(unique=True, index=True)
    data: dict = _json_column()


class CompanyRecord(SQLModel, table=True):
    __tablename__ = "companies"
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: str = Field(unique=True, index=True)
    data: dict = _json_column()


class UserRecord(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    company_id: str = Field(index=True)
    reset_token: Optional[str] = Field(default=None, index=True)
    data: dict = _json_column()


class TargetRecord(SQLModel, table=True):
    __tablename__ = "targets"
    id: Optional[int] = Field(default=None, primary_key=True)
    target_id: str = Field(unique=True, index=True)
    company_id: str = Field(index=True)
    data: dict = _json_column()


class Collection:
    """Dict-in/dict-out access to one table, filtered by its key columns."""

    def __init__(self, model: type[SQLModel]):
        self.model = model
        self.keys = [
            name for name in model.model_fields if name not in ("id", "data")
        ]

    def _row(self, record: dict[str, Any]) -> SQLModel:
        keys = {key: record.get(key) for key in self.keys}
        return self.model(**keys, data=dict(record))

    def _where(self, filters: dict[str, Any]) -> list[Any]:
        unknown = set(filters) - set(self.keys)
        if unknown:
            raise ValueError(f"Cannot filter {self.model.__name__} by {unknown}.")
        return [getattr(self.model, key) == value for key, value in filters.items()]

    def insert(self, record: dict[str, Any]) -> None:
        self.insert_multiple([record])

    def insert_multiple(self, records: list[dict[str, Any]]) -> None:
        with Session(engine) as session:
            session.add_all(self._row(record) for record in records)
            session.commit()

    def all(self) -> list[dict[str, Any]]:
        with Session(engine) as session:
            rows = session.exec(select(self.model).order_by(self.model.id)).all()
            return [dict(row.data) for row in rows]

    def find(self, **filters: Any) -> list[dict[str, Any]]:
        with Session(engine) as session:
            statement = select(self.model).where(*self._where(filters)).order_by(self.model.id)
            return [dict(row.data) for row in session.exec(statement).all()]

    def get(self, **filters: Any) -> Optional[dict[str, Any]]:
        result = self.find(**filters)
        return result[0] if result else None

    def update(self, fields: dict[str, Any], **filters: Any) -> None:
        """Merge ``fields`` into every matching record in one transaction."""
        with Session(engine) as session:
            statement = select(self.model).where(*self._where(filters)).with_for_update()
            for row in session.exec(statement).all():
                merged = {**row.data, **fields}
                row.data = merged
                for key in self.keys:
                    setattr(row, key, merged.get(key))
                session.add(row)
            session.commit()

    def remove(self, **filters: Any) -> None:
        with Session(engine) as session:
            session.exec(delete(self.model).where(*self._where(filters)))
            session.commit()

    def truncate(self) -> None:
        self.remove()


sessions_collection = Collection(SessionRecord)
products_collection = Collection(ProductRecord)
customers_collection = Collection(CustomerRecord)
orders_collection = Collection(OrderRecord)
carts_collection = Collection(CartRecord)

# Multi-tenant platform tables: registered companies (tenants), their user
# accounts, and the external chatbot targets each company has onboarded.
companies_collection = Collection(CompanyRecord)
users_collection = Collection(UserRecord)
targets_collection = Collection(TargetRecord)


def init_database() -> None:
    """Create any missing tables."""
    SQLModel.metadata.create_all(engine)


async def ping_database():
    """Create tables and confirm the database is reachable."""
    try:
        init_database()
        print(f"🚀 Database ready ({engine.url.get_backend_name()})")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
