"""Model clients used by every AI feature: Claude (Anthropic) or Gemini (Google).

- Structured output: responses are constrained to a JSON schema and validated with Pydantic.
- Refusal handling: server-side fallback is enabled, and a final refusal raises LLMRefusal.
- LLMOps: every call is logged to ai.llm_calls with tokens, latency and cost.

Provider choice: LLM_PROVIDER=claude|gemini, or automatic from whichever key is set
(ANTHROPIC_API_KEY first, then GEMINI_API_KEY). Gemini has a free tier.

Tests swap in FakeLLM, so the whole pipeline runs without an API key.
"""
import json
import logging
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Protocol, TypeVar

import anthropic
from pydantic import BaseModel

from ecom.ai import db

log = logging.getLogger("llm")

MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
# USD per million tokens (input, output) at paid list prices. Gemini's free tier is billed at $0;
# the logged cost then shows what the same traffic would cost on a paid plan.
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50),
          "gemini-2.5-flash": (0.30, 2.50), "gemini-2.5-pro": (1.25, 10.0)}

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


def _inline_refs(schema: dict) -> dict:
    """Replace $ref/$defs with the referenced definitions (some providers do not resolve $ref)."""
    defs = schema.get("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].split("/")[-1]])
            return {k: resolve(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node
    return resolve(schema)


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


class _Usage:
    def __init__(self, input_tokens: int, output_tokens: int):
        self.input_tokens, self.output_tokens = input_tokens, output_tokens


class GeminiLLM:
    """Gemini via its REST API (no extra dependency). Structured output via responseJsonSchema."""

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, model: str = GEMINI_MODEL, api_key: str | None = None, opener=urllib.request.urlopen):
        self.model = model
        self.api_key = api_key or os.environ["GEMINI_API_KEY"]
        self.opener = opener

    def structured(self, purpose: str, system: str, user: str, schema: type[T], effort: str = "medium") -> T:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": _inline_refs(_strict_schema(schema)),
            },
        }
        request = urllib.request.Request(
            self.URL.format(model=self.model), data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
        )
        start = time.perf_counter()
        try:
            with self.opener(request, timeout=120) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{purpose}: Gemini API error {e.code}: {e.read()[:300]!r}") from e
        meta = data.get("usageMetadata", {})
        candidate = (data.get("candidates") or [{}])[0]
        finish = candidate.get("finishReason")
        log_call(purpose, self.model, _Usage(meta.get("promptTokenCount", 0), meta.get("candidatesTokenCount", 0)),
                 int((time.perf_counter() - start) * 1000), finish)
        if finish in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST") or ("promptFeedback" in data and not candidate):
            raise LLMRefusal(f"{purpose}: model declined the request ({finish})")
        if finish == "MAX_TOKENS":
            raise RuntimeError(f"{purpose}: response was cut off at max tokens")
        text = "".join(p.get("text", "") for p in candidate.get("content", {}).get("parts", []))
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


def provider() -> str | None:
    """Which provider will be used: LLM_PROVIDER if set, else the first key found."""
    chosen = os.getenv("LLM_PROVIDER", "").lower()
    if chosen in ("claude", "gemini"):
        return chosen
    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"):
        return "claude"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    return None


def default_llm() -> LLM:
    p = provider()
    if p == "claude":
        return ClaudeLLM()
    if p == "gemini":
        return GeminiLLM()
    raise RuntimeError("No model key found. Set GEMINI_API_KEY (free at aistudio.google.com) or ANTHROPIC_API_KEY.")
