"""Commerce endpoints must be authenticated and scoped to the caller's tenant."""

from tests.conftest import register_active_company


def _auth(api_client, name, email):
    _, token = register_active_company(api_client, name, email)
    return {"Authorization": f"Bearer {token}"}


def test_commerce_endpoints_require_authentication(api_client):
    assert api_client.get("/api/v1/commerce/cart").status_code == 401
    assert api_client.post(
        "/api/v1/commerce/carts/items",
        json={"product_id": "prod-keyboard-001", "quantity": 1},
    ).status_code == 401
    assert api_client.post("/api/v1/commerce/checkout", json={}).status_code == 401
    assert api_client.post(
        "/api/v1/commerce/chat", json={"message": "hi", "history": []}
    ).status_code == 401


def test_each_company_gets_an_isolated_sandbox_cart(api_client):
    a = _auth(api_client, "A", "a@cart.test")
    b = _auth(api_client, "B", "b@cart.test")
    added = api_client.post(
        "/api/v1/commerce/carts/items",
        json={"product_id": "prod-keyboard-001", "quantity": 1},
        headers=a,
    )
    assert added.status_code == 200

    cart_a = api_client.get("/api/v1/commerce/cart", headers=a).json()
    cart_b = api_client.get("/api/v1/commerce/cart", headers=b).json()
    assert cart_a["customer_id"] != cart_b["customer_id"]
    assert cart_a["items"] and not cart_b["items"]


def test_chat_ignores_client_supplied_customer_id(api_client, monkeypatch):
    seen = {}

    def fake_defender(message, chat_history=None, customer_id=None, **_):
        seen["customer_id"] = customer_id
        return "ok"

    monkeypatch.setattr("app.routers.query_defender", fake_defender)
    headers = _auth(api_client, "A", "chat@cart.test")
    response = api_client.post(
        "/api/v1/commerce/chat",
        json={"customer_id": "customer-demo-001", "message": "hi", "history": []},
        headers=headers,
    )
    assert response.status_code == 200
    assert seen["customer_id"].startswith("sandbox-company-")
