"""Stateful process tools built on the shared ProcessManager."""

from __future__ import annotations

from typing import Any

from sage.models import ToolMetadata, ToolResourceRef, ToolResult
from sage.tools.decorator import tool
from sage.tools.process_manager import get_process_manager

_MANAGER = get_process_manager()


@tool
async def process_start(
    command: list[str] | str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    shell: bool = False,
) -> ToolResult:
    """Start a managed subprocess and return its process ID."""
    process_id = await _MANAGER.start(command, cwd=cwd, env=env, shell=shell)
    return ToolResult(
        text=f"Started process {process_id}",
        data={"process_id": process_id, "running": True},
        resource=ToolResourceRef(kind="process", resource_id=process_id),
        metadata={"process_id": process_id},
    )


@tool
async def process_send(process_id: str, data: str) -> ToolResult:
    """Send text to a managed process stdin."""
    sent = await _MANAGER.send(process_id, data)
    return ToolResult(
        text=f"{'Sent input to' if sent else 'Could not write to'} process {process_id}",
        data={"process_id": process_id, "sent": sent},
        resource=ToolResourceRef(kind="process", resource_id=process_id),
    )


@tool
async def process_read(
    process_id: str,
    max_chars: int = 4000,
    since_cursor: int | None = None,
) -> ToolResult:
    """Read buffered output from a managed process."""
    payload = await _MANAGER.read(process_id, max_chars=max_chars, since_cursor=since_cursor)
    if not payload.get("found", True):
        return ToolResult(text=f"Process {process_id} not found", data=payload)
    return ToolResult(
        text=payload["output"],
        data=payload,
        resource=ToolResourceRef(kind="process", resource_id=process_id),
    )


@tool
async def process_wait(process_id: str, timeout: float | None = None) -> ToolResult:
    """Wait for a managed process to exit."""
    payload = await _MANAGER.wait(process_id, timeout=timeout)
    if not payload.get("found", True):
        return ToolResult(text=f"Process {process_id} not found", data=payload)
    if payload.get("timed_out"):
        text = f"Process {process_id} is still running"
    else:
        text = f"Process {process_id} exited with code {payload['returncode']}"
    return ToolResult(
        text=text,
        data=payload,
        resource=ToolResourceRef(kind="process", resource_id=process_id),
    )


@tool
async def process_kill(process_id: str) -> ToolResult:
    """Terminate a managed process."""
    payload = await _MANAGER.kill(process_id)
    if not payload.get("found", True):
        return ToolResult(text=f"Process {process_id} not found", data=payload)
    return ToolResult(
        text=f"Stopped process {process_id}",
        data=payload,
        resource=ToolResourceRef(kind="process", resource_id=process_id),
    )


@tool
async def process_list() -> ToolResult:
    """List managed processes."""
    processes = await _MANAGER.list()
    return ToolResult(
        text=f"{len(processes)} managed processes",
        data={"count": len(processes), "processes": processes},
    )


for fn in (process_start, process_send, process_read, process_wait, process_kill, process_list):
    fn.__tool_schema__.metadata = ToolMetadata(  # type: ignore[attr-defined]
        risk_level="medium",
        stateful=True,
        resource_kind="process",
        approval_hint="Starts or interacts with a persistent local process.",
        idempotent=False,
    )
