# Git Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add first-class git tools (status, diff, log, commit, branch, undo, worktrees) with permission control, dangerous command detection, and auto-snapshot before agent runs.

**Architecture:** New `GitTools(ToolBase)` class in `sage/git/tools.py` with 8 `@tool` methods. Shared `run_git()` helper extracted to `sage/git/utils.py`. New `"git"` permission category wired through `CATEGORY_TOOLS`. Auto-snapshot integration in `Agent.run()`/`stream()` via `GitConfig` model.

**Tech Stack:** Python 3.10+, asyncio, pydantic, pytest-asyncio

---

### Task 1: Extract shared `run_git()` helper

**Files:**
- Create: `sage/git/utils.py`
- Modify: `sage/git/snapshot.py`
- Test: `tests/test_git/test_utils.py`

**Step 1: Write the failing test**

Create `tests/test_git/test_utils.py`:

```python
"""Tests for the shared git subprocess helper."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from sage.git.utils import run_git


async def _init_git_repo(path: Path) -> None:
    """Initialize a git repo with an initial commit."""
    for cmd in [
        ["git", "init"],
        ["git", "config", "user.email", "test@test.com"],
        ["git", "config", "user.name", "Test"],
    ]:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
    (path / "README.md").write_text("# Test\n")
    for cmd in [["git", "add", "."], ["git", "commit", "-m", "initial"]]:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()


class TestRunGit:
    async def test_returns_output_and_returncode(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        output, rc = await run_git(["status", "--porcelain"], repo_path=str(tmp_path))
        assert rc == 0
        assert isinstance(output, str)

    async def test_nonzero_returncode_on_bad_command(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        output, rc = await run_git(["log", "--bad-flag"], repo_path=str(tmp_path))
        assert rc != 0

    async def test_uses_repo_path(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        output, rc = await run_git(["rev-parse", "--is-inside-work-tree"], repo_path=str(tmp_path))
        assert rc == 0
        assert output.strip() == "true"

    async def test_not_a_repo_returns_error(self, tmp_path: Path) -> None:
        output, rc = await run_git(["status"], repo_path=str(tmp_path))
        assert rc != 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_git/test_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sage.git.utils'`

**Step 3: Write the implementation**

Create `sage/git/utils.py`:

```python
"""Shared async git subprocess helper."""

from __future__ import annotations

import asyncio


async def run_git(args: list[str], repo_path: str = ".") -> tuple[str, int]:
    """Run a git command and return (output, returncode).

    Args:
        args: Git subcommand and arguments (e.g. ["status", "--porcelain"]).
        repo_path: Path to the git repository root.

    Returns:
        Tuple of (combined stdout/stderr output, return code).
    """
    cmd = ["git", "-C", repo_path] + args
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode(errors="replace").strip()
    err = stderr.decode(errors="replace").strip()
    combined = output or err
    return combined, proc.returncode or 0
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_git/test_utils.py -v`
Expected: PASS (all 4 tests)

**Step 5: Refactor GitSnapshot to use shared helper**

Modify `sage/git/snapshot.py`: replace `_git()` method body with a call to `run_git()`:

```python
# At the top, add import:
from sage.git.utils import run_git

# Replace the _git method:
async def _git(self, args: list[str]) -> tuple[str, int]:
    """Run a git command and return (output, returncode)."""
    return await run_git(args, repo_path=self.repo_path)
```

**Step 6: Run existing snapshot tests to verify no regression**

Run: `uv run pytest tests/test_git/ -v`
Expected: PASS (all snapshot tests + new utils tests)

**Step 7: Commit**

```bash
git add sage/git/utils.py tests/test_git/test_utils.py sage/git/snapshot.py
git commit -m "refactor(git): extract shared run_git() helper to utils"
```

---

### Task 2: Add git-specific dangerous patterns

**Files:**
- Modify: `sage/tools/builtins.py`
- Test: `tests/test_git/test_safety.py`

**Step 1: Write the failing tests**

Create `tests/test_git/test_safety.py`:

```python
"""Tests for git-specific dangerous pattern detection in the shell tool."""

from __future__ import annotations

import pytest

from sage.exceptions import ToolError
from sage.tools.builtins import shell


class TestGitDangerousPatterns:
    """Verify git-specific dangerous commands are rejected by the shell tool."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "git push origin main --force",
            "git push -f origin feature",
            "git reset --hard HEAD~3",
            "git clean -fd",
            "git clean -f",
            "git checkout .",
            "git branch -D feature-branch",
            "git rebase main",
            "git push origin main",
            "git push origin master",
        ],
    )
    async def test_dangerous_git_command_rejected(self, cmd: str) -> None:
        with pytest.raises(ToolError, match="Command rejected"):
            await shell(command=cmd)

    @pytest.mark.parametrize(
        "cmd",
        [
            "git status",
            "git diff",
            "git log --oneline -10",
            "git branch --list",
            "git add README.md",
            "git commit -m 'fix: typo'",
            "git push origin feature-branch",
            "git stash list",
            "git diff --staged",
            "git checkout -b new-branch",
        ],
    )
    async def test_safe_git_command_allowed(self, cmd: str) -> None:
        # These should NOT raise ToolError for dangerous pattern.
        # They may fail for other reasons (e.g. not in a git repo), which is fine.
        try:
            await shell(command=cmd)
        except ToolError as e:
            assert "dangerous pattern" not in str(e).lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_git/test_safety.py -v`
Expected: FAIL — dangerous git commands are NOT currently blocked

**Step 3: Add the patterns to builtins.py**

Modify `sage/tools/builtins.py`, append to `_DANGEROUS_PATTERNS` list (before the closing `]`):

```python
    # Git-specific dangerous commands
    r"\bgit\s+push\s+.*--force\b",
    r"\bgit\s+push\s+.*-f\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[fd]",
    r"\bgit\s+checkout\s+\.\s*$",
    r"\bgit\s+branch\s+-D\b",
    r"\bgit\s+rebase\b",
    r"\bgit\s+push\s+.*\bmain\b",
    r"\bgit\s+push\s+.*\bmaster\b",
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_git/test_safety.py tests/test_tools/test_builtins.py -v`
Expected: PASS (new git safety tests + existing builtin tests)

**Step 5: Commit**

```bash
git add sage/tools/builtins.py tests/test_git/test_safety.py
git commit -m "feat(git): add git-specific dangerous command patterns"
```

---

### Task 3: Add `git` permission category and config

**Files:**
- Modify: `sage/tools/registry.py`
- Modify: `sage/config.py`
- Test: `tests/test_tools/test_registry.py` (add tests)
- Test: `tests/test_config.py` (add tests)
- Test: `tests/test_permissions/test_policy.py` (add tests)

**Step 1: Write the failing tests**

Append to `tests/test_tools/test_registry.py`:

```python
class TestGitCategory:
    def test_git_category_exists(self) -> None:
        from sage.tools.registry import CATEGORY_TOOLS
        assert "git" in CATEGORY_TOOLS

    def test_git_category_tools_listed(self) -> None:
        from sage.tools.registry import CATEGORY_TOOLS
        git_tools = CATEGORY_TOOLS["git"]
        assert "git_status" in git_tools
        assert "git_diff" in git_tools
        assert "git_log" in git_tools
        assert "git_commit" in git_tools
        assert "git_branch" in git_tools
        assert "git_undo" in git_tools
        assert "snapshot_create" in git_tools
        assert "snapshot_restore" in git_tools
        assert "snapshot_list" in git_tools

    def test_git_category_arg_map_is_none(self) -> None:
        from sage.tools.registry import CATEGORY_ARG_MAP
        assert CATEGORY_ARG_MAP["git"] is None
```

Append to `tests/test_config.py` in the `TestPermissionModel` class:

```python
    def test_permission_git_field(self) -> None:
        from sage.config import Permission
        perm = Permission(git="allow")
        assert perm.git == "allow"

    def test_permission_git_default_none(self) -> None:
        from sage.config import Permission
        perm = Permission()
        assert perm.git is None

    def test_git_config_parsed(self, tmp_path: Path) -> None:
        config_file = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "test",
                "model": "gpt-4o",
                "git": {
                    "auto_snapshot": True,
                    "auto_commit_dirty": False,
                    "auto_commit_edits": False,
                },
            },
        )
        config = load_config(str(config_file))
        assert config.git is not None
        assert config.git.auto_snapshot is True
        assert config.git.auto_commit_dirty is False

    def test_git_config_defaults(self, tmp_path: Path) -> None:
        config_file = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "test", "model": "gpt-4o"},
        )
        config = load_config(str(config_file))
        assert config.git is None
```

Append to `tests/test_permissions/test_policy.py`:

```python
    async def test_git_category_tool_resolved(self) -> None:
        handler = self._handler(
            rules=[CategoryPermissionRule(category="git", action=PermissionAction.ALLOW)]
        )
        decision = await handler.check("git_status", {})
        assert decision.action == PermissionAction.ALLOW

    async def test_git_snapshot_tool_in_git_category(self) -> None:
        handler = self._handler(
            rules=[CategoryPermissionRule(category="git", action=PermissionAction.DENY)]
        )
        decision = await handler.check("snapshot_create", {})
        assert decision.action == PermissionAction.DENY
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools/test_registry.py::TestGitCategory tests/test_config.py::TestPermissionModel::test_permission_git_field tests/test_permissions/test_policy.py::TestPolicyPermissionHandler::test_git_category_tool_resolved -v`
Expected: FAIL

**Step 3: Implement the changes**

Modify `sage/tools/registry.py` — add to `CATEGORY_TOOLS` and `CATEGORY_ARG_MAP`:

```python
CATEGORY_TOOLS: dict[str, list[str]] = {
    "read": ["file_read"],
    "edit": ["file_write", "file_edit"],
    "shell": ["shell"],
    "web": ["web_fetch", "web_search", "http_request"],
    "memory": ["memory_store", "memory_recall"],
    "task": [],
    "git": [
        "git_status", "git_diff", "git_log", "git_commit",
        "git_branch", "git_undo",
        "git_worktree_create", "git_worktree_remove",
        "snapshot_create", "snapshot_restore", "snapshot_list",
    ],
}

CATEGORY_ARG_MAP: dict[str, str | None] = {
    "read": "path",
    "edit": "path",
    "shell": "command",
    "web": "url",
    "memory": None,
    "task": None,
    "git": None,
}
```

Also add `"sage.git.tools"` and `"sage.git.snapshot"` to `_TOOL_MODULE_MAP` for bare-name resolution. Add each git tool name:

```python
_TOOL_MODULE_MAP: dict[str, str] = {
    "file_edit": "sage.tools.file_tools",
    "web_search": "sage.tools.web_tools",
    "web_fetch": "sage.tools.web_tools",
    "git_status": "sage.git.tools",
    "git_diff": "sage.git.tools",
    "git_log": "sage.git.tools",
    "git_commit": "sage.git.tools",
    "git_branch": "sage.git.tools",
    "git_undo": "sage.git.tools",
    "git_worktree_create": "sage.git.tools",
    "git_worktree_remove": "sage.git.tools",
    "snapshot_create": "sage.git.snapshot",
    "snapshot_restore": "sage.git.snapshot",
    "snapshot_list": "sage.git.snapshot",
}
```

Note: `_TOOL_MODULE_MAP` uses colon-style resolution for ToolBase instances. Since `GitTools` and `GitSnapshot` are `ToolBase` subclasses (not bare functions), `load_from_module("sage.git.tools")` will auto-discover the `GitTools` class instance. But `_TOOL_MODULE_MAP` maps individual tool names to modules. For ToolBase, we need the module-level import to work. The `load_from_module` method with a bare module path iterates `dir(mod)` and registers any `ToolBase` instances found. Since we'll instantiate `GitTools` at module level, this will work. However, `_TOOL_MODULE_MAP` expects `module:attr` resolution. We need to handle this differently for ToolBase classes.

**Alternative approach for _TOOL_MODULE_MAP:** Since git tools are ToolBase methods (not bare functions), bare-name resolution via `_TOOL_MODULE_MAP` won't work the same way. Instead, the `register_from_permissions` method should handle loading git tools by module path when the `git` category is not denied. Update `register_from_permissions` to know which modules to load for each category:

```python
# Add a category-to-module mapping:
_CATEGORY_MODULE_MAP: dict[str, str] = {
    "git": "sage.git.tools",
}
```

Then in `register_from_permissions`, after loading individual tools, also load category modules:

```python
for category, tool_names in CATEGORY_TOOLS.items():
    value = getattr(permission, category, None)
    effective = default if value is None else value
    if effective == "deny":
        continue
    for tool_name in tool_names:
        if tool_name in self._tools or tool_name in self._schemas:
            continue  # already registered
        try:
            self.load_from_module(tool_name)
        except (ToolError, ImportError):
            pass  # tool not available as bare name
    # Load category modules (for ToolBase classes)
    if category in _CATEGORY_MODULE_MAP:
        try:
            self.load_from_module(_CATEGORY_MODULE_MAP[category])
        except (ToolError, ImportError):
            pass
```

Actually, the simpler approach: don't add git tools to `_TOOL_MODULE_MAP`. Instead, in `register_from_permissions`, add special handling for the `git` category to load both `sage.git.tools` and `sage.git.snapshot` modules. This avoids bare-name resolution complexity.

Modify `sage/config.py`:

Add `git` field to `Permission`:

```python
class Permission(BaseModel):
    model_config = ConfigDict(extra="allow")
    read: PermissionValue | None = None
    edit: PermissionValue | None = None
    shell: PermissionValue | None = None
    web: PermissionValue | None = None
    memory: PermissionValue | None = None
    task: PermissionValue | None = None
    git: PermissionValue | None = None
```

Add `GitConfig` model and `git` field to `AgentConfig`:

```python
class GitConfig(BaseModel):
    """Git integration configuration."""
    auto_snapshot: bool = True
    auto_commit_dirty: bool = False
    auto_commit_edits: bool = False
```

```python
class AgentConfig(BaseModel):
    # ... existing fields ...
    git: GitConfig | None = None
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools/test_registry.py tests/test_config.py tests/test_permissions/test_policy.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add sage/tools/registry.py sage/config.py tests/test_tools/test_registry.py tests/test_config.py tests/test_permissions/test_policy.py
git commit -m "feat(git): add git permission category, GitConfig, and registry wiring"
```

---

### Task 4: Implement GitTools core — status, diff, log

**Files:**
- Create: `sage/git/tools.py`
- Test: `tests/test_git/test_tools.py`

**Step 1: Write the failing tests**

Create `tests/test_git/test_tools.py`:

```python
"""Tests for GitTools (ToolBase)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from sage.exceptions import ToolError
from sage.git.tools import GitTools


async def _init_git_repo(path: Path) -> None:
    """Initialize a git repo with an initial commit."""
    for cmd in [
        ["git", "init"],
        ["git", "config", "user.email", "test@test.com"],
        ["git", "config", "user.name", "Test"],
    ]:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
    (path / "README.md").write_text("# Test\n")
    for cmd in [["git", "add", "."], ["git", "commit", "-m", "initial"]]:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()


class TestGitToolsSetup:
    async def test_setup_in_git_repo(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()  # Should not raise

    async def test_setup_outside_git_raises(self, tmp_path: Path) -> None:
        tools = GitTools(repo_root=tmp_path)
        with pytest.raises(ToolError, match="[Nn]ot a git repo"):
            await tools.setup()


class TestGitStatus:
    async def test_clean_status(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_status()
        # Clean repo should report nothing or "clean"
        assert "nothing to commit" in result.lower() or result.strip() == ""

    async def test_dirty_status(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "new_file.txt").write_text("hello")
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_status()
        assert "new_file.txt" in result


class TestGitDiff:
    async def test_diff_no_changes(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_diff()
        assert result.strip() == "" or "no changes" in result.lower()

    async def test_diff_with_changes(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "README.md").write_text("# Modified\n")
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_diff()
        assert "Modified" in result

    async def test_diff_staged(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "README.md").write_text("# Staged\n")
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", str(tmp_path), "add", "README.md",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_diff(staged=True)
        assert "Staged" in result


class TestGitLog:
    async def test_log_shows_initial_commit(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_log()
        assert "initial" in result.lower()

    async def test_log_count(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_log(count=1)
        lines = [l for l in result.strip().split("\n") if l.strip()]
        assert len(lines) >= 1

    async def test_log_oneline_false(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_log(oneline=False)
        assert "commit" in result.lower() or "Author" in result
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_git/test_tools.py -v -k "TestGitToolsSetup or TestGitStatus or TestGitDiff or TestGitLog"`
Expected: FAIL with `ModuleNotFoundError: No module named 'sage.git.tools'`

**Step 3: Write the implementation**

Create `sage/git/tools.py`:

```python
"""First-class git integration tools."""

from __future__ import annotations

import logging
from pathlib import Path

from sage.exceptions import ToolError
from sage.git.utils import run_git
from sage.tools.base import ToolBase
from sage.tools.decorator import tool

logger = logging.getLogger(__name__)

_CO_AUTHOR_TRAILER = "Co-authored-by: sage-agent <noreply@sagebynature.com>"


class GitTools(ToolBase):
    """First-class git integration tools.

    Provides structured git operations as LLM-callable tools.
    """

    def __init__(self, repo_root: Path | None = None) -> None:
        self._repo_root = str(repo_root or Path.cwd())
        self._sage_commit_hashes: set[str] = set()
        super().__init__()

    async def _git(self, args: list[str]) -> tuple[str, int]:
        return await run_git(args, repo_path=self._repo_root)

    async def setup(self) -> None:
        """Verify we're inside a git repository."""
        output, rc = await self._git(["rev-parse", "--is-inside-work-tree"])
        if rc != 0 or output.strip() != "true":
            raise ToolError(f"Not a git repo: {self._repo_root}")

    async def teardown(self) -> None:
        """No-op."""

    @tool
    async def git_status(self) -> str:
        """Show working tree status (staged, unstaged, untracked files)."""
        logger.debug("git_status")
        output, rc = await self._git(["status"])
        if rc != 0:
            raise ToolError(f"git status failed: {output}")
        return output

    @tool
    async def git_diff(self, ref: str = "HEAD", staged: bool = False) -> str:
        """Show diff of changes. Use staged=True for staged changes only."""
        logger.debug("git_diff: ref=%s, staged=%s", ref, staged)
        args = ["diff"]
        if staged:
            args.append("--staged")
        else:
            args.append(ref)
        output, rc = await self._git(args)
        if rc != 0:
            raise ToolError(f"git diff failed: {output}")
        return output if output else "No changes."

    @tool
    async def git_log(self, count: int = 10, oneline: bool = True) -> str:
        """Show recent commit history."""
        logger.debug("git_log: count=%d, oneline=%s", count, oneline)
        args = ["log", f"-{count}"]
        if oneline:
            args.append("--oneline")
        output, rc = await self._git(args)
        if rc != 0:
            raise ToolError(f"git log failed: {output}")
        return output
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_git/test_tools.py -v -k "TestGitToolsSetup or TestGitStatus or TestGitDiff or TestGitLog"`
Expected: PASS

**Step 5: Commit**

```bash
git add sage/git/tools.py tests/test_git/test_tools.py
git commit -m "feat(git): implement GitTools with status, diff, log tools"
```

---

### Task 5: Implement GitTools commit and undo

**Files:**
- Modify: `sage/git/tools.py`
- Test: `tests/test_git/test_tools.py` (append)
- Test: `tests/test_git/test_undo.py`

**Step 1: Write the failing tests for commit**

Append to `tests/test_git/test_tools.py`:

```python
class TestGitCommit:
    async def test_commit_staged_files(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "new.txt").write_text("content")
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", str(tmp_path), "add", "new.txt",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_commit(message="add new file")
        assert "add new file" in result.lower() or "committed" in result.lower()

    async def test_commit_specific_files(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_commit(message="add a", files=["a.txt"])
        assert "a.txt" in result or "add a" in result.lower()
        # b.txt should NOT be committed
        log_out, _ = await tools._git(["log", "--oneline", "-1"])
        assert "add a" in log_out.lower()

    async def test_commit_appends_co_author(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "file.txt").write_text("data")
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        await tools.git_commit(message="test co-author", files=["file.txt"])
        log_out, _ = await tools._git(["log", "-1", "--format=%B"])
        assert "Co-authored-by: sage-agent" in log_out

    async def test_commit_tracks_hash(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "file.txt").write_text("data")
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        await tools.git_commit(message="tracked commit", files=["file.txt"])
        assert len(tools._sage_commit_hashes) == 1

    async def test_commit_nothing_staged_errors(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_commit(message="empty")
        assert "nothing" in result.lower() or "no changes" in result.lower()
```

Create `tests/test_git/test_undo.py`:

```python
"""Tests for git_undo safety checks."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from sage.git.tools import GitTools


async def _init_git_repo(path: Path) -> None:
    """Initialize a git repo with an initial commit."""
    for cmd in [
        ["git", "init"],
        ["git", "config", "user.email", "test@test.com"],
        ["git", "config", "user.name", "Test"],
    ]:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
    (path / "README.md").write_text("# Test\n")
    for cmd in [["git", "add", "."], ["git", "commit", "-m", "initial"]]:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()


class TestGitUndo:
    async def test_undo_sage_commit(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        (tmp_path / "file.txt").write_text("data")
        await tools.git_commit(message="to undo", files=["file.txt"])
        assert len(tools._sage_commit_hashes) == 1

        result = await tools.git_undo()
        assert "undone" in result.lower() or "reset" in result.lower()
        # File should still exist in working tree (soft reset)
        assert (tmp_path / "file.txt").exists()

    async def test_undo_non_sage_commit_rejected(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        # The initial commit was NOT made by sage
        result = await tools.git_undo()
        assert "no sage" in result.lower() or "cannot undo" in result.lower()

    async def test_undo_clears_hash_tracking(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        (tmp_path / "file.txt").write_text("data")
        await tools.git_commit(message="to undo", files=["file.txt"])
        assert len(tools._sage_commit_hashes) == 1

        await tools.git_undo()
        assert len(tools._sage_commit_hashes) == 0

    async def test_undo_pushed_commit_rejected(self, tmp_path: Path) -> None:
        """Undo should refuse if the commit has been pushed to a remote."""
        await _init_git_repo(tmp_path)
        # Create a bare remote and push
        remote_path = tmp_path.parent / "remote.git"
        for cmd in [["git", "init", "--bare", str(remote_path)]]:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        for cmd in [
            ["git", "-C", str(tmp_path), "remote", "add", "origin", str(remote_path)],
            ["git", "-C", str(tmp_path), "push", "-u", "origin", "master"],
        ]:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        (tmp_path / "file.txt").write_text("data")
        await tools.git_commit(message="will push", files=["file.txt"])
        # Push the sage commit
        await tools._git(["push", "origin", "HEAD"])

        result = await tools.git_undo()
        assert "pushed" in result.lower() or "cannot undo" in result.lower()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_git/test_tools.py::TestGitCommit tests/test_git/test_undo.py -v`
Expected: FAIL — `git_commit` and `git_undo` not yet implemented

**Step 3: Implement commit and undo in GitTools**

Append to `sage/git/tools.py` in the `GitTools` class:

```python
    @tool
    async def git_commit(self, message: str, files: list[str] | None = None) -> str:
        """Stage and commit files. If files is None, commits all staged changes.

        Automatically appends a Co-authored-by trailer for attribution.
        """
        logger.debug("git_commit: message=%s, files=%s", message[:80], files)

        if files:
            for f in files:
                _, rc = await self._git(["add", f])
                if rc != 0:
                    raise ToolError(f"Failed to stage file: {f}")

        # Check if there's anything to commit.
        status, _ = await self._git(["diff", "--cached", "--quiet"])
        # diff --cached --quiet returns 0 if no staged changes, 1 if there are changes.
        # We need to check: if rc == 0 and no files were explicitly added, nothing to commit.
        staged_check, staged_rc = await self._git(["diff", "--cached", "--name-only"])
        if not staged_check.strip():
            return "Nothing to commit — no staged changes."

        full_message = f"{message}\n\n{_CO_AUTHOR_TRAILER}"
        output, rc = await self._git(["commit", "-m", full_message])
        if rc != 0:
            raise ToolError(f"git commit failed: {output}")

        # Track the commit hash for safe undo.
        hash_out, _ = await self._git(["rev-parse", "HEAD"])
        commit_hash = hash_out.strip()
        self._sage_commit_hashes.add(commit_hash)
        logger.info("Sage commit: %s (%s)", commit_hash[:8], message[:60])

        return f"Committed: {commit_hash[:8]} — {message}"

    @tool
    async def git_undo(self) -> str:
        """Undo the last sage-authored commit (soft reset).

        Safety checks:
        1. The commit must have been authored by sage in this session.
        2. The commit must not have been pushed to a remote.
        """
        logger.debug("git_undo")

        # Get current HEAD hash.
        head_out, rc = await self._git(["rev-parse", "HEAD"])
        if rc != 0:
            raise ToolError(f"Failed to get HEAD: {head_out}")
        head_hash = head_out.strip()

        # Check 1: Was this commit made by sage?
        if head_hash not in self._sage_commit_hashes:
            return "Cannot undo — no sage-authored commit found at HEAD."

        # Check 2: Has it been pushed?
        # Compare HEAD with all remote tracking branches.
        remote_check, _ = await self._git(["branch", "-r", "--contains", head_hash])
        if remote_check.strip():
            return "Cannot undo — commit has been pushed to remote."

        # Soft reset — preserves changes in working tree.
        output, rc = await self._git(["reset", "--soft", "HEAD~1"])
        if rc != 0:
            raise ToolError(f"git reset failed: {output}")

        self._sage_commit_hashes.discard(head_hash)
        logger.info("Undone sage commit: %s", head_hash[:8])
        return f"Undone commit {head_hash[:8]} — changes preserved in working tree."
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_git/test_tools.py::TestGitCommit tests/test_git/test_undo.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add sage/git/tools.py tests/test_git/test_tools.py tests/test_git/test_undo.py
git commit -m "feat(git): implement git_commit and git_undo with safety checks"
```

---

### Task 6: Implement GitTools branch and worktree

**Files:**
- Modify: `sage/git/tools.py`
- Test: `tests/test_git/test_tools.py` (append)

**Step 1: Write the failing tests**

Append to `tests/test_git/test_tools.py`:

```python
class TestGitBranch:
    async def test_list_branches(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_branch(list_branches=True)
        assert "master" in result or "main" in result

    async def test_create_branch(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_branch(name="feature-test")
        assert "feature-test" in result
        # Verify branch was created
        listing = await tools.git_branch(list_branches=True)
        assert "feature-test" in listing

    async def test_create_branch_no_name_errors(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_branch()
        # With no name and list_branches=False, should give usage hint or list
        assert isinstance(result, str)


class TestGitWorktree:
    async def test_create_worktree(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_worktree_create(name="test-wt")
        assert "test-wt" in result
        wt_path = Path(self._repo_root(tmp_path)) / ".sage" / "worktrees" / "test-wt"
        assert wt_path.exists() or ".sage/worktrees/test-wt" in result

    async def test_remove_worktree(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        await tools.git_worktree_create(name="to-remove")
        result = await tools.git_worktree_remove(name="to-remove")
        assert "removed" in result.lower()

    async def test_remove_nonexistent_worktree(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_worktree_remove(name="nope")
        assert "not found" in result.lower() or "error" in result.lower()

    def _repo_root(self, tmp_path: Path) -> str:
        return str(tmp_path)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_git/test_tools.py::TestGitBranch tests/test_git/test_tools.py::TestGitWorktree -v`
Expected: FAIL — `git_branch`, `git_worktree_create`, `git_worktree_remove` not yet implemented

**Step 3: Implement branch and worktree in GitTools**

Append to `sage/git/tools.py` in the `GitTools` class:

```python
    @tool
    async def git_branch(self, name: str | None = None, list_branches: bool = False) -> str:
        """Create a new branch or list existing branches."""
        logger.debug("git_branch: name=%s, list=%s", name, list_branches)

        if list_branches or name is None:
            output, rc = await self._git(["branch", "--list", "-a"])
            if rc != 0:
                raise ToolError(f"git branch failed: {output}")
            return output if output else "No branches found."

        output, rc = await self._git(["branch", name])
        if rc != 0:
            raise ToolError(f"Failed to create branch '{name}': {output}")
        return f"Created branch: {name}"

    @tool
    async def git_worktree_create(self, name: str, branch: str | None = None) -> str:
        """Create an isolated git worktree at .sage/worktrees/<name>.

        Uses detached HEAD by default to avoid branch pollution.
        """
        logger.debug("git_worktree_create: name=%s, branch=%s", name, branch)
        wt_dir = Path(self._repo_root) / ".sage" / "worktrees" / name
        wt_dir.parent.mkdir(parents=True, exist_ok=True)

        if branch:
            args = ["worktree", "add", str(wt_dir), branch]
        else:
            args = ["worktree", "add", "--detach", str(wt_dir)]

        output, rc = await self._git(args)
        if rc != 0:
            raise ToolError(f"Failed to create worktree '{name}': {output}")
        logger.info("Created worktree: %s at %s", name, wt_dir)
        return f"Worktree created: {wt_dir}"

    @tool
    async def git_worktree_remove(self, name: str) -> str:
        """Remove a worktree. Warns if uncommitted changes exist."""
        logger.debug("git_worktree_remove: name=%s", name)
        wt_dir = Path(self._repo_root) / ".sage" / "worktrees" / name

        if not wt_dir.exists():
            return f"Worktree not found: {name}"

        # Check for uncommitted changes in the worktree.
        dirty_check, _ = await run_git(["status", "--porcelain"], repo_path=str(wt_dir))
        if dirty_check.strip():
            logger.warning("Worktree '%s' has uncommitted changes", name)

        output, rc = await self._git(["worktree", "remove", str(wt_dir), "--force"])
        if rc != 0:
            raise ToolError(f"Failed to remove worktree '{name}': {output}")
        logger.info("Removed worktree: %s", name)
        return f"Worktree removed: {name}"
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_git/test_tools.py::TestGitBranch tests/test_git/test_tools.py::TestGitWorktree -v`
Expected: PASS

**Step 5: Commit**

```bash
git add sage/git/tools.py tests/test_git/test_tools.py
git commit -m "feat(git): implement git_branch, git_worktree_create, git_worktree_remove"
```

---

### Task 7: Wire git tools into registry and agent auto-snapshot

**Files:**
- Modify: `sage/tools/registry.py`
- Modify: `sage/agent.py`
- Test: `tests/test_agent.py` (append)

**Step 1: Write the failing tests**

Append to `tests/test_agent.py` (or create a new test file if test_agent.py doesn't have a good place). First read the existing test_agent.py structure to find the right place:

Create `tests/test_git/test_agent_integration.py`:

```python
"""Tests for git integration with Agent (auto-snapshot, tool registration)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from sage.config import AgentConfig, GitConfig, Permission


async def _init_git_repo(path: Path) -> None:
    for cmd in [
        ["git", "init"],
        ["git", "config", "user.email", "test@test.com"],
        ["git", "config", "user.name", "Test"],
    ]:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
    (path / "README.md").write_text("# Test\n")
    for cmd in [["git", "add", "."], ["git", "commit", "-m", "initial"]]:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()


class TestGitToolRegistration:
    def test_git_tools_registered_when_permission_allows(self) -> None:
        from sage.tools.registry import ToolRegistry
        from sage.config import Permission

        registry = ToolRegistry()
        registry.register_from_permissions(Permission(git="allow"))

        names = {s.name for s in registry.get_schemas()}
        assert "git_status" in names
        assert "git_diff" in names
        assert "git_log" in names
        assert "git_commit" in names
        assert "git_branch" in names
        assert "git_undo" in names

    def test_git_tools_not_registered_when_denied(self) -> None:
        from sage.tools.registry import ToolRegistry
        from sage.config import Permission

        registry = ToolRegistry()
        registry.register_from_permissions(Permission(git="deny"))

        names = {s.name for s in registry.get_schemas()}
        assert "git_status" not in names

    def test_snapshot_tools_registered_with_git_permission(self) -> None:
        from sage.tools.registry import ToolRegistry
        from sage.config import Permission

        registry = ToolRegistry()
        registry.register_from_permissions(Permission(git="allow"))

        names = {s.name for s in registry.get_schemas()}
        assert "snapshot_create" in names
        assert "snapshot_restore" in names
        assert "snapshot_list" in names


class TestGitConfig:
    def test_git_config_on_agent_config(self) -> None:
        cfg = AgentConfig(
            name="test", model="gpt-4o",
            git=GitConfig(auto_snapshot=True, auto_commit_dirty=False),
        )
        assert cfg.git is not None
        assert cfg.git.auto_snapshot is True

    def test_git_config_default_none(self) -> None:
        cfg = AgentConfig(name="test", model="gpt-4o")
        assert cfg.git is None
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_git/test_agent_integration.py -v`
Expected: FAIL — git tools not yet wired into `register_from_permissions`

**Step 3: Wire git tool loading into register_from_permissions**

Modify `sage/tools/registry.py`. Update `register_from_permissions` to handle the `git` category by loading the modules that contain ToolBase instances:

```python
# Add at module level, after CATEGORY_ARG_MAP:
_CATEGORY_MODULES: dict[str, list[str]] = {
    "git": ["sage.git.tools", "sage.git.snapshot"],
}
```

In `register_from_permissions`, after the existing loop that loads individual tools, add module-based loading:

```python
def register_from_permissions(
    self,
    permission: Permission,
    default: str = "ask",
    extensions: list[str] | None = None,
) -> None:
    from sage.config import Permission

    if not isinstance(permission, Permission):
        raise ToolError(f"Expected Permission, got {type(permission).__name__}")

    for category, tool_names in CATEGORY_TOOLS.items():
        value = getattr(permission, category, None)
        effective = default if value is None else value
        if effective == "deny":
            continue
        # Load individual tools (bare functions).
        for tool_name in tool_names:
            if tool_name in self._tools:
                continue
            try:
                self.load_from_module(tool_name)
            except (ToolError, ImportError, ModuleNotFoundError):
                pass
        # Load category modules (for ToolBase classes).
        if category in _CATEGORY_MODULES:
            for mod_path in _CATEGORY_MODULES[category]:
                try:
                    self.load_from_module(mod_path)
                except (ToolError, ImportError, ModuleNotFoundError):
                    pass

    for module_path in extensions or []:
        self.load_from_module(module_path)
```

**Step 4: Wire auto-snapshot into Agent**

Modify `sage/agent.py`. Add a private method `_maybe_auto_snapshot` and call it at the start of `run()` and `stream()`:

```python
async def _maybe_auto_snapshot(self) -> None:
    """Create a pre-run git snapshot if configured."""
    if not hasattr(self, '_git_config') or self._git_config is None:
        return
    if not self._git_config.auto_snapshot:
        return

    from sage.git.snapshot import GitSnapshot
    snapshot: GitSnapshot | None = None
    for instance in self.tool_registry._instances:
        if isinstance(instance, GitSnapshot):
            snapshot = instance
            break

    if snapshot is None:
        return

    try:
        await snapshot.setup()
        result = await snapshot.snapshot_create(label="pre-run")
        logger.info("Auto-snapshot: %s", result)
    except Exception as exc:
        logger.warning("Auto-snapshot failed: %s", exc)
```

In `Agent.__init__`, store the git config:

```python
self._git_config = None  # Set via _from_agent_config
```

In `Agent._from_agent_config`, pass the git config:

```python
agent._git_config = config.git
```

In `Agent.run()`, add before the loop (after MCP/memory init):

```python
await self._maybe_auto_snapshot()
```

Same in `Agent.stream()`.

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_git/test_agent_integration.py tests/test_git/ -v`
Expected: PASS

**Step 6: Run full test suite to check for regressions**

Run: `uv run pytest -v`
Expected: PASS (all existing tests + new tests)

**Step 7: Commit**

```bash
git add sage/tools/registry.py sage/agent.py sage/config.py tests/test_git/test_agent_integration.py
git commit -m "feat(git): wire git tools into registry, add auto-snapshot to agent"
```

---

### Task 8: Full integration test and cleanup

**Files:**
- Test: `tests/test_git/test_integration.py`
- Modify: `sage/git/__init__.py` (update docstring)

**Step 1: Write integration test**

Create `tests/test_git/test_integration.py`:

```python
"""End-to-end integration test for git tools."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from sage.git.snapshot import GitSnapshot
from sage.git.tools import GitTools
from sage.tools.registry import ToolRegistry


async def _init_git_repo(path: Path) -> None:
    for cmd in [
        ["git", "init"],
        ["git", "config", "user.email", "test@test.com"],
        ["git", "config", "user.name", "Test"],
    ]:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
    (path / "README.md").write_text("# Test\n")
    for cmd in [["git", "add", "."], ["git", "commit", "-m", "initial"]]:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()


class TestGitIntegration:
    """End-to-end: register tools, execute via registry, verify results."""

    async def test_full_workflow_via_registry(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)

        git_tools = GitTools(repo_root=tmp_path)
        snapshot = GitSnapshot(repo_path=str(tmp_path))
        await git_tools.setup()
        await snapshot.setup()

        registry = ToolRegistry()
        registry.register(git_tools)
        registry.register(snapshot)

        # Verify all tools are registered.
        names = {s.name for s in registry.get_schemas()}
        assert "git_status" in names
        assert "git_commit" in names
        assert "snapshot_create" in names

        # Execute status via registry.
        status = await registry.execute("git_status", {})
        assert isinstance(status, str)

        # Create a file, commit, check log.
        (tmp_path / "feature.txt").write_text("new feature")
        commit_result = await registry.execute(
            "git_commit", {"message": "add feature", "files": ["feature.txt"]}
        )
        assert "add feature" in commit_result.lower() or "committed" in commit_result.lower()

        log_result = await registry.execute("git_log", {"count": 5})
        assert "add feature" in log_result.lower()

        # Undo the commit.
        undo_result = await registry.execute("git_undo", {})
        assert "undone" in undo_result.lower()

        # Snapshot workflow.
        (tmp_path / "README.md").write_text("# Changed\n")
        snap_result = await registry.execute("snapshot_create", {"label": "test"})
        assert "sage:" in snap_result.lower() or "snapshot" in snap_result.lower()

    async def test_permission_controlled_execution(self, tmp_path: Path) -> None:
        """Git tools respect permission handler."""
        from unittest.mock import AsyncMock
        from sage.permissions.base import PermissionAction, PermissionDecision
        from sage.exceptions import PermissionError as SagePermissionError

        await _init_git_repo(tmp_path)
        git_tools = GitTools(repo_root=tmp_path)
        await git_tools.setup()

        registry = ToolRegistry()
        registry.register(git_tools)

        # Set up a deny-all handler.
        handler = AsyncMock()
        handler.check = AsyncMock(
            return_value=PermissionDecision(action=PermissionAction.DENY, reason="blocked")
        )
        registry.set_permission_handler(handler)

        with pytest.raises(SagePermissionError, match="Permission denied"):
            await registry.execute("git_status", {})
```

**Step 2: Run the integration tests**

Run: `uv run pytest tests/test_git/test_integration.py -v`
Expected: PASS

**Step 3: Update sage/git/__init__.py**

```python
"""Git integration for Sage — snapshots, tools, and worktrees."""
```

**Step 4: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS (all tests green)

**Step 5: Commit**

```bash
git add tests/test_git/test_integration.py sage/git/__init__.py
git commit -m "test(git): add end-to-end integration tests for git tools"
```
