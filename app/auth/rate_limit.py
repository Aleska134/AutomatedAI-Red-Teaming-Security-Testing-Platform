"""In-memory rate limiting for unauthenticated auth endpoints.

Counts requests per client IP in a sliding window. State lives in the process,
so limits are per worker and reset on restart: enough to slow down password
brute force and reset spam on a single-dyno deployment without extra services.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, name: str, max_requests: int, window_seconds: int):
        self.name = name
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def __call__(self, request: Request) -> None:
        """FastAPI dependency: raise 429 once the caller exceeds the limit."""
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self.window_seconds:
                hits.popleft()
            if len(hits) >= self.max_requests:
                retry_after = int(hits[0] + self.window_seconds - now) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many attempts. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


login_limiter = RateLimiter("login", max_requests=10, window_seconds=60)
register_limiter = RateLimiter("register", max_requests=5, window_seconds=3600)
forgot_password_limiter = RateLimiter("forgot-password", max_requests=5, window_seconds=900)

ALL_LIMITERS = (login_limiter, register_limiter, forgot_password_limiter)
