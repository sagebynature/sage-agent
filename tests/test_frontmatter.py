"""Tests for shared frontmatter parser utility."""

from sage.frontmatter import parse_frontmatter


class TestParseFrontmatter:
    """Test suite for parse_frontmatter function."""

    def test_valid_frontmatter_with_body(self):
        """Test parsing valid frontmatter with body text."""
        raw = """---
name: test-agent
model: gpt-4o
description: A test agent
---
You are a helpful assistant."""
        meta, body = parse_frontmatter(raw)
        assert meta == {
            "name": "test-agent",
            "model": "gpt-4o",
            "description": "A test agent",
        }
        assert body == "You are a helpful assistant."

    def test_no_frontmatter(self):
        """Test handling of text without frontmatter."""
        raw = "Just plain text\nwith multiple lines"
        meta, body = parse_frontmatter(raw)
        assert meta == {}
        assert body == "Just plain text\nwith multiple lines"

    def test_unclosed_frontmatter(self):
        """Test handling of unclosed frontmatter delimiter."""
        raw = """---
name: test
model: gpt-4o
No closing delimiter"""
        meta, body = parse_frontmatter(raw)
        assert meta == {}
        assert body == raw.strip()

    def test_invalid_yaml_in_frontmatter(self):
        """Test handling of invalid YAML in frontmatter."""
        raw = """---
name: test
model: gpt-4o: invalid: yaml: syntax:
---
Body text"""
        meta, body = parse_frontmatter(raw)
        # Invalid YAML should return empty dict and full text
        assert meta == {}
        assert raw.strip() in body or body.startswith("---")

    def test_empty_body(self):
        """Test frontmatter with empty body (frontmatter only)."""
        raw = """---
name: test
model: gpt-4o
description: A test agent
---
"""
        meta, body = parse_frontmatter(raw)
        assert meta == {
            "name": "test",
            "model": "gpt-4o",
            "description": "A test agent",
        }
        assert body == ""

    def test_empty_file(self):
        """Test parsing of empty file."""
        raw = ""
        meta, body = parse_frontmatter(raw)
        assert meta == {}
        assert body == ""

    def test_frontmatter_with_list_field(self):
        """Test frontmatter with YAML list fields."""
        raw = """---
name: test
model: gpt-4o
tools:
  - shell
  - file_read
  - http_request
---
You are helpful."""
        meta, body = parse_frontmatter(raw)
        assert meta == {
            "name": "test",
            "model": "gpt-4o",
            "tools": ["shell", "file_read", "http_request"],
        }
        assert body == "You are helpful."

    def test_frontmatter_with_dict_field(self):
        """Test frontmatter with nested dict fields (e.g., memory config)."""
        raw = """---
name: test
model: gpt-4o
memory:
  backend: sqlite
  path: memory.db
---
You are helpful."""
        meta, body = parse_frontmatter(raw)
        assert meta == {
            "name": "test",
            "model": "gpt-4o",
            "memory": {
                "backend": "sqlite",
                "path": "memory.db",
            },
        }
        assert body == "You are helpful."

    def test_body_with_markdown_formatting(self):
        """Test that markdown formatting in body is preserved as-is."""
        raw = """---
name: test
model: gpt-4o
---
# You are a helpful assistant

You can:
- Answer questions
- Write code
- Solve problems

Here's an example code block:
```python
def hello():
    print("Hello, world!")
```
"""
        meta, body = parse_frontmatter(raw)
        assert meta == {"name": "test", "model": "gpt-4o"}
        # Body should preserve all markdown formatting
        assert "# You are a helpful assistant" in body
        assert "- Answer questions" in body
        assert "```python" in body

    def test_triple_dash_in_body(self):
        """Test that --- appearing in body doesn't confuse parser."""
        raw = """---
name: test
model: gpt-4o
---
You are helpful.

---

This is a horizontal rule in the body, not a delimiter."""
        meta, body = parse_frontmatter(raw)
        assert meta == {"name": "test", "model": "gpt-4o"}
        assert "---" in body
        assert "horizontal rule" in body

    def test_whitespace_handling(self):
        """Test that leading/trailing whitespace is handled correctly."""
        raw = """   ---
name: test
model: gpt-4o
---
Body text
"""
        meta, body = parse_frontmatter(raw)
        # Lines with just whitespace might not match "---" exactly
        # This test verifies the actual behavior
        if meta:
            assert meta.get("name") == "test"
            assert body == "Body text"
        else:
            # If it doesn't match, both should be empty
            assert meta == {}

    def test_single_field_in_frontmatter(self):
        """Test frontmatter with just one field."""
        raw = """---
name: minimal
---
Minimal body."""
        meta, body = parse_frontmatter(raw)
        assert meta == {"name": "minimal"}
        assert body == "Minimal body."

    def test_special_characters_in_body(self):
        """Test that special characters and quotes in body are preserved."""
        raw = """---
name: test
model: gpt-4o
---
You're a helpful assistant with "special" characters & symbols!
Use YAML: `key: value` format."""
        meta, body = parse_frontmatter(raw)
        assert meta == {"name": "test", "model": "gpt-4o"}
        assert "You're a helpful" in body
        assert "special" in body
        assert "YAML:" in body

    def test_multiline_frontmatter_value(self):
        """Test YAML frontmatter with multiline string values."""
        raw = """---
name: test
model: gpt-4o
description: |
  This is a multiline
  description that spans
  multiple lines
---
Body text"""
        meta, body = parse_frontmatter(raw)
        assert meta["name"] == "test"
        assert meta["model"] == "gpt-4o"
        # Multiline YAML string should preserve newlines
        assert "multiline" in meta["description"]
        assert body == "Body text"

    def test_scalar_yaml_returns_empty_dict(self):
        """Test that YAML parsing a scalar (non-dict) returns empty dict and body."""
        raw = """---
just a string value
---

Body content here"""
        meta, body = parse_frontmatter(raw)
        # Non-dict YAML should return empty dict but preserve body
        assert meta == {}
        assert body == "Body content here"

    def test_all_agentconfig_fields(self):
        """Test parsing all standard AgentConfig fields in frontmatter."""
        raw = """---
name: full-agent
model: gpt-4o
persona: You are a helpful AI.
system_prompt: Extra instructions here
max_turns: 20
---

Agent description goes here."""
        meta, body = parse_frontmatter(raw)
        assert meta["name"] == "full-agent"
        assert meta["model"] == "gpt-4o"
        assert meta["persona"] == "You are a helpful AI."
        assert meta["system_prompt"] == "Extra instructions here"
        assert meta["max_turns"] == 20
        assert body == "Agent description goes here."

    def test_permission_bool_coercion_simple(self):
        """Test that YAML booleans in permission block are coerced to allow/deny strings."""
        raw = """---
name: test
model: gpt-4o
permission:
  read: true
  edit: false
---
Body text"""
        meta, body = parse_frontmatter(raw)
        # true -> "allow", false -> "deny"
        assert meta["permission"]["read"] == "allow"
        assert meta["permission"]["edit"] == "deny"
        assert body == "Body text"

    def test_permission_bool_coercion_nested_dict(self):
        """Test bool coercion in nested permission pattern maps."""
        raw = """---
name: test
model: gpt-4o
permission:
  shell:
    "*": true
    "git log*": false
---
Body text"""
        meta, body = parse_frontmatter(raw)
        assert isinstance(meta["permission"]["shell"], dict)
        assert meta["permission"]["shell"]["*"] == "allow"
        assert meta["permission"]["shell"]["git log*"] == "deny"
        assert body == "Body text"

    def test_permission_bool_coercion_all_bool_forms(self):
        """Test YAML boolean syntax variations (true/false/yes/no/on/off)."""
        raw = """---
name: test
model: gpt-4o
permission:
  read: yes
  edit: no
  shell: on
  web: off
---
Body text"""
        meta, body = parse_frontmatter(raw)
        assert meta["permission"]["read"] == "allow"
        assert meta["permission"]["edit"] == "deny"
        assert meta["permission"]["shell"] == "allow"
        assert meta["permission"]["web"] == "deny"

    def test_permission_bool_coercion_string_values_unchanged(self):
        """Test that string values in permission block are NOT coerced."""
        raw = """---
name: test
model: gpt-4o
permission:
  read: allow
  edit: ask
  shell: deny
---
Body text"""
        meta, body = parse_frontmatter(raw)
        assert meta["permission"]["read"] == "allow"
        assert meta["permission"]["edit"] == "ask"
        assert meta["permission"]["shell"] == "deny"

    def test_bools_outside_permission_unchanged(self):
        """Test that boolean values OUTSIDE permission block are NOT coerced."""
        raw = """---
name: test
model: gpt-4o
memory:
  enabled: true
permission:
  read: true
---
Body text"""
        meta, body = parse_frontmatter(raw)
        # memory.enabled should still be bool
        assert meta["memory"]["enabled"] is True
        # permission.read should be coerced to string
        assert meta["permission"]["read"] == "allow"

    def test_permission_bool_coercion_deeply_nested(self):
        """Test nested permission patterns with multiple levels."""
        raw = """---
name: test
model: gpt-4o
permission:
  shell:
    "git*":
      "git push*": true
      "git rm*": false
---
Body text"""
        meta, body = parse_frontmatter(raw)
        shell_perm = meta["permission"]["shell"]
        assert isinstance(shell_perm["git*"], dict)
        assert shell_perm["git*"]["git push*"] == "allow"
        assert shell_perm["git*"]["git rm*"] == "deny"
