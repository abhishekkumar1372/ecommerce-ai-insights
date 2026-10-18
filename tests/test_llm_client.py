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
