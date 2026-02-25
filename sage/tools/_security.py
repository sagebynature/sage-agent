"""Shared security validation utilities for tools."""

from __future__ import annotations

import ipaddress
import logging
import socket
import urllib.parse

from sage.exceptions import ToolError

logger = logging.getLogger(__name__)

_BLOCKED_HOSTNAMES = frozenset(
    {
        "metadata.google.internal",
        "metadata.internal",
    }
)


def validate_url(url: str) -> None:
    """Validate that a URL is safe to fetch (not targeting internal resources).

    Blocks private IPs, loopback, link-local, cloud metadata endpoints,
    and non-HTTP schemes.

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

    # Check if hostname is an IP address directly.
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        # It's a hostname — try resolving it.
        try:
            resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            if resolved:
                addr = ipaddress.ip_address(resolved[0][4][0])
            else:
                return  # Can't resolve — allow (will fail at fetch time)
        except socket.gaierror:
            return  # Can't resolve — allow (will fail at fetch time)

    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
        raise ToolError(f"URL not allowed: {hostname} resolves to a private/reserved address")
