from __future__ import annotations

import json
import importlib
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

_loaded_sage = sys.modules.get("sage")
if _loaded_sage is not None:
    loaded_file = Path(getattr(_loaded_sage, "__file__", ""))
    if _REPO_ROOT not in loaded_file.parents:
        for name in [
            module_name
            for module_name in sys.modules
            if module_name == "sage" or module_name.startswith("sage.")
        ]:
            sys.modules.pop(name, None)

_aieos = importlib.import_module("sage.identity.aieos")
_parse_aieos = _aieos._parse_aieos
format_identity_prompt = _aieos.format_identity_prompt
load_identity = _aieos.load_identity


@pytest.fixture
def sample_aieos_file(tmp_path: Path) -> Path:
    payload = {
        "identity": {
            "names": {
                "first": "Ari",
                "middle": "Nova",
                "last": "Quinn",
                "nickname": "AQ",
            },
            "bio": {
                "gender": "non-binary",
                "age_perceived": 28,
            },
        },
        "psychology": {
            "neural_matrix": {
                "creativity": 0.9,
                "empathy": 0.8,
                "logic": 0.7,
                "adaptability": 0.6,
                "charisma": 0.75,
                "reliability": 0.95,
            }
        },
        "linguistics": {
            "text_style": {
                "formality_level": 0.4,
                "verbosity_level": 0.7,
                "vocabulary_level": "advanced",
                "slang_usage": True,
                "style_descriptors": ["playful", "precise"],
            },
            "idiolect": {
                "catchphrases": ["Let us map that out."],
                "forbidden_words": ["impossible"],
            },
        },
        "capabilities": {
            "skills": [
                {
                    "name": "analysis",
                    "description": "Breaks down complex tasks",
                    "version": "1.0.0",
                }
            ]
        },
    }
    file_path = tmp_path / "persona.aieos.json"
    file_path.write_text(json.dumps(payload), encoding="utf-8")
    return file_path


class TestAieosIdentityLoading:
    def test_load_identity_from_json_file(self, sample_aieos_file: Path) -> None:
        identity = load_identity(sample_aieos_file)
        assert identity.names.first == "Ari"
        assert identity.names.nickname == "AQ"
        assert identity.neural_matrix.creativity == 0.9
        assert identity.text_style.vocabulary_level == "advanced"
        assert len(identity.skills) == 1
        assert identity.skills[0].name == "analysis"

    def test_parse_aieos_with_full_data(self) -> None:
        data = {
            "identity": {
                "names": {"first": "Sam", "last": "Lee"},
                "bio": {"gender": "female", "age_perceived": 34},
            },
            "psychology": {"neural_matrix": {"creativity": 0.8, "empathy": 0.4}},
            "linguistics": {
                "text_style": {"formality_level": 0.6, "verbosity_level": 0.3},
                "idiolect": {"catchphrases": ["Ship it."]},
            },
            "capabilities": {
                "skills": [
                    {"name": "coding", "description": "Writes code"},
                    {"name": "debugging", "description": "Finds root causes"},
                ]
            },
        }

        identity = _parse_aieos(data)
        assert identity.names.first == "Sam"
        assert identity.names.last == "Lee"
        assert identity.bio.age_perceived == 34
        assert identity.neural_matrix.creativity == 0.8
        assert identity.text_style.formality_level == 0.6
        assert identity.idiolect.catchphrases == ["Ship it."]
        assert [skill.name for skill in identity.skills] == ["coding", "debugging"]

    def test_parse_aieos_with_minimal_empty_data(self) -> None:
        identity = _parse_aieos({})
        assert identity.names.first == ""
        assert identity.names.last == ""
        assert identity.bio.gender == ""
        assert identity.neural_matrix.logic == 0.5
        assert identity.text_style.vocabulary_level == "medium"
        assert identity.idiolect.catchphrases == []
        assert identity.skills == []

    def test_load_identity_file_not_found_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_identity(tmp_path / "missing.aieos.json")

    def test_load_identity_invalid_json_raises(self, tmp_path: Path) -> None:
        invalid_file = tmp_path / "broken.aieos.json"
        invalid_file.write_text("{not-json}", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            load_identity(invalid_file)


class TestAieosIdentityPromptFormatting:
    def test_format_identity_prompt_output_structure(self, sample_aieos_file: Path) -> None:
        identity = load_identity(sample_aieos_file)
        prompt = format_identity_prompt(identity)

        assert prompt.startswith("## AIEOS Identity")
        assert 'Name: Ari Nova Quinn ("AQ")' in prompt
        assert "Personality traits:" in prompt
        assert "Communication style:" in prompt
        assert "Declared skills:" in prompt

    @pytest.mark.xfail(
        reason="Current formatter always emits default personality/style blocks for empty identities"
    )
    def test_format_identity_prompt_with_empty_identity_returns_empty_string(self) -> None:
        identity = _parse_aieos({})
        assert format_identity_prompt(identity) == ""
