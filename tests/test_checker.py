import httpx

from app.services.checker import run_check


def _transport(handler):
    return httpx.MockTransport(handler)


def test_200_is_success():
    result = run_check("https://8.8.8.8/", 5, transport=_transport(lambda r: httpx.Response(200)))
    assert result.is_success and result.status_code == 200
    assert result.response_ms is not None and result.error is None


def test_redirect_counts_as_up_and_is_not_followed():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(301, headers={"Location": "http://127.0.0.1/secret"})

    result = run_check("https://8.8.8.8/", 5, transport=_transport(handler))
    assert result.is_success and result.status_code == 301
    assert len(calls) == 1


def test_500_is_failure_with_error_text():
    result = run_check("https://8.8.8.8/", 5, transport=_transport(lambda r: httpx.Response(500)))
    assert not result.is_success
    assert result.status_code == 500 and result.error == "HTTP 500"


def test_timeout_is_failure():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    result = run_check("https://8.8.8.8/", 1, transport=_transport(handler))
    assert not result.is_success and result.error == "timeout"


def test_connection_error_is_failure():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    result = run_check("https://8.8.8.8/", 1, transport=_transport(handler))
    assert not result.is_success and result.error == "ConnectError"


def test_private_target_is_blocked_without_request():
    called = []
    result = run_check(
        "http://127.0.0.1/", 5, transport=_transport(lambda r: called.append(1) or httpx.Response(200))
    )
    assert not result.is_success and result.error.startswith("blocked")
    assert not called
