# ADR-001: Pure Python

## Status
Accepted

## Context
The Sage needs a primary implementation language. The SDK must support rich AI/ML library integrations (sentence-transformers, litellm, numpy), provide a familiar developer experience for the AI/ML community, and enable rapid prototyping of agent workflows.

Alternative languages considered included Rust (as used by ZeroClaw for performance) and TypeScript (as used by OpenClaw and Vercel AI SDK for web ecosystem compatibility).

## Decision
Implement the SDK in pure Python, targeting Python 3.11+ for modern syntax features including:
- Native `str | None` union types
- `asyncio.TaskGroup` for structured concurrency
- Improved error messages and type annotations

## Consequences
**Positive:**
- Direct access to the Python AI/ML ecosystem (sentence-transformers, numpy, litellm)
- Familiar to the majority of AI/ML practitioners
- Rapid development and iteration cycles
- Strong async/await support for I/O-bound LLM workloads
- Pydantic for robust configuration validation

**Negative:**
- Slower execution than Rust or Go for CPU-bound tasks
- GIL limits true parallelism (mitigated by asyncio for I/O-bound work)
- Deployment requires Python runtime and dependency management
