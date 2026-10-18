"""Login, register and forgot-password are rate-limited per client IP."""

from app.auth.rate_limit import login_limiter, register_limiter


def test_login_is_rate_limited(api_client):
    body = {"email": "nobody@limit.test", "password": "wrong-password"}
    for _ in range(login_limiter.max_requests):
        assert api_client.post("/api/v1/auth/login", json=body).status_code == 401

    blocked = api_client.post("/api/v1/auth/login", json=body)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


def test_register_is_rate_limited(api_client):
    for i in range(register_limiter.max_requests):
        response = api_client.post(
            "/api/v1/auth/register",
            json={
                "company_name": f"Co {i}",
                "email": f"user{i}@limit.test",
                "password": "company-pass-1",
            },
        )
        assert response.status_code == 201

    blocked = api_client.post(
        "/api/v1/auth/register",
        json={"company_name": "Extra", "email": "extra@limit.test", "password": "company-pass-1"},
    )
    assert blocked.status_code == 429


def test_forgot_password_is_rate_limited(api_client):
    body = {"email": "nobody@limit.test"}
    responses = [
        api_client.post("/api/v1/auth/forgot-password", json=body).status_code
        for _ in range(6)
    ]
    assert responses[:5] == [200] * 5
    assert responses[5] == 429
