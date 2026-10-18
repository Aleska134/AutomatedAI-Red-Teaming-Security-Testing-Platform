import os
import tempfile

# Point the app at a throwaway database BEFORE any app module is imported, so
# the suite never truncates the developer's real local database.
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(
    tempfile.mkdtemp(prefix="redteam-tests-"), "test.db"
)
os.environ.setdefault("APP_ENV", "development")

import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import (
    companies_collection,
    customers_collection,
    init_database,
    sessions_collection,
    targets_collection,
    users_collection,
)
from app.services.accounts import register_company, set_company_status
from app.services.commerce import seed_commerce_data


@pytest.fixture(autouse=True, scope="session")
def _seed_commerce_once():
    """Seed the deterministic demo catalog so tests do not depend on ordering."""
    init_database()
    seed_commerce_data()
    yield


@pytest.fixture
def api_client():
    """A TestClient with isolated auth/tenant tables for each test."""
    companies_collection.truncate()
    users_collection.truncate()
    targets_collection.truncate()
    sessions_collection.truncate()
    from app.main import app

    with TestClient(app) as client:
        yield client

    companies_collection.truncate()
    users_collection.truncate()
    targets_collection.truncate()
    sessions_collection.truncate()


@pytest.fixture
def admin_token(api_client):
    """Create an active admin account and return a bearer token for it."""
    register_company(
        company_name="Admin Co",
        email="admin@test.local",
        password="admin-pass-123",
        role="admin",
        status="active",
    )
    response = api_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "admin-pass-123"},
    )
    return response.json()["access_token"]


def register_active_company(api_client, name: str, email: str, password: str = "company-pass-1"):
    """Helper: register a company, activate it, and return (company_id, token)."""
    from app.services.accounts import get_user_by_email

    register_company(company_name=name, email=email, password=password)
    user = get_user_by_email(email)
    set_company_status(user["company_id"], "active")
    token = api_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]
    return user["company_id"], token


@pytest.fixture
def test_customer():
    """Create and remove an isolated demo customer for a commerce test."""
    seed_commerce_data()
    customer_id = f"customer-test-{uuid.uuid4().hex[:8]}"
    customers_collection.insert(
        {
            "customer_id": customer_id,
            "name": "Automated Test Customer",
            "email": f"{customer_id}@example.test",
        }
    )
    yield customer_id
    customers_collection.remove(customer_id=customer_id)


@pytest.fixture(autouse=True)
def _offline_public_dns(monkeypatch):
    """Resolve every webhook host to a public IP so tests stay offline.

    SSRF tests override this to simulate private resolutions.
    """
    monkeypatch.setattr(
        "app.services.webhook_adapter._resolve_host", lambda host: ["93.184.216.34"]
    )
