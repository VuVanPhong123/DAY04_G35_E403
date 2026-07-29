from __future__ import annotations

import json
import os
from typing import Any

from providers.base import ModelResponse, ToolCall


def _to_gemini_declarations(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    declarations: list[dict[str, Any]] = []
    for item in tools or []:
        function = item.get("function", item)
        declarations.append({
            "name": function["name"],
            "description": function.get("description", ""),
            "parameters": function.get("parameters", {"type": "object", "properties": {}}),
        })
    return declarations


def _to_gemini_contents(messages: list[dict[str, str]]) -> tuple[str | None, list[dict[str, Any]]]:
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system":
            system_parts.append(content)
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": content}]})
        elif role == "user":
            contents.append({"role": "user", "parts": [{"text": content}]})
    return ("\n\n".join(system_parts) if system_parts else None), contents


def _part_text(part: Any) -> str | None:
    if hasattr(part, "text"):
        return getattr(part, "text") or None
    if isinstance(part, dict):
        return part.get("text") or None
    return None


def _part_function_call(part: Any) -> Any | None:
    if hasattr(part, "function_call"):
        return getattr(part, "function_call")
    if isinstance(part, dict):
        return part.get("function_call")
    return None


def _function_call_name(call: Any) -> str | None:
    if hasattr(call, "name"):
        return getattr(call, "name") or None
    if isinstance(call, dict):
        return call.get("name") or None
    return None


def _jsonable_args(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "items"):
        return dict(value.items())
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(exclude_none=True)
        return dict(dumped or {})
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return {}


def _function_call_args(call: Any) -> dict[str, Any]:
    if hasattr(call, "args"):
        return _jsonable_args(getattr(call, "args"))
    if isinstance(call, dict):
        return _jsonable_args(call.get("args"))
    return {}


def _candidate_parts(candidate: Any) -> list[Any]:
    content = getattr(candidate, "content", None)
    if isinstance(candidate, dict):
        content = candidate.get("content")
    if content is None:
        return []
    if isinstance(content, dict):
        return list(content.get("parts") or [])
    return list(getattr(content, "parts", []) or [])


def parse_gemini_response(resp: Any) -> ModelResponse:
    text_parts: list[str] = []
    calls: list[ToolCall] = []

    def append_call(function_call: Any) -> None:
        name = _function_call_name(function_call)
        if name:
            calls.append(ToolCall(name=name, args=_function_call_args(function_call)))

    candidates = list(getattr(resp, "candidates", []) or [])
    if isinstance(resp, dict):
        candidates = list(resp.get("candidates") or [])

    for candidate in candidates:
        finish_reason = getattr(candidate, "finish_reason", None)
        if isinstance(candidate, dict):
            finish_reason = candidate.get("finish_reason")
        for part in _candidate_parts(candidate):
            text = _part_text(part)
            if text:
                text_parts.append(text)
            function_call = _part_function_call(part)
            if function_call:
                append_call(function_call)
        if finish_reason and "SAFETY" in str(finish_reason).upper():
            raise RuntimeError("Gemini response was blocked by safety settings.")

    response_calls = getattr(resp, "function_calls", []) or []
    if isinstance(resp, dict):
        response_calls = resp.get("function_calls") or []
    for function_call in response_calls:
        append_call(function_call)

    if not candidates and not calls:
        prompt_feedback = getattr(resp, "prompt_feedback", None)
        block_reason = getattr(prompt_feedback, "block_reason", None) if prompt_feedback else None
        if isinstance(resp, dict):
            block_reason = (resp.get("prompt_feedback") or {}).get("block_reason")
        if block_reason:
            raise RuntimeError(f"Gemini request was blocked: {block_reason}")
        raise RuntimeError("Gemini returned no candidates.")

    deduped_calls: list[ToolCall] = []
    seen: set[tuple[str, str]] = set()
    for call in calls:
        key = (call.name, json.dumps(call.args, ensure_ascii=False, sort_keys=True, default=str))
        if key not in seen:
            seen.add(key)
            deduped_calls.append(call)

    return ModelResponse(text="\n".join(part for part in text_parts if part) or None, tool_calls=deduped_calls, raw=resp)


def build_tool_config(types: Any, tool_choice: Any | None, declarations: list[dict[str, Any]]) -> Any | None:
    if not declarations:
        return None
    if tool_choice in (None, "auto"):
        return None

    mode = None
    allowed_names: list[str] | None = None
    if tool_choice == "required":
        mode = types.FunctionCallingConfigMode.ANY
        allowed_names = [item["name"] for item in declarations]
    elif tool_choice == "none":
        mode = types.FunctionCallingConfigMode.NONE
    elif isinstance(tool_choice, dict):
        function = tool_choice.get("function") or {}
        name = function.get("name")
        if name:
            mode = types.FunctionCallingConfigMode.ANY
            allowed_names = [name]

    if mode is None:
        return None
    return types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(
            mode=mode,
            allowed_function_names=allowed_names,
        )
    )


class GeminiProvider:
    """Google Gemini API provider with normalized tool_calls output."""

    def __init__(
        self,
        *,
        api_key_env: str = "GEMINI_API_KEY",
        model_env: str = "GEMINI_MODEL",
        default_model: str = "gemini-3.1-flash-lite",
    ) -> None:
        self.api_key_env = api_key_env
        self.model_env = model_env
        self.default_model = default_model

    @property
    def selected_model(self) -> str:
        return os.getenv(self.model_env) or self.default_model

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.0,
        tool_choice: Any | None = None,
    ) -> ModelResponse:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("Install live provider dependency first: pip install google-genai") from exc

        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing API key env var: {self.api_key_env}")

        system_instruction, contents = _to_gemini_contents(messages)
        declarations = _to_gemini_declarations(tools)
        config_kwargs: dict[str, Any] = {"temperature": temperature}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if declarations:
            config_kwargs["tools"] = [types.Tool(function_declarations=declarations)]
            tool_config = build_tool_config(types, tool_choice, declarations)
            if tool_config is not None:
                config_kwargs["tool_config"] = tool_config

        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model or self.selected_model,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        return parse_gemini_response(resp)
