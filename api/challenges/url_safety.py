"""
SSRF guard for freelancer-submitted URLs.

Every submission URL is fetched server-side by the automated grader
(Lighthouse), which would otherwise let a participant point the platform's own
infrastructure at itself — cloud metadata endpoints, internal service names
resolved through Docker's own DNS, a loopback admin panel. `assert_safe_url`
closes that off by resolving the hostname and rejecting anything that is not a
public, routable address.

Called twice on purpose: once at submission time, for fast feedback on an
obviously bad URL, and again immediately before the actual fetch inside the
grading task. DNS is not a fact that stays true — a domain that resolves
publicly at submission time can be repointed at an internal address by the
time grading runs (DNS rebinding), so the check that actually matters is the
one closest to the fetch.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}


class UnsafeURLError(ValueError):
    """The URL is not safe to fetch server-side."""


def assert_safe_url(url: str) -> None:
    """Raise ``UnsafeURLError`` if ``url`` is not a fetchable public address.

    Not a guarantee against every SSRF variant — a public host could still
    redirect to a private one after this check passes. Whatever actually
    performs the fetch (`challenges.grading`) must not follow redirects
    blindly; this function only covers the address being submitted.
    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"URL must be http or https, not {parsed.scheme or '(none)'}.")
    if not parsed.hostname:
        raise UnsafeURLError("URL has no host.")
    if parsed.username or parsed.password:
        raise UnsafeURLError("URL must not carry credentials.")

    hostname = parsed.hostname
    try:
        addrinfo = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Could not resolve {hostname}.") from exc

    if not addrinfo:
        raise UnsafeURLError(f"Could not resolve {hostname}.")

    for _family, _type, _proto, _canon, sockaddr in addrinfo:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise UnsafeURLError(f"{hostname} resolves to a non-public address ({ip}).")
