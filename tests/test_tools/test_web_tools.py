"""Tests for web tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from sage.exceptions import ToolError
from sage.tools._security import ResolvedURL
from sage.tools.web_tools import web_fetch, web_search

# Reusable resolved URL for a safe public host.
_EXAMPLE_RESOLVED = ResolvedURL(
    original_url="https://example.com/",
    resolved_ip="93.184.216.34",
    hostname="example.com",
    port=None,
    scheme="https",
    path="/",
    query="",
    fragment="",
)


def _make_mock_client(mock_response: object) -> AsyncMock:
    """Build an AsyncMock httpx client whose send() returns *mock_response*."""
    mock_request = MagicMock()
    mock_request.extensions = {}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.build_request = MagicMock(return_value=mock_request)
    mock_client.send = AsyncMock(return_value=mock_response)
    return mock_client


class TestWebFetch:
    async def test_successful_fetch(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><h1>Hello</h1><p>World</p></body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"content-type": "text/html"}

        with patch("sage.tools.web_tools.validate_and_resolve_url", return_value=_EXAMPLE_RESOLVED):
            with patch("sage.tools.web_tools.httpx.AsyncClient") as mock_client_cls:
                mock_client_cls.return_value = _make_mock_client(mock_response)
                result = await web_fetch(url="https://example.com")

        assert "Hello" in result
        assert "World" in result

    async def test_truncation(self) -> None:
        long_text = "<html><body>" + "x" * 20000 + "</body></html>"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = long_text
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"content-type": "text/html"}

        with patch("sage.tools.web_tools.validate_and_resolve_url", return_value=_EXAMPLE_RESOLVED):
            with patch("sage.tools.web_tools.httpx.AsyncClient") as mock_client_cls:
                mock_client_cls.return_value = _make_mock_client(mock_response)
                result = await web_fetch(url="https://example.com")

        assert len(result) <= 10500  # 10000 + some markdown overhead


class TestWebSearch:
    async def test_returns_results(self) -> None:
        """web_search should return formatted results (mocked)."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = (
            "<html><body>"
            '<a href="https://example.com">Example</a>'
            "<span>A test result snippet</span>"
            "</body></html>"
        )
        mock_response.raise_for_status = MagicMock()

        with patch("sage.tools.web_tools.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await web_search(query="test query")

        assert isinstance(result, str)


class TestWebFetchSSRF:
    """Tests for SSRF prevention in web_fetch."""

    @pytest.mark.parametrize(
        "url",
        [
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/",
            "http://127.0.0.1:8080/admin",
            "http://localhost/admin",
            "http://10.0.0.1/internal",
            "http://172.16.0.1/internal",
            "http://192.168.1.1/internal",
            "file:///etc/passwd",
            "ftp://internal.server/data",
        ],
    )
    async def test_ssrf_urls_blocked(self, url: str) -> None:
        with pytest.raises(ToolError, match="URL not allowed"):
            await web_fetch(url=url)

    async def test_public_url_allowed(self) -> None:
        """Public URLs should pass validation (actual fetch is mocked)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"content-type": "text/plain"}

        with patch("sage.tools.web_tools.validate_and_resolve_url", return_value=_EXAMPLE_RESOLVED):
            with patch("sage.tools.web_tools.httpx.AsyncClient") as mock_client_cls:
                mock_client_cls.return_value = _make_mock_client(mock_response)
                result = await web_fetch(url="https://example.com")
        assert result == "OK"


class TestWebFetchErrors:
    async def test_network_error_raises_tool_error(self) -> None:
        with patch("sage.tools.web_tools.validate_and_resolve_url", return_value=_EXAMPLE_RESOLVED):
            with patch("sage.tools.web_tools.httpx.AsyncClient") as mock_client_cls:
                mock_request = MagicMock()
                mock_request.extensions = {}

                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.build_request = MagicMock(return_value=mock_request)
                mock_client.send = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
                mock_client_cls.return_value = mock_client

                with pytest.raises(ToolError, match="web_fetch failed"):
                    await web_fetch(url="https://unreachable.example.com")
