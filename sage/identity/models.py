"""Pydantic models for AIEOS v1.2 identity schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NeuralMatrix(BaseModel):
    """Behavioral weights from AIEOS psychology.neural_matrix."""

    creativity: float = 0.5
    empathy: float = 0.5
    logic: float = 0.5
    adaptability: float = 0.5
    charisma: float = 0.5
    reliability: float = 0.5


class TextStyle(BaseModel):
    """Communication style from AIEOS linguistics.text_style."""

    formality_level: float = 0.5
    verbosity_level: float = 0.5
    vocabulary_level: str = "medium"
    slang_usage: bool = False
    style_descriptors: list[str] = Field(default_factory=list)


class Idiolect(BaseModel):
    """Personal speech patterns from AIEOS linguistics.idiolect."""

    catchphrases: list[str] = Field(default_factory=list)
    forbidden_words: list[str] = Field(default_factory=list)
    hesitation_markers: bool = False


class Names(BaseModel):
    """Identity names from AIEOS identity.names."""

    first: str = ""
    middle: str = ""
    last: str = ""
    nickname: str = ""


class Bio(BaseModel):
    """Biography from AIEOS identity.bio."""

    birthday: str = ""
    age_biological: int | None = None
    age_perceived: int | None = None
    gender: str = ""


class SkillEntry(BaseModel):
    """Declarative skill from AIEOS capabilities.skills[]."""

    name: str = ""
    description: str = ""
    uri: str = ""
    version: str = ""
    auto_activate: bool = False
    priority: int = 5


class AieosIdentity(BaseModel):
    """Parsed AIEOS v1.2 identity — only the fields relevant to system prompt injection.

    This is NOT a complete representation of the AIEOS spec.  We extract
    identity, psychology, linguistics, and capabilities — the sections that
    meaningfully shape how an LLM behaves.  Sections like ``presence``,
    ``physicality``, and ``history`` are ignored.
    """

    # identity
    names: Names = Field(default_factory=Names)
    bio: Bio = Field(default_factory=Bio)

    # psychology
    neural_matrix: NeuralMatrix = Field(default_factory=NeuralMatrix)

    # linguistics
    text_style: TextStyle = Field(default_factory=TextStyle)
    idiolect: Idiolect = Field(default_factory=Idiolect)

    # capabilities
    skills: list[SkillEntry] = Field(default_factory=list)
