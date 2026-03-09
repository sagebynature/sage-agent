"""Managed subprocess registry for stateful process tools."""

from __future__ import annotations

import asyncio
import os
import shlex
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class ManagedProcess:
    process_id: str
    process: asyncio.subprocess.Process
    buffer: str = ""
    buffer_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    pump_tasks: list[asyncio.Task[None]] = field(default_factory=list)

    @property
    def running(self) -> bool:
        return self.process.returncode is None


class ProcessManager:
    def __init__(self) -> None:
        self._processes: dict[str, ManagedProcess] = {}

    async def start(
        self,
        command: Sequence[str] | str,
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        shell: bool = False,
    ) -> str:
        merged_env = None
        if env is not None:
            merged_env = {**os.environ, **env}

        if shell:
            shell_command = command if isinstance(command, str) else shlex.join(command)
            process = await asyncio.create_subprocess_shell(
                shell_command,
                cwd=cwd,
                env=merged_env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            argv = list(command) if not isinstance(command, str) else [command]
            process = await asyncio.create_subprocess_exec(
                *argv,
                cwd=cwd,
                env=merged_env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        process_id = uuid4().hex
        managed = ManagedProcess(process_id=process_id, process=process)
        managed.pump_tasks = [
            asyncio.create_task(self._pump_stream(managed, process.stdout)),
            asyncio.create_task(self._pump_stream(managed, process.stderr)),
        ]
        self._processes[process_id] = managed
        return process_id

    async def send(self, process_id: str, data: str) -> bool:
        managed = self._processes.get(process_id)
        if managed is None or managed.process.stdin is None or not managed.running:
            return False
        managed.process.stdin.write(data.encode())
        await managed.process.stdin.drain()
        return True

    async def read(
        self,
        process_id: str,
        *,
        max_chars: int = 4000,
        since_cursor: int | None = None,
    ) -> dict[str, Any]:
        managed = self._processes.get(process_id)
        if managed is None:
            return {"found": False, "process_id": process_id}

        async with managed.buffer_lock:
            buffer = managed.buffer

        if since_cursor is None:
            start = max(len(buffer) - max_chars, 0)
        else:
            start = max(since_cursor, 0)
        output = buffer[start : start + max_chars]
        cursor = start + len(output)
        return {
            "found": True,
            "process_id": process_id,
            "output": output,
            "cursor": cursor,
            "running": managed.running,
            "returncode": managed.process.returncode,
        }

    async def wait(self, process_id: str, timeout: float | None = None) -> dict[str, Any]:
        managed = self._processes.get(process_id)
        if managed is None:
            return {"found": False, "process_id": process_id}

        try:
            if timeout is None:
                await managed.process.wait()
            else:
                await asyncio.wait_for(managed.process.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return {
                "found": True,
                "process_id": process_id,
                "running": managed.running,
                "returncode": managed.process.returncode,
                "timed_out": True,
            }

        await self._flush_pumps(managed)
        return {
            "found": True,
            "process_id": process_id,
            "running": managed.running,
            "returncode": managed.process.returncode,
            "timed_out": False,
        }

    async def kill(self, process_id: str) -> dict[str, Any]:
        managed = self._processes.get(process_id)
        if managed is None:
            return {"found": False, "process_id": process_id}

        if managed.running:
            managed.process.terminate()
            try:
                await asyncio.wait_for(managed.process.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                managed.process.kill()
                await managed.process.wait()

        await self._flush_pumps(managed)
        return {
            "found": True,
            "process_id": process_id,
            "running": managed.running,
            "returncode": managed.process.returncode,
        }

    async def list_processes(self) -> list[dict[str, Any]]:
        return [
            {
                "process_id": process_id,
                "running": managed.running,
                "returncode": managed.process.returncode,
            }
            for process_id, managed in self._processes.items()
        ]

    async def _pump_stream(
        self,
        managed: ManagedProcess,
        stream: asyncio.StreamReader | None,
    ) -> None:
        if stream is None:
            return
        while True:
            chunk = await stream.read(4096)
            if not chunk:
                return
            async with managed.buffer_lock:
                managed.buffer += chunk.decode(errors="replace")

    async def _flush_pumps(self, managed: ManagedProcess) -> None:
        if managed.pump_tasks:
            await asyncio.gather(*managed.pump_tasks, return_exceptions=True)


_PROCESS_MANAGER = ProcessManager()


def get_process_manager() -> ProcessManager:
    return _PROCESS_MANAGER
