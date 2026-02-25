"""Built-in tools for file I/O, shell execution, HTTP, and memory."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from sage.exceptions import ToolError
from sage.tools._security import validate_url
from sage.tools.decorator import tool

logger = logging.getLogger(__name__)


def _validate_path(path: str, allowed_dir: Path | None = None) -> Path:
    """Validate that a path resolves within the allowed directory.

    Raises ToolError if the resolved path is outside the allowed directory.
    Defaults to CWD if no allowed_dir is specified.
    """
    resolved = Path(path).resolve()
    base = (allowed_dir or Path.cwd()).resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise ToolError(f"Access denied: {path} is outside allowed directory ({base})")
    return resolved


# Patterns considered dangerous for shell execution.
_DANGEROUS_PATTERNS: list[str] = [
    # Destructive filesystem commands (flexible whitespace, various targets)
    r"\brm\s+-\w*r\w*f\b.*\s/",  # rm with -rf flags targeting /
    r"\brm\s+--no-preserve-root",  # explicit root removal
    r"\bmkfs\b",  # format filesystem
    r"\bdd\s+.*of=/dev/",  # overwrite devices
    r":>\s*/dev/",  # redirect to devices
    # System control
    r"\bshutdown\b",
    r"\breboot\b",
    r"\binit\s+[06]\b",
    r"\bsystemctl\s+(halt|poweroff|reboot)\b",
    # Command substitution wrapping dangerous commands
    r"\$\(.*\brm\s+-\w*r",  # $(rm -r...)
    r"`.*\brm\s+-\w*r",  # `rm -r...`
    # Eval/exec wrappers
    r"\beval\s+",
    r"\bbash\s+-c\s+",
    r"\bsh\s+-c\s+",
    # Data exfiltration patterns
    r"\bcurl\b.*(-d\s+@|-T\s+|--data-binary\s+@|--upload-file\s+)",
    r"\bwget\b.*--post-file",
]


@tool
async def shell(command: str) -> str:
    """Run a shell command and return combined stdout and stderr.

    Security: Commands are checked against a blocklist of dangerous patterns
    (destructive operations, data exfiltration, command substitution wrapping).
    This is defense-in-depth — not a substitute for OS-level sandboxing.
    """
    logger.debug("shell: %s", command[:100])
    for pattern in _DANGEROUS_PATTERNS:
        if re.search(pattern, command):
            raise ToolError(f"Command rejected \u2014 matches dangerous pattern: {pattern}")

    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    output = stdout.decode(errors="replace")
    if stderr:
        err_text = stderr.decode(errors="replace")
        if err_text:
            output += f"\n[stderr]\n{err_text}"
    return output.strip()


@tool
async def file_read(path: str) -> str:
    """Read and return the contents of a file.

    Paths are restricted to the current working directory for security.
    """
    logger.debug("file_read: %s", path)
    file_path = _validate_path(path)
    if not file_path.is_file():
        raise ToolError(f"File not found: {path}")
    return file_path.read_text(encoding="utf-8")


@tool
async def file_write(path: str, content: str) -> str:
    """Write content to a file, creating parent directories as needed.

    Paths are restricted to the current working directory for security.
    """
    logger.debug("file_write: %s (%d bytes)", path, len(content))
    file_path = _validate_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} bytes to {path}"


@tool
async def http_request(
    url: str,
    method: str = "GET",
    headers: str = "",
    body: str = "",
) -> str:
    """Make an HTTP request and return the response status and body.

    SSRF protection: blocks private IPs, loopback, link-local,
    cloud metadata endpoints, and non-HTTP schemes.

    Args:
        url: The URL to request.
        method: HTTP method (GET, POST, PUT, DELETE, etc.). Defaults to GET.
        headers: Comma-separated headers in ``Name: Value`` format, e.g.
            ``"Content-Type: application/json, X-API-Key: abc"``.
        body: Request body for POST/PUT requests.

    Returns:
        Response as ``Status: <code>\n<body>`` (body truncated to 5000 chars).
    """
    logger.debug("http_request: %s %s", method.upper(), url)
    validate_url(url)
    req_headers: dict[str, str] = {"User-Agent": "Sage/1.0"}
    if headers:
        for h in headers.split(","):
            if ":" in h:
                k, v = h.split(":", 1)
                req_headers[k.strip()] = v.strip()

    data = body.encode() if body else None
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method.upper())

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body_text = resp.read().decode("utf-8", errors="replace")
            return f"Status: {resp.status}\n{body_text[:5000]}"
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")[:1000]
        return f"HTTP Error {exc.code}: {error_body}"
    except Exception as exc:
        raise ToolError(f"http_request failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Memory tools
# ---------------------------------------------------------------------------

_MEMORY_PATH_DEFAULT = Path.home() / ".sage" / "memory_store.json"


def _memory_path() -> Path:
    """Return the memory storage path (overridable via SAGE_MEMORY_PATH)."""
    env = os.environ.get("SAGE_MEMORY_PATH", "")
    return Path(env) if env else _MEMORY_PATH_DEFAULT


def _load_memory() -> dict[str, str]:
    path = _memory_path()
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data: dict[str, str] = json.load(f)
            return data
    except Exception:
        return {}


def _save_memory(data: dict[str, str]) -> None:
    path = _memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


@tool
async def memory_store(key: str, value: str) -> str:
    """Persist a key-value pair to long-term memory.

    Memory survives across sessions and is stored locally at
    ``~/.sage/memory_store.json`` (override with ``SAGE_MEMORY_PATH``).

    Args:
        key: The key to store under.
        value: The value to store (any string).

    Returns:
        Confirmation message.
    """
    logger.debug("memory_store: key=%s", key)
    data = _load_memory()
    data[key] = value
    _save_memory(data)
    return f"Stored: {key}"


@tool
async def memory_recall(query: str) -> str:
    """Search long-term memory for entries matching the query.

    Performs a case-insensitive substring match on both keys and values.

    Args:
        query: Search string to match against stored keys and values.

    Returns:
        JSON object of matching entries, or a message if nothing matches.
    """
    logger.debug("memory_recall: %s", query[:100])
    data = _load_memory()
    if not data:
        return "No memories stored yet"

    q = query.lower()
    matches = {k: v for k, v in data.items() if q in k.lower() or q in v.lower()}
    if not matches:
        return f"No matches for: {query}"
    return json.dumps(matches, indent=2)
