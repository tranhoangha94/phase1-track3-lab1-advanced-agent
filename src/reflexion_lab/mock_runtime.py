from __future__ import annotations

import json

from pydantic import ValidationError

from .llm import chat, extract_json, use_mock
from .prompts import ACTOR_SYSTEM, EVALUATOR_SYSTEM, REFLECTOR_SYSTEM
from .schemas import QAExample, JudgeResult, ReflectionEntry
from .utils import normalize_answer

FIRST_ATTEMPT_WRONG = {"hp2": "London", "hp4": "Atlantic Ocean", "hp6": "Red Sea", "hp8": "Andes"}
FAILURE_MODE_BY_QID = {
    "hp2": "incomplete_multi_hop",
    "hp4": "wrong_final_answer",
    "hp6": "entity_drift",
    "hp8": "entity_drift",
}


def _format_context(example: QAExample) -> str:
    return "\n\n".join(f"[{chunk.title}]\n{chunk.text}" for chunk in example.context)


def _mock_actor_answer(
    example: QAExample,
    attempt_id: int,
    agent_type: str,
    reflection_memory: list[str],
) -> str:
    if example.qid not in FIRST_ATTEMPT_WRONG:
        return example.gold_answer
    if agent_type == "react":
        return FIRST_ATTEMPT_WRONG[example.qid]
    if attempt_id == 1 and not reflection_memory:
        return FIRST_ATTEMPT_WRONG[example.qid]
    return example.gold_answer


def _mock_evaluator(example: QAExample, answer: str) -> JudgeResult:
    if normalize_answer(example.gold_answer) == normalize_answer(answer):
        return JudgeResult(score=1, reason="Final answer matches the gold answer after normalization.")
    if normalize_answer(answer) == "london":
        return JudgeResult(
            score=0,
            reason="The answer stopped at the birthplace city and never completed the second hop to the river.",
        )
    return JudgeResult(
        score=0,
        reason="The final answer selected the wrong second-hop entity.",
    )


def _mock_reflector(example: QAExample, attempt_id: int, judge: JudgeResult) -> ReflectionEntry:
    strategy = (
        "Do the second hop explicitly: birthplace city -> river through that city."
        if example.qid == "hp2"
        else "Verify the final entity against the second paragraph before answering."
    )
    return ReflectionEntry(
        attempt_id=attempt_id,
        failure_reason=judge.reason,
        lesson="A partial first-hop answer is not enough; the final answer must complete all hops.",
        next_strategy=strategy,
    )


def _llm_actor_answer(
    example: QAExample,
    attempt_id: int,
    agent_type: str,
    reflection_memory: list[str],
) -> str:
    reflection_block = ""
    if reflection_memory:
        notes = "\n".join(f"- {note}" for note in reflection_memory)
        reflection_block = f"\n\nReflection notes from previous attempts:\n{notes}\n"

    user_prompt = f"""Question:
{example.question}

Context:
{_format_context(example)}
{reflection_block}
Attempt: {attempt_id}
Agent type: {agent_type}

Return only the final answer."""

    answer = chat(ACTOR_SYSTEM, user_prompt)
    return answer.splitlines()[0].strip().strip('"').strip("'")


def _llm_evaluator(example: QAExample, answer: str) -> JudgeResult:
    if normalize_answer(example.gold_answer) == normalize_answer(answer):
        return JudgeResult(score=1, reason="Exact match after normalization.")

    user_prompt = f"""Question:
{example.question}

Gold answer:
{example.gold_answer}

Predicted answer:
{answer}
"""
    raw = chat(EVALUATOR_SYSTEM, user_prompt)
    try:
        payload = extract_json(raw)
        return JudgeResult.model_validate(payload)
    except (json.JSONDecodeError, ValidationError):
        return JudgeResult(
            score=0,
            reason=f"Evaluator could not parse LLM output; treating as incorrect. Raw: {raw[:200]}",
        )


def _llm_reflector(example: QAExample, attempt_id: int, judge: JudgeResult) -> ReflectionEntry:
    user_prompt = f"""Question:
{example.question}

Wrong answer attempt: {attempt_id}
Evaluator reason: {judge.reason}

Context:
{_format_context(example)}

Set attempt_id to {attempt_id} in the JSON response."""

    raw = chat(REFLECTOR_SYSTEM, user_prompt)
    try:
        payload = extract_json(raw)
        payload["attempt_id"] = attempt_id
        return ReflectionEntry.model_validate(payload)
    except (json.JSONDecodeError, ValidationError):
        return ReflectionEntry(
            attempt_id=attempt_id,
            failure_reason=judge.reason,
            lesson="The previous answer did not satisfy the multi-hop question.",
            next_strategy="Re-read all context paragraphs and complete every hop before answering.",
        )


def actor_answer(
    example: QAExample,
    attempt_id: int,
    agent_type: str,
    reflection_memory: list[str],
) -> str:
    if use_mock():
        return _mock_actor_answer(example, attempt_id, agent_type, reflection_memory)
    return _llm_actor_answer(example, attempt_id, agent_type, reflection_memory)


def evaluator(example: QAExample, answer: str) -> JudgeResult:
    if use_mock():
        return _mock_evaluator(example, answer)
    return _llm_evaluator(example, answer)


def reflector(example: QAExample, attempt_id: int, judge: JudgeResult) -> ReflectionEntry:
    if use_mock():
        return _mock_reflector(example, attempt_id, judge)
    return _llm_reflector(example, attempt_id, judge)


def classify_failure_mode(example: QAExample, judge: JudgeResult, is_correct: bool) -> str:
    if is_correct:
        return "none"
    if use_mock():
        return FAILURE_MODE_BY_QID.get(example.qid, "wrong_final_answer")

    reason = judge.reason.lower()
    if "hop" in reason or "partial" in reason or "incomplete" in reason:
        return "incomplete_multi_hop"
    if "entity" in reason or "drift" in reason or "wrong second" in reason:
        return "entity_drift"
    return "wrong_final_answer"
