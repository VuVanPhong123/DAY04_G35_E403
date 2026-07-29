from __future__ import annotations

import pytest

from providers.gemini_provider import GeminiProvider, build_tool_config, parse_gemini_response


class Obj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_parse_text_response() -> None:
    resp = Obj(candidates=[Obj(content=Obj(parts=[Obj(text="hello")]))])
    parsed = parse_gemini_response(resp)
    assert parsed.text == "hello"
    assert parsed.tool_calls == []


def test_parse_function_call_and_deduplicate() -> None:
    call = Obj(name="lookup", args={"query": "AI"})
    resp = Obj(
        candidates=[Obj(content=Obj(parts=[Obj(function_call=call)]))],
        function_calls=[call],
    )
    parsed = parse_gemini_response(resp)
    assert len(parsed.tool_calls) == 1
    assert parsed.tool_calls[0].name == "lookup"
    assert parsed.tool_calls[0].args == {"query": "AI"}


def test_empty_response_raises_structured_error() -> None:
    with pytest.raises(RuntimeError, match="no candidates"):
        parse_gemini_response(Obj(candidates=[]))


def test_safety_finish_reason_raises() -> None:
    resp = Obj(candidates=[Obj(finish_reason="SAFETY", content=Obj(parts=[]))])
    with pytest.raises(RuntimeError, match="safety"):
        parse_gemini_response(resp)


def test_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiProvider()
    with pytest.raises(RuntimeError, match="Missing API key"):
        provider.complete([{"role": "user", "content": "hi"}])


def test_tool_choice_mapping() -> None:
    from google.genai import types

    declarations = [{"name": "lookup"}, {"name": "fetch"}]
    required = build_tool_config(types, "required", declarations)
    none = build_tool_config(types, "none", declarations)
    auto = build_tool_config(types, None, declarations)

    assert required.function_calling_config.mode == types.FunctionCallingConfigMode.ANY
    assert required.function_calling_config.allowed_function_names == ["lookup", "fetch"]
    assert none.function_calling_config.mode == types.FunctionCallingConfigMode.NONE
    assert auto is None

