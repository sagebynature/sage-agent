#!/usr/bin/make -f

.PHONY: check-env check-deps sync install update lint format type-check test tests test-only run clean validate-examples run-examples demo-phase1 demo-orchestration run-examples-new check-tui-deps tui-install tui-build tui-dev tui-test tui-lint tui-install-global tui-clean

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

tests: test

test-only:
	uv run pytest -v tests

clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +

validate-examples:
	uv run sage agent validate examples/simple_assistant.md
	uv run sage agent validate examples/parallel_agents/AGENTS.md
	uv run sage agent validate examples/parallel_agents/research_agent
	uv run sage agent validate examples/parallel_agents/summarize_agent
	uv run sage agent validate examples/custom_tools/AGENTS.md
	uv run sage agent validate examples/mcp_agent/AGENTS.md
	uv run sage agent validate examples/claude_agent/AGENTS.md
	uv run sage agent validate examples/skills_agent/AGENTS.md

# Run each example with a minimal prompt to verify end-to-end execution.
# Requires a configured LLM provider (see .env.example).
# Note: mcp_agent requires npx and @modelcontextprotocol/server-filesystem.
run-examples:
	@echo "--- simple_agent ---"
	uv run sage agent run examples/simple-assistant.md -i "Reply with exactly one word: hello."
	@echo "--- orchestrator ---"
	uv run sage agent run examples/parallel_agents/orchestrator.md -i "research python vs rust and give me a summary"
	@echo "--- custom_tools ---"
	uv run sage agent run examples/custom_tools/tool-agent.md -i "List your available tools."
	@echo "--- mcp_agent ---"
	uv run sage agent run examples/mcp-assistant.md -i "List the files in /tmp using MCP"
	@echo "--- skills_agent ---"
	uv run sage agent run examples/skills_agent/skills-agent.md -i "Review this code for issues: def add(a, b): return a + b"
	@echo "--- memory_agent ---"
	uv run python examples/memory_agent/run.py

# ── New feature demos ──────────────────────────────────────────────────────────

# Demo: per-agent tool restrictions (blocked_tools + allowed_tools).
# Uses examples/phase1_foundation/config.toml so the category routing config
# (quick/deep) is also in scope.
demo-category-routing-with-tool-restrictions:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║  Demo: Session Continuity + Category Routing + Tool Restrictions ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "    orchestrator → researcher  (session_id, category routing)"
	@echo "    orchestrator → safe-coder  (blocked_tools in action)"
	@echo ""
	@echo "    The prompt asks the orchestrator to:"
	@echo "      1. Research asyncio.TaskGroup with category='deep' (routes to"
	@echo "         a more capable model), saving the session as 'asyncio-deep'"
	@echo "      2. Resume that same session to ask a follow-up about error"
	@echo "         handling (session continuity restores conversation history)"
	@echo "      3. Delegate to safe-coder to write a code example — the agent"
	@echo "         has no shell access, so it must write the file directly"
	@echo ""
	SAGE_CONFIG_PATH=examples/category_routing_with_tool_restrictions/config.toml \
		uv run sage agent run examples/category_routing_with_tool_restrictions/orchestrator.md \
		-i "Do three things in order: (1) delegate to researcher with category='deep' and session_id='asyncio-deep' to explain what asyncio.TaskGroup does and when to prefer it over asyncio.gather(); (2) resume session_id='asyncio-deep' to ask the researcher how TaskGroup handles exceptions raised by child tasks; (3) delegate to safe-coder to write a short Python snippet demonstrating TaskGroup with exception handling and save it to /tmp/taskgroup_example.py."

# Demo: planning pipeline — Planner decomposes a goal, Conductor drives
# execution task-by-task, Executor carries out each step.
# Uses the root config.toml (planning.analysis + planning.review enabled globally).
demo-orchestration:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║  Demo: Planning Pipeline (planner → conductor → executor)        ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "    Planner  — decomposes the goal into a structured plan"
	@echo "    Conductor — reads the plan and drives task-by-task execution"
	@echo "    Executor  — carries out each individual task and reports back"
	@echo ""
	@echo "    Prompt: a 3-step documentation task that exercises the full"
	@echo "    create → analyze → review → delegate → persist loop."
	@echo ""
	SAGE_CONFIG_PATH=examples/orchestrated_agents/config.toml \
	uv run sage agent run examples/orchestrated_agents/planner.md \
		-i "Create and execute a 3-step plan to document Python's core async primitives: (1) explain what asyncio.run() does and when to use it, (2) explain asyncio.gather() and how it differs from running tasks sequentially, (3) explain asyncio.TaskGroup and when it is preferable to gather(). Execute all three steps."

# Run both new feature demos back-to-back.
run-examples-new: demo-phase1 demo-orchestration

# ── TUI (Node.js / Ink) ──────────────────────────────────────────────────────

check-tui-deps:
	@which node >/dev/null 2>&1 || (echo "ERROR: Node.js 22+ is required for the TUI. Install: https://nodejs.org" && exit 1)
	@which pnpm >/dev/null 2>&1 || (echo "ERROR: pnpm 10+ is required for the TUI. Install: https://pnpm.io" && exit 1)
	@echo "TUI dependencies found."

tui-install: check-tui-deps
	cd tui && pnpm install

tui-build: tui-install
	cd tui && pnpm run build

tui-dev: tui-install
	cd tui && pnpm run dev

tui-test: tui-install
	cd tui && pnpm run test

tui-lint: tui-install
	cd tui && pnpm run lint
	cd tui && pnpm run typecheck

tui-install-global: tui-build
	cd tui && pnpm run install:global

tui-clean:
	rm -rf tui/dist tui/node_modules
