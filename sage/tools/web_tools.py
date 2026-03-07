"""Web tools: search and fetch."""

from __future__ import annotations

import logging
import re
import urllib.parse

import httpx
from markdownify import markdownify as md

from sage.exceptions import ToolError
from sage.tools._security import validate_and_resolve_url
from sage.tools.decorator import tool

logger = logging.getLogger(__name__)

_MAX_CONTENT_LENGTH = 10000


@tool
async def web_fetch(url: str) -> str:
    """Fetch a URL and return content as markdown.

    HTML is automatically converted to markdown.
    Content is truncated to 10000 characters.

    Validates the URL targets a public IP (not internal/private) before fetching.
    """
    logger.debug("web_fetch: %s", url)
    validate_and_resolve_url(url)

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0, verify=True) as client:
            response = await client.get(url, headers={"User-Agent": "Sage/1.0"})
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ToolError(f"HTTP {exc.response.status_code}: {url}") from exc
    except Exception as exc:
        detail = str(exc) or type(exc).__name__
        raise ToolError(f"web_fetch failed: {detail}") from exc

    content_type = response.headers.get("content-type", "")
    text = response.text

    # Convert HTML to markdown.
    if "html" in content_type or text.strip().startswith("<"):
        text = md(text, strip=["script", "style", "img"])

    # Truncate.
    if len(text) > _MAX_CONTENT_LENGTH:
        text = text[:_MAX_CONTENT_LENGTH] + "\n\n[Content truncated]"

    return text


@tool
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo HTML. Returns titles, URLs, and snippets."""
    logger.debug("web_search: %s", query[:100])
    encoded = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": ("Mozilla/5.0 (compatible; Sage/1.0)"),
                },
            )
            response.raise_for_status()
    except Exception as exc:
        detail = str(exc) or type(exc).__name__
        raise ToolError(f"web_search failed: {detail}") from exc

    # Parse results from DDG HTML.
    text = response.text
    results: list[str] = []

    # DDG HTML results are in <a class="result__a" ...> tags
    links = re.findall(r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', text, re.DOTALL)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:td|div|span)>', text, re.DOTALL)

    for i, (link, title) in enumerate(links[:max_results]):
        # Clean HTML tags from title and snippet.
        clean_title = re.sub(r"<[^>]+>", "", title).strip()
        snippet = ""
        if i < len(snippets):
            snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()

        # Decode DDG redirect URLs.
        if "uddg=" in link:
            match = re.search(r"uddg=([^&]+)", link)
            if match:
                link = urllib.parse.unquote(match.group(1))

        results.append(f"{i + 1}. {clean_title}\n   {link}\n   {snippet}")

    if not results:
        return f"No results found for: {query}"

    return "\n\n".join(results)
