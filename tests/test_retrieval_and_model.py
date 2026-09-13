import json

import httpx
import pytest

from cwi.conversation.backends import BackendError, OllamaBackend
from cwi.retrieval.service import Procedure, Retriever


def test_retrieval_filters_inactive_and_other_warehouse_documents():
    retriever = Retriever(
        (
            Procedure("CURRENT", "Transport", "Move totes to packing"),
            Procedure("STALE", "Transport", "Move totes to packing", active=False),
            Procedure("OTHER", "Transport", "Move totes to packing", warehouse="other"),
        )
    )
    assert [c.document_id for c in retriever.search("move totes")] == ["CURRENT"]
    assert retriever.search("unrelatedxyz") == []
    with pytest.raises(ValueError):
        retriever.required("STALE")


def install_transport(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)
    )


def test_ollama_contract_supplies_evidence_schema_and_history(monkeypatch):
    def handler(request):
        body = json.loads(request.content)
        assert body["stream"] is False
        assert body["format"]["additionalProperties"] is False
        context = json.loads(body["messages"][1]["content"])
        assert context["operator_turns"] == ["Move T17 to P2"]
        assert context["procedure_evidence"][0]["document_id"] == "TRANSPORT"
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {"action": "transport", "tote_id": "T17", "destination": "P2"}
                    )
                }
            },
        )

    install_transport(monkeypatch, handler)
    backend = OllamaBackend("test-model")
    intent = backend.extract(["Move T17 to P2"], [Retriever().required("TRANSPORT")])
    assert intent.tote_id == "T17"


@pytest.mark.parametrize("content", ["not json", '{"action":"delete"}', '{"role":"supervisor"}'])
def test_invalid_model_outputs_fail_closed(monkeypatch, content):
    install_transport(
        monkeypatch, lambda request: httpx.Response(200, json={"message": {"content": content}})
    )
    with pytest.raises(BackendError):
        OllamaBackend("test-model").extract(["Move T17 to P2"], [])


def test_model_outage_has_no_silent_rules_fallback(monkeypatch):
    install_transport(monkeypatch, lambda request: httpx.Response(503))
    with pytest.raises(BackendError):
        OllamaBackend("test-model").extract(["Move T17 to P2"], [])


@pytest.mark.parametrize("url", ["https://example.com", "http://example.com", "http://a@localhost"])
def test_model_endpoint_is_local_only(url):
    with pytest.raises(ValueError):
        OllamaBackend("test-model", url)
