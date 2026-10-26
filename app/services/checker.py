import time
from dataclasses import dataclass

import httpx

from app.services.url_safety import UnsafeURL, validate_target_url


@dataclass
class CheckResult:
    status_code: int | None
    response_ms: int | None
    is_success: bool
    error: str | None


def run_check(
    url: str,
    timeout_seconds: int,
    allow_private: bool = False,
    transport: httpx.BaseTransport | None = None,
) -> CheckResult:
    """Send one HTTP GET and describe the outcome.

    Status codes below 400 count as up. Redirects are not followed, so a
    redirect can never send the worker to an address that was not validated.
    Only response headers are read; bodies are never downloaded or stored.
    """
    try:
        validate_target_url(url, allow_private)
    except UnsafeURL as exc:
        return CheckResult(None, None, False, f"blocked: {exc}"[:255])

    started = time.perf_counter()
    try:
        with httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=False,
            transport=transport,
            headers={"User-Agent": "Vigil/1.0 (+uptime monitor)"},
        ) as client:
            with client.stream("GET", url) as response:
                status = response.status_code
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        ok = status < 400
        return CheckResult(status, elapsed_ms, ok, None if ok else f"HTTP {status}")
    except httpx.TimeoutException:
        return CheckResult(None, None, False, "timeout")
    except httpx.HTTPError as exc:
        return CheckResult(None, None, False, type(exc).__name__)
