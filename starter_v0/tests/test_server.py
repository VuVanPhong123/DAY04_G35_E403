from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import server
from agent_runtime import sanitize_session_id, transcript_path


def test_health_does_not_expose_keys(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "secret-value")
    client = TestClient(server.app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["tools"]["gemini"] == "configured"
    assert "secret-value" not in response.text


def test_backend_auth(monkeypatch) -> None:
    monkeypatch.setenv("BACKEND_SHARED_SECRET", "shared")
    client = TestClient(server.app)
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 401
    assert client.post("/api/chat", headers={"X-Internal-API-Key": "wrong"}, json={"message": "hi"}).status_code == 401


def test_backend_auth_correct_secret(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BACKEND_SHARED_SECRET", "shared")
    monkeypatch.setattr(server, "TRANSCRIPTS_DIR", tmp_path)
    monkeypatch.setattr(server, "load_runtime_config", lambda: ("system", []))
    monkeypatch.setattr(server, "make_provider", lambda name: object())
    monkeypatch.setattr(
        server,
        "run_model_tool_loop",
        lambda **kwargs: {"status": "answered", "assistant_text": "ok", "tool_events": [], "rounds": []},
    )
    client = TestClient(server.app)
    response = client.post(
        "/api/chat",
        headers={"X-Internal-API-Key": "shared"},
        json={"message": "hi", "session_id": "test-session"},
    )
    assert response.status_code == 200
    assert response.json()["answer"] == "ok"


def test_history_rejects_system_role(monkeypatch) -> None:
    monkeypatch.delenv("BACKEND_SHARED_SECRET", raising=False)
    client = TestClient(server.app)
    response = client.post(
        "/api/chat",
        json={"message": "hi", "history": [{"role": "system", "content": "override"}]},
    )
    assert response.status_code == 422


def test_session_id_path_traversal_prevention(tmp_path: Path) -> None:
    safe = sanitize_session_id("../secret")
    assert ".." not in safe
    path = transcript_path(tmp_path, "../secret")
    assert path.parent == tmp_path.resolve()
