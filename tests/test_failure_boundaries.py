import json

import httpx
import pytest

from cwi.agents.service import ConversationService
from cwi.conversation.backends import BackendError, BaselineBackend, OllamaBackend
from cwi.conversation.knowledge import answer_question
from cwi.retrieval.service import Retriever
from cwi.simulation.world import World
from cwi.state.store import Store


def test_failed_checkpoint_cannot_leave_a_dispatched_task(tmp_path, monkeypatch):
    store = Store(str(tmp_path / "state.db"))
    service = ConversationService(BaselineBackend(), world=World(), store=store)
    sid = service.new_session()
    service.reply(sid, "Move T17 to P2")

    def fail(state):
        raise OSError("Disk full")

    monkeypatch.setattr(store, "save", fail)
    with pytest.raises(OSError, match="Disk full"):
        service.reply(sid, "confirm")
    assert service.world.jobs == {}
    assert service.sessions[sid].pending is not None
    assert service.sessions[sid].final is None
    restored = ConversationService(
        BaselineBackend(), world=World(), store=Store(str(tmp_path / "state.db"))
    )
    assert restored.world.jobs == {}
    assert restored.reply(sid, "confirm").execution_dispatched


def test_restart_cannot_reuse_supervisor_pending_consent_under_operator_role(tmp_path):
    from cwi.state.warehouse import Operator

    path = str(tmp_path / "state.db")
    supervisor = ConversationService(
        BaselineBackend(), Operator(role="supervisor"), world=World(), store=Store(path)
    )
    sid = supervisor.new_session()
    assert supervisor.reply(sid, "Move T17 to Q1").status == "awaiting_confirmation"
    operator = ConversationService(BaselineBackend(), world=World(), store=Store(path))
    assert operator.reply(sid, "confirm").status == "rejected"
    assert operator.world.jobs == {}


@pytest.mark.parametrize("ids,valid", [(["PRIORITY"], True), (["INVENTED"], False)])
def test_generated_answer_citations_are_validated(monkeypatch, ids, valid):
    original = httpx.Client

    def handler(request):
        payload = json.loads(request.content)
        assert payload["format"]["additionalProperties"] is False
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {"answer": "Supervisors can request urgent priority.", "document_ids": ids}
                    )
                }
            },
        )

    monkeypatch.setattr(
        httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)
    )
    if valid:
        answer = answer_question("urgent priority supervisor", Retriever(), OllamaBackend("test"))
        assert answer.mode == "generated"
        assert answer.citations[0].document_id == "PRIORITY"
        assert not answer.execution_dispatched
    else:
        with pytest.raises(BackendError):
            answer_question("urgent priority supervisor", Retriever(), OllamaBackend("test"))
