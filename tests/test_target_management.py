"""Tests for deleting registered chatbot targets.

A company can remove its own saved targets (e.g. a duplicate), and the delete
is tenant-scoped: one company can never delete another company's target.
"""

from tests.conftest import register_active_company


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_target(api_client, token, name="Chatbot"):
    response = api_client.post(
        "/api/v1/targets",
        json={"name": name, "webhook_url": "https://merchant.example.test/api/v1/chat"},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()["target_id"]


def test_delete_removes_target(api_client):
    _, token = register_active_company(api_client, "Acme", "owner@acme.test")
    target_id = _create_target(api_client, token)

    assert len(api_client.get("/api/v1/targets", headers=_auth(token)).json()) == 1

    response = api_client.delete(f"/api/v1/targets/{target_id}", headers=_auth(token))
    assert response.status_code == 204

    assert api_client.get("/api/v1/targets", headers=_auth(token)).json() == []


def test_delete_unknown_target_returns_404(api_client):
    _, token = register_active_company(api_client, "Acme", "owner@acme.test")
    response = api_client.delete(
        "/api/v1/targets/target-does-not-exist", headers=_auth(token)
    )
    assert response.status_code == 404


def test_delete_twice_returns_404_the_second_time(api_client):
    _, token = register_active_company(api_client, "Acme", "owner@acme.test")
    target_id = _create_target(api_client, token)

    assert api_client.delete(
        f"/api/v1/targets/{target_id}", headers=_auth(token)
    ).status_code == 204
    assert api_client.delete(
        f"/api/v1/targets/{target_id}", headers=_auth(token)
    ).status_code == 404


def test_cannot_delete_another_companys_target(api_client):
    # Company A owns the target.
    _, token_a = register_active_company(api_client, "Company A", "a@test.local")
    target_id = _create_target(api_client, token_a, name="A's bot")

    # Company B must not be able to delete it.
    _, token_b = register_active_company(api_client, "Company B", "b@test.local")
    response = api_client.delete(
        f"/api/v1/targets/{target_id}", headers=_auth(token_b)
    )
    assert response.status_code == 404

    # And the target must still exist for its real owner.
    owner_targets = api_client.get("/api/v1/targets", headers=_auth(token_a)).json()
    assert len(owner_targets) == 1
    assert owner_targets[0]["target_id"] == target_id


def test_delete_requires_authentication(api_client):
    _, token = register_active_company(api_client, "Acme", "owner@acme.test")
    target_id = _create_target(api_client, token)

    # No Authorization header -> unauthenticated.
    response = api_client.delete(f"/api/v1/targets/{target_id}")
    assert response.status_code in (401, 403)


# --- Editing targets ------------------------------------------------------- #


def _create_target_with_rules(api_client, token, coupons, token_value="secret-123"):
    response = api_client.post(
        "/api/v1/targets",
        json={
            "name": "Shop",
            "webhook_url": "https://merchant.example.test/api/v1/chat",
            "auth_token": token_value,
            "business_rules": {"valid_coupons": coupons, "max_discount_percent": 10},
        },
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_edit_adds_more_coupons(api_client):
    _, token = register_active_company(api_client, "Acme", "owner@acme.test")
    target = _create_target_with_rules(api_client, token, ["TECH10"])

    response = api_client.patch(
        f"/api/v1/targets/{target['target_id']}",
        json={
            "business_rules": {
                "valid_coupons": ["TECH10", "SAVE20", "WELCOME15"],
                "max_discount_percent": 15,
            }
        },
        headers=_auth(token),
    )
    assert response.status_code == 200
    rules = response.json()["business_rules"]
    assert rules["valid_coupons"] == ["TECH10", "SAVE20", "WELCOME15"]
    assert rules["max_discount_percent"] == 15


def test_edit_without_token_keeps_existing_one(api_client):
    _, token = register_active_company(api_client, "Acme", "owner@acme.test")
    target = _create_target_with_rules(api_client, token, ["TECH10"])
    assert target["has_auth_token"] is True

    # Edit the name only; do not send a token.
    response = api_client.patch(
        f"/api/v1/targets/{target['target_id']}",
        json={"name": "Renamed Shop"},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Shop"
    # The token must be preserved.
    assert response.json()["has_auth_token"] is True


def test_edit_can_clear_token(api_client):
    _, token = register_active_company(api_client, "Acme", "owner@acme.test")
    target = _create_target_with_rules(api_client, token, ["TECH10"])

    response = api_client.patch(
        f"/api/v1/targets/{target['target_id']}",
        json={"clear_auth_token": True},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["has_auth_token"] is False


def test_edit_can_replace_token(api_client):
    _, token = register_active_company(api_client, "Acme", "owner@acme.test")
    target = _create_target_with_rules(api_client, token, ["TECH10"], token_value=None)
    assert target["has_auth_token"] is False

    response = api_client.patch(
        f"/api/v1/targets/{target['target_id']}",
        json={"auth_token": "a-new-token"},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["has_auth_token"] is True


def test_cannot_edit_another_companys_target(api_client):
    _, token_a = register_active_company(api_client, "Company A", "a@test.local")
    target = _create_target_with_rules(api_client, token_a, ["TECH10"])

    _, token_b = register_active_company(api_client, "Company B", "b@test.local")
    response = api_client.patch(
        f"/api/v1/targets/{target['target_id']}",
        json={"name": "hacked"},
        headers=_auth(token_b),
    )
    assert response.status_code == 404

    # Target is unchanged for its real owner.
    owner_view = api_client.get("/api/v1/targets", headers=_auth(token_a)).json()[0]
    assert owner_view["name"] == "Shop"


def test_edit_unknown_target_returns_404(api_client):
    _, token = register_active_company(api_client, "Acme", "owner@acme.test")
    response = api_client.patch(
        "/api/v1/targets/target-does-not-exist",
        json={"name": "x"},
        headers=_auth(token),
    )
    assert response.status_code == 404
