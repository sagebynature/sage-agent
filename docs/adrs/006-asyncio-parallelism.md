# ADR-006: asyncio for Parallelism

## Status
Accepted

## Context
LLM API calls are I/O-bound, often taking seconds per request. The SDK must support running multiple agents concurrently (parallel execution, race conditions) and handling streaming responses without blocking.

Alternatives considered included threading (`concurrent.futures`), multiprocessing, and Trio/AnyIO.

## Decision
Use `asyncio` as the concurrency model throughout the SDK. All provider calls, memory operations, and MCP interactions are `async`/`await`. The `Orchestrator` uses `asyncio.gather` for parallel execution and `asyncio.wait` with `FIRST_COMPLETED` for race semantics. Sync tool functions are bridged via `asyncio.to_thread`.

## Consequences
**Positive:**
- Native Python async support, no external runtime required
- Efficient for I/O-bound workloads (LLM calls, network, disk)
- Single-threaded model avoids race conditions on shared state
- Clean composition with `async for` streaming and context managers
- `asyncio.TaskGroup` (Python 3.11+) provides structured concurrency

**Negative:**
- Requires `async`/`await` throughout the call chain (viral pattern)
- CPU-bound operations (embedding generation) must be offloaded to thread pool
- Debugging async stack traces is harder than synchronous code
- Users must understand async basics to use the code API effectively
