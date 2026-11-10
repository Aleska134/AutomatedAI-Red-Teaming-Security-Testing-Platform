"""The admin-only 'wake up' ping for chatbots that sleep on free hosting."""

import pytest
import requests

from app.services.webhook_adapter import WebhookAdapterError, wake_webhook
from tests.conftest import register_active_company

URL = "https://sleepy-bot.example.test/api/v1/chat"
HEALTH = "https://sleepy-bot.example.test/health"


class FakeTime:
    """A clock that only moves when the code sleeps, so tests are instant."""

    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class Reply:
    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = headers or {}


def _wake(health=(200,), webhook=(200,), **kwargs):
    """Run a wake against scripted answers per URL (an Exception is raised, the
    last answer repeats). Returns ``(result, calls, fake_time)``."""
    fake = FakeTime()
    scripts = {HEALTH: list(health), URL: list(webhook)}
    calls = []

    def transport(url, **kw):
        calls.append((url, kw))
        fake.now += 0.5  # a request takes a moment
        queue = scripts[url]
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome if isinstance(outcome, Reply) else Reply(outcome)

    result = wake_webhook(URL, transport=transport, sleep=fake.sleep, clock=fake.clock, **kwargs)
    return result, calls, fake


def test_a_healthy_chatbot_is_active_on_the_first_try():
    result, calls, _ = _wake(health=[200])
    assert result["awake"] is True and result["status_code"] == 200
    assert result["attempts"] == 1 and "is active (HTTP 200)" in result["message"]
    assert [url for url, _ in calls] == [HEALTH]  # the webhook itself is not touched


def test_429_is_not_ready_it_waits_for_the_200():
    result, calls, _ = _wake(health=[429, 429, 429, 200])
    assert result["awake"] is True and result["status_code"] == 200
    assert result["attempts"] == 4


def test_a_chatbot_that_keeps_answering_429_is_not_reported_active():
    result, calls, _ = _wake(health=[429], budget_seconds=20)
    assert result["awake"] is False and result["status_code"] == 429
    assert "limiting requests (HTTP 429)" in result["message"]
    assert 2 <= len(calls) <= 10  # bounded, not an endless loop


def test_retry_after_is_respected_but_capped():
    _, _, fake = _wake(
        health=[Reply(429, {"Retry-After": "7"}), Reply(429, {"Retry-After": "9999"}), 200],
        budget_seconds=75,
    )
    assert fake.sleeps == [7.0, 10.0]


def test_a_bad_retry_after_falls_back_to_the_default_delay():
    _, _, fake = _wake(health=[Reply(429, {"Retry-After": "soon"}), 200], retry_delay=3)
    assert fake.sleeps == [3]


def test_retries_through_timeouts_connection_errors_and_gateway_errors():
    result, _, _ = _wake(
        health=[requests.Timeout(), requests.ConnectionError(), 503, 502, 504, 200]
    )
    assert result["awake"] is True and result["attempts"] == 6


def test_a_service_stuck_on_503_is_not_reported_awake():
    result, _, _ = _wake(health=[503], budget_seconds=15)
    assert result["awake"] is False and result["status_code"] == 503
    assert "did not wake up" in result["message"]


@pytest.mark.parametrize("status", [404, 405, 401, 422])
def test_without_a_health_route_the_webhook_answering_counts_as_awake(status):
    result, calls, _ = _wake(health=[404], webhook=[status])
    assert result["awake"] is True and result["status_code"] == status
    assert [url for url, _ in calls] == [HEALTH, URL]


def test_without_a_health_route_a_429_from_the_webhook_still_waits():
    result, _, _ = _wake(health=[404], webhook=[429, 429, 405])
    assert result["awake"] is True and result["status_code"] == 405
    assert result["attempts"] == 3


def test_health_error_then_webhook_gateway_error_keeps_retrying():
    result, _, _ = _wake(health=[404], webhook=[502], budget_seconds=12)
    assert result["awake"] is False


def test_a_webhook_that_raises_is_retried_not_crashed():
    result, _, _ = _wake(health=[404], webhook=[requests.Timeout(), 405])
    assert result["awake"] is True and result["status_code"] == 405


def test_health_is_taken_from_the_host_even_with_a_port_path_and_query():
    fake = FakeTime()
    seen = []

    def transport(url, **kw):
        seen.append(url)
        return Reply(200)

    wake_webhook("https://bot.example.test:8443/a/b/c?x=1#frag", transport=transport,
                 sleep=fake.sleep, clock=fake.clock)
    assert seen == ["https://bot.example.test:8443/health"]


def test_pings_send_no_credentials_and_do_not_follow_redirects():
    _, calls, _ = _wake(health=[404], webhook=[405])
    assert len(calls) == 2
    for _, kwargs in calls:
        assert kwargs["allow_redirects"] is False
        assert "authorization" not in {k.lower() for k in kwargs["headers"]}
        assert "json" not in kwargs and "data" not in kwargs


def test_each_request_timeout_is_bounded_by_the_remaining_budget():
    _, calls, _ = _wake(health=[200], budget_seconds=5)
    assert 1 <= calls[0][1]["timeout"] <= 5


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254", "10.0.0.5"])
def test_private_addresses_are_refused_before_any_request(monkeypatch, address):
    monkeypatch.setattr("app.services.webhook_adapter._resolve_host", lambda host: [address])
    calls = []
    with pytest.raises(WebhookAdapterError):
        wake_webhook("https://evil.example.test/", transport=lambda *a, **k: calls.append(a))
    assert calls == []


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://x.test/", "", "javascript:alert(1)"])
def test_non_http_urls_are_refused(url):
    with pytest.raises(WebhookAdapterError):
        wake_webhook(url, transport=lambda *a, **k: Reply(200))


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
