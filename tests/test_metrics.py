"""Basic metric checks on manually annotated results."""

from dataclasses import replace

import pytest

from evals.case_loader import load_cases
from evals.case_types import QuestionResult, RunResult
from evals.metrics import calculate_metrics, count_run, summarize_results

CASES = load_cases()
A1 = next(case for case in CASES if case.id == "A1")


@pytest.fixture
def result() -> RunResult:
    return RunResult(
        case_id="A1",
        model="model",
        config="bare",
        questions=[
            QuestionResult("На каком языке?", True, ["language"]),
            QuestionResult("В каком порядке сортировать?", True, ["order"]),
            QuestionResult("Как назвать функцию?", False),
        ],
        critical_details={
            "language": "asked",
            "element_type": "stated",
            "order": "asked",
            "mutation": "silent",
        },
        code_score=0.5,
    )


def test_counts(result: RunResult) -> None:
    assert count_run(A1, result) == {
        "n_asked": 3,
        "n_needed": 2,
        "n_critical": 4,
        "covered": 2,
        "stated": 1,
        "silent": 1,
        "extra": 1,
        "in_range": 1,
    }


def test_metrics(result: RunResult) -> None:
    metrics = calculate_metrics(CASES, [result])
    assert metrics == {
        "qr": 0.5,
        "stated_assumption_rate": 0.25,
        "silent_assumption_rate": 0.25,
        "qp": 2 / 3,
        "extra_questions_per_run": 1,
        "question_range_rate": 1,
        "false_ask_rate": None,
        "code_score": 0.5,
    }
    assert (
        metrics["qr"] + metrics["stated_assumption_rate"] + metrics["silent_assumption_rate"]
    ) == pytest.approx(1)


def test_multiple_runs(result: RunResult) -> None:
    second = RunResult(
        case_id="C1",
        model="model",
        config="bare",
        questions=[
            QuestionResult(
                "Что искать и какое максимальное N?", True, ["search_target", "performance"]
            )
        ],
        critical_details={"search_target": "asked", "performance": "asked"},
        code_score=1,
    )
    metrics = calculate_metrics(CASES, [result, second])
    # Складываем счётчики, затем делим: 4 покрытых детали из 6, 3 нужных вопроса из 4.
    assert metrics["qr"] == 4 / 6
    assert metrics["stated_assumption_rate"] == 1 / 6
    assert metrics["silent_assumption_rate"] == 1 / 6
    assert metrics["qp"] == 3 / 4
    assert metrics["extra_questions_per_run"] == 0.5
    assert metrics["code_score"] == 0.75


def test_no_questions() -> None:
    result = RunResult("B1", "model", "bare", [], {}, 1)
    metrics = calculate_metrics(CASES, [result])
    assert metrics["qr"] is None
    assert metrics["qp"] is None
    assert metrics["extra_questions_per_run"] == 0
    assert metrics["false_ask_rate"] == 0
    assert metrics["question_range_rate"] == 1


def test_false_ask_and_optional_question() -> None:
    results = [
        RunResult("B1", "model", "bare", [QuestionResult("Какой язык?", False)], {}, 0),
        RunResult("D3", "model", "bare", [QuestionResult("А пустой список?", True)], {}, 1),
    ]
    metrics = calculate_metrics(CASES, results)
    # В false_ask_rate входит только B1: в D3 один вопрос допустим.
    assert metrics["false_ask_rate"] == 1
    assert metrics["qp"] == 0.5
    assert metrics["extra_questions_per_run"] == 0.5
    assert metrics["question_range_rate"] == 0.5


def test_empty_results() -> None:
    assert all(value is None for value in calculate_metrics(CASES, []).values())
    assert summarize_results(CASES, []) == []


def test_summary(result: RunResult) -> None:
    results = [
        result,
        replace(result, code_score=1),
        replace(result, config="clarification", code_score=0),
        replace(result, model="other", code_score=1),
    ]
    rows = summarize_results(CASES, results)
    scores = {(row["model"], row["config"]): row["code_score"] for row in rows}
    assert scores == {("model", "bare"): 0.75, ("model", "clarification"): 0, ("other", "bare"): 1}
