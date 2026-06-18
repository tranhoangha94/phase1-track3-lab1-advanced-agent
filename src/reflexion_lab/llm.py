from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: LLMUsage) -> LLMUsage:
        return LLMUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            latency_ms=self.latency_ms + other.latency_ms,
        )


_accumulated_usage = LLMUsage()
_client: OpenAI | None = None


def use_mock() -> bool:
    return os.getenv("USE_MOCK", "0").strip().lower() in {"1", "true", "yes"}


def reset_usage_accumulator() -> None:
    global _accumulated_usage
    _accumulated_usage = LLMUsage()


def get_accumulated_usage() -> LLMUsage:
    return _accumulated_usage


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.getenv("LLM_API_KEY", "ollama"),
        )
    return _client


def _get_model() -> str:
    return os.getenv("LLM_MODEL", "qwen2:1.5b")


def extract_json(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        text = fenced.group(1).strip()
    return json.loads(text)


def chat(system: str, user: str, *, temperature: float = 0.0) -> str:
    global _accumulated_usage
    client = _get_client()
    started = time.perf_counter()
    response = client.chat.completions.create(
        model=_get_model(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    usage = response.usage
    step_usage = LLMUsage(
        prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        latency_ms=latency_ms,
    )
    _accumulated_usage += step_usage
    content = response.choices[0].message.content or ""
    return content.strip()
