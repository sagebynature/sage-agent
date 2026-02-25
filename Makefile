#!/usr/bin/make -f

.PHONY: check-env check-deps sync install update lint format type-check test run clean validate-examples run-examples build publish

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

install: check-env
	uv sync --frozen --group dev

update: check-env
	uv sync --group dev

lint:
	uv run ruff check $(SRC_DIR) tests --fix

format:
	uv run ruff format $(SRC_DIR) tests

type-check:
	uv run mypy $(SRC_DIR)

test: install lint format type-check
	uv run pytest -v tests

test-only:
	uv run pytest -v tests

clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +

validate-examples:
	uv run sage agent validate examples/simple_agent/AGENTS.md
	uv run sage agent validate examples/parallel_agents/AGENTS.md
	uv run sage agent validate examples/parallel_agents/researcher.md
	uv run sage agent validate examples/parallel_agents/summarizer.md
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
	uv run sage agent run examples/simple_agent -i "Reply with exactly one word: hello."
	@echo "--- orchestrator ---"
	uv run sage agent run examples/parallel_agents -i "In one sentence, what is 1 + 1?"
	@echo "--- custom_tools ---"
	uv run sage agent run examples/custom_tools -i "List your available tools."
	@echo "--- mcp_agent ---"
	uv run sage agent run examples/mcp_agent -i "List the files in /tmp."
	@echo "--- claude_agent ---"
	uv run sage agent run examples/claude_agent -i "Reply with exactly one word: hello."
	@echo "--- skills_agent ---"
	uv run sage agent run examples/skills_agent -i "Review this code for issues: def add(a, b): return a + b"
	@echo "--- memory_agent ---"
	uv run python examples/memory_agent/run.py

# Library build and publish commands
build: install
	@echo "Building $(PACKAGE_NAME)..."
	@if [ -n "$(TAG)" ]; then \
		echo "Setting version to $(TAG)..."; \
		cp pyproject.toml pyproject.toml.bak; \
		sed -i 's/^version = ".*"/version = "$(TAG)"/' pyproject.toml; \
	fi
	@echo "Cleaning previous builds..."
	rm -rf dist/
	@echo "Building package..."
	uv build || { if [ -f pyproject.toml.bak ]; then mv pyproject.toml.bak pyproject.toml; fi; exit 1; }
	@if [ -f pyproject.toml.bak ]; then \
		echo "Restoring original pyproject.toml..."; \
		mv pyproject.toml.bak pyproject.toml; \
	fi
	@echo "Build completed."
	ls -la dist/

publish: build
	@echo "Publishing $(PACKAGE_NAME) to Azure Artifacts..."
	@if [ -z "$$AZURE_ARTIFACTS_ENV_ACCESS_TOKEN" ]; then \
		echo "Error: AZURE_ARTIFACTS_ENV_ACCESS_TOKEN environment variable is required"; \
		exit 1; \
	fi
	uv publish \
		--publish-url "https://pkgs.dev.azure.com/ApolloAzureDevOps/_packaging/ApolloAzureDevOps/pypi/upload/" \
		--username user \
		--password "$$AZURE_ARTIFACTS_ENV_ACCESS_TOKEN" \
		dist/*
	@echo "Successfully published to Azure Artifacts."