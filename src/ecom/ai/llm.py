"""Thin wrapper around the Claude API used by every AI feature.

- Structured output: responses are constrained to a JSON schema and validated with Pydantic.
- Refusal handling: server-side fallback is enabled, and a final refusal raises LLMRefusal.
- LLMOps: every call is logged to ai.llm_calls with tokens, latency and cost.

Tests swap in FakeLLM, so the whole pipeline runs without an API key.
"""
import json
import logging
import os
import time
from collections.abc import Callable
from typing import Protocol, TypeVar

import anthropic
from pydantic import BaseModel

from ecom.ai import db

log = logging.getLogger("llm")

MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
# USD per million tokens (input, output)
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}

T = TypeVar("T", bound=BaseModel)


class LLMRefusal(RuntimeError):
    pass


class LLM(Protocol):
    model: str

    def structured(self, purpose: str, system: str, user: str, schema: type[T], effort: str = "medium") -> T: ...


def _strict_schema(schema: type[BaseModel]) -> dict:
    """JSON schema for structured outputs: every object closed with additionalProperties=false."""
    s = schema.model_json_schema()

    def close(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                node.setdefault("additionalProperties", False)
            for v in node.values():
                close(v)
        elif isinstance(node, list):
            for v in node:
                close(v)
    close(s)
    return s


def log_call(purpose: str, model: str, usage, latency_ms: int, stop_reason: str | None) -> None:
    pin, pout = PRICES.get(model, (0.0, 0.0))
    inp, out = getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0
    cost = (inp * pin + out * pout) / 1_000_000
    try:
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO ai.llm_calls (purpose, model, input_tokens, output_tokens, latency_ms, cost_usd, stop_reason)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (purpose, model, inp, out, latency_ms, cost, stop_reason),
            )
    except Exception as e:  # noqa: BLE001 - logging must never break the feature
        log.warning("could not log LLM call: %s", e)


class ClaudeLLM:
    def __init__(self, model: str = MODEL, client: anthropic.Anthropic | None = None):
        self.model = model
        self.client = client or anthropic.Anthropic()

    def structured(self, purpose: str, system: str, user: str, schema: type[T], effort: str = "medium") -> T:
        start = time.perf_counter()
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": _strict_schema(schema)}},
            # If a safety classifier declines, the API retries on Anthropic's recommended fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        log_call(purpose, response.model, response.usage, int((time.perf_counter() - start) * 1000),
                 response.stop_reason)
        if response.stop_reason == "refusal":
            raise LLMRefusal(f"{purpose}: model declined the request")
        if response.stop_reason == "max_tokens":
            raise RuntimeError(f"{purpose}: response was cut off at max_tokens")
        text = "".join(b.text for b in response.content if b.type == "text")
        return schema.model_validate_json(text)


class FakeLLM:
    """Deterministic stand-in for tests and offline demos. `responder(purpose, user)` returns a dict."""

    model = "fake"

    def __init__(self, responder: Callable[[str, str], dict]):
        self.responder = responder
        self.calls: list[tuple[str, str]] = []

    def structured(self, purpose: str, system: str, user: str, schema: type[T], effort: str = "medium") -> T:
        self.calls.append((purpose, user))
        return schema.model_validate(json.loads(json.dumps(self.responder(purpose, user))))


def default_llm() -> LLM:
    return ClaudeLLM()
