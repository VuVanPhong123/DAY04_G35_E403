from __future__ import annotations

import json
import hmac
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Literal

import anyio
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent_runtime import append_transcript_turn, client_safe_result, now_iso, run_model_tool_loop, sanitize_session_id
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools


ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
TRANSCRIPTS_DIR = ROOT / "transcripts"
load_lab_env(ROOT)


def env_status(key: str) -> str:
    return "configured" if os.getenv(key) else "missing"


def parse_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [item.strip() for item in raw.split(",") if item.strip()]


def upstream_error_detail(exc: Exception) -> str:
    text = str(exc)
    for key in ("GEMINI_API_KEY", "TAVILY_API_KEY", "FIRECRAWL_API_KEY", "RAPIDAPI_KEY", "BACKEND_SHARED_SECRET"):
        value = os.getenv(key)
        if value:
            text = text.replace(value, "<redacted>")
    return f"{type(exc).__name__}: {text[:420]}"


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)
    session_id: str | None = Field(default=None, max_length=120)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message is required")
        return stripped


app = FastAPI(title="Research Agent Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Internal-API-Key"],
)


def require_internal_secret(x_internal_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("BACKEND_SHARED_SECRET")
    if not expected:
        return
    if not x_internal_api_key or not hmac.compare_digest(x_internal_api_key, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def load_runtime_config() -> tuple[str, list[dict]]:
    system_prompt = (ARTIFACTS_DIR / "system_prompt.md").read_text(encoding="utf-8")
    tools = to_openai_tools(load_tool_declarations(ARTIFACTS_DIR / "tools.yaml"))
    return system_prompt, tools


async def run_chat_request(request: Request, payload: ChatRequest) -> dict:
    session_id = sanitize_session_id(payload.session_id)
    system_prompt, tools = load_runtime_config()
    provider = make_provider("gemini")
    messages = [
        {"role": "system", "content": system_prompt},
        *[item.model_dump() for item in payload.history],
        {"role": "user", "content": payload.message},
    ]

    started_at = now_iso()
    try:
        with anyio.fail_after(float(os.getenv("CHAT_TIMEOUT_SECONDS", "90"))):
            result = await anyio.to_thread.run_sync(
                lambda: run_model_tool_loop(
                    provider=provider,
                    messages=messages,
                    tools=tools,
                    model=None,
                    max_tool_rounds=int(os.getenv("MAX_TOOL_ROUNDS", "4")),
                    echo_tools=False,
                )
            )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Provider or tool loop timed out") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)[:500]) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=upstream_error_detail(exc)) from exc

    safe = client_safe_result(result)
    turn = {
        "started_at": started_at,
        "ended_at": now_iso(),
        "client": request.client.host if request.client else None,
        "user": payload.message,
        "status": safe["status"],
        "assistant_text": safe["assistant_text"],
        "tool_events": safe["tool_events"],
        "rounds": safe["rounds"],
    }
    append_transcript_turn(
        transcripts_dir=TRANSCRIPTS_DIR,
        session_id=session_id,
        turn=turn,
        metadata={"provider": "gemini", "model": getattr(provider, "selected_model", None), "source": "api"},
    )
    return {
        "session_id": session_id,
        "status": safe["status"],
        "answer": safe["assistant_text"],
        "tool_events": safe["tool_events"],
        "rounds": safe["rounds"],
    }


def sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


@app.get("/health")
def health() -> dict:
    provider = make_provider("gemini")
    return {
        "status": "ok",
        "provider": "gemini",
        "model": getattr(provider, "selected_model", None) or getattr(provider, "default_model", None),
        "tools": {
            "gemini": env_status("GEMINI_API_KEY"),
            "tavily": env_status("TAVILY_API_KEY"),
            "firecrawl": env_status("FIRECRAWL_API_KEY"),
            "rapidapi": env_status("RAPIDAPI_KEY"),
        },
    }


@app.post("/api/chat")
async def chat(request: Request, payload: ChatRequest, _: None = Depends(require_internal_secret)) -> dict:
    return await run_chat_request(request, payload)


@app.post("/api/chat/stream")
async def chat_stream(request: Request, payload: ChatRequest, _: None = Depends(require_internal_secret)) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        yield sse("status", {"message": "Đã nhận yêu cầu..."})
        yield sse("status", {"message": "Đang gọi model và công cụ..."})
        try:
            result = await run_chat_request(request, payload)
        except HTTPException as exc:
            yield sse("error", {"status_code": exc.status_code, "detail": exc.detail})
            return
        except Exception as exc:
            yield sse("error", {"status_code": 500, "detail": upstream_error_detail(exc)})
            return
        yield sse("final", result)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
