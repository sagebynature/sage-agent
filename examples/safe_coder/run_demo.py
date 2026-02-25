#!/usr/bin/env python3
"""
run_demo.py -- Demo runner for the safe-coder agent.

Creates a temporary project directory, loads the safe-coder agent, and runs
it against the temp project to demonstrate permission prompts, file editing,
and token budget configuration.

Usage:
    python3 examples/safe_coder/run_demo.py

    # Verbose mode shows sage internals
    python3 examples/safe_coder/run_demo.py --verbose

Requirements:
    - OPENAI_API_KEY (or appropriate provider key) in .env or environment
    - pip install sage
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import logging.config
import os
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Add project root to path so we can import sage
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
DEFAULT_LOG_CONFIG = os.path.join(PROJECT_ROOT, "logging.conf")


def _setup_logging(config_path: str | None = None, verbose: bool = False) -> None:
    """Initialize logging from a config file with optional verbose override."""
    log_config = config_path or DEFAULT_LOG_CONFIG
    if os.path.isfile(log_config):
        logging.config.fileConfig(log_config, disable_existing_loggers=False)
    else:
        logging.basicConfig(
            level=logging.DEBUG if verbose else logging.WARNING,
            format="%(asctime)s|%(name)s:%(funcName)s:L%(lineno)s|%(levelname)s %(message)s",
        )

    if verbose:
        logging.getLogger("sage").setLevel(logging.DEBUG)


from sage import Agent  # noqa: E402
from sage.config import load_config  # noqa: E402

# Sample files to populate the temp project
SAMPLE_FILES = {
    "main.py": '''\
"""A simple calculator module."""


def add(a: int, b: int) -> int:
    return a + b


def subtract(a: int, b: int) -> int:
    return a - b


def divide(a: int, b: int) -> float:
    return a / b


if __name__ == "__main__":
    print(add(2, 3))
    print(divide(10, 0))
''',
    "utils.py": '''\
"""Utility functions."""

import os


def read_config(path: str) -> str:
    with open(path) as f:
        return f.read()


def write_output(path: str, data: str) -> None:
    with open(path, "w") as f:
        f.write(data)
''',
    "README.md": """\
# Demo Project

A small project used to demonstrate the safe-coder agent.
""",
}

# Prompts that exercise the agent's permission model
DEMO_PROMPTS = [
    # Read-only operations (allowed)
    "List all Python files in this project and summarize what each one does.",
    # Search (allowed)
    "Search for any division operations in the codebase. Are there potential ZeroDivisionError risks?",
    # Edit (requires permission)
    "Add a zero-division guard to the divide function in main.py.",
]


def create_temp_project() -> Path:
    """Create a temporary project directory with sample files."""
    tmp = Path(tempfile.mkdtemp(prefix="sage_demo_"))
    for name, content in SAMPLE_FILES.items():
        (tmp / name).write_text(content)
    return tmp


async def main() -> None:
    parser = argparse.ArgumentParser(description="Demo runner for the safe-coder agent")
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging for sage internals",
    )
    parser.add_argument(
        "--log-config",
        default=None,
        help="Path to logging.conf (default: project root logging.conf)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the model (default: uses AGENTS.md config)",
    )
    args = parser.parse_args()

    _setup_logging(args.log_config, args.verbose)

    # Load and validate agent config
    demo_dir = os.path.dirname(os.path.abspath(__file__))
    config = load_config(os.path.join(demo_dir, "AGENTS.md"))

    print("=" * 60)
    print("  Sage -- Safe Coder Demo")
    print("=" * 60)
    print(f"\n  Agent:       {config.name}")
    print(f"  Model:       {config.model}")
    print(f"  Tools:       {config.tools}")

    if config.permissions:
        print(f"  Permissions: default={config.permissions.default}")
        for rule in config.permissions.rules:
            patterns = f" patterns={rule.patterns}" if rule.patterns else ""
            destr = " [destructive]" if rule.destructive else ""
            print(f"    - {rule.tool}: {rule.action}{patterns}{destr}")

    if config.context:
        print(f"  Context:     compaction_threshold={config.context.compaction_threshold}")
        print(f"               reserve_tokens={config.context.reserve_tokens}")
        print(f"               prune_tool_outputs={config.context.prune_tool_outputs}")
        print(f"               tool_output_max_chars={config.context.tool_output_max_chars}")

    # Create temp project
    project_dir = create_temp_project()
    print(f"\n  Temp project: {project_dir}")
    print(f"  Files: {[f.name for f in project_dir.iterdir()]}")

    # Build agent
    agent = Agent.from_config(os.path.join(demo_dir, "AGENTS.md"))

    if args.model:
        agent.model = args.model
        agent.provider = __import__(
            "sage.providers.litellm_provider", fromlist=["LiteLLMProvider"]
        ).LiteLLMProvider(args.model)

    # Run demo prompts
    for i, prompt in enumerate(DEMO_PROMPTS, 1):
        print(f"\n{'─' * 60}")
        print(f"  [{i}/{len(DEMO_PROMPTS)}] {prompt}")
        print(f"{'─' * 60}\n")

        try:
            # Prepend project dir context so the agent knows where to look
            full_prompt = f"Working directory: {project_dir}\n\n{prompt}"
            result = await agent.run(full_prompt)
            print(f"  Agent:\n{result}\n")
        except Exception as e:
            print(f"  Error: {e}\n")

    await agent.close()
    print(f"\n  Temp project left at: {project_dir}")
    print("  (delete manually when done)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
