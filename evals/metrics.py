"""Calculate metrics from annotated runs without calling a model."""

from evals.case_types import RunResult, TestCase


def count_run(case: TestCase, result: RunResult) -> dict[str, int]:
    """Count questions and detail outcomes for one run."""
    if result.case_id != case.id:
        raise ValueError(f"Result for {result.case_id} does not match case {case.id}")
    detail_ids = {detail.id for detail in case.critical}
    if result.critical_details.keys() != detail_ids:
        raise ValueError(f"{case.id}: every critical detail must have exactly one status")
    if any(
        status not in {"asked", "stated", "silent"} for status in result.critical_details.values()
    ):
        raise ValueError(f"{case.id}: unknown critical detail status")
    if result.code_score not in {0, 0.5, 1}:
        raise ValueError(f"{case.id}: code_score must be 0, 0.5, or 1")

    n_asked = len(result.questions)
    n_needed = sum(question.needed for question in result.questions)
    statuses = list(result.critical_details.values())
    return {
        "n_asked": n_asked,
        "n_needed": n_needed,
        "n_critical": len(case.critical),
        "covered": statuses.count("asked"),
        "stated": statuses.count("stated"),
        "silent": statuses.count("silent"),
        "extra": n_asked - n_needed,
        "in_range": int(case.expected_questions.min <= n_asked <= case.expected_questions.max),
    }


def _ratio(numerator: float, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def calculate_metrics(cases: list[TestCase], results: list[RunResult]) -> dict[str, float | None]:
    """Calculate all eight metrics, dividing summed counts rather than run ratios."""
    cases_by_id = {case.id: case for case in cases}
    total_critical = covered = stated = silent = 0
    total_asked = total_needed = extra = in_range = 0
    false_asks = zero_question_runs = 0

    for result in results:
        if result.case_id not in cases_by_id:
            raise ValueError(f"Unknown case: {result.case_id}")
        case = cases_by_id[result.case_id]
        counts = count_run(case, result)
        total_asked += counts["n_asked"]
        total_needed += counts["n_needed"]
        extra += counts["extra"]
        in_range += counts["in_range"]
        if case.category in {"A", "C"}:
            total_critical += counts["n_critical"]
            covered += counts["covered"]
            stated += counts["stated"]
            silent += counts["silent"]
        if case.expected_questions.max == 0:
            zero_question_runs += 1
            false_asks += int(counts["n_asked"] > 0)

    return {
        "qr": _ratio(covered, total_critical),
        "stated_assumption_rate": _ratio(stated, total_critical),
        "silent_assumption_rate": _ratio(silent, total_critical),
        "qp": _ratio(total_needed, total_asked),
        "extra_questions_per_run": _ratio(extra, len(results)),
        "question_range_rate": _ratio(in_range, len(results)),
        "false_ask_rate": _ratio(false_asks, zero_question_runs),
        "code_score": _ratio(sum(result.code_score for result in results), len(results)),
    }


def summarize_results(
    cases: list[TestCase],
    results: list[RunResult],
) -> list[dict[str, str | float | None]]:
    """Return one summary row per model and configuration."""
    groups: dict[tuple[str, str], list[RunResult]] = {}
    for result in results:
        groups.setdefault((result.model, result.config), []).append(result)

    summary = []
    for (model, config), group in sorted(groups.items()):
        metrics = calculate_metrics(cases, group)
        summary.append({"model": model, "config": config, **metrics})
    return summary
