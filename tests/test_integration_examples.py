from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from sage.config import AgentConfig, Permission
from sage.frontmatter import parse_frontmatter
from sage.permissions.base import PermissionAction
from sage.permissions.policy import CategoryPermissionRule, PolicyPermissionHandler
from sage.tools.registry import CATEGORY_TOOLS, ToolRegistry

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def load_config(path: str) -> AgentConfig:
    content = (EXAMPLES_DIR / path).read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)
    config = AgentConfig(**metadata)
    config._body = body
    return config


def _registered_names(permission: Permission, *, default: str = "deny") -> set[str]:
    registry = ToolRegistry()
    registry.register_from_permissions(permission, default=default)
    return {schema.name for schema in registry.get_schemas()}


def _expected_tools(permission: Permission) -> set[str]:
    expected: set[str] = set()
    for category, tools in CATEGORY_TOOLS.items():
        value = getattr(permission, category, None)
        if value is None or value == "deny":
            continue
        expected.update(tools)
    return expected


@pytest.mark.parametrize(
    "relpath",
    [
        "memory_agent/AGENTS.md",
        "mcp_agent/AGENTS.md",
        "safe_coder/AGENTS.md",
        "devtools_agent/AGENTS.md",
        "skills_agent/AGENTS.md",
        "simple_assistant/AGENTS.md",
        "custom_tools/AGENTS.md",
        "permissions_agent/AGENTS.md",
        "parallel_agents/AGENTS.md",
        "skills_demo/AGENTS.md",
        "parallel_agents/research_agent/AGENTS.md",
        "parallel_agents/summarize_agent/AGENTS.md",
    ],
)
def test_example_loads(relpath: str) -> None:
    config = load_config(relpath)
    assert config.name != ""
    assert config.model != ""


def test_simple_assistant_permissions() -> None:
    config = load_config("simple_assistant/AGENTS.md")
    assert config.permission is not None
    assert config.permission.read == "allow"
    assert config.permission.shell == "allow"


def test_devtools_agent_permissions() -> None:
    config = load_config("devtools_agent/AGENTS.md")
    assert config.permission is not None
    assert config.permission.read == "allow"
    assert config.permission.edit == "allow"
    assert isinstance(config.permission.shell, dict)
    assert config.permission.shell["*"] == "allow"
    assert config.permission.shell["python *"] == "allow"
    assert config.permission.shell["python3 *"] == "allow"
    assert config.permission.web == "allow"


def test_safe_coder_pattern_shell() -> None:
    config = load_config("safe_coder/AGENTS.md")
    assert config.permission is not None
    assert config.permission.read == "allow"
    assert config.permission.edit == "allow"
    shell = config.permission.shell
    assert isinstance(shell, dict)
    assert shell["*"] == "ask"
    assert shell["git status"] == "allow"
    assert shell["git diff*"] == "allow"
    assert shell["git log*"] == "allow"


def test_permissions_agent_pattern_shell() -> None:
    config = load_config("permissions_agent/AGENTS.md")
    assert config.permission is not None
    assert config.permission.read == "allow"
    shell = config.permission.shell
    assert isinstance(shell, dict)
    assert shell["*"] == "ask"
    assert shell["git status"] == "allow"
    assert shell["git diff*"] == "allow"
    assert shell["git log*"] == "allow"


def test_memory_agent_no_permission() -> None:
    config = load_config("memory_agent/AGENTS.md")
    assert config.permission is None
    assert config.extensions == []


def test_simple_assistant_has_permission() -> None:
    config = load_config("simple_assistant/AGENTS.md")
    assert config.permission is not None
    assert config.permission.read == "allow"
    assert config.permission.shell == "allow"


def test_custom_tools_extensions() -> None:
    config = load_config("custom_tools/AGENTS.md")
    assert config.permission is None
    assert "examples.custom_tools.tools" in config.extensions


def test_research_agent_extensions() -> None:
    config = load_config("parallel_agents/research_agent/AGENTS.md")
    assert config.permission is None
    assert "sage.tools.builtins" in config.extensions


@pytest.mark.parametrize(
    "relpath",
    [
        "simple_assistant/AGENTS.md",
        "mcp_agent/AGENTS.md",
        "safe_coder/AGENTS.md",
        "devtools_agent/AGENTS.md",
        "skills_agent/AGENTS.md",
        "permissions_agent/AGENTS.md",
        "skills_demo/AGENTS.md",
    ],
)
def test_permission_declared_categories_drive_tool_registration(relpath: str) -> None:
    config = load_config(relpath)
    assert config.permission is not None
    assert _registered_names(config.permission, default="deny") == _expected_tools(
        config.permission
    )


def test_tools_field_rejected() -> None:
    content = "---\nname: x\nmodel: y\ntools:\n  - file_read\n---\nBody"
    metadata, _ = parse_frontmatter(content)
    with pytest.raises(ValidationError, match="extra|Extra inputs are not permitted"):
        AgentConfig(**metadata)


def test_permissions_field_rejected() -> None:
    content = "---\nname: x\nmodel: y\npermissions:\n  default: ask\n---\nBody"
    metadata, _ = parse_frontmatter(content)
    with pytest.raises(ValidationError, match="extra|Extra inputs are not permitted"):
        AgentConfig(**metadata)


def test_permission_allow_values() -> None:
    permission = Permission(read="allow", shell="allow")
    assert permission.read == "allow"
    assert permission.shell == "allow"
    assert permission.edit is None


def test_permission_pattern_dict() -> None:
    permission = Permission(shell={"*": "ask", "git log*": "allow"})
    assert isinstance(permission.shell, dict)
    assert permission.shell["*"] == "ask"
    assert permission.shell["git log*"] == "allow"


def test_permission_deny() -> None:
    permission = Permission(read="deny", edit="deny")
    assert permission.read == "deny"
    assert permission.edit == "deny"


def test_permission_invalid_action_rejected() -> None:
    with pytest.raises(ValidationError):
        Permission(read="invalid_action")


def test_read_allow_registers_file_read() -> None:
    names = _registered_names(Permission(read="allow"), default="deny")
    assert names == {"file_read"}


def test_shell_allow_registers_shell() -> None:
    names = _registered_names(Permission(shell="allow"), default="deny")
    assert names == {"shell"}


def test_deny_does_not_register() -> None:
    names = _registered_names(Permission(read="deny", shell="deny"), default="deny")
    assert "file_read" not in names
    assert "shell" not in names


def test_web_allow_registers_web_tools() -> None:
    names = _registered_names(Permission(web="allow"), default="deny")
    assert names == {"web_fetch", "web_search", "http_request"}


def test_empty_permission_default_deny_registers_no_tools() -> None:
    names = _registered_names(Permission(), default="deny")
    assert names == set()


@pytest.mark.asyncio
async def test_pattern_shell_last_match_wins() -> None:
    rule = CategoryPermissionRule(
        category="shell",
        action=PermissionAction.ASK,
        patterns={"*": PermissionAction.ASK, "git log*": PermissionAction.ALLOW},
    )
    handler = PolicyPermissionHandler(rules=[rule], default=PermissionAction.ASK)
    decision = await handler.check("shell", {"command": "git log HEAD"})
    assert decision.action == PermissionAction.ALLOW


@pytest.mark.asyncio
async def test_pattern_shell_wildcard_fallback() -> None:
    rule = CategoryPermissionRule(
        category="shell",
        action=PermissionAction.ASK,
        patterns={"*": PermissionAction.ASK, "git log*": PermissionAction.ALLOW},
    )
    handler = PolicyPermissionHandler(rules=[rule], default=PermissionAction.ASK)
    decision = await handler.check("shell", {"command": "rm -rf /tmp/foo"})
    assert decision.action == PermissionAction.ASK
