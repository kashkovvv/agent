"""Basic checks for evaluation case files, without calling a model."""

from pathlib import Path

import pytest

from evals.case_loader import load_cases
from evals.case_types import QuestionRange
from evals.case_types import TestCase as EvalCase

ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "evals/cases/clarification"
CASES = load_cases(CASE_DIR)


def test_case_count() -> None:
    assert len(CASES) == 13
    assert [case.id for case in CASES] == [path.stem for path in sorted(CASE_DIR.glob("*.yaml"))]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_case_fields(case: EvalCase) -> None:
    assert isinstance(case, EvalCase)
    assert case.category in {"A", "B", "C", "D"}
    assert case.category == case.id[0]
    assert isinstance(case.prompt, str) and case.prompt.strip()

    assert len({detail.id for detail in case.critical}) == len(case.critical)
    for detail in case.critical:
        for value in (detail.id, detail.question, detail.answer):
            assert isinstance(value, str) and value.strip()
    if case.category in {"A", "C"}:
        assert case.critical
    else:
        assert not case.critical

    for values in (case.free, case.forbidden_questions, case.optional_questions):
        assert isinstance(values, list)
        assert all(isinstance(value, str) and value.strip() for value in values)
    assert case.check.language in {"python", "javascript", "cpp", "java"}
    assert isinstance(case.check.description, str) and case.check.description.strip()


@pytest.mark.parametrize("bounds", [(-1, 0), (3, 2), (True, 2), (0, 1.5)])
def test_invalid_question_range(bounds: tuple) -> None:
    with pytest.raises(ValueError):
        QuestionRange(*bounds)


def test_load_cases_from_another_folder(tmp_path: Path) -> None:
    for name in ("B2.yaml", "A1.yaml"):
        (tmp_path / name).write_text(
            (CASE_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
        )

    assert [case.id for case in load_cases(tmp_path)] == ["A1", "B2"]


@pytest.mark.parametrize("contents", ["prompt: [", "{}", ""])
def test_invalid_case_reports_filename(tmp_path: Path, contents: str) -> None:
    (tmp_path / "broken.yaml").write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match="broken.yaml"):
        load_cases(tmp_path)


def test_missing_case_folder(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        load_cases(tmp_path / "missing")
