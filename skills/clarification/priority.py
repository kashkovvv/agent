from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class MissingDetail:
    description: str
    question: str
    impact: int
    rework: int
    answer_cost: int
    # Includes access control and data handling decisions.
    security: bool = False

    def __post_init__(self) -> None:
        for score in (self.impact, self.rework, self.answer_cost):
            if type(score) is not int or not 0 <= score <= 3:
                raise ValueError("Scores must be integers from 0 to 3")

    @property
    def priority(self) -> int:
        return 3 * self.impact + 2 * self.rework - self.answer_cost

    def needs_question(self, threshold: int = 8) -> bool:
        return self.security or self.priority >= threshold


def select_questions(
    details: Iterable[MissingDetail],
    *,
    already_asked: int = 0,
    threshold: int = 8,
    max_questions: int = 3,
    max_total: int = 5,
) -> list[MissingDetail]:
    """Select from unresolved details, keeping input order for equal priorities."""
    if min(already_asked, max_questions, max_total) < 0:
        raise ValueError("Question counts must be non-negative")
    remaining = min(max_questions, max_total - already_asked)
    if remaining <= 0:
        return []
    candidates = (detail for detail in details if detail.needs_question(threshold))
    return sorted(candidates, key=lambda detail: detail.priority, reverse=True)[:remaining]
