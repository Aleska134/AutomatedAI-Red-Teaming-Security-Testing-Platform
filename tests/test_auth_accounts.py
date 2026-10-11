"""Deterministic, offline tests for auth, multi-tenancy, and onboarding."""

from tests.conftest import register_active_company


def test_register_creates_pending_company(api_client):
    response = api_client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "acme@test.local", "password": "acme-pass-1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["company"]["status"] == "pending"
    assert body["role"] == "company"
    assert body["access_token"]


def test_duplicate_email_rejected(api_client):
    payload = {"company_name": "Acme", "email": "dup@test.local", "password": "acme-pass-1"}
    assert api_client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert api_client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_login_wrong_password_rejected(api_client):
    api_client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "x@test.local", "password": "right-pass-1"},
    )
    response = api_client.post(
        "/api/v1/auth/login", json={"email": "x@test.local", "password": "wrong-pass-1"}
    )
    assert response.status_code == 401


def test_pending_company_cannot_operate(api_client):
    token = api_client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "p@test.local", "password": "pass-123456"},
    ).json()["access_token"]
    response = api_client.post(
        "/api/v1/targets",
        json={"name": "bot", "webhook_url": "https://bot.test/chat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_missing_token_is_unauthorized(api_client):
    assert api_client.get("/api/v1/targets").status_code == 401


def test_invalid_token_is_unauthorized(api_client):
    response = api_client.get(
        "/api/v1/targets", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


def test_admin_can_list_and_activate_companies(api_client, admin_token):
    api_client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "acme@test.local", "password": "acme-pass-1"},
    )
    listing = api_client.get(
        "/api/v1/admin/companies", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert listing.status_code == 200
    acme = next(c for c in listing.json() if c["name"] == "Acme")
    assert acme["status"] == "pending"

    activated = api_client.post(
        f"/api/v1/admin/companies/{acme['company_id']}/status",
        json={"status": "active"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"


def test_company_cannot_access_admin_endpoints(api_client):
    _, token = register_active_company(api_client, "Acme", "acme@test.local")
    response = api_client.get(
        "/api/v1/admin/companies", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_targets_are_tenant_isolated(api_client):
    _, a_token = register_active_company(api_client, "CompanyA", "a@test.local")
    _, b_token = register_active_company(api_client, "CompanyB", "b@test.local")

    created = api_client.post(
        "/api/v1/targets",
        json={"name": "A-bot", "webhook_url": "https://a.test/chat"},
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert created.status_code == 201
    target_id = created.json()["target_id"]

    # B sees none of A's targets.
    b_list = api_client.get(
        "/api/v1/targets", headers={"Authorization": f"Bearer {b_token}"}
    )
    assert b_list.json() == []

    # B cannot test A's target.
    b_test = api_client.post(
        f"/api/v1/targets/{target_id}/test",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert b_test.status_code == 404


def test_change_password_flow(api_client):
    _, token = register_active_company(api_client, "Acme", "cp@test.local", password="old-pass-1")
    changed = api_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "old-pass-1", "new_password": "new-pass-2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert changed.status_code == 200
    assert api_client.post(
        "/api/v1/auth/login", json={"email": "cp@test.local", "password": "new-pass-2"}
    ).status_code == 200


def test_change_password_wrong_current_rejected(api_client):
    _, token = register_active_company(api_client, "Acme", "cp2@test.local", password="old-pass-1")
    response = api_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "not-the-pass", "new_password": "new-pass-2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


def test_forgot_and_reset_password_flow(api_client):
    register_active_company(api_client, "Acme", "fr@test.local", password="old-pass-1")
    forgot = api_client.post("/api/v1/auth/forgot-password", json={"email": "fr@test.local"})
    assert forgot.status_code == 200
    token = forgot.json()["reset_token"]
    assert token

    reset = api_client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "reset-pass-9"}
    )
    assert reset.status_code == 200
    assert api_client.post(
        "/api/v1/auth/login", json={"email": "fr@test.local", "password": "reset-pass-9"}
    ).status_code == 200


def test_forgot_password_unknown_email_is_generic(api_client):
    response = api_client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody@test.local"}
    )
    assert response.status_code == 200
    # No token for an unknown account, but the message does not reveal that.
    assert response.json()["reset_token"] is None


def test_reset_with_invalid_token_rejected(api_client):
    response = api_client.post(
        "/api/v1/auth/reset-password",
        json={"token": "bogus-token", "new_password": "whatever-1"},
    )
    assert response.status_code == 400
