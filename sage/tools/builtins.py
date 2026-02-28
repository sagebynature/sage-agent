"""Built-in tools for file I/O, shell execution, HTTP, and memory."""

from __future__ import annotations

import json
import logging
import os
import re
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from sage.exceptions import ToolError
from sage.tools._security import ResolvedURL, validate_and_resolve_url
from sage.tools.decorator import tool

if TYPE_CHECKING:
    from sage.tools._sandbox import SandboxExecutor

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
    # Git-specific dangerous commands
    r"\bgit\s+push\s+.*--force\b",
    r"\bgit\s+push\s+.*-f\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[fd]",
    r"\bgit\s+checkout\s+\.\s*$",
    r"\bgit\s+branch\s+-D\b",
    r"\bgit\s+rebase\b",
    r"\bgit\s+push\s+.*\bmain\b",
    r"\bgit\s+push\s+.*\bmaster\b",
    # Interpreter-based bypasses
    r"\bpython[23]?\s+-c\s+",
    r"\bperl\s+-e\s+",
    r"\bruby\s+-e\s+",
    r"\bnode\s+-e\s+",
    r"\bnodejs\s+-e\s+",
    # Base64 decode piped to shell
    r"\bbase64\s+(-d|--decode)\b.*\|",
    # wget/curl to pipe to shell
    r"\b(curl|wget)\s+.*\|\s*(sh|bash|zsh|fish)\b",
    # Environment variable prefix bypass
    r"\benv\s+.*\brm\b",
]


def _check_dangerous_patterns(command: str, allowed_patterns: frozenset[str] | None = None) -> None:
    """Raise ToolError if *command* matches any dangerous pattern.

    Patterns listed in *allowed_patterns* are skipped.
    """
    for pattern in _DANGEROUS_PATTERNS:
        if allowed_patterns and pattern in allowed_patterns:
            continue
        if re.search(pattern, command, re.IGNORECASE):
            raise ToolError(f"Command rejected \u2014 matches dangerous pattern: {pattern}")


def _validate_shell_command(command: str, allowed_patterns: frozenset[str] | None = None) -> None:
    """Validate each segment of a chained command independently.

    First checks the full command string (catches pipe-based patterns like
    curl | bash and base64 -d | sh), then splits on &&, ||, ;, | and
    checks each segment independently.
    """
    # Check full command first — catches pipe-to-shell and base64-decode-pipe patterns
    _check_dangerous_patterns(command, allowed_patterns)
    # Also check each chained segment independently
    segments = re.split(r"\s*(?:&&|\|\||;|\|)\s*", command)
    for segment in segments:
        segment = segment.strip()
        if segment:
            _check_dangerous_patterns(segment, allowed_patterns)


@tool
async def shell(command: str) -> str:
    """Run a shell command and return combined stdout and stderr.

    Security: Commands are checked against a blocklist of dangerous patterns
    (destructive operations, data exfiltration, command substitution wrapping).
    This is defense-in-depth — not a substitute for OS-level sandboxing.
    """
    import asyncio

    logger.debug("shell: %s", command[:100])
    _validate_shell_command(command)

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


def make_shell(allowed_patterns: frozenset[str] | None = None) -> Any:
    """Build a ``@tool``-decorated ``shell`` function with custom allowed patterns.

    Returns a ``@tool``-decorated async callable that can be passed directly
    to ``ToolRegistry.register()``.  Registering it under the same name
    ``"shell"`` replaces the module-level default.
    """

    @tool
    async def shell(command: str) -> str:  # noqa: F811
        """Run a shell command and return combined stdout and stderr.

        Security: Commands are checked against a blocklist of dangerous patterns
        (destructive operations, data exfiltration, command substitution wrapping).
        This is defense-in-depth — not a substitute for OS-level sandboxing.
        """
        import asyncio

        logger.debug("shell: %s", command[:100])
        _validate_shell_command(command, allowed_patterns)

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

    return shell


def make_sandboxed_shell(
    sandbox: SandboxExecutor, allowed_patterns: frozenset[str] | None = None
) -> Any:
    """Build a ``@tool``-decorated ``shell`` function bound to *sandbox*.

    This factory creates a per-agent ``shell`` tool that executes commands
    through *sandbox* (environment isolation, optional namespace containment).
    The dangerous-pattern blocklist still applies as a fast-fail first pass.

    Returns a ``@tool``-decorated async callable that can be passed directly
    to ``ToolRegistry.register()``.  Registering it under the same name
    ``"shell"`` replaces the module-level default.
    """

    @tool
    async def shell(command: str) -> str:  # noqa: F811
        """Run a shell command and return combined stdout and stderr.

        Security: Commands are checked against a blocklist of dangerous patterns
        first, then executed inside an isolated sandbox environment that strips
        inherited environment variables (blocking ``$SHELL`` / env-var bypass).
        """
        logger.debug("shell (sandboxed): %s", command[:100])
        _validate_shell_command(command, allowed_patterns)
        stdout, stderr = await sandbox.execute(command)
        output = stdout
        if stderr.strip():
            output += f"\n[stderr]\n{stderr}"
        return output.strip()

    return shell


# ---------------------------------------------------------------------------
# File tools
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# HTTP tool
# ---------------------------------------------------------------------------


def _build_pinned_url(resolved: ResolvedURL) -> str:
    """Build a URL that substitutes the hostname with the resolved IP address.

    The resulting URL connects directly to the pinned IP, preventing DNS
    rebinding after validation.  Callers must pass the original hostname as
    the HTTP ``Host`` header and, for HTTPS, set ``sni_hostname`` so that
    TLS certificate verification uses the correct name.
    """
    port = resolved.port
    if port is None:
        port = 443 if resolved.scheme == "https" else 80
    query_str = f"?{resolved.query}" if resolved.query else ""
    path = resolved.path or "/"
    return f"{resolved.scheme}://{resolved.resolved_ip}:{port}{path}{query_str}"


@tool
async def http_request(
    url: str,
    method: str = "GET",
    headers: str = "",
    body: str = "",
) -> str:
    """Make an HTTP request and return the response status and body.

    SSRF protection: resolves the hostname exactly once, validates the
    resulting IP, then connects to that pinned IP address.  This prevents
    DNS rebinding (TOCTOU) where a second resolution could return a
    private/internal address.

    Args:
        url: The URL to request.
        method: HTTP method (GET, POST, PUT, DELETE, etc.). Defaults to GET.
        headers: Comma-separated headers in ``Name: Value`` format, e.g.
            ``"Content-Type: application/json, X-API-Key: abc"``.
        body: Request body for POST/PUT requests.

    Returns:
        Response as ``Status: <code>\\n<body>`` (body truncated to 5000 chars).
    """
    logger.debug("http_request: %s %s", method.upper(), url)
    resolved = validate_and_resolve_url(url)

    req_headers: dict[str, str] = {
        "User-Agent": "Sage/1.0",
        "Host": resolved.hostname,
    }
    if headers:
        for h in headers.split(","):
            if ":" in h:
                k, v = h.split(":", 1)
                req_headers[k.strip()] = v.strip()

    pinned_url = _build_pinned_url(resolved)
    content = body.encode() if body else None

    try:
        async with httpx.AsyncClient(verify=True, timeout=30.0) as client:
            request = client.build_request(
                method.upper(),
                pinned_url,
                headers=req_headers,
                content=content,
            )
            # Pin TLS SNI to the original hostname so cert validation works
            # correctly when the URL uses the resolved IP address.
            request.extensions["sni_hostname"] = resolved.hostname.encode()
            response = await client.send(request)
            body_text = response.text[:5000]
            return f"Status: {response.status_code}\n{body_text}"
    except httpx.HTTPStatusError as exc:
        return f"HTTP Error {exc.response.status_code}: {exc.response.text[:1000]}"
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
    warnings.warn(
        "The JSON memory_store tool is deprecated. Configure a 'memory:' backend "
        "in your agent frontmatter to use semantic memory instead.",
        DeprecationWarning,
        stacklevel=2,
    )
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
    warnings.warn(
        "The JSON memory_recall tool is deprecated. Configure a 'memory:' backend "
        "in your agent frontmatter to use semantic memory instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    logger.debug("memory_recall: %s", query[:100])
    data = _load_memory()
    if not data:
        return "No memories stored yet"

    q = query.lower()
    matches = {k: v for k, v in data.items() if q in k.lower() or q in v.lower()}
    if not matches:
        return f"No matches for: {query}"
    return json.dumps(matches, indent=2)
