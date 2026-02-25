#!/usr/bin/env python3
"""
run_demo.py — Interactive demo runner for the skills_demo agent.

This script exercises the DevOps assistant agent with prompts that showcase
each skill. It demonstrates that the agent uses real computation (via skills)
rather than hallucinating answers.

Usage:
    # Run all demo scenarios
    python3 examples/skills_demo/run_demo.py

    # Run a specific scenario
    python3 examples/skills_demo/run_demo.py --scenario crypto

    # Interactive mode
    python3 examples/skills_demo/run_demo.py --interactive

Requirements:
    - OPENAI_API_KEY (or appropriate provider key) in .env or environment
    - pip install sage
"""

import argparse
import asyncio
import logging
import logging.config
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Add project root to path so we can import sage
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Configure logging — use project logging.conf if available, else sensible defaults.
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

# Demo scenarios — each targets a specific skill
SCENARIOS = {
    "crypto": {
        "title": "Crypto Toolkit (Bash)",
        "description": "Demonstrates that LLMs cannot compute real cryptographic hashes.",
        "prompts": [
            'What is the SHA-256 hash of the string "Hello, Sage!"?',
            "Generate a 32-byte secure random token for use as an API key.",
            'Base64 encode the string "skills give agents superpowers".',
        ],
    },
    "network": {
        "title": "Network Diagnostics (Bash)",
        "description": "Demonstrates real-time network probing that LLMs cannot do.",
        "prompts": [
            "Is google.com reachable? What's the latency?",
            "Run a full diagnostic report on github.com.",
        ],
    },
    "dependencies": {
        "title": "Dependency Auditor (JavaScript/Node.js)",
        "description": "Analyzes real project files that LLMs cannot read from disk.",
        "prompts": [
            "Audit the dependencies in sample_data/package.json — "
            "what version patterns are used and are there any warnings?",
            "Analyze the Python dependencies in sample_data/requirements.txt. "
            "Are there any unpinned packages or security concerns?",
        ],
    },
    "data": {
        "title": "Data Cruncher (Python)",
        "description": "Performs precise statistical computation that LLMs cannot do reliably.",
        "prompts": [
            "Analyze the sample metrics data at sample_data/metrics.csv. "
            "Give me a full statistical summary.",
            "What's the correlation between cpu_usage and response_time_ms "
            "in sample_data/metrics.csv?",
            "Are there any outliers in the response_time_ms column of sample_data/metrics.csv?",
        ],
    },
}


async def run_scenario(agent: Agent, scenario_key: str) -> None:
    """Run a single demo scenario."""
    scenario = SCENARIOS[scenario_key]
    print(f"\n{'=' * 70}")
    print(f"  SCENARIO: {scenario['title']}")
    print(f"  {scenario['description']}")
    print(f"{'=' * 70}")

    for i, prompt in enumerate(scenario["prompts"], 1):
        print(f"\n{'─' * 70}")
        print(f"  [{i}] User: {prompt}")
        print(f"{'─' * 70}\n")

        try:
            result = await agent.run(prompt)
            print(f"  Agent:\n{result}\n")
        except Exception as e:
            print(f"  Error: {e}\n")


async def run_interactive(agent: Agent) -> None:
    """Interactive chat mode."""
    print("\n" + "=" * 70)
    print("  INTERACTIVE MODE — DevOps Assistant with Skills")
    print("  Type 'quit' to exit, 'help' for suggested prompts")
    print("=" * 70)

    suggestions = [
        'What is the SHA-256 hash of "test"?',
        "Is github.com reachable?",
        "Analyze sample_data/metrics.csv",
        "Generate a secure 64-byte token",
        "Check what ports are open on localhost",
        "What's the P99 response time in sample_data/metrics.csv?",
    ]

    while True:
        try:
            prompt = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not prompt:
            continue
        if prompt.lower() == "quit":
            print("Goodbye!")
            break
        if prompt.lower() == "help":
            print("\nSuggested prompts:")
            for s in suggestions:
                print(f"  • {s}")
            continue

        try:
            result = await agent.run(prompt)
            print(f"\nAgent: {result}")
        except Exception as e:
            print(f"\nError: {e}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Demo runner for Sage skills showcase")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()) + ["all"],
        default="all",
        help="Which demo scenario to run (default: all)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive chat mode",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the model (default: uses AGENTS.md config)",
    )
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
    args = parser.parse_args()

    # Initialize logging before anything else.
    _setup_logging(args.log_config, args.verbose)

    # Load agent from config — this auto-discovers skills/ directory
    demo_dir = os.path.dirname(os.path.abspath(__file__))
    agent = Agent.from_config(os.path.join(demo_dir, "AGENTS.md"))

    # Override model if specified
    if args.model:
        agent.model = args.model
        agent.provider = __import__(
            "sage.providers.litellm_provider", fromlist=["LiteLLMProvider"]
        ).LiteLLMProvider(args.model)

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║           Sage — Skills Demo                    ║")
    print("║                                                             ║")
    print("║  This demo shows an agent augmented with skills that give   ║")
    print("║  it capabilities no LLM has natively:                       ║")
    print("║                                                             ║")
    print("║  • Crypto Toolkit (Bash)    — Real cryptographic hashing    ║")
    print("║  • Network Diagnostics (Bash) — Live network probing        ║")
    print("║  • Dependency Auditor (JS)  — Project file analysis         ║")
    print("║  • Data Cruncher (Python)   — Precise statistics            ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\n  Agent: {agent.name}")
    print(f"  Model: {agent.model}")
    print(f"  Skills loaded: {[s.name for s in agent.skills]}")
    print(f"  Tools: {list(agent.tool_registry._schemas.keys())}")

    if args.interactive:
        await run_interactive(agent)
    elif args.scenario == "all":
        for key in SCENARIOS:
            await run_scenario(agent, key)
    else:
        await run_scenario(agent, args.scenario)

    await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
