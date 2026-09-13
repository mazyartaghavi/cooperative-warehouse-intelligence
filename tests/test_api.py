import pytest
from fastapi.testclient import TestClient

from cwi.agents.service import ConversationService
from cwi.api.app import app_factory, create_app
from cwi.conversation.backends import BaselineBackend

TOKEN = "test-only-operator-token"
HEADERS = {"X-CWI-Token": TOKEN}


def test_api_conversation_and_authentication():
    client = TestClient(create_app(ConversationService(BaselineBackend()), TOKEN))
    assert client.post("/sessions").status_code == 401
    sid = client.post("/sessions", headers=HEADERS).json()["session_id"]
    url = f"/sessions/{sid}/messages"
    response = client.post(url, headers=HEADERS, json={"text": "Move T17 to P2"})
    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_confirmation"
    assert (
        client.post(url, headers=HEADERS, json={"text": "confirm"}).json()["status"] == "accepted"
    )
    assert client.post(url, json={"text": "confirm"}).status_code == 401
    assert (
        client.post(url, headers=HEADERS, json={"text": "x", "role": "supervisor"}).status_code
        == 422
    )
    assert (
        client.post(
            "/sessions/absent/messages", headers=HEADERS, json={"text": "hello"}
        ).status_code
        == 404
    )


@pytest.mark.parametrize("text", ["", "   ", "x" * 2001])
def test_api_rejects_invalid_messages(text):
    client = TestClient(create_app(ConversationService(BaselineBackend()), TOKEN))
    sid = client.post("/sessions", headers=HEADERS).json()["session_id"]
    assert (
        client.post(f"/sessions/{sid}/messages", headers=HEADERS, json={"text": text}).status_code
        == 422
    )


def test_startup_requires_token_and_valid_backend(monkeypatch):
    monkeypatch.delenv("CWI_API_TOKEN", raising=False)
    monkeypatch.setenv("CWI_BACKEND", "baseline")
    with pytest.raises(ValueError, match="TOKEN"):
        app_factory()
    monkeypatch.setenv("CWI_BACKEND", "typo")
    with pytest.raises(ValueError, match="BACKEND"):
        app_factory()
