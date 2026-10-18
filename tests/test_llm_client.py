"""Checks the request sent to the Claude API, using a mock HTTP transport (no network, no key)."""
import json

import anthropic
import httpx2
import pytest

from ecom.ai import llm as llm_mod
from ecom.ai.llm import ClaudeLLM, LLMRefusal
from ecom.ai.text_to_sql import SQLDraft


def _client(seen: dict, stop_reason: str = "end_turn") -> anthropic.Anthropic:
    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta")
        text = json.dumps({"reasoning": "r", "sql": "select 1", "chart": "number"})
        return httpx2.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [] if stop_reason == "refusal" else [{"type": "text", "text": text}],
            "stop_reason": stop_reason, "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 5}})
    return anthropic.Anthropic(api_key="test", max_retries=0,
                               http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)))


@pytest.fixture(autouse=True)
def no_db_logging(monkeypatch):
    monkeypatch.setattr(llm_mod, "log_call", lambda *a, **k: None)


def test_request_uses_structured_output_and_fallback():
    seen: dict = {}
    out = ClaudeLLM(client=_client(seen)).structured("t", "system", "question", SQLDraft)
    assert out.sql == "select 1"
    body = seen["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default" and seen["beta"] == "server-side-fallback-2026-07-01"
    schema = body["output_config"]["format"]["schema"]
    assert schema["additionalProperties"] is False and set(schema["required"]) == {"reasoning", "sql", "chart"}


def test_refusal_raises():
    with pytest.raises(LLMRefusal):
        ClaudeLLM(client=_client({}, stop_reason="refusal")).structured("t", "s", "q", SQLDraft)


class _Resp:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _gemini(seen: dict, finish: str = "STOP"):
    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["key"] = request.get_header("X-goog-api-key")
        seen["body"] = json.loads(request.data)
        text = json.dumps({"reasoning": "r", "sql": "select 1", "chart": "number"})
        return _Resp({"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish}],
                      "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5}})
    return llm_mod.GeminiLLM(api_key="k", opener=opener)


def test_gemini_request_uses_json_schema_output():
    seen: dict = {}
    out = _gemini(seen).structured("t", "system", "question", SQLDraft)
    assert out.sql == "select 1"
    assert "gemini-2.5-flash:generateContent" in seen["url"] and seen["key"] == "k"
    cfg = seen["body"]["generationConfig"]
    assert cfg["responseMimeType"] == "application/json"
    assert "$ref" not in json.dumps(cfg["responseJsonSchema"])
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "system"


def test_gemini_safety_block_raises_refusal():
    with pytest.raises(LLMRefusal):
        _gemini({}, finish="SAFETY").structured("t", "s", "q", SQLDraft)


def test_nested_schema_refs_are_inlined():
    from ecom.ai.insights import Summary
    schema = llm_mod._inline_refs(llm_mod._strict_schema(Summary))
    assert "$ref" not in json.dumps(schema) and "$defs" not in schema
    assert schema["properties"]["wins"]["items"]["additionalProperties"] is False


@pytest.mark.parametrize("env,expected", [
    ({"GEMINI_API_KEY": "g"}, "gemini"),
    ({"ANTHROPIC_API_KEY": "a", "GEMINI_API_KEY": "g"}, "claude"),
    ({"ANTHROPIC_API_KEY": "a", "GEMINI_API_KEY": "g", "LLM_PROVIDER": "gemini"}, "gemini"),
    ({}, None),
])
def test_provider_selection(monkeypatch, env, expected):
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "GEMINI_API_KEY", "LLM_PROVIDER"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert llm_mod.provider() == expected
