import io

import pytest
from fastapi.testclient import TestClient

from cwi.agents.service import ConversationService
from cwi.api.app import create_app
from cwi.conversation.backends import BaselineBackend
from cwi.retrieval.service import PROCEDURES, Retriever
from cwi.simulation.world import World

TOKEN = "test-only-operator-token"
HEADERS = {"X-CWI-Token": TOKEN}


class FakeSpeech:
    def transcribe(self, audio):
        assert audio == b"synthetic audio"
        return "Move T17 to P2"


def test_voice_requires_review_and_does_not_execute():
    service = ConversationService(BaselineBackend(), world=World())
    client = TestClient(create_app(service, TOKEN, FakeSpeech()))
    r = client.post(
        "/speech/transcribe",
        headers=HEADERS,
        files={"file": ("recording.wav", io.BytesIO(b"synthetic audio"), "audio/wav")},
    )
    assert r.json() == {"text": "Move T17 to P2"}
    assert service.world.jobs == {}
    assert client.post("/speech/transcribe", files={"file": ("x", b"a")}).status_code == 401


def test_dashboard_and_full_api_delivery():
    service = ConversationService(BaselineBackend(), world=World())
    client = TestClient(create_app(service, TOKEN))
    assert "Cooperative Warehouse Intelligence" in client.get("/").text
    assert client.get("/warehouse").status_code == 401
    sid = client.post("/sessions", headers=HEADERS).json()["session_id"]
    for text in ("Move T17 to P2", "confirm"):
        r = client.post(f"/sessions/{sid}/messages", headers=HEADERS, json={"text": text})
        assert r.status_code == 200
    assert r.json()["execution_dispatched"]
    r = client.post("/warehouse/advance", headers=HEADERS, json={"ticks": 100})
    assert r.json()["metrics"]["completed"] == 1
    assert (
        client.post("/warehouse/advance", headers=HEADERS, json={"ticks": 501}).status_code == 422
    )
    assert (
        client.post("/warehouse/obstacles", headers=HEADERS, json={"x": 3, "y": 2}).status_code
        == 422
    )


def test_knowledge_is_grounded_and_cannot_dispatch():
    service = ConversationService(BaselineBackend(), world=World())
    client = TestClient(create_app(service, TOKEN))
    r = client.post(
        "/knowledge", headers=HEADERS, json={"text": "Who can request urgent priority?"}
    )
    assert r.status_code == 200
    assert r.json()["citations"][0]["document_id"] == "PRIORITY"
    assert not r.json()["execution_dispatched"]
    assert service.world.jobs == {}
    assert (
        client.post(
            "/speech/transcribe", headers=HEADERS, files={"file": ("x.wav", b"a")}
        ).status_code
        == 503
    )


def test_duplicate_active_procedure_versions_fail_closed():
    with pytest.raises(ValueError, match="Multiple active"):
        Retriever(PROCEDURES + PROCEDURES)
