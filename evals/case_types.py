"""Data shared by evaluation cases, the user simulator, and the judge."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class CriticalDetail:
    """A required clarification with a stable ID local to its case."""

    id: str
    question: str
    answer: str


@dataclass
class QuestionRange:
    min: int
    max: int

    def __post_init__(self) -> None:
        if type(self.min) is not int or type(self.max) is not int:
            raise ValueError("Question bounds must be integers")
        if not 0 <= self.min <= self.max:
            raise ValueError("Question bounds must satisfy 0 <= min <= max")


@dataclass
class CodeCheck:
    """Criteria the judge uses to assess code, without executing it."""

    language: Literal["python", "javascript", "cpp", "java"]
    description: str


@dataclass
class TestCase:
    id: str
    category: Literal["A", "B", "C", "D"]
    prompt: str
    critical: list[CriticalDetail]
    free: list[str]
    expected_questions: QuestionRange
    check: CodeCheck
    forbidden_questions: list[str] = field(default_factory=list)
    optional_questions: list[str] = field(default_factory=list)


@dataclass
class QuestionResult:
    """Judge's assessment of one question, including optional clarifications."""

    text: str
    needed: bool
    critical_ids: list[str] = field(default_factory=list)


DetailStatus = Literal["asked", "stated", "silent"]


@dataclass
class RunResult:
    """One completed run; clarification labels and code score come from the judge."""

    case_id: str
    model: str
    config: str
    questions: list[QuestionResult]
    critical_details: dict[str, DetailStatus]
    code_score: float
    code_reason: str = ""
