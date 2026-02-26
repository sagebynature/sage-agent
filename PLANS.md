# sage-agent Gap Remediation Plans

> Generated 2026-02-26 from competitive analysis against Claude Code, Codex CLI, Aider, OpenCode, Goose, Cline, CrewAI, LangGraph, SWE-agent, and others.

---

## Table of Contents

1. [Plan 1: Git Integration (P0)](#plan-1-git-integration)
2. [Plan 2: Execution Sandboxing (P0)](#plan-2-execution-sandboxing)
3. [Plan 3: Headless / CI Mode (P1)](#plan-3-headless--ci-mode)
4. [Plan 4: Built-in Evaluation CLI (P1)](#plan-4-built-in-evaluation-cli)
5. [Plan 5: Observability & Tracing (P1)](#plan-5-observability--tracing)
6. [Plan 6: IDE Integration (P2)](#plan-6-ide-integration)
7. [Plan 7: Durable Execution & Sessions (P2)](#plan-7-durable-execution--sessions)
8. [Plan 8: AGENTS.md Naming Resolution (P2)](#plan-8-agentsmd-naming-resolution)
9. [Plan 9: Multimodal Input (P3)](#plan-9-multimodal-input)
10. [Plan 10: CLI UX Table-Stakes (P2)](#plan-10-cli-ux-table-stakes)
11. [Plan 11: Community & Ecosystem (P3)](#plan-11-community--ecosystem)
12. [Plan 12: Plugin Marketplace (P3)](#plan-12-plugin-marketplace)

---

## Plan 1: Git Integration

**Priority:** P0 (Critical)
**Effort:** Medium (2-3 weeks)
**Rationale:** Every major agent CLI has git integration. Aider's identity is built on it. Without git tools, agents can't safely make code changes with rollback capability.

### Current State

- `sage/git/snapshot.py` exists with `GitSnapshot` class (stash-based snapshots using `git stash create` + `git stash store` with `sage:` prefix)
- `shell` tool can run git commands but has no git-specific dangerous pattern detection
- Permission system supports pattern matching on shell commands (e.g., `"git log*": allow`)
- No `git` permission category exists

### Architecture

```
sage/git/
  snapshot.py      # existing - stash-based snapshots
  tools.py         # NEW - GitTools(ToolBase) with @tool methods
  safety.py        # NEW - git-specific command validation

sage/tools/
  registry.py      # UPDATE - add "git" permission category
  builtins.py      # UPDATE - add git patterns to _DANGEROUS_PATTERNS
```

### Implementation Steps

#### Step 1: Add git-specific dangerous patterns to `_DANGEROUS_PATTERNS`

**File:** `sage/tools/builtins.py`

Add these patterns:
```python
r"\bgit\s+push\s+.*--force\b",
r"\bgit\s+push\s+.*-f\b",
r"\bgit\s+reset\s+--hard\b",
r"\bgit\s+clean\s+-[fd]",
r"\bgit\s+checkout\s+\.\s*$",
r"\bgit\s+branch\s+-D\b",
r"\bgit\s+rebase\b",              # requires interactive approval
r"\bgit\s+push\s+.*main\b",       # push to main should require approval
r"\bgit\s+push\s+.*master\b",
```

#### Step 2: Create `GitTools(ToolBase)` class

**File:** `sage/git/tools.py` (new)

```python
class GitTools(ToolBase):
    """First-class git integration tools."""

    def __init__(self, repo_root: Path | None = None):
        super().__init__()
        self._repo_root = repo_root or Path.cwd()
        self._sage_commit_hashes: set[str] = set()  # track sage-authored commits

    @tool
    async def git_status(self) -> str:
        """Show working tree status (staged, unstaged, untracked files)."""

    @tool
    async def git_diff(self, ref: str = "HEAD", staged: bool = False) -> str:
        """Show diff of changes. Use staged=True for staged changes only."""

    @tool
    async def git_log(self, count: int = 10, oneline: bool = True) -> str:
        """Show recent commit history."""

    @tool
    async def git_commit(self, message: str, files: list[str] | None = None) -> str:
        """Stage and commit files. If files is None, commits all staged changes.
        Appends 'Co-authored-by: sage-agent' trailer automatically."""

    @tool
    async def git_branch(self, name: str | None = None, list_branches: bool = False) -> str:
        """Create a new branch or list existing branches."""

    @tool
    async def git_undo(self) -> str:
        """Undo the last sage-authored commit (only if not yet pushed).
        Uses _sage_commit_hashes to verify safe undo."""
```

Design decisions (following Aider's proven patterns):
- Auto-commit attribution via `Co-authored-by: sage-agent <noreply@sagebynature.com>` trailer
- Track sage commit hashes in `_sage_commit_hashes` for safe undo (Aider pattern)
- `git_undo` checks: (1) commit was authored by sage, (2) not yet pushed to remote, (3) no dirty files in changed paths
- Commit dirty files separately before AI edits when `auto_snapshot: true` is set (Aider pattern)

#### Step 3: Add `git` permission category

**File:** `sage/tools/registry.py`

```python
CATEGORY_TOOLS["git"] = [
    "git_status", "git_diff", "git_log", "git_commit",
    "git_branch", "git_undo",
    "snapshot_create", "snapshot_restore", "snapshot_list",
]

CATEGORY_ARG_MAP["git"] = "command"  # or None if using structured args
```

**File:** `sage/config.py`

Add `git` to the `Permission` model.

#### Step 4: Auto-snapshot before agent runs

**File:** `sage/agent.py` — in `run()` method

Before the first turn, if git tools are enabled:
1. Check for dirty working tree
2. Call `GitSnapshot.snapshot_create("pre-run")` to save state
3. Optionally auto-commit dirty files (configurable via `git.auto_commit_dirty: true`)

#### Step 5: Worktree support for parallel agents

**File:** `sage/git/tools.py`

```python
@tool
async def git_worktree_create(self, name: str, branch: str | None = None) -> str:
    """Create an isolated git worktree at .sage/worktrees/<name>.
    Uses detached HEAD to avoid branch pollution (Codex pattern)."""

@tool
async def git_worktree_remove(self, name: str) -> str:
    """Remove a worktree. Warns if uncommitted changes exist."""
```

Worktree path: `.sage/worktrees/<name>` (following Claude Code convention).

#### Step 6: Agent config support

```yaml
# AGENTS.md frontmatter
git:
  auto_snapshot: true        # snapshot before runs (default: true)
  auto_commit_dirty: false   # commit dirty files before AI edits (default: false)
  auto_commit_edits: false   # auto-commit after file_write/file_edit (default: false)

permission:
  git: allow                 # or {pattern: action} for fine-grained
```

### Tests

- `tests/test_git/test_tools.py` — unit tests for each git tool
- `tests/test_git/test_safety.py` — verify dangerous patterns are blocked
- `tests/test_git/test_undo.py` — verify undo safety checks
- Integration test: run an agent that edits files, verify commits are attributed

### Dependencies

None new — `asyncio.create_subprocess_exec` for git commands (same as `shell` tool).

---

## Plan 2: Execution Sandboxing

**Priority:** P0 (Critical)
**Effort:** High (3-4 weeks)
**Rationale:** Without sandboxing, a hallucinating LLM can `rm -rf /` or exfiltrate data via `curl`. Codex CLI uses OS-level Landlock + seccomp. Claude Code uses bubblewrap + proxy-based network filtering. The current regex-based `_DANGEROUS_PATTERNS` is trivially bypassable (e.g., `python3 -c "import shutil; shutil.rmtree('/')"` is not blocked).

### Current State

- `sage/tools/_security.py` — SSRF protection for URLs (blocks private IPs, cloud metadata)
- `sage/tools/builtins.py` — `_DANGEROUS_PATTERNS` regex blocklist (14 patterns), acknowledged as "not a substitute for OS-level sandboxing"
- `sage/tools/builtins.py` — `_validate_path()` restricts `file_read`/`file_write`/`file_edit` to cwd, but `shell` has no path restriction
- `sage/permissions/` — ALLOW/DENY/ASK per tool category with glob pattern matching
- No filesystem isolation, no network isolation, no container support

### Architecture

Layered defense-in-depth, each layer independently useful:

```
Layer 1: Improved Application Checks     (1 week)
Layer 2: Bubblewrap/Seatbelt Subprocess  (2 weeks)
Layer 3: Docker Container Backend         (1 week, optional)

sage/sandbox/
  __init__.py
  config.py        # SandboxConfig Pydantic model
  manager.py       # SandboxManager (platform detection + dispatch)
  bubblewrap.py    # Linux bwrap implementation
  seatbelt.py      # macOS sandbox-exec implementation
  docker.py        # Docker container backend (optional)
  none.py          # Passthrough (no sandbox)
```

### Implementation Steps

#### Step 1: Harden application-level checks (Layer 1)

**File:** `sage/tools/builtins.py`

Expand `_DANGEROUS_PATTERNS`:
```python
# Interpreter-based bypasses
r"\bpython[23]?\s+-c\s+",
r"\bperl\s+-e\s+",
r"\bruby\s+-e\s+",
r"\bnode\s+-e\s+",
# Base64 decode piped to shell
r"\bbase64\s+(-d|--decode)\s*\|",
# Environment variable prefix bypass
r"\benv\s+.*\brm\b",
# wget/curl to pipe to shell
r"\b(curl|wget)\s+.*\|\s*(sh|bash|zsh)\b",
```

Add **chained command detection** (following Claude Code's approach):
```python
def _validate_shell_command(command: str) -> None:
    """Validate each segment of a chained command independently."""
    # Split on &&, ||, ;, | and validate each segment
    segments = re.split(r'\s*(?:&&|\|\||;|\|)\s*', command)
    for segment in segments:
        _check_dangerous_patterns(segment.strip())
```

#### Step 2: Implement `SandboxConfig` model

**File:** `sage/sandbox/config.py`

```python
class SandboxConfig(BaseModel):
    enabled: bool = False
    mode: Literal["read-only", "workspace-write", "full-access"] = "workspace-write"
    workspace: Path = Field(default_factory=Path.cwd)
    writable_roots: list[str] = Field(default_factory=lambda: ["/tmp"])
    network_access: bool = False
    deny_read: list[str] = Field(default_factory=lambda: ["~/.ssh", "~/.aws", "~/.gnupg"])
    timeout: float = 30.0
    backend: Literal["auto", "bubblewrap", "seatbelt", "docker", "none"] = "auto"
```

**File:** `sage/config.py` — add `sandbox` to `AgentConfig`.

#### Step 3: Implement bubblewrap backend (Linux)

**File:** `sage/sandbox/bubblewrap.py`

```python
class BubblewrapSandbox:
    """Linux sandbox using bubblewrap (bwrap)."""

    async def execute(self, command: str, config: SandboxConfig) -> SandboxResult:
        bwrap_args = [
            "bwrap",
            "--ro-bind", "/", "/",                          # read-only root
            "--bind", str(config.workspace), str(config.workspace),  # writable workspace
            "--bind", "/tmp", "/tmp",
            "--dev", "/dev",
            "--proc", "/proc",
            "--die-with-parent",
        ]
        if not config.network_access:
            bwrap_args.append("--unshare-net")              # network namespace isolation
        for path in config.writable_roots:
            expanded = Path(path).expanduser().resolve()
            bwrap_args.extend(["--bind", str(expanded), str(expanded)])
        for path in config.deny_read:
            expanded = Path(path).expanduser().resolve()
            if expanded.exists():
                bwrap_args.extend(["--tmpfs", str(expanded)])  # hide with empty tmpfs
        bwrap_args.extend(["--", "sh", "-c", command])
        # ... asyncio.create_subprocess_exec with timeout
```

#### Step 4: Implement seatbelt backend (macOS)

**File:** `sage/sandbox/seatbelt.py`

Generate a dynamic Seatbelt profile and invoke via `sandbox-exec`:
```python
class SeatbeltSandbox:
    """macOS sandbox using sandbox-exec (Seatbelt)."""

    def _generate_profile(self, config: SandboxConfig) -> str:
        """Generate a Seatbelt profile string."""
        # (version 1)
        # (allow default)
        # (deny file-write* (subpath "/") (allow (subpath workspace)))
        # (deny network*)  if not config.network_access
```

#### Step 5: Wire sandbox into shell tool

**File:** `sage/tools/builtins.py`

The `shell()` function currently uses `asyncio.create_subprocess_shell`. Replace with:
```python
async def shell(command: str, timeout: float = 30.0) -> str:
    """Execute a shell command."""
    _validate_shell_command(command)  # application-level check (Layer 1)

    sandbox = _get_sandbox()  # from agent context
    if sandbox and sandbox.config.enabled:
        result = await sandbox.execute(command, timeout=timeout)
        return result.stdout
    else:
        # fallback to direct execution (current behavior)
        proc = await asyncio.create_subprocess_shell(...)
```

#### Step 6: Optional Docker backend

**File:** `sage/sandbox/docker.py`

For evaluation/benchmark scenarios:
```python
class DockerSandbox:
    """Strongest isolation using ephemeral Docker containers."""

    async def execute(self, command: str, config: SandboxConfig) -> SandboxResult:
        # docker run --rm --network=none --read-only \
        #   --tmpfs /tmp:size=512m -v workspace:/workspace:rw \
        #   --memory=512m --cpus=0.5 --pids-limit=100 \
        #   python:3.11-slim sh -c "command"
```

### Agent Config

```yaml
# AGENTS.md frontmatter
sandbox:
  enabled: true
  mode: workspace-write
  network_access: false
  deny_read: ["~/.ssh", "~/.aws"]
  timeout: 30
  backend: auto                  # auto-detects: bwrap on Linux, seatbelt on macOS
```

### Tests

- `tests/test_sandbox/test_bubblewrap.py` — requires Linux, skip on macOS/Windows
- `tests/test_sandbox/test_seatbelt.py` — requires macOS, skip on Linux/Windows
- `tests/test_sandbox/test_security.py` — verify chained command detection, bypass prevention
- `tests/test_sandbox/test_config.py` — config parsing and validation

### Dependencies

- `bubblewrap` — system package on Linux (`apt install bubblewrap`, `brew install bubblewrap`)
- `sandbox-exec` — built into macOS (no install needed)
- `docker` — optional, for Docker backend

### Risk Mitigation

- Sandbox is **opt-in** (`enabled: false` default) to avoid breaking existing users
- Graceful degradation: if `bwrap` is not installed, log a warning and fall back to application-level checks
- `backend: auto` detects the platform and selects the best available backend
- `backend: none` explicitly disables sandboxing (for trusted environments)

---

## Plan 3: Headless / CI Mode

**Priority:** P1 (High)
**Effort:** Low-Medium (1-2 weeks)
**Rationale:** The 2026 trend is agents in CI/CD pipelines — code review bots, test writers, PR generators. Codex CLI has `codex exec`, Cline CLI 2.0 has headless mode, Aider supports `--yes` + piping. sage-agent's `sage agent run -i "..."` is close but lacks structured output, proper exit codes, and CI-safe permission handling.

### Current State

- `sage agent run AGENTS.md -i "text" [--stream]` works for single-shot execution
- Output is plain text only (no JSON)
- All errors return exit code 1 (no differentiation)
- `ASK` permissions silently become `ALLOW` when no interactive handler is registered (security hole)
- No `--timeout`, `--json`, `--yes`, `--quiet`, `--stdin` flags
- No GitHub Actions template or CI documentation

### Implementation Steps

#### Step 1: Structured exit codes

**File:** `sage/cli/main.py`

```python
EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_PROVIDER_ERROR = 3
EXIT_TOOL_ERROR = 4
EXIT_PERMISSION_DENIED = 5
EXIT_TIMEOUT = 6
EXIT_MAX_TURNS = 7
```

Update the error handler:
```python
except ConfigError as e:
    click.echo(f"Config error: {e}", err=True)
    sys.exit(EXIT_CONFIG_ERROR)
except ProviderError as e:
    click.echo(f"Provider error: {e}", err=True)
    sys.exit(EXIT_PROVIDER_ERROR)
except ToolError as e:
    click.echo(f"Tool error: {e}", err=True)
    sys.exit(EXIT_TOOL_ERROR)
except PermissionError as e:
    click.echo(f"Permission denied: {e}", err=True)
    sys.exit(EXIT_PERMISSION_DENIED)
```

#### Step 2: Add CI-mode flags

**File:** `sage/cli/main.py`

```python
@agent.command()
@click.argument("config_path")
@click.option("--input", "-i", "user_input")
@click.option("--stream", is_flag=True)
@click.option("--json", "json_output", is_flag=True, help="JSONL event stream to stdout")
@click.option("--output", "-o", type=click.Path(), help="Write final message to file")
@click.option("--yes", is_flag=True, help="Auto-approve all ASK permissions")
@click.option("--deny-all", is_flag=True, help="Deny all ASK permissions (safe CI default)")
@click.option("--timeout", type=float, help="Max execution time in seconds")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-essential output")
@click.option("--stdin", is_flag=True, help="Read input from stdin")
```

#### Step 3: Fix ASK permission security hole

**File:** `sage/tools/registry.py`

Replace the current "silently allow" behavior:
```python
if decision.action == PermissionAction.ASK:
    if self._auto_approve:
        logger.info("Auto-approving tool %r (--yes mode)", name)
        # proceed
    elif self._deny_all:
        logger.warning("Denying tool %r (--deny-all mode)", name)
        return "Permission denied: tool execution blocked in CI mode"
    else:
        logger.warning("Permission ASK for tool %r with no handler; denying.", name)
        return "Permission denied: no interactive handler available"
```

#### Step 4: JSONL output format

**File:** `sage/cli/output.py` (new)

```python
class JSONLWriter:
    """Writes JSONL events to stdout for machine consumption."""

    def session_started(self, agent_name: str, model: str) -> None:
        self._write({"type": "session.started", "agent": agent_name, "model": model,
                      "timestamp": _now()})

    def turn_started(self, turn: int, max_turns: int) -> None:
        self._write({"type": "turn.started", "turn": turn, "max_turns": max_turns})

    def tool_started(self, name: str, arguments: dict) -> None:
        self._write({"type": "tool.started", "name": name, "arguments": arguments,
                      "timestamp": _now()})

    def tool_completed(self, name: str, result: str, duration_ms: int) -> None:
        self._write({"type": "tool.completed", "name": name,
                      "result": result[:1000], "duration_ms": duration_ms})

    def turn_completed(self, turn: int, usage: dict) -> None:
        self._write({"type": "turn.completed", "turn": turn, "usage": usage})

    def session_completed(self, output: str, total_usage: dict, duration_ms: int) -> None:
        self._write({"type": "session.completed", "output": output,
                      "usage": total_usage, "duration_ms": duration_ms})

    def _write(self, event: dict) -> None:
        sys.stdout.write(json.dumps(event) + "\n")
        sys.stdout.flush()
```

#### Step 5: Stdin piping support

```python
if stdin_flag:
    user_input = sys.stdin.read().strip()
elif user_input is None:
    click.echo("Error: --input or --stdin required", err=True)
    sys.exit(EXIT_GENERAL_ERROR)
```

#### Step 6: Timeout implementation

```python
try:
    result = await asyncio.wait_for(agent.run(user_input), timeout=timeout)
except asyncio.TimeoutError:
    click.echo("Error: execution timed out", err=True)
    sys.exit(EXIT_TIMEOUT)
```

#### Step 7: GitHub Actions workflow template

**File:** `examples/github-actions/review.yml`

```yaml
name: Sage Agent Code Review
on:
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: astral-sh/setup-uv@v5
      - run: uv pip install sage-agent

      - name: Run review agent
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          git diff origin/main...HEAD | \
            sage agent run .sage/reviewer.md \
              --stdin --yes --timeout 120 --json \
              -o review.json

      - name: Post review
        run: |
          jq -r '.output' review.json | \
            gh pr comment ${{ github.event.pull_request.number }} --body @-
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Tests

- `tests/test_cli/test_headless.py` — exit codes, JSON output, timeout, stdin
- `tests/test_cli/test_permissions_ci.py` — verify ASK->DENY in CI mode, ASK->ALLOW with --yes
- Test the GitHub Actions workflow in a sample repo

---

## Plan 4: Built-in Evaluation CLI

**Priority:** P1 (High)
**Effort:** Medium (2-3 weeks)
**Rationale:** Only OpenAI Agents SDK, CrewAI, and LangSmith have meaningful eval stories. sage-evaluator exists but is a separate package with no `sage eval` command. A built-in eval system with dataset support, code assertions, and regression tracking is a significant differentiator.

### Current State

- `sage-evaluator` is a separate package with `evaluate validate|benchmark|suggest|compare` commands
- Has `LLMJudge` (1-5 rubric scoring), `InstrumentedProvider` (metrics capture), `PricingLookup`
- Benchmarks use a single intent string — no dataset/test-case concept
- No regression tracking between runs
- No code-based assertions (only LLM-as-judge)
- No trajectory evaluation (only final output judged)
- No `sage eval` CLI command

### Architecture

```
sage/eval/
  __init__.py
  suite.py           # TestSuite, TestCase models
  assertions.py      # Assertion types (exact, contains, regex, python, llm_judge, tool_calls)
  runner.py           # EvalRunner — execute test cases against agent
  history.py          # SQLite-backed eval history for regression tracking
  report.py           # Report generation (text, JSON, markdown)

sage/cli/
  main.py             # UPDATE — add `sage eval` command group
```

### Test Suite Format

**File format:** YAML

```yaml
# evals/code-reviewer.yaml
name: code-reviewer-eval
description: Evaluation suite for the code reviewer agent
agent: ./code-reviewer/AGENTS.md
rubric: code_generation                 # built-in rubric name or path to custom YAML

test_cases:
  - id: detect-sql-injection
    input: "Review this code for security issues"
    context_files: ["fixtures/vulnerable_app.py"]   # files to place in working dir
    assertions:
      - type: contains
        value: "SQL injection"
      - type: contains
        value: "parameterized"
      - type: tool_calls
        expected: ["file_read"]
      - type: llm_judge
        min_score: 3.5
    tags: [security, critical]

  - id: handle-clean-code
    input: "Review this code"
    context_files: ["fixtures/clean_code.py"]
    assertions:
      - type: not_contains
        value: "critical"
      - type: llm_judge
        min_score: 4.0
    tags: [positive-case]

settings:
  models: ["gpt-4o", "anthropic/claude-sonnet-4-20250514"]
  runs_per_case: 3
  timeout: 60
  max_turns: 10
```

### Assertion Types

| Type | Description | Inspired By |
|------|-------------|-------------|
| `exact_match` | String equality | OpenAI `string_check` (eq) |
| `contains` | Substring present in output | OpenAI `string_check` (like) |
| `not_contains` | Substring absent from output | Negation guard |
| `regex` | Regex pattern matches output | Standard |
| `json_schema` | Output validates against JSON Schema | OpenAI custom schema |
| `python` | Custom Python function returns score 0-1 | OpenAI `PythonGrader` |
| `llm_judge` | LLM evaluates against rubric (1-5) | sage-evaluator `LLMJudge` |
| `tool_calls` | Expected tools were called | LangSmith trajectory eval |
| `no_tool_calls` | Certain tools were NOT called | Safety guard |
| `cost_under` | Total cost below threshold | Cost guard |
| `turns_under` | Completed in fewer than N turns | Efficiency guard |

### CLI Commands

```
sage eval run <suite.yaml> [-m model1 -m model2] [--runs N] [--format text|json]
sage eval validate <suite.yaml>
sage eval history [--suite name] [--last N]
sage eval compare <run-id-1> <run-id-2>
sage eval list                          # list available suites
```

### Regression Tracking

SQLite-backed eval history at `~/.config/sage/eval_history.db`:

```sql
CREATE TABLE eval_runs (
    id          TEXT PRIMARY KEY,
    suite_name  TEXT NOT NULL,
    model       TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    completed_at TEXT,
    pass_rate   REAL,
    avg_score   REAL,
    total_cost  REAL,
    total_tokens INTEGER,
    metadata    TEXT DEFAULT '{}'
);

CREATE TABLE eval_results (
    id          TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL REFERENCES eval_runs(id),
    test_case_id TEXT NOT NULL,
    passed      BOOLEAN NOT NULL,
    score       REAL,
    output      TEXT,
    assertions  TEXT,    -- JSON array of assertion results
    latency_ms  INTEGER,
    tokens      INTEGER,
    cost        REAL
);
```

### CI/CD Integration

```bash
# Fail CI if pass rate drops below threshold
sage eval run evals/suite.yaml --format json --min-pass-rate 0.9
# Exit 0 if >= 90% pass, exit 1 otherwise
```

### Dependencies

- Reuse existing `sage-evaluator` components (`LLMJudge`, `InstrumentedProvider`, rubrics)
- New: `pyyaml` (already a dependency), `aiosqlite` (already a dependency)

---

## Plan 5: Observability & Tracing

**Priority:** P1 (High)
**Effort:** Medium (2-3 weeks)
**Rationale:** LangGraph has LangSmith. OpenAI Agents SDK has built-in tracing. When an agent produces bad output, you need to understand why. The TUI already instruments tool calls — this generalizes that pattern.

### Current State

- Python `logging` with `colorlog.ColoredFormatter` (basic text logs)
- Agent loop logs: run start/end, turn count, tool dispatch, tool errors, compaction
- TUI `instrument_agent()` wraps `ToolRegistry.execute` to emit Textual events — this is a proto-tracing system
- `LiteLLMProvider` extracts `Usage` but discards it (not propagated to agent)
- `litellm` has built-in OTEL integration (`litellm.success_callback = ["otel"]`) — unused
- `litellm.completion_cost()` is available but unused
- No structured traces, no spans, no cost tracking, no OTEL export

### Architecture

```
sage/observability/
  __init__.py
  models.py          # TraceContext, Span, SpanType
  collector.py       # TraceCollector — accumulates spans during a run
  litellm_logger.py  # CustomLogger subclass for litellm callbacks
  otel.py            # OpenTelemetry export adapter
  console.py         # Console/JSONL export
  sqlite_store.py    # Local trace storage for development

sage/providers/
  litellm_provider.py  # UPDATE — wire litellm callbacks, propagate Usage + cost
```

### Implementation Steps

#### Step 1: Quick win — add cost tracking to LiteLLMProvider

**File:** `sage/providers/litellm_provider.py`

After each completion:
```python
try:
    cost = litellm.completion_cost(completion_response=response)
except Exception:
    cost = 0.0

usage = Usage(
    prompt_tokens=...,
    completion_tokens=...,
    total_tokens=...,
    cost=cost,     # new field
)
```

**File:** `sage/models.py` — add `cost: float = 0.0` to `Usage` model.

**File:** `sage/agent.py` — accumulate `self._session_cost` and expose via `get_usage_stats()`.

#### Step 2: Define trace data model

**File:** `sage/observability/models.py`

```python
class SpanType(str, Enum):
    AGENT = "agent"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    DELEGATION = "delegation"
    MEMORY_RECALL = "memory_recall"
    MEMORY_STORE = "memory_store"
    MCP_CALL = "mcp_call"
    COMPACTION = "compaction"

class Span(BaseModel):
    span_id: str
    trace_id: str
    parent_span_id: str | None = None
    name: str                          # e.g., "chat gpt-4o", "tool shell"
    span_type: SpanType
    start_time: float
    end_time: float | None = None
    status: Literal["success", "failure"] = "success"
    attributes: dict[str, Any] = Field(default_factory=dict)
    # gen_ai.* convention attributes stored here

class TraceContext(BaseModel):
    trace_id: str
    agent_name: str
    model: str
    start_time: float
    end_time: float | None = None
    spans: list[Span] = Field(default_factory=list)
    total_cost: float = 0.0
    total_tokens: int = 0
```

#### Step 3: Implement TraceCollector

**File:** `sage/observability/collector.py`

```python
class TraceCollector:
    """Accumulates spans during an agent run."""

    def __init__(self, agent_name: str, model: str):
        self.trace = TraceContext(
            trace_id=uuid4().hex, agent_name=agent_name,
            model=model, start_time=time.time()
        )
        self._span_stack: list[Span] = []

    def start_span(self, name: str, span_type: SpanType, **attrs) -> Span: ...
    def end_span(self, span: Span, status: str = "success") -> None: ...
    def finalize(self) -> TraceContext: ...
```

#### Step 4: Instrument agent loop

**File:** `sage/agent.py`

Wrap key operations with spans:
- `run()` → `SpanType.AGENT`
- Each `provider.complete()` call → `SpanType.LLM_CALL` with `gen_ai.*` attributes
- Each `tool_registry.execute()` → `SpanType.TOOL_CALL`
- Each `delegate()` → `SpanType.DELEGATION`
- Each `memory.recall()` → `SpanType.MEMORY_RECALL`
- Each `compact_messages()` → `SpanType.COMPACTION`

#### Step 5: LiteLLM CustomLogger for automatic LLM tracing

**File:** `sage/observability/litellm_logger.py`

```python
class SageLiteLLMLogger(CustomLogger):
    def __init__(self, collector: TraceCollector):
        self.collector = collector

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        payload = kwargs.get("standard_logging_object", {})
        span = self.collector.start_span(
            f"chat {payload.get('model', 'unknown')}",
            SpanType.LLM_CALL,
            **{
                "gen_ai.request.model": payload.get("model"),
                "gen_ai.usage.input_tokens": payload.get("prompt_tokens"),
                "gen_ai.usage.output_tokens": payload.get("completion_tokens"),
                "gen_ai.response.cost": payload.get("response_cost"),
                "gen_ai.response.time": payload.get("response_time"),
            }
        )
        span.start_time = start_time.timestamp()
        self.collector.end_span(span, start_time=start_time, end_time=end_time)
```

#### Step 6: OTEL export (optional)

**File:** `sage/observability/otel.py`

Two approaches:
1. **Use litellm's built-in OTEL**: `litellm.success_callback = ["otel"]` — covers LLM calls automatically
2. **Custom OTEL spans for tool calls**: Create OTEL spans alongside sage-native spans

Config:
```yaml
observability:
  enabled: true
  exporters: ["console"]          # console | jsonl | sqlite | otel
  otel_endpoint: "http://localhost:4318/v1/traces"    # optional
  capture_content: false          # opt-in for input/output capture
```

### Tests

- `tests/test_observability/test_collector.py` — span lifecycle, nesting, finalization
- `tests/test_observability/test_litellm_logger.py` — cost calculation, token tracking
- `tests/test_observability/test_cost.py` — verify cost accumulation across turns

### Dependencies

New optional: `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp` (only if OTEL export is enabled).

---

## Plan 6: IDE Integration

**Priority:** P2 (High effort, high impact)
**Effort:** 2-8 weeks (phased)
**Rationale:** Developers live in their editors. OpenCode reaches Zed/JetBrains/Neovim via ACP. Claude Code has a VS Code extension. A terminal-only tool is always secondary.

### Phased Approach

#### Phase 1: File Watcher (Aider-style) — 1-2 days

**File:** `sage/watch.py` (new)

```python
AI_COMMENT_PATTERN = re.compile(
    r'(?:#|//|--|;)\s*(?:SAGE[!?]|.*\bSAGE[!?])\s*(.*)', re.IGNORECASE
)

class SageFileWatcher:
    """Watch for SAGE! comments in files and trigger agent runs."""

    def __init__(self, agent: Agent, watch_dir: str = "."):
        self.agent = agent
        self.observer = Observer()  # from watchdog

    async def process_file_change(self, filepath: str) -> None:
        """Scan changed file for SAGE! comments, send to agent."""
```

**File:** `sage/cli/main.py` — add `sage watch` command.

Works with **every editor** immediately. Users add `# SAGE! refactor this function` comments and save.

#### Phase 2: ACP Server — 2-3 weeks

**File:** `sage/acp/server.py` (new)

Implement the Agent Client Protocol (JSON-RPC 2.0 over stdio). This unlocks Zed, JetBrains, Neovim, and Emacs with a single implementation.

Key methods:
- `initialize` → return agent capabilities
- `session/new` → create agent session
- `session/prompt` → run agent, stream `session/update` notifications
- `permission/request` → forward to IDE for approval
- `fs/read_text_file` → delegate to IDE for file reads

**File:** `sage/cli/main.py` — add `sage acp` command.

**Dependencies:** `agent-client-protocol` Python SDK (`pip install agent-client-protocol`).

Editor configuration:

```json
// JetBrains acp.json
{"agents": [{"name": "sage-agent", "command": "sage", "args": ["acp", "-c", "AGENTS.md"]}]}
```

```json
// Zed settings.json
{"agent": {"profiles": {"sage": {"command": "sage", "args": ["acp", "-c", "AGENTS.md"]}}}}
```

#### Phase 3: VS Code Extension (optional) — 4-8 weeks

Only pursue if ACP integration proves insufficient for VS Code users. A minimal extension that:
1. Opens a terminal running `sage tui -c AGENTS.md`
2. Sends selected text as context
3. Uses VS Code's `createTerminal` API

### Recommended Priority

Phase 1 (file watcher) and Phase 2 (ACP) are the highest-leverage investments. ACP reaches 5+ editors with one implementation.

---

## Plan 7: Durable Execution & Sessions

**Priority:** P2
**Effort:** Medium (2-3 weeks)
**Rationale:** If an agent crashes mid-run, all progress is lost. LangGraph's core value is durable execution. Codex CLI has session resume/fork. Claude Code persists conversations.

### Architecture

Reuse existing `aiosqlite` infrastructure from `sage/memory/sqlite_backend.py`.

```
sage/sessions/
  __init__.py
  manager.py         # SessionManager — create/load/save/list/fork
  models.py          # Session, Checkpoint models
  storage.py         # SQLite storage implementation
```

### SQLite Schema

```sql
CREATE TABLE sessions (
    id            TEXT PRIMARY KEY,
    agent_name    TEXT NOT NULL,
    agent_model   TEXT NOT NULL,
    working_dir   TEXT NOT NULL,
    title         TEXT DEFAULT '',
    status        TEXT DEFAULT 'active',    -- active | paused | completed | error
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    parent_id     TEXT,                     -- for fork support
    message_count INTEGER DEFAULT 0,
    total_tokens  INTEGER DEFAULT 0,
    total_cost    REAL DEFAULT 0.0,
    metadata      TEXT DEFAULT '{}'
);

CREATE TABLE checkpoints (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES sessions(id),
    sequence_num  INTEGER NOT NULL,
    conversation  TEXT NOT NULL,            -- JSON array of Message.model_dump()
    agent_state   TEXT NOT NULL,            -- JSON blob of runtime state
    created_at    TEXT NOT NULL,
    UNIQUE(session_id, sequence_num)
);

CREATE INDEX idx_sessions_dir ON sessions(working_dir, updated_at DESC);
```

Storage location: `~/.config/sage/sessions.db`

### CLI Integration

```
sage session list [--all]              # List sessions (default: current directory)
sage session resume [SESSION_ID]       # Resume (picker if no ID)
sage session resume --last             # Resume most recent
sage session fork [SESSION_ID]         # Fork into new thread
sage session export <SESSION_ID>       # Export as JSON
sage session delete <SESSION_ID>

# Shorthand flags:
sage agent run AGENTS.md -i "..." --continue     # Continue last session
sage agent run AGENTS.md -i "..." --resume ID    # Resume specific
sage tui -c AGENTS.md --continue
```

### Checkpoint Strategy

- **Full checkpoint** after each completed `run()` / `stream()` call
- **Incremental turn writes** for each message within a turn (crash recovery)
- Signal handler on SIGTERM/SIGINT for graceful checkpoint
- Resume loads latest checkpoint, restores `_conversation_history` and agent state

### Fork Flow

1. Load source session's latest checkpoint
2. Create new session with `parent_id = source_session_id`
3. Copy conversation history to new session
4. New session proceeds independently

---

## Plan 8: AGENTS.md Naming Resolution

**Priority:** P2
**Effort:** Low (1-2 days)
**Rationale:** The AGENTS.md community standard (60K+ repos, Linux Foundation AAIF) uses plain markdown with no frontmatter. sage-agent uses AGENTS.md with mandatory YAML frontmatter. If both exist in a repo, tools collide.

### Current State

- sage-agent's `load_config()` in `config.py` looks for `AGENTS.md` inside directories
- `sage init` scaffolds `AGENTS.md`
- 11 example directories each contain `AGENTS.md`
- `Agent.from_config()` resolves directory paths to `AGENTS.md`
- Community standard AGENTS.md has no frontmatter — sage-agent would fail with `ConfigError`

### Resolution Strategy: Rename + Backward Compatibility

Following GitHub Copilot's pattern (AGENTS.md for community standard, `.github/agents/*.agent.md` for agent definitions) and Claude Code's pattern (CLAUDE.md avoids collision entirely):

#### Step 1: Rename sage-agent config files to `SAGE.md`

**Files to update:**
- `sage/config.py` — change `AGENTS.md` references to `SAGE.md`
- `sage/agent.py` — update `from_config()` directory resolution
- `sage/cli/main.py` — update `sage init` scaffold
- All 11 `examples/*/AGENTS.md` → `examples/*/SAGE.md`
- Documentation (README.md, .docs/agent-authoring.md)

#### Step 2: Backward compatibility

```python
# In load_config(), check both filenames:
SAGE_CONFIG_FILENAMES = ["SAGE.md", "AGENTS.md"]

def _resolve_config_path(dir_path: Path) -> Path:
    for filename in SAGE_CONFIG_FILENAMES:
        candidate = dir_path / filename
        if candidate.exists():
            return candidate
    raise ConfigError(f"No SAGE.md found in {dir_path}")
```

Log a deprecation warning when `AGENTS.md` is used:
```python
if resolved.name == "AGENTS.md":
    logger.warning(
        "AGENTS.md is deprecated for sage-agent configs. "
        "Rename to SAGE.md to avoid conflicts with the community standard. "
        "See: https://agents.md/"
    )
```

#### Step 3: Add community AGENTS.md reading (optional)

When sage-agent loads, walk up the directory tree looking for community-standard `AGENTS.md` files and inject their content as additional system prompt context:

```python
def _load_community_agents_md(start_dir: Path) -> str | None:
    """Walk up to project root, find community AGENTS.md, return content."""
    current = start_dir
    while current != current.parent:
        agents_md = current / "AGENTS.md"
        if agents_md.exists():
            metadata, body = parse_frontmatter(agents_md.read_text())
            if not metadata or "name" not in metadata:
                # Community standard format — return as context
                return body
        current = current.parent
    return None
```

---

## Plan 9: Multimodal Input

**Priority:** P3 (Medium impact, medium effort)
**Effort:** Medium (2-3 weeks phased)
**Rationale:** Codex CLI has voice input and vision. Aider has voice-to-code. Claude Code accepts screenshots. sage-agent is text-only.

### Phase 1: Image Input (1 week)

#### Step 1: Extend `Message.content` to support multimodal

**File:** `sage/models.py`

```python
ContentBlock = dict[str, Any]  # {"type": "text", "text": "..."} or {"type": "image_url", ...}

class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[ContentBlock] | None = None  # was: str | None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
```

No provider changes needed — litellm already handles `list[ContentBlock]` format and translates between OpenAI/Anthropic formats automatically.

#### Step 2: Add image helper

**File:** `sage/utils/image.py` (new)

```python
async def encode_image(path: str) -> dict[str, Any]:
    """Read an image file and return a litellm-compatible content block."""
    mime = _detect_mime(path)  # image/png, image/jpeg, etc.
    data = base64.b64encode(Path(path).read_bytes()).decode("utf-8")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{data}"}
    }
```

#### Step 3: TUI image input

Add `/image <path>` slash command to TUI that encodes and attaches the image to the next message.

### Phase 2: Image Display in TUI (3 days)

Add `textual-image` dependency. In `ChatPanel`, when rendering assistant messages that reference images, use `textual_image.renderable.Image` for inline display.

### Phase 3: Voice Input (1 week)

Optional dependencies: `sounddevice`, `soundfile` (graceful degradation if missing).

```python
class Voice:
    """Voice input via microphone + Whisper transcription."""

    async def record_and_transcribe(self) -> str:
        audio = self._record()  # sounddevice
        result = await litellm.atranscription(model="whisper-1", file=audio)
        return result.text
```

TUI keybinding: hold Space on empty input to record.

### Dependencies

```toml
# Required for image display
"textual-image>=0.8"

# Optional for voice
[project.optional-dependencies]
voice = ["sounddevice>=0.4", "soundfile>=0.12"]
```

---

## Plan 10: CLI UX Table-Stakes

**Priority:** P2
**Effort:** Medium (2-3 weeks total, can be incremental)
**Rationale:** Session management, slash commands, cost tracking, model switching, and conversation export are expected features in every agent CLI tool.

### 10.1: Slash Command System (3 days)

**File:** `sage/cli/commands.py` (new)

```python
class SlashCommandRegistry:
    def register(self, name: str, handler: Callable, description: str, aliases: list[str] = []) -> None: ...
    async def dispatch(self, input_text: str, context: dict) -> bool: ...
    def list_commands(self) -> list[tuple[str, str]]: ...
```

**Initial commands:**

| Command | Handler |
|---------|---------|
| `/help` | List all slash commands |
| `/clear` | Clear conversation history |
| `/compact` | Trigger history compaction |
| `/model <name>` | Switch model mid-session |
| `/models` | List available models |
| `/cost` | Show session cost + tokens |
| `/status` | Show session info |
| `/export [--format]` | Export conversation |
| `/quit` | Exit |

Wire into TUI's input handler: check for `/` prefix before dispatching to agent.

### 10.2: Cost Tracking (2 days)

**File:** `sage/models.py` — add `cost: float = 0.0` to `Usage`.

**File:** `sage/providers/litellm_provider.py` — call `litellm.completion_cost()` after each completion.

**File:** `sage/agent.py` — accumulate `_session_cost`, `_session_prompt_tokens`, `_session_completion_tokens`.

**File:** `sage/cli/tui.py` — extend status bar to show cost: `Tokens: 12.4k | Cost: $0.034`.

### 10.3: Model Switching (1 day)

**File:** `sage/agent.py`

```python
def switch_model(self, new_model: str, **params: Any) -> None:
    self.model = new_model
    self.provider = LiteLLMProvider(new_model, **params)
```

**File:** `sage/config.py` or `config.toml` — define `[models].available` list.

### 10.4: Conversation Export (2 days)

**File:** `sage/sessions/export.py` (new)

Export formats:
- **Markdown**: Human-readable with headers per message, tool call details
- **JSON**: Machine-readable with full metadata (timestamps, tokens, cost)

### 10.5: Update Notifications (1 day)

**File:** `sage/cli/update.py` (new)

Check PyPI JSON API once per 24 hours, cache result, display notice at CLI startup.

```python
async def check_for_update() -> str | None:
    current = Version(importlib.metadata.version("sage-agent"))
    resp = await httpx.AsyncClient().get("https://pypi.org/pypi/sage-agent/json", timeout=5)
    latest = Version(resp.json()["info"]["version"])
    return str(latest) if latest > current else None
```

---

## Plan 11: Community & Ecosystem

**Priority:** P3 (Ongoing)
**Effort:** Ongoing
**Rationale:** sage-agent has strong architecture but zero community. Every successful tool (Goose 30K stars, Aider 39K stars, OpenCode 95K stars) invested heavily in community building.

### First 30 Days: Foundation

| Day | Action |
|-----|--------|
| 1 | Create `sagebynature/awesome-sage-agent` GitHub repo with curated MCP servers, tools, agent configs |
| 2 | Record 3 asciinema demos (simple agent, TUI, multi-agent pipeline), embed in README |
| 3-4 | Write Show HN post: "Show HN: Sage — Define AI agents in a Markdown file, no boilerplate" |
| 5-7 | Write blog post: "gpt-4o vs claude-sonnet-4 for code review: benchmarked with sage-agent" |
| 7 | Post to r/LocalLLaMA, r/Python, r/MachineLearning |
| 8-10 | Create 15+ "good first issue" GitHub issues |
| 11-14 | Write second blog post: "Build a multi-agent research pipeline in 15 minutes" |
| 14 | Get listed on litellm's community page |
| 15-20 | Submit to MCP clients directory |
| 21-28 | Publish benchmark leaderboard on GitHub Pages |
| 30 | Enable GitHub Discussions |

### Months 2-3: Growth

- Create blog post for every major model release (benchmark results)
- Submit PyCon / AI conference talk proposals
- Create `sage-ext-*` example packages as templates for community extensions
- Launch Discord at 500+ stars
- Weekly "Agent of the Week" showcase in GitHub Discussions

### Key Metrics

- GitHub stars (target: 500 at 3 months, 2K at 6 months)
- Contributors (target: 10 at 3 months)
- PyPI downloads (target: 1K/month at 3 months)
- Community extensions published (target: 5 at 6 months)

### Content Strategy

Monthly cadence:
1. **Week 1:** Benchmark/comparison post (every model release)
2. **Week 2:** Tutorial/cookbook (step-by-step guide)
3. **Week 3:** Changelog + contributor spotlight
4. **Week 4:** Thought leadership (architecture decisions, design philosophy)

Distribute via: Dev.to, Twitter/X, relevant Discord servers, Reddit.

---

## Plan 12: Plugin Marketplace

**Priority:** P3
**Effort:** Medium (phased over months)
**Rationale:** Goose has 3K+ MCP servers. CrewAI has a tool marketplace. sage-agent supports extensions but has no discovery mechanism.

### Phase 1: Entry Points Discovery (3 days)

**File:** `sage/tools/registry.py`

Auto-discover installed extensions via Python entry points:

```python
from importlib.metadata import entry_points

def discover_installed_extensions() -> list[str]:
    """Find all installed sage-agent extensions via entry points."""
    discovered = entry_points(group="sage.extensions")
    return [ep.name for ep in discovered]
```

Extension packages declare entry points in their `pyproject.toml`:
```toml
[project.entry-points."sage.extensions"]
calculator = "sage_ext_calculator"
```

### Phase 2: CLI Plugin Management (1 week)

```
sage plugin list                  # show installed extensions + their tools
sage plugin search <query>        # search PyPI for sage-ext-* packages
sage plugin install <name>        # uv pip install sage-ext-<name>
sage plugin remove <name>         # uv pip uninstall sage-ext-<name>
sage plugin info <name>           # show tool schemas
```

### Phase 3: MCP Registry Integration (3 days)

```
sage mcp search <query>           # query official MCP registry API
sage mcp add <server-id>          # add to config.toml
sage mcp list                     # show configured MCP servers
```

### Phase 4: Curated Registry (ongoing)

Create `sagebynature/sage-registry` GitHub repo with `registry.json`:

```json
{
  "version": 1,
  "plugins": [
    {
      "name": "github",
      "pypi": "sage-ext-github",
      "description": "GitHub API tools",
      "tools": ["create_issue", "list_prs", "review_pr"],
      "min_sage_version": "1.2.0",
      "verified": true,
      "tags": ["git", "github", "devtools"]
    }
  ]
}
```

### Naming Convention

- PyPI packages: `sage-ext-<name>`
- Entry point group: `sage.extensions`
- Import path: `sage_ext_<name>`

---

## Implementation Roadmap

### Wave 1 (Weeks 1-4): Safety & Trust
- Plan 1: Git Integration (P0)
- Plan 2: Execution Sandboxing — Layer 1 (app-level hardening) (P0)
- Plan 3: Headless / CI Mode (P1)
- Plan 8: AGENTS.md Naming Resolution (P2, low effort)

### Wave 2 (Weeks 5-8): Operational Maturity
- Plan 2: Execution Sandboxing — Layers 2-3 (bubblewrap/seatbelt) (P0)
- Plan 5: Observability — Steps 1-3 (cost tracking, trace model, instrumentation) (P1)
- Plan 10: CLI UX — Slash commands, cost tracking, model switching (P2)

### Wave 3 (Weeks 9-12): Developer Experience
- Plan 4: Built-in Evaluation CLI (P1)
- Plan 7: Durable Execution & Sessions (P2)
- Plan 6: IDE Integration — Phase 1 (file watcher) + Phase 2 (ACP) (P2)

### Wave 4 (Ongoing): Growth & Ecosystem
- Plan 9: Multimodal Input (P3)
- Plan 11: Community & Ecosystem (P3)
- Plan 12: Plugin Marketplace (P3)
- Plan 5: Observability — Step 6 (OTEL export) (P1)
- Plan 6: IDE Integration — Phase 3 (VS Code extension if warranted) (P2)
