"""A company must confirm it may test a chatbot; the platform records who/when."""

import pytest

from app.database import targets_collection
from tests.conftest import register_active_company

URL = "https://merchant.example.test/api/v1/chat"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create(api_client, token, **extra):
    return api_client.post(
        "/api/v1/targets",
        json={"name": "Bot", "webhook_url": URL, **extra},
        headers=_auth(token),
    )


@pytest.mark.parametrize("extra", [{}, {"authorization_confirmed": False}])
def test_creating_a_target_requires_confirmation(api_client, extra):
    _, token = register_active_company(api_client, "Acme", "o@acme.test")

    response = _create(api_client, token, **extra)

    assert response.status_code == 400
    assert "authorized" in response.json()["detail"]
    assert api_client.get("/api/v1/targets", headers=_auth(token)).json() == []


@pytest.mark.parametrize("bad", ["yes", 1, None, [], {}])
def test_confirmation_must_be_a_real_boolean(api_client, bad):
    _, token = register_active_company(api_client, "Acme", "o@acme.test")
    assert _create(api_client, token, authorization_confirmed=bad).status_code in (400, 422)


def test_confirmation_records_who_and_when(api_client):
    _, token = register_active_company(api_client, "Acme", "Owner@Acme.test")

    created = _create(api_client, token, authorization_confirmed=True).json()

    assert created["authorization_confirmed_by"] == "owner@acme.test"
    assert created["authorization_confirmed_at"]
    listed = api_client.get("/api/v1/targets", headers=_auth(token)).json()[0]
    assert listed["authorization_confirmed_at"] == created["authorization_confirmed_at"]


def test_a_client_cannot_forge_who_confirmed(api_client):
    _, token = register_active_company(api_client, "Acme", "o@acme.test")

    created = _create(
        api_client, token, authorization_confirmed=True,
        authorization_confirmed_by="ceo@other.test", authorization_confirmed_at="2000-01-01",
    ).json()

    assert created["authorization_confirmed_by"] == "o@acme.test"
    assert not created["authorization_confirmed_at"].startswith("2000")


def _legacy_target(api_client, token):
    """A target saved before authorization was recorded."""
    created = _create(api_client, token, authorization_confirmed=True).json()
    targets_collection.update(
        {"authorization_confirmed_at": None, "authorization_confirmed_by": None},
        target_id=created["target_id"],
    )
    return created["target_id"]


def test_tests_are_blocked_against_an_unconfirmed_target(api_client):
    _, token = register_active_company(api_client, "Acme", "o@acme.test")
    target_id = _legacy_target(api_client, token)

    response = api_client.post(
        "/api/v1/simulation/loop",
        json={"turns": 1, "target_id": target_id},
        headers=_auth(token),
    )

    assert response.status_code == 400
    assert "authorized" in response.json()["detail"]


def test_legacy_target_can_be_confirmed_later_and_only_the_first_confirmation_counts(api_client):
    _, token = register_active_company(api_client, "Acme", "o@acme.test")
    target_id = _legacy_target(api_client, token)

    first = api_client.patch(
        f"/api/v1/targets/{target_id}", json={"authorization_confirmed": True},
        headers=_auth(token),
    ).json()
    again = api_client.patch(
        f"/api/v1/targets/{target_id}", json={"authorization_confirmed": True},
        headers=_auth(token),
    ).json()

    assert first["authorization_confirmed_by"] == "o@acme.test"
    assert again["authorization_confirmed_at"] == first["authorization_confirmed_at"]


def test_editing_a_target_does_not_confirm_it(api_client):
    _, token = register_active_company(api_client, "Acme", "o@acme.test")
    target_id = _legacy_target(api_client, token)

    edited = api_client.patch(
        f"/api/v1/targets/{target_id}", json={"name": "Renamed"}, headers=_auth(token)
    ).json()

    assert edited["authorization_confirmed_at"] is None


def test_another_company_cannot_confirm_my_target(api_client):
    _, token_a = register_active_company(api_client, "A", "a@x.test")
    _, token_b = register_active_company(api_client, "B", "b@x.test")
    target_id = _legacy_target(api_client, token_a)

    response = api_client.patch(
        f"/api/v1/targets/{target_id}", json={"authorization_confirmed": True},
        headers=_auth(token_b),
    )

    assert response.status_code == 404
    assert targets_collection.get(target_id=target_id).get(
        "authorization_confirmed_at"
    ) is None
