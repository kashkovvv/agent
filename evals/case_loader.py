"""Read evaluation cases from YAML files."""

from pathlib import Path

import yaml

from evals.case_types import CodeCheck, CriticalDetail, QuestionRange, TestCase

DEFAULT_CASES_DIR = Path(__file__).resolve().parent / "cases" / "clarification"


def load_cases(folder: str | Path = DEFAULT_CASES_DIR) -> list[TestCase]:
    """Read all *.yaml files in filename order and return their cases."""
    folder = Path(folder)
    if not folder.is_dir():
        raise NotADirectoryError(f"Case directory not found: {folder}")

    cases = []
    for path in sorted(folder.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            data["critical"] = [CriticalDetail(**detail) for detail in data["critical"]]
            data["expected_questions"] = QuestionRange(**data["expected_questions"])
            data["check"] = CodeCheck(**data["check"])
            cases.append(TestCase(**data))
        except (yaml.YAMLError, KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Invalid case in {path}: {error}") from error

    return cases
