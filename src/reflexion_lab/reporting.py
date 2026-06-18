from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from .schemas import ReportPayload, RunRecord

def summarize(records: list[RunRecord]) -> dict:
    grouped: dict[str, list[RunRecord]] = defaultdict(list)
    for record in records:
        grouped[record.agent_type].append(record)
    summary: dict[str, dict] = {}
    for agent_type, rows in grouped.items():
        summary[agent_type] = {
            "count": len(rows),
            "em": round(mean(1.0 if r.is_correct else 0.0 for r in rows), 4),
            "avg_attempts": round(mean(r.attempts for r in rows), 4),
            "avg_token_estimate": round(mean(r.token_estimate for r in rows), 2),
            "avg_latency_ms": round(mean(r.latency_ms for r in rows), 2),
        }
    if "react" in summary and "reflexion" in summary:
        summary["delta_reflexion_minus_react"] = {
            "em_abs": round(summary["reflexion"]["em"] - summary["react"]["em"], 4),
            "attempts_abs": round(summary["reflexion"]["avg_attempts"] - summary["react"]["avg_attempts"], 4),
            "tokens_abs": round(summary["reflexion"]["avg_token_estimate"] - summary["react"]["avg_token_estimate"], 2),
            "latency_abs": round(summary["reflexion"]["avg_latency_ms"] - summary["react"]["avg_latency_ms"], 2),
        }
    return summary


def failure_breakdown(records: list[RunRecord]) -> dict:
    grouped: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        grouped[record.agent_type][record.failure_mode] += 1
    return {agent: dict(counter) for agent, counter in grouped.items()}


def _format_duration(ms: float) -> str:
    total_seconds = int(ms // 1000)
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _estimate_token_cost(total_tokens: int, input_ratio: float = 0.72) -> float:
    input_cost_per_1m = float(os.getenv("LLM_INPUT_COST_PER_1M", "0"))
    output_cost_per_1m = float(os.getenv("LLM_OUTPUT_COST_PER_1M", "0"))
    prompt_tokens = total_tokens * input_ratio
    completion_tokens = total_tokens - prompt_tokens
    return (prompt_tokens / 1_000_000) * input_cost_per_1m + (completion_tokens / 1_000_000) * output_cost_per_1m


def _agent_cost_row(rows: list[RunRecord]) -> dict:
    total_tokens = sum(r.token_estimate for r in rows)
    total_latency_ms = sum(r.latency_ms for r in rows)
    count = len(rows) or 1
    return {
        "questions": len(rows),
        "total_tokens": total_tokens,
        "avg_tokens_per_question": round(total_tokens / count, 2),
        "total_running_time_ms": total_latency_ms,
        "total_running_time": _format_duration(total_latency_ms),
        "avg_running_time_ms": round(total_latency_ms / count, 2),
        "avg_running_time": _format_duration(total_latency_ms / count),
        "estimated_api_cost_usd": round(_estimate_token_cost(total_tokens), 6),
    }


def build_cost_estimate(records: list[RunRecord], mode: str) -> dict:
    react_rows = [r for r in records if r.agent_type == "react"]
    reflexion_rows = [r for r in records if r.agent_type == "reflexion"]
    react = _agent_cost_row(react_rows)
    reflexion = _agent_cost_row(reflexion_rows)

    combined_tokens = react["total_tokens"] + reflexion["total_tokens"]
    combined_latency_ms = react["total_running_time_ms"] + reflexion["total_running_time_ms"]
    combined_cost = react["estimated_api_cost_usd"] + reflexion["estimated_api_cost_usd"]
    question_count = react["questions"] or reflexion["questions"] or 1

    projected_questions = max(int(os.getenv("REPORT_PROJECTED_QUESTIONS", "100")), question_count)
    scale = projected_questions / question_count

    input_cost = float(os.getenv("LLM_INPUT_COST_PER_1M", "0"))
    output_cost = float(os.getenv("LLM_OUTPUT_COST_PER_1M", "0"))
    is_local = "localhost" in os.getenv("LLM_BASE_URL", "127.0.0.1") or (input_cost == 0 and output_cost == 0)

    return {
        "model": os.getenv("LLM_MODEL", "unknown"),
        "mode": mode,
        "pricing": {
            "input_cost_per_1m_usd": input_cost,
            "output_cost_per_1m_usd": output_cost,
            "billing_mode": "local_compute_only" if is_local else "api_metered",
            "note": "Chi phí API = 0 khi chạy Ollama local hoặc chưa cấu hình giá token.",
        },
        "react": react,
        "reflexion": reflexion,
        "combined_run": {
            "total_tokens": combined_tokens,
            "total_running_time_ms": combined_latency_ms,
            "total_running_time": _format_duration(combined_latency_ms),
            "estimated_api_cost_usd": round(combined_cost, 6),
        },
        "delta_reflexion_minus_react": {
            "tokens": reflexion["total_tokens"] - react["total_tokens"],
            "running_time_ms": reflexion["total_running_time_ms"] - react["total_running_time_ms"],
            "running_time": _format_duration(reflexion["total_running_time_ms"] - react["total_running_time_ms"]),
            "estimated_api_cost_usd": round(
                reflexion["estimated_api_cost_usd"] - react["estimated_api_cost_usd"], 6
            ),
        },
        "projection": {
            "target_questions": projected_questions,
            "react_running_time": _format_duration(react["total_running_time_ms"] * scale),
            "reflexion_running_time": _format_duration(reflexion["total_running_time_ms"] * scale),
            "combined_running_time": _format_duration(combined_latency_ms * scale),
            "react_estimated_api_cost_usd": round(react["estimated_api_cost_usd"] * scale, 4),
            "reflexion_estimated_api_cost_usd": round(reflexion["estimated_api_cost_usd"] * scale, 4),
            "combined_estimated_api_cost_usd": round(combined_cost * scale, 4),
        },
    }


def render_cost_section(cost: dict) -> str:
    react = cost["react"]
    reflexion = cost["reflexion"]
    delta = cost["delta_reflexion_minus_react"]
    combined = cost["combined_run"]
    projection = cost["projection"]
    pricing = cost["pricing"]

    return f"""## 3. Bảng ước tính cost & running time

**Model:** `{cost['model']}` | **Billing:** {pricing['billing_mode']} | **Input:** ${pricing['input_cost_per_1m_usd']}/1M | **Output:** ${pricing['output_cost_per_1m_usd']}/1M

{pricing['note']}

### Chi phí thực tế của run hiện tại

| Metric | ReAct | Reflexion | Delta (Reflexion − ReAct) | Cả run (ReAct + Reflexion) |
|---|---:|---:|---:|---:|
| Số câu đã chạy | {react['questions']} | {reflexion['questions']} | — | {react['questions'] + reflexion['questions']} records |
| Tổng tokens | {react['total_tokens']:,} | {reflexion['total_tokens']:,} | {delta['tokens']:+,} | {combined['total_tokens']:,} |
| TB tokens / câu | {react['avg_tokens_per_question']:,} | {reflexion['avg_tokens_per_question']:,} | {reflexion['avg_tokens_per_question'] - react['avg_tokens_per_question']:+.2f} | — |
| Tổng running time | {react['total_running_time']} | {reflexion['total_running_time']} | {delta['running_time']} | {combined['total_running_time']} |
| TB thời gian / câu | {react['avg_running_time']} | {reflexion['avg_running_time']} | — | — |
| Ước tính API cost (USD) | ${react['estimated_api_cost_usd']:.4f} | ${reflexion['estimated_api_cost_usd']:.4f} | ${delta['estimated_api_cost_usd']:+.4f} | ${combined['estimated_api_cost_usd']:.4f} |

### Projection cho {projection['target_questions']} câu hỏi

| Metric | ReAct | Reflexion | Combined |
|---|---:|---:|---:|
| Ước tính running time | {projection['react_running_time']} | {projection['reflexion_running_time']} | {projection['combined_running_time']} |
| Ước tính API cost (USD) | ${projection['react_estimated_api_cost_usd']:.4f} | ${projection['reflexion_estimated_api_cost_usd']:.4f} | ${projection['combined_estimated_api_cost_usd']:.4f} |

*Projection = scale tuyến tính từ run hiện tại × ({projection['target_questions']} / số câu đã đo).*
"""


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _records_by_qid(records: list[RunRecord]) -> dict[str, dict[str, RunRecord]]:
    grouped: dict[str, dict[str, RunRecord]] = defaultdict(dict)
    for record in records:
        grouped[record.qid][record.agent_type] = record
    return grouped


def build_examples(records: list[RunRecord]) -> list[dict]:
    examples: list[dict] = []
    for record in records:
        examples.append(
            {
                "qid": record.qid,
                "agent_type": record.agent_type,
                "question": record.question,
                "gold_answer": record.gold_answer,
                "predicted_answer": record.predicted_answer,
                "is_correct": record.is_correct,
                "attempts": record.attempts,
                "failure_mode": record.failure_mode,
                "reflection_count": len(record.reflections),
                "token_estimate": record.token_estimate,
                "latency_ms": record.latency_ms,
                "reflections": [item.model_dump() for item in record.reflections],
            }
        )
    return examples


def build_discussion(records: list[RunRecord], summary: dict, failure_modes: dict) -> str:
    react_rows = [r for r in records if r.agent_type == "react"]
    reflexion_rows = [r for r in records if r.agent_type == "reflexion"]
    delta = summary.get("delta_reflexion_minus_react", {})

    react_correct = {r.qid for r in react_rows if r.is_correct}
    reflexion_correct = {r.qid for r in reflexion_rows if r.is_correct}
    recovered = sorted(reflexion_correct - react_correct)
    regressed = sorted(react_correct - reflexion_correct)

    react_failures = Counter(r.failure_mode for r in react_rows if not r.is_correct)
    reflexion_failures = Counter(r.failure_mode for r in reflexion_rows if not r.is_correct)
    top_react_failure = react_failures.most_common(1)[0][0] if react_failures else "none"
    top_reflexion_failure = reflexion_failures.most_common(1)[0][0] if reflexion_failures else "none"

    em_delta = delta.get("em_abs", 0.0)
    if em_delta > 0:
        em_verdict = "Reflexion cải thiện EM so với ReAct."
    elif em_delta < 0:
        em_verdict = "Reflexion làm giảm EM so với ReAct — cần kiểm tra chất lượng evaluator/reflector."
    else:
        em_verdict = "Hai agent có EM bằng nhau trên tập này."

    discussion = f"""### Phân tích tổng quan

Trên {len(react_rows)} câu hỏi, ReAct đạt EM {_pct(summary.get('react', {}).get('em', 0))} với trung bình {summary.get('react', {}).get('avg_attempts', 0):.2f} lần thử, còn Reflexion đạt EM {_pct(summary.get('reflexion', {}).get('em', 0))} với trung bình {summary.get('reflexion', {}).get('avg_attempts', 0):.2f} lần thử. {em_verdict}

Reflexion tốn thêm token trung bình {delta.get('tokens_abs', 0):.0f} và latency {delta.get('latency_abs', 0):.0f} ms mỗi câu so với ReAct. Đây là chi phí đổi lấy khả năng phản chiếu sau khi trả lời sai.

### So sánh failure modes

ReAct sai chủ yếu ở mode `{top_react_failure}`; Reflexion sai chủ yếu ở mode `{top_reflexion_failure}`. Reflection memory hữu ích nhất khi lỗi đến từ multi-hop chưa hoàn tất hoặc chọn nhầm entity ở bước cuối — reflector gợi ý chiến thuật cụ thể để attempt tiếp theo bám context hơn.

### Câu Reflexion cứu được / làm tệ hơn

- Câu Reflexion sửa được so với ReAct: {', '.join(recovered) if recovered else 'không có'}
- Câu ReAct đúng nhưng Reflexion sai: {', '.join(regressed) if regressed else 'không có'}

### Kết luận

Reflexion phù hợp khi câu trả lời cần nhiều bước suy luận và attempt đầu dễ dừng sớm. ReAct vẫn hợp lý khi ưu tiên chi phí thấp và độ trễ ngắn. Chất lượng cuối cùng phụ thuộc mạnh vào evaluator (chấm 0/1 chính xác) và reflector (đưa ra strategy khả thi cho attempt kế tiếp)."""

    return discussion.strip()


def render_report_md(report: ReportPayload) -> str:
    s = report.summary
    react = s.get("react", {})
    reflexion = s.get("reflexion", {})
    delta = s.get("delta_reflexion_minus_react", {})
    cost = report.meta.get("cost_estimate", {})
    cost_section = render_cost_section(cost) if cost else ""
    ext_lines = "\n".join(f"- {item}" for item in report.extensions)

    paired: list[tuple[dict, dict | None]] = []
    by_qid: dict[str, dict[str, dict]] = defaultdict(dict)
    for example in report.examples:
        by_qid[example["qid"]][example["agent_type"]] = example
    for qid in sorted(by_qid):
        paired.append((by_qid[qid].get("react", {}), by_qid[qid].get("reflexion")))

    comparison_rows = []
    for react_ex, reflexion_ex in paired:
        if not react_ex:
            continue
        qid = react_ex.get("qid", "?")
        question = react_ex.get("question", "")[:80]
        react_ok = "✓" if react_ex.get("is_correct") else "✗"
        reflex_ok = "✓" if reflexion_ex and reflexion_ex.get("is_correct") else "✗"
        react_pred = react_ex.get("predicted_answer", "")
        reflex_pred = reflexion_ex.get("predicted_answer", "") if reflexion_ex else "-"
        reflex_attempts = reflexion_ex.get("attempts", "-") if reflexion_ex else "-"
        comparison_rows.append(
            f"| {qid} | {question} | {react_ok} | {reflex_ok} | {react_pred} | {reflex_pred} | {reflex_attempts} |"
        )

    wrong_examples = [ex for ex in report.examples if not ex.get("is_correct")][:10]
    wrong_lines = []
    for ex in wrong_examples:
        wrong_lines.append(
            f"- **{ex['qid']}** ({ex['agent_type']}): gold=`{ex['gold_answer']}`, pred=`{ex['predicted_answer']}`, mode=`{ex['failure_mode']}`, reflections={ex['reflection_count']}"
        )

    return f"""# Lab 16 — Báo cáo đánh giá Reflexion Agent

## 1. Metadata
- **Dataset:** {report.meta['dataset']}
- **Mode:** {report.meta['mode']}
- **Tổng records:** {report.meta['num_records']}
- **Agents:** {', '.join(report.meta['agents'])}

## 2. So sánh ReAct vs Reflexion

| Metric | ReAct | Reflexion | Delta (Reflexion − ReAct) |
|---|---:|---:|---:|
| Exact Match (EM) | {_pct(react.get('em', 0))} | {_pct(reflexion.get('em', 0))} | {delta.get('em_abs', 0):+.4f} |
| Avg attempts | {react.get('avg_attempts', 0)} | {reflexion.get('avg_attempts', 0)} | {delta.get('attempts_abs', 0):+.4f} |
| Avg tokens | {react.get('avg_token_estimate', 0)} | {reflexion.get('avg_token_estimate', 0)} | {delta.get('tokens_abs', 0):+.2f} |
| Avg latency (ms) | {react.get('avg_latency_ms', 0)} | {reflexion.get('avg_latency_ms', 0)} | {delta.get('latency_abs', 0):+.2f} |

**Đọc nhanh:** EM cao hơn = trả lời đúng nhiều hơn; attempts/tokens/latency cao hơn = tốn thêm tài nguyên cho vòng phản chiếu.

{cost_section}
## 4. Failure modes
```json
{json.dumps(report.failure_modes, indent=2, ensure_ascii=False)}
```

## 5. Bảng so sánh từng câu
| QID | Question | ReAct | Reflexion | ReAct answer | Reflexion answer | Reflexion attempts |
|---|---|:---:|:---:|---|---|---:|
{chr(10).join(comparison_rows)}

## 6. Ví dụ sai tiêu biểu
{chr(10).join(wrong_lines) if wrong_lines else '- Không có câu sai trong run này.'}

## 7. Extensions đã triển khai
{ext_lines}

## 8. Discussion
{report.discussion}
"""


def build_report(records: list[RunRecord], dataset_name: str, mode: str = "mock") -> ReportPayload:
    summary = summarize(records)
    failure_modes = failure_breakdown(records)
    examples = build_examples(records)
    discussion = build_discussion(records, summary, failure_modes)
    cost_estimate = build_cost_estimate(records, mode)
    return ReportPayload(
        meta={
            "dataset": dataset_name,
            "mode": mode,
            "num_records": len(records),
            "agents": sorted({r.agent_type for r in records}),
            "cost_estimate": cost_estimate,
        },        summary=summary,
        failure_modes=failure_modes,
        examples=examples,
        extensions=[
            "structured_evaluator",
            "reflection_memory",
            "benchmark_report_json",
            "mock_mode_for_autograding",
        ],
        discussion=discussion,
    )


def save_report(report: ReportPayload, out_dir: str | Path, root_report: str | Path | None = "Report.md") -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    markdown = render_report_md(report)

    json_path.write_text(json.dumps(report.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")

    if root_report is not None:
        Path(root_report).write_text(markdown, encoding="utf-8")

    return json_path, md_path
