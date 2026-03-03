#!/usr/bin/make -f

.PHONY: check-env check-deps sync install update lint format type-check test test-only run clean validate-examples run-examples

PACKAGE_NAME = sage
SRC_DIR = $(PACKAGE_NAME)

check-env:
	@which python >/dev/null 2>&1 || (echo "Python 3 is required. Please install it first." && exit 1)
	@which uv >/dev/null 2>&1 || (echo "uv is required. Please install it first." && exit 1)

check-deps:
	@echo "Checking required binary dependencies..."
	@which rg >/dev/null 2>&1 || (echo "ERROR: ripgrep (rg) is required. Install: https://github.com/BurntSushi/ripgrep" && exit 1)
	@which git >/dev/null 2>&1 || (echo "ERROR: git is required." && exit 1)
	@which fd >/dev/null 2>&1 || which fdfind >/dev/null 2>&1 || (echo "WARNING: fd/fdfind not found. glob_find will use Python fallback.")
	@which gh >/dev/null 2>&1 || (echo "WARNING: gh (GitHub CLI) not found. git_pr_create will not work.")
	@echo "All required dependencies found."

sync: check-env
	uv sync --frozen --group dev

install: sync
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg

update: check-env
	uv sync --group dev

lint:
	uv run ruff check $(SRC_DIR) tests --fix

format:
	uv run ruff format $(SRC_DIR) tests

type-check:
	uv run ty check $(SRC_DIR)

test: sync lint format type-check
	uv run pytest -v tests

test-only:
	uv run pytest -v tests

clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +

validate-examples:
	uv run sage agent validate examples/simple_agent/AGENTS.md
	uv run sage agent validate examples/parallel_agents/AGENTS.md
	uv run sage agent validate examples/parallel_agents/research_agent
	uv run sage agent validate examples/parallel_agents/summarize_agent
	uv run sage agent validate examples/custom_tools/AGENTS.md
	uv run sage agent validate examples/mcp_agent/AGENTS.md
	uv run sage agent validate examples/claude_agent/AGENTS.md
	uv run sage agent validate examples/skills_agent/AGENTS.md
	uv run sage agent validate examples/memory_agent/AGENTS.md

# Run each example with a minimal prompt to verify end-to-end execution.
# Requires a configured LLM provider (see .env.example).
# Note: mcp_agent requires npx and @modelcontextprotocol/server-filesystem.
run-examples:
	@echo "--- simple_agent ---"
	uv run sage agent run examples/simple_assistant -i "Reply with exactly one word: hello."
	@echo "--- orchestrator ---"
	uv run sage agent run examples/parallel_agents -i "In one sentence, what is 1 + 1?"
	@echo "--- custom_tools ---"
	uv run sage agent run examples/custom_tools -i "List your available tools."
	@echo "--- mcp_agent ---"
	uv run sage agent run examples/mcp_agent -i "List the files in /tmp."
	@echo "--- skills_agent ---"
	uv run sage agent run examples/skills_agent -i "Review this code for issues: def add(a, b): return a + b"
	@echo "--- memory_agent ---"
	uv run python examples/memory_agent/run.py
