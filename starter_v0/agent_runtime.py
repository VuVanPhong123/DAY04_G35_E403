from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from providers.base import ToolCall
from tools import TOOL_FUNCTIONS


MAX_EVENT_TEXT = 2400


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return slug.strip("_") or "run"


def sanitize_session_id(session_id: str | None) -> str:
    if not session_id:
        return str(uuid.uuid4())
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", session_id.strip())
    cleaned = cleaned.strip("._-")
    if not cleaned or cleaned in {".", ".."}:
        return str(uuid.uuid4())
    return cleaned[:80]


def json_text(value: Any, *, max_chars: int | None = None) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars] + "\n...<truncated>"
    return text


def trim_history(history: list[dict[str, str]], window: int) -> list[dict[str, str]]:
    if window <= 0:
        return []
    return history[-window * 2:]


def _truncate_text(value: str, max_chars: int) -> str:
    return value if len(value) <= max_chars else value[:max_chars] + "...<truncated>"


def sanitize_for_client(value: Any, *, max_chars: int = MAX_EVENT_TEXT) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("api_key", "apikey", "token", "authorization", "secret", "x-rapidapi-key", "x-internal-api-key")):
                sanitized[key] = "<redacted>"
            else:
                sanitized[key] = sanitize_for_client(item, max_chars=max_chars)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_client(item, max_chars=max_chars) for item in value[:20]]
    if isinstance(value, str):
        return _truncate_text(value, max_chars)
    return value


def execute_tool_call(call: ToolCall) -> dict[str, Any]:
    func = TOOL_FUNCTIONS.get(call.name)
    if not func:
        return {
            "tool": call.name,
            "args": call.args,
            "result": {"error": "unknown_tool", "message": f"No local implementation for {call.name}"},
        }
    try:
        result = func(**call.args)
    except Exception as exc:
        result = {"error": type(exc).__name__, "message": str(exc)}
    return {"tool": call.name, "args": call.args, "result": result}


def tool_results_message(events: list[dict[str, Any]]) -> dict[str, str]:
    return {
        "role": "user",
        "content": (
            "TOOL_RESULTS_JSON:\n"
            f"{json_text(events, max_chars=24000)}\n\n"
            "Use only these tool results. If the user asked for a digest and the items are ready, "
            "call the formatting tool. Otherwise answer the user directly with cited sources when available."
        ),
    }


def assistant_tool_message(response_text: str | None, calls: list[ToolCall]) -> dict[str, str]:
    call_summary = [{"name": call.name, "args": call.args} for call in calls]
    content = response_text or "I will call the selected tool(s)."
    return {
        "role": "assistant",
        "content": f"{content}\n\nTOOL_CALLS_JSON:\n{json_text(call_summary)}",
    }


def run_model_tool_loop(
    *,
    provider: Any,
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]],
    model: str | None,
    max_tool_rounds: int,
    echo_tools: bool = False,
) -> dict[str, Any]:
    working_messages = list(messages)
    rounds: list[dict[str, Any]] = []
    all_tool_events: list[dict[str, Any]] = []

    for round_index in range(1, max_tool_rounds + 1):
        response = provider.complete(working_messages, tools, model=model, temperature=0.0)
        calls = response.tool_calls
        round_record: dict[str, Any] = {
            "round": round_index,
            "assistant_text": response.text,
            "tool_calls": [{"name": call.name, "args": call.args} for call in calls],
            "tool_results": [],
        }

        if not calls:
            rounds.append(round_record)
            return {
                "status": "answered",
                "assistant_text": response.text or "",
                "answer": response.text or "",
                "rounds": rounds,
                "tool_events": all_tool_events,
            }

        working_messages.append(assistant_tool_message(response.text, calls))
        non_clarification_events: list[dict[str, Any]] = []

        for call in calls:
            if echo_tools:
                print(f"TOOL {call.name}({json.dumps(call.args, ensure_ascii=False, sort_keys=True)})")
            event = execute_tool_call(call)
            round_record["tool_results"].append(event)
            all_tool_events.append(event)

            result = event.get("result", {})
            if isinstance(result, dict) and result.get("awaiting_user"):
                question = result.get("question") or call.args.get("question") or "Please provide the missing information."
                rounds.append(round_record)
                return {
                    "status": "waiting_for_user",
                    "assistant_text": question,
                    "answer": question,
                    "rounds": rounds,
                    "tool_events": all_tool_events,
                }

            non_clarification_events.append(event)

        rounds.append(round_record)
        working_messages.append(tool_results_message(non_clarification_events))

    answer = f"Stopped after {max_tool_rounds} tool rounds. Inspect the transcript for details."
    return {
        "status": "max_tool_rounds",
        "assistant_text": answer,
        "answer": answer,
        "rounds": rounds,
        "tool_events": all_tool_events,
    }


def client_safe_result(result: dict[str, Any]) -> dict[str, Any]:
    copy = dict(result)
    copy["tool_events"] = sanitize_for_client(copy.get("tool_events", []))
    copy["rounds"] = sanitize_for_client(copy.get("rounds", []))
    return copy


def transcript_path(transcripts_dir: Path, session_id: str) -> Path:
    safe_id = sanitize_session_id(session_id)
    path = (transcripts_dir / f"{safe_id}.transcript.json").resolve()
    base = transcripts_dir.resolve()
    if base != path.parent:
        raise ValueError("Invalid transcript path")
    return path


def append_transcript_turn(
    *,
    transcripts_dir: Path,
    session_id: str,
    turn: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> Path:
    path = transcript_path(transcripts_dir, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        transcript = json.loads(path.read_text(encoding="utf-8"))
    else:
        transcript = {
            "transcript_id": path.stem.replace(".transcript", ""),
            "session_id": session_id,
            "created_at": now_iso(),
            "turns": [],
        }
        if metadata:
            transcript.update(metadata)
    transcript["updated_at"] = now_iso()
    transcript.setdefault("turns", []).append(turn)
    path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path

