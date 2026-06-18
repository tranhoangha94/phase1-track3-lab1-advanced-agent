from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from .schemas import ContextChunk, QAExample, RunRecord


def normalize_answer(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _normalize_difficulty(value: str | None) -> str:
    allowed = {"easy", "medium", "hard"}
    if value in allowed:
        return value
    return "medium"


def _convert_hotpot_item(item: dict) -> QAExample:
    context: list[ContextChunk] = []
    for entry in item.get("context", []):
        if isinstance(entry, dict):
            context.append(ContextChunk(title=entry["title"], text=entry["text"]))
            continue
        title, sentences = entry
        if isinstance(sentences, list):
            text = " ".join(str(part).strip() for part in sentences)
        else:
            text = str(sentences)
        context.append(ContextChunk(title=str(title), text=text.strip()))

    return QAExample(
        qid=str(item.get("qid") or item.get("_id")),
        difficulty=_normalize_difficulty(item.get("difficulty") or item.get("level")),
        question=item["question"],
        gold_answer=str(item.get("gold_answer") or item.get("answer")),
        context=context,
    )


def load_dataset(path: str | Path) -> list[QAExample]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    examples: list[QAExample] = []
    for item in raw:
        try:
            examples.append(QAExample.model_validate(item))
        except Exception:
            examples.append(_convert_hotpot_item(item))
    return examples


def save_jsonl(path: str | Path, records: Iterable[RunRecord]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(record.model_dump_json() + "\n")
