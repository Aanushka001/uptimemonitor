"""Validation for user-supplied monitor URLs.

Vigil makes outbound requests to URLs that users submit. Without checks, someone
could point a monitor at internal addresses (SSRF). This module allows only
http/https URLs whose host resolves to public IP addresses.
"""
import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURL(ValueError):
    """Raised when a URL must not be requested."""


def validate_target_url(url: str, allow_private: bool = False) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURL("Only http and https URLs are allowed")
    host = parsed.hostname
    if not host:
        raise UnsafeURL("URL has no host")
    if allow_private:
        return

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURL("Host could not be resolved") from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise UnsafeURL("Target resolves to a non-public address")
