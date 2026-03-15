from collections import defaultdict, deque
from threading import Lock
from time import time

from fastapi import HTTPException, Request, status

_requests: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def enforce_rate_limit(request: Request, scope: str, limit: int, window_seconds: int) -> None:
    client_ip = request.client.host if request.client else "unknown"
    key = f"{scope}:{client_ip}"
    now = time()
    with _lock:
        bucket = _requests[key]
        while bucket and bucket[0] <= now - window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {scope}. Try again later.",
            )
        bucket.append(now)

