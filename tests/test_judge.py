"""Test judge integration with prepared model replies, without real API calls."""

import json
from pathlib import Path

import pytest

from agent.types import LLMResponse, Usage
from evals.case_loader import load_cases
from evals.case_types import QuestionResult
from evals.judge import evaluate_dialogue
from evals.metrics import calculate_metrics

CASES = {case.id: case for case in load_cases()}


class FakeLLM:
    def __init__(self, reply: dict | str):
        self.reply = json.dumps(reply, ensure_ascii=False) if isinstance(reply, dict) else reply
        self.calls = []

    def complete(self, messages, json_schema=None, temperature=0.0):
        self.calls.append((messages, json_schema, temperature))
        return LLMResponse(self.reply, Usage())


def no_code_reply(case_id: str) -> dict:
    return {
        "questions": [],
        "critical_details": {detail.id: "silent" for detail in CASES[case_id].critical},
        "code_score": 0,
        "code_reason": "В ответе нет кода.",
    }


@pytest.mark.parametrize("case_id", ["A1", "B2", "B3", "D2"])
def test_same_judge_interface_for_all_languages(case_id: str) -> None:
    case = CASES[case_id]
    llm = FakeLLM(no_code_reply(case_id))
    dialogue = [
        {"role": "user", "content": case.prompt},
        {"role": "assistant", "content": "Не могу предложить решение."},
    ]
    result = evaluate_dialogue(llm, case, dialogue, model="agent-model", config="bare")

    assert result.case_id == case_id
    assert result.model == "agent-model"
    assert result.config == "bare"
    assert result.code_score == 0
    assert result.code_reason == "В ответе нет кода."
    assert len(llm.calls) == 1
    messages, schema, temperature = llm.calls[0]
    payload = json.loads(messages[1]["content"])
    assert payload["case"]["check"]["description"] == case.check.description
    assert payload["dialogue"] == dialogue
    assert schema["properties"]["code_score"]["enum"] == [0, 0.5, 1]
    assert temperature == 0


def test_judge_result_can_be_used_by_metrics() -> None:
    reply = no_code_reply("A1")
    reply["questions"] = [{"text": "На каком языке?", "needed": True, "critical_ids": ["language"]}]
    reply["critical_details"]["language"] = "asked"
    reply["code_score"] = 0.5
    reply["code_reason"] = "Сортировка верная, но исходный список изменяется."
    dialogue = [
        {"role": "user", "content": CASES["A1"].prompt},
        {"role": "assistant", "content": "На каком языке?"},
        {"role": "user", "content": "Python 3"},
        {"role": "assistant", "content": "def sort_values(x): x.sort(); return x"},
    ]
    result = evaluate_dialogue(FakeLLM(reply), CASES["A1"], dialogue, "model", "bare")
    metrics = calculate_metrics(list(CASES.values()), [result])

    assert result.questions == [QuestionResult("На каком языке?", True, ["language"])]
    assert metrics["qr"] == 0.25
    assert metrics["code_score"] == 0.5


def test_submitted_code_is_never_executed(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    dialogue = [
        {
            "role": "assistant",
            "content": (f"```python\nfrom pathlib import Path\nPath({str(marker)!r}).touch()\n```"),
        }
    ]
    evaluate_dialogue(FakeLLM(no_code_reply("A1")), CASES["A1"], dialogue, "model", "bare")
    assert not marker.exists()


def test_invalid_json_is_rejected() -> None:
    with pytest.raises(ValueError):
        evaluate_dialogue(FakeLLM("not JSON"), CASES["A1"], [], "model", "bare")


def test_missing_critical_status_is_rejected() -> None:
    reply = no_code_reply("A1")
    del reply["critical_details"]["language"]
    with pytest.raises(ValueError, match="every critical detail"):
        evaluate_dialogue(FakeLLM(reply), CASES["A1"], [], "model", "bare")


def test_invalid_score_is_rejected() -> None:
    reply = no_code_reply("A1")
    reply["code_score"] = 2
    with pytest.raises(ValueError, match="code_score"):
        evaluate_dialogue(FakeLLM(reply), CASES["A1"], [], "model", "bare")
