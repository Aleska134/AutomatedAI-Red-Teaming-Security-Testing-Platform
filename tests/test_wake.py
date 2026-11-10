"""The admin-only 'wake up' ping for chatbots that sleep on free hosting."""

import pytest
import requests

from app.services.webhook_adapter import WebhookAdapterError, wake_webhook
from tests.conftest import register_active_company

URL = "https://sleepy-bot.example.test/api/v1/chat"


class FakeTime:
    """A clock that only moves when the code sleeps, so tests are instant."""

    def __init__(self):
        self.now = 0.0

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Reply:
    def __init__(self, status_code):
        self.status_code = status_code


def _transport(*outcomes, time_=None):
    """Return each outcome in turn (an Exception is raised); records the calls."""
    calls = []
    queue = list(outcomes)

    def transport(url, **kwargs):
        calls.append((url, kwargs))
        if time_:
            time_.now += 0.5  # a request takes a moment
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(outcome, Exception):
            raise outcome
        return Reply(outcome)

    transport.calls = calls
    return transport


def _wake(*outcomes, **kwargs):
    fake = FakeTime()
    transport = _transport(*outcomes, time_=fake)
    result = wake_webhook(URL, transport=transport, sleep=fake.sleep, clock=fake.clock, **kwargs)
    return result, transport


def test_awake_chatbot_answers_on_the_first_try():
    result, transport = _wake(200)
    assert result["awake"] is True and result["attempts"] == 1
    assert len(transport.calls) == 1


@pytest.mark.parametrize("status", [401, 404, 405, 422, 500])
def test_any_real_answer_counts_as_awake(status):
    result, _ = _wake(status)
    assert result["awake"] is True and result["status_code"] == status


def test_retries_through_timeouts_and_gateway_errors_until_it_answers():
    result, transport = _wake(
        requests.Timeout(), requests.ConnectionError(), 503, 502, 504, 405
    )
    assert result["awake"] is True
    assert result["attempts"] == 6
    assert result["status_code"] == 405


def test_gives_up_when_the_budget_runs_out_and_says_so():
    result, transport = _wake(requests.Timeout(), budget_seconds=20, retry_delay=3)
    assert result["awake"] is False
    assert result["status_code"] is None
    assert "did not wake up" in result["message"]
    assert 2 <= len(transport.calls) <= 8  # bounded, not an endless loop


def test_a_service_stuck_on_503_is_not_reported_awake():
    result, _ = _wake(503, budget_seconds=15)
    assert result["awake"] is False and result["status_code"] == 503


def test_the_ping_sends_no_credentials_and_does_not_follow_redirects():
    _, transport = _wake(200)
    (url, kwargs), = transport.calls
    assert url == URL
    assert kwargs["allow_redirects"] is False
    assert "authorization" not in {k.lower() for k in kwargs["headers"]}
    assert "json" not in kwargs and "data" not in kwargs


def test_each_request_timeout_is_bounded_by_the_remaining_budget():
    _, transport = _wake(200, budget_seconds=5)
    assert 1 <= transport.calls[0][1]["timeout"] <= 5


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254", "10.0.0.5"])
def test_private_addresses_are_refused_before_any_request(monkeypatch, address):
    monkeypatch.setattr("app.services.webhook_adapter._resolve_host", lambda host: [address])
    transport = _transport(200)
    with pytest.raises(WebhookAdapterError):
        wake_webhook("https://evil.example.test/", transport=transport)
    assert transport.calls == []


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://x.test/", "", "javascript:alert(1)"])
def test_non_http_urls_are_refused(url):
    with pytest.raises(WebhookAdapterError):
        wake_webhook(url, transport=_transport(200))


# --- API ------------------------------------------------------------------ #

def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create(api_client, token):
    response = api_client.post(
        "/api/v1/targets",
        json={"name": "Sleepy", "webhook_url": URL, "authorization_confirmed": True},
        headers=_auth(token),
    )
    return response.json()["target_id"]


def test_admin_can_wake_their_target(api_client, admin_token, monkeypatch):
    seen = {}

    def fake_wake(url):
        seen["url"] = url
        return {"awake": True, "status_code": 405, "seconds": 31.2, "attempts": 4,
                "message": "The chatbot answered (HTTP 405) after 31.2 s."}

    monkeypatch.setattr("app.auth.router.wake_webhook", fake_wake)
    target_id = _create(api_client, admin_token)

    response = api_client.post(f"/api/v1/targets/{target_id}/wake", headers=_auth(admin_token))

    assert response.status_code == 200
    assert response.json()["awake"] is True and seen["url"] == URL


def test_regular_companies_cannot_wake_chatbots(api_client, monkeypatch):
    called = []
    monkeypatch.setattr("app.auth.router.wake_webhook", lambda url: called.append(url))
    _, token = register_active_company(api_client, "Shop", "shop@wake.test")
    target_id = _create(api_client, token)

    response = api_client.post(f"/api/v1/targets/{target_id}/wake", headers=_auth(token))

    assert response.status_code == 403
    assert called == []


def test_wake_requires_authentication(api_client):
    assert api_client.post("/api/v1/targets/any/wake").status_code in (401, 403)
    bad = api_client.post("/api/v1/targets/any/wake", headers=_auth("not-a-token"))
    assert bad.status_code in (401, 403)


def test_admin_cannot_wake_another_companys_target(api_client, admin_token, monkeypatch):
    called = []
    monkeypatch.setattr("app.auth.router.wake_webhook", lambda url: called.append(url))
    _, shop_token = register_active_company(api_client, "Shop", "shop@wake.test")
    shop_target = _create(api_client, shop_token)

    response = api_client.post(f"/api/v1/targets/{shop_target}/wake", headers=_auth(admin_token))

    assert response.status_code == 404
    assert called == []


def test_unknown_target_is_404(api_client, admin_token):
    response = api_client.post("/api/v1/targets/nope/wake", headers=_auth(admin_token))
    assert response.status_code == 404


def test_ssrf_failure_becomes_a_400_not_a_500(api_client, admin_token, monkeypatch):
    target_id = _create(api_client, admin_token)
    monkeypatch.setattr("app.services.webhook_adapter._resolve_host", lambda host: ["127.0.0.1"])

    response = api_client.post(f"/api/v1/targets/{target_id}/wake", headers=_auth(admin_token))

    assert response.status_code == 400
