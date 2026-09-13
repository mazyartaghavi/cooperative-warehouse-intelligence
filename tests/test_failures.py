import pytest
from fastapi.testclient import TestClient

from cwi.agents.service import ConversationService
from cwi.api.app import create_app
from cwi.conversation.backends import BackendError, BaselineBackend


@pytest.mark.parametrize("text", ["Do not move T17 to P2", "Delete T17"])
def test_unsupported_baseline_request_does_not_propose_transport(text):
    service = ConversationService(BaselineBackend())
    with pytest.raises(BackendError):
        service.reply(service.new_session(), text)


def test_api_failed_interpretation_clears_pending_confirmation():
    token = "test-only-long-token"
    client = TestClient(create_app(ConversationService(BaselineBackend()), token))
    headers = {"X-CWI-Token": token}
    sid = client.post("/sessions", headers=headers).json()["session_id"]
    url = f"/sessions/{sid}/messages"
    client.post(url, headers=headers, json={"text": "Move T17 to P2"})
    assert client.post(url, headers=headers, json={"text": "Delete T17"}).status_code == 503
    assert client.post(url, headers=headers, json={"text": "confirm"}).json()["status"] == (
        "clarification"
    )
