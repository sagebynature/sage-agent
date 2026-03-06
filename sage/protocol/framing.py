"""Message framing for JSON-RPC over stdio."""

from __future__ import annotations

import asyncio
import json
import logging

logger = logging.getLogger(__name__)


async def read_message(reader: asyncio.StreamReader) -> dict | None:
    """Read a newline-delimited JSON message from stdin.

    Returns:
        Parsed JSON dict on success, None on EOF.

    Logs warnings for partial reads or malformed JSON and continues.
    """
    try:
        line = await reader.readuntil(b"\n")
        if not line:
            return None

        line = line.rstrip(b"\n")

        try:
            return json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.warning(f"Malformed JSON received: {e}")
            return None

    except asyncio.LimitOverrunError as e:
        logger.warning(f"Message too long or incomplete: {e}")
        return None
    except asyncio.IncompleteReadError:
        return None
    except Exception as e:
        logger.warning(f"Error reading message: {e}")
        return None


async def write_message(writer: asyncio.StreamWriter, message: dict) -> None:
    """Write a JSON message to stdout with newline and ensure flush.

    Args:
        writer: asyncio.StreamWriter for stdout
        message: Dict to serialize as JSON
    """
    try:
        json_str = json.dumps(message)
        writer.write(json_str.encode("utf-8"))
        writer.write(b"\n")
        await writer.drain()
    except Exception as e:
        logger.error(f"Error writing message: {e}")
