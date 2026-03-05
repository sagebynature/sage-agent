"""Tests for AgentConfig extensions for new Wave 1-5 features (Task 27)."""

from __future__ import annotations


from sage.config import (
    AgentConfig,
    CredentialScrubConfig,
    FollowThroughConfig,
    MemoryConfig,
    QueryClassificationConfig,
    ResearchFrontmatterConfig,
    SessionConfig,
)


# ---------------------------------------------------------------------------
# Config model parsing tests
# ---------------------------------------------------------------------------


def test_credential_scrubbing_config_defaults():
    """CredentialScrubConfig should have sensible defaults."""
    cfg = CredentialScrubConfig()
    assert cfg.enabled is False
    assert cfg.patterns == []
    assert cfg.allowlist == []


def test_credential_scrubbing_config_parsed():
    """CredentialScrubConfig fields should parse from dict."""
    cfg = CredentialScrubConfig(enabled=True, patterns=["sk-.*"], allowlist=["sk-test"])
    assert cfg.enabled is True
    assert "sk-.*" in cfg.patterns
    assert "sk-test" in cfg.allowlist


def test_query_classification_config_parsed():
    """QueryClassificationConfig should parse rules list."""
    from sage.config import ClassificationRuleConfig

    rule = ClassificationRuleConfig(pattern="python.*", model="gpt-4o", priority=1)
    cfg = QueryClassificationConfig(rules=[rule])
    assert len(cfg.rules) == 1
    assert cfg.rules[0].pattern == "python.*"
    assert cfg.rules[0].model == "gpt-4o"
    assert cfg.rules[0].priority == 1


def test_research_config_parsed():
    """ResearchFrontmatterConfig should parse enabled, max_sources, timeout."""
    cfg = ResearchFrontmatterConfig(enabled=True, max_sources=5, timeout=15.0)
    assert cfg.enabled is True
    assert cfg.max_sources == 5
    assert cfg.timeout == 15.0


def test_research_config_defaults():
    """ResearchFrontmatterConfig should have disabled-by-default."""
    cfg = ResearchFrontmatterConfig()
    assert cfg.enabled is False
    assert cfg.max_sources == 3
    assert cfg.timeout == 10.0


def test_follow_through_config_parsed():
    """FollowThroughConfig should parse enabled and patterns."""
    cfg = FollowThroughConfig(enabled=True, patterns=["I cannot", "I'm unable"])
    assert cfg.enabled is True
    assert "I cannot" in cfg.patterns


def test_follow_through_config_has_defaults():
    """FollowThroughConfig should have default patterns."""
    cfg = FollowThroughConfig()
    assert cfg.enabled is False
    assert len(cfg.patterns) > 0


def test_session_config_parsed():
    """SessionConfig should parse enabled field."""
    cfg = SessionConfig(enabled=True)
    assert cfg.enabled is True


def test_memory_config_file_backend():
    """MemoryConfig should accept 'file' as backend."""
    cfg = MemoryConfig(backend="file", path="/tmp/memory")
    assert cfg.backend == "file"
    assert cfg.path == "/tmp/memory"


def test_memory_config_auto_load():
    """MemoryConfig should support auto_load and auto_load_top_k."""
    cfg = MemoryConfig(auto_load=True, auto_load_top_k=3)
    assert cfg.auto_load is True
    assert cfg.auto_load_top_k == 3


def test_memory_config_auto_load_defaults():
    """MemoryConfig auto_load should default to False."""
    cfg = MemoryConfig()
    assert cfg.auto_load is False
    assert cfg.auto_load_top_k == 5


def test_agent_config_has_new_fields():
    """AgentConfig should expose all new optional fields."""
    field_names = set(AgentConfig.model_fields.keys())
    assert "credential_scrubbing" in field_names
    assert "query_classification" in field_names
    assert "research" in field_names
    assert "follow_through" in field_names
    assert "session" in field_names


def test_agent_config_new_fields_default_none():
    """All new AgentConfig fields should default to None."""
    cfg = AgentConfig(name="test", model="gpt-4o")
    assert cfg.credential_scrubbing is None
    assert cfg.query_classification is None
    assert cfg.research is None
    assert cfg.follow_through is None
    assert cfg.session is None


def test_backward_compat_no_new_fields():
    """Config without new fields should parse normally."""
    cfg = AgentConfig(name="test", model="gpt-4o-mini")
    assert cfg.name == "test"
    assert cfg.model == "gpt-4o-mini"
    assert cfg.credential_scrubbing is None


def test_backward_compat_sqlite_memory():
    """MemoryConfig with backend='sqlite' should still work."""
    cfg = MemoryConfig(backend="sqlite", path="memory.db")
    assert cfg.backend == "sqlite"


def test_agent_config_with_credential_scrubbing():
    """AgentConfig should accept credential_scrubbing field."""
    cfg = AgentConfig(
        name="test",
        model="gpt-4o",
        credential_scrubbing=CredentialScrubConfig(enabled=True),
    )
    assert cfg.credential_scrubbing is not None
    assert cfg.credential_scrubbing.enabled is True


def test_agent_config_with_follow_through():
    """AgentConfig should accept follow_through field."""
    cfg = AgentConfig(
        name="test",
        model="gpt-4o",
        follow_through=FollowThroughConfig(enabled=True),
    )
    assert cfg.follow_through is not None
    assert cfg.follow_through.enabled is True
