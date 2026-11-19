"""Evaluate a dialogue and its code with one model call; never execute the code."""

import json
from dataclasses import asdict
from pathlib import Path

from agent.types import LLMClient, Message
from evals.case_types import QuestionResult, RunResult, TestCase
from evals.metrics import count_run

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "judge.md"


def _response_schema(case: TestCase) -> dict:
    """Describe the judge's JSON response, including this case's critical IDs."""
    fields = {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "needed": {"type": "boolean"},
                    "critical_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "needed", "critical_ids"],
                "additionalProperties": False,
            },
        },
        "critical_details": {
            "type": "object",
            "properties": {
                detail.id: {"type": "string", "enum": ["asked", "stated", "silent"]}
                for detail in case.critical
            },
            "required": [detail.id for detail in case.critical],
            "additionalProperties": False,
        },
        "code_score": {"type": "number", "enum": [0, 0.5, 1]},
        "code_reason": {"type": "string"},
    }
    return {
        "type": "object",
        "properties": fields,
        "required": list(fields),
        "additionalProperties": False,
    }


def evaluate_dialogue(
    llm: LLMClient,
    case: TestCase,
    dialogue: list[Message],
    model: str,
    config: str,
) -> RunResult:
    """Return the judge's labels and code score for any supported language.

    model and config identify the evaluated agent, not the judge.
    """
    messages = [
        {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
        {
            "role": "user",
            "content": json.dumps(
                {"case": asdict(case), "dialogue": dialogue},
                ensure_ascii=False,
            ),
        },
    ]
    response = llm.complete(messages, json_schema=_response_schema(case), temperature=0.0)
    data = json.loads(response.text)
    result = RunResult(
        case_id=case.id,
        model=model,
        config=config,
        questions=[QuestionResult(**question) for question in data["questions"]],
        critical_details=data["critical_details"],
        code_score=data["code_score"],
        code_reason=data["code_reason"],
    )
    count_run(case, result)  # Check required detail statuses and the allowed score.
    return result
