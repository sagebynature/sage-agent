# Git Integration Design

## Summary

Add first-class git tools to sage-agent following the existing `ToolBase` + `@tool` pattern. Agents get structured git operations (status, diff, log, commit, branch, undo, worktrees) with permission control, dangerous command detection, and auto-snapshot before runs.

## Architecture

### New Files

- `sage/git/utils.py` — shared async `run_git()` helper extracted from `GitSnapshot._git()`
- `sage/git/tools.py` — `GitTools(ToolBase)` with 8 `@tool` methods

### Modified Files

- `sage/git/snapshot.py` — use shared `run_git()` from utils
- `sage/tools/builtins.py` — add 9 git-specific dangerous patterns to `_DANGEROUS_PATTERNS`
- `sage/tools/registry.py` — add `"git"` to `CATEGORY_TOOLS` and `CATEGORY_ARG_MAP`
- `sage/config.py` — add `git` field to `Permission`, add `GitConfig` model to `AgentConfig`
- `sage/agent.py` — auto-snapshot before `run()`/`stream()` when configured

### New Test Files

- `tests/test_git/test_tools.py` — unit tests for all GitTools methods
- `tests/test_git/test_safety.py` — dangerous pattern detection tests
- `tests/test_git/test_undo.py` — undo safety checks

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| GitTools vs extending GitSnapshot | Separate class | Different concerns: snapshots (stash) vs porcelain commands |
| Shared `_git()` helper | Extract to `sage/git/utils.py` | Both GitSnapshot and GitTools need async git subprocess execution |
| Permission arg for patterns | `None` | Git tools use structured params, not a single string to match |
| Worktree path | `.sage/worktrees/<name>` | Convention from Claude Code, `.gitignore`-able |
| Commit attribution | `Co-authored-by` trailer | GitHub-recognized standard, same as Aider |
| Undo safety | In-memory hash tracking | Only undo sage-authored, unpushed commits |

## GitTools API

```python
class GitTools(ToolBase):
    def __init__(self, repo_root: Path | None = None):
        # repo_root defaults to cwd
        # _sage_commit_hashes: set[str] tracks sage-authored commits

    async def setup(self):
        # Verify git repo exists

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
        """Stage and commit files with Co-authored-by trailer.
        If files is None, commits all staged changes."""

    @tool
    async def git_branch(self, name: str | None = None, list_branches: bool = False) -> str:
        """Create a new branch or list existing branches."""

    @tool
    async def git_undo(self) -> str:
        """Undo the last sage-authored commit.
        Safety checks: (1) commit was by sage, (2) not pushed, (3) no dirty files in changed paths."""

    @tool
    async def git_worktree_create(self, name: str, branch: str | None = None) -> str:
        """Create isolated worktree at .sage/worktrees/<name>."""

    @tool
    async def git_worktree_remove(self, name: str) -> str:
        """Remove a worktree. Warns if uncommitted changes exist."""
```

## Dangerous Patterns (Step 1)

Added to `_DANGEROUS_PATTERNS` in `builtins.py`:

```python
r"\bgit\s+push\s+.*--force\b",
r"\bgit\s+push\s+.*-f\b",
r"\bgit\s+reset\s+--hard\b",
r"\bgit\s+clean\s+-[fd]",
r"\bgit\s+checkout\s+\.\s*$",
r"\bgit\s+branch\s+-D\b",
r"\bgit\s+rebase\b",
r"\bgit\s+push\s+.*main\b",
r"\bgit\s+push\s+.*master\b",
```

## Permission Integration (Step 3)

```python
# registry.py
CATEGORY_TOOLS["git"] = [
    "git_status", "git_diff", "git_log", "git_commit",
    "git_branch", "git_undo",
    "git_worktree_create", "git_worktree_remove",
    "snapshot_create", "snapshot_restore", "snapshot_list",
]

CATEGORY_ARG_MAP["git"] = None  # structured args, no single pattern key
```

```python
# config.py
class Permission(BaseModel):
    # ... existing fields ...
    git: PermissionValue | None = None  # new
```

## Agent Config (Step 6)

```python
class GitConfig(BaseModel):
    auto_snapshot: bool = True
    auto_commit_dirty: bool = False
    auto_commit_edits: bool = False
```

```yaml
# AGENTS.md frontmatter
git:
  auto_snapshot: true
  auto_commit_dirty: false
  auto_commit_edits: false

permission:
  git: allow
```

## Auto-Snapshot Flow (Step 4)

In `Agent.run()` and `Agent.stream()`, before the first turn:

1. Check if any `GitSnapshot` instance is in `tool_registry._instances`
2. If found and git config has `auto_snapshot: true`:
   - Check for dirty working tree via `git status --porcelain`
   - If dirty, call `snapshot_create("pre-run")`
3. If `auto_commit_dirty: true`, auto-commit dirty files before AI edits

## Worktree Support (Step 5)

- Path: `.sage/worktrees/<name>`
- Uses detached HEAD to avoid branch pollution
- `git_worktree_create` creates the worktree directory and returns its path
- `git_worktree_remove` checks for uncommitted changes before removal
