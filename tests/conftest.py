import uuid

import pytest

from app.database import customers_collection
from app.services.commerce import seed_commerce_data


@pytest.fixture(autouse=True, scope="session")
def _seed_commerce_once():
    """Seed the deterministic demo catalog so tests do not depend on ordering."""
    seed_commerce_data()
    yield


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
    from tinydb import Query

    customers_collection.remove(Query().customer_id == customer_id)
