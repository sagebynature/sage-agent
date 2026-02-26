"""Shared security validation utilities for tools."""

from __future__ import annotations

import ipaddress
import logging
import socket
import urllib.parse
from dataclasses import dataclass

from sage.exceptions import ToolError

logger = logging.getLogger(__name__)

_BLOCKED_HOSTNAMES = frozenset(
    {
        "metadata.google.internal",
        "metadata.internal",
    }
)


@dataclass(frozen=True)
class ResolvedURL:
    """A URL with its hostname resolved once to a pinned IP address.

    Using the pinned IP for the actual connection prevents DNS rebinding
    attacks (TOCTOU): the hostname is resolved exactly once, validated,
    and the result is stored here for callers to use directly.
    """

    original_url: str
    resolved_ip: str
    hostname: str
    port: int | None
    scheme: str
    path: str
    query: str
    fragment: str


def validate_and_resolve_url(url: str) -> ResolvedURL:
    """Validate a URL and resolve its hostname exactly once.

    Returns a :class:`ResolvedURL` whose ``resolved_ip`` is the validated
    IP address callers should connect to.  Callers must use this IP for
    the actual connection and pass the original hostname as the ``Host``
    header, preventing DNS rebinding (TOCTOU).

    Raises:
        ToolError: If the URL targets a restricted resource.
    """
    parsed = urllib.parse.urlparse(url)

    # Block non-HTTP schemes.
    if parsed.scheme.lower() not in ("http", "https"):
        raise ToolError(f"URL not allowed: scheme '{parsed.scheme}' is blocked")

    hostname = parsed.hostname or ""

    # Block known metadata hostnames.
    if hostname.lower() in _BLOCKED_HOSTNAMES:
        raise ToolError(f"URL not allowed: '{hostname}' is a blocked host")

    # Block localhost variants.
    if hostname.lower() in ("localhost", ""):
        raise ToolError("URL not allowed: localhost is blocked")

    # Resolve hostname to IP exactly once.
    try:
        addr = ipaddress.ip_address(hostname)
        # Already an IP literal — no DNS lookup needed.
        resolved_ip = hostname
    except ValueError:
        # It's a hostname — resolve it once and pin the result.
        try:
            results = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            if not results:
                raise ToolError(f"URL not allowed: could not resolve '{hostname}'")
            resolved_ip = str(results[0][4][0])
            addr = ipaddress.ip_address(resolved_ip)
        except socket.gaierror as exc:
            raise ToolError(f"URL not allowed: could not resolve '{hostname}': {exc}") from exc

    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
        raise ToolError(
            f"URL not allowed: '{hostname}' resolves to a private/reserved address ({resolved_ip})"
        )

    return ResolvedURL(
        original_url=url,
        resolved_ip=resolved_ip,
        hostname=hostname,
        port=parsed.port,
        scheme=parsed.scheme.lower(),
        path=parsed.path,
        query=parsed.query,
        fragment=parsed.fragment,
    )


def validate_url(url: str) -> None:
    """Validate that a URL is safe to fetch (not targeting internal resources).

    Thin wrapper around :func:`validate_and_resolve_url` for backward
    compatibility with callers that only need a pass/fail check.

    Raises:
        ToolError: If the URL targets a restricted resource.
    """
    validate_and_resolve_url(url)
