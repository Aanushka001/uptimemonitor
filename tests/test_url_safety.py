import pytest

from app.services.url_safety import UnsafeURL, validate_target_url


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file",
        "file:///etc/passwd",
        "http://",
        "http://127.0.0.1:8000/admin",
        "http://localhost/",
        "http://10.0.0.5/",
        "http://192.168.1.10/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
    ],
)
def test_rejects_unsafe_urls(url):
    with pytest.raises(UnsafeURL):
        validate_target_url(url)


def test_accepts_public_ip_literal():
    validate_target_url("https://8.8.8.8/")


def test_private_targets_allowed_only_when_enabled():
    validate_target_url("http://127.0.0.1:8000/health", allow_private=True)


def test_scheme_still_enforced_when_private_allowed():
    with pytest.raises(UnsafeURL):
        validate_target_url("ftp://127.0.0.1/", allow_private=True)
