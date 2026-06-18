from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from rich import print

from .llm import get_accumulated_usage, reset_usage_accumulator
from .mock_runtime import actor_answer, classify_failure_mode, evaluator, reflector
from .schemas import AttemptTrace, JudgeResult, QAExample, ReflectionEntry, RunRecord


def _verbose_log(message: str) -> None:
    if os.getenv("BENCHMARK_VERBOSE", "0").lower() in {"1", "true", "yes"}:
        print(f"  [dim]{message}[/dim]")


@dataclass
class BaseAgent:
    agent_type: Literal["react", "reflexion"]
    max_attempts: int = 1

    def run(self, example: QAExample) -> RunRecord:
        reflection_memory: list[str] = []
        reflections: list[ReflectionEntry] = []
        traces: list[AttemptTrace] = []
        final_answer = ""
        final_score = 0
        judge_reason = ""
        for attempt_id in range(1, self.max_attempts + 1):
            reset_usage_accumulator()
            _verbose_log(
                f"{self.agent_type} | qid={example.qid} | attempt {attempt_id}/{self.max_attempts} | actor..."
            )
            answer = actor_answer(example, attempt_id, self.agent_type, reflection_memory)
            _verbose_log(f"{self.agent_type} | qid={example.qid} | attempt {attempt_id} | evaluator...")
            judge = evaluator(example, answer)
            final_answer = answer
            final_score = judge.score
            judge_reason = judge.reason
            if judge.score == 1:
                usage = get_accumulated_usage()
                traces.append(
                    AttemptTrace(
                        attempt_id=attempt_id,
                        answer=answer,
                        score=judge.score,
                        reason=judge.reason,
                        token_estimate=usage.total_tokens,
                        latency_ms=usage.latency_ms,
                    )
                )
                break

            # TODO: Học viên triển khai logic Reflexion tại đây
            # 1. Kiểm tra nếu agent_type là 'reflexion' và chưa hết số lần attempt
            if self.agent_type == "reflexion" and attempt_id < self.max_attempts:
                # 2. Gọi hàm reflector để lấy nội dung reflection
                _verbose_log(f"{self.agent_type} | qid={example.qid} | attempt {attempt_id} | reflector...")
                reflection = reflector(example, attempt_id, judge)
                reflections.append(reflection)
                usage = get_accumulated_usage()
                trace = AttemptTrace(
                    attempt_id=attempt_id,
                    answer=answer,
                    score=judge.score,
                    reason=judge.reason,
                    token_estimate=usage.total_tokens,
                    latency_ms=usage.latency_ms,
                    reflection=reflection,
                )
                # 3. Cập nhật reflection_memory để Actor dùng cho lần sau
                reflection_memory.append(reflection.next_strategy)
                traces.append(trace)
                continue

            usage = get_accumulated_usage()
            traces.append(
                AttemptTrace(
                    attempt_id=attempt_id,
                    answer=answer,
                    score=judge.score,
                    reason=judge.reason,
                    token_estimate=usage.total_tokens,
                    latency_ms=usage.latency_ms,
                )
            )
        total_tokens = sum(t.token_estimate for t in traces)
        total_latency = sum(t.latency_ms for t in traces)
        failure_mode = classify_failure_mode(
            example,
            JudgeResult(score=final_score, reason=judge_reason),
            bool(final_score),
        )
        return RunRecord(
            qid=example.qid,
            question=example.question,
            gold_answer=example.gold_answer,
            agent_type=self.agent_type,
            predicted_answer=final_answer,
            is_correct=bool(final_score),
            attempts=len(traces),
            token_estimate=total_tokens,
            latency_ms=total_latency,
            failure_mode=failure_mode,
            reflections=reflections,
            traces=traces,
        )


class ReActAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(agent_type="react", max_attempts=1)


class ReflexionAgent(BaseAgent):
    def __init__(self, max_attempts: int = 3) -> None:
        super().__init__(agent_type="reflexion", max_attempts=max_attempts)
