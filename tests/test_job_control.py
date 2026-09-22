import pytest
from fastapi.testclient import TestClient

from cwi.agents.service import ConversationService
from cwi.api.app import create_app
from cwi.conversation.backends import BaselineBackend
from cwi.conversation.models import Task
from cwi.simulation.world import World
from cwi.state.store import Store
from cwi.state.warehouse import Operator

TOKEN = "job-control-test-token"
HEADERS = {"X-CWI-Token": TOKEN}


def accepted(service, tote="T17", destination="P2"):
    sid = service.new_session()
    service.reply(sid, f"Move {tote} to {destination}")
    receipt = service.reply(sid, "confirm")
    assert receipt.execution_dispatched and receipt.job_id == sid
    return sid


def advance_until(world, sid, status):
    for _ in range(100):
        if world.jobs[sid].status == status:
            return
        world.step()
    pytest.fail(f"Job never reached {status}")


def test_queued_pause_prevents_assignment_and_resume_completes():
    service = ConversationService(BaselineBackend(), world=World())
    sid = accepted(service)
    assert service.control_job(sid, "pause").paused
    service.world.step(10)
    assert service.world.jobs[sid].status == "queued"
    assert all(r.job is None for r in service.world.robots)
    assert service.world.distance == 0
    assert not service.control_job(sid, "resume").paused
    advance_until(service.world, sid, "completed")
    assert service.job_update(sid).status == "completed"


def test_pausing_one_robot_preserves_cargo_and_allows_other_delivery():
    service = ConversationService(BaselineBackend(), world=World())
    sid = accepted(service)
    advance_until(service.world, sid, "carrying")
    service.world.step(2)
    robot = next(r for r in service.world.robots if r.job == sid)
    before = (robot.cell, robot.battery)
    service.control_job(sid, "pause")
    other = accepted(service, "T42", "P1")
    service.world.step(100)
    assert (robot.cell, robot.battery) == before
    assert service.world.jobs[sid].status == "carrying"
    assert service.world.jobs[other].status == "completed"
    assert len({r.cell for r in service.world.robots}) == 3
    service.control_job(sid, "resume")
    advance_until(service.world, sid, "completed")


@pytest.mark.parametrize("ticks", [0, 1])
def test_cancel_before_pickup_releases_tote_without_delivery(ticks):
    service = ConversationService(BaselineBackend(), world=World())
    sid = accepted(service)
    if ticks:
        service.world.step(ticks)
    assert service.control_job(sid, "cancel").status == "cancelled"
    events = len(service.world.events)
    service.control_job(sid, "cancel")
    assert len(service.world.events) == events
    assert not any(r.job == sid for r in service.world.robots)
    assert service.world.jobs[sid].completed is None
    replacement = accepted(service)
    advance_until(service.world, replacement, "completed")
    assert service.world.snapshot()["metrics"]["completed"] == 1
    assert not any(e["kind"] == "delivered" and e["job"] == sid for e in service.world.events)


def test_cancellation_returns_carried_tote_before_unlocking_and_survives_restart(tmp_path):
    path = str(tmp_path / "state.db")
    service = ConversationService(BaselineBackend(), world=World(), store=Store(path))
    sid = accepted(service)
    advance_until(service.world, sid, "carrying")
    service.world.step(3)
    assert service.control_job(sid, "cancel").status == "returning"
    task = service.world.jobs[sid].task
    with pytest.raises(ValueError, match="active"):
        service.world.submit("duplicate", task)
    service = ConversationService(BaselineBackend(), world=World(), store=Store(path))
    robot = next(r for r in service.world.robots if r.job == sid)
    assert robot.phase == "return"
    advance_until(service.world, sid, "cancelled")
    assert robot.cell == service.world.locations[task.source]
    assert next(t for t in service.world.warehouse.totes if t.identifier == "T17").source == "A"
    assert service.world.jobs[sid].completed is None
    assert service.world.snapshot()["metrics"]["completed"] == 0
    assert service.world.snapshot()["metrics"]["cancelled"] == 1
    assert any(e["kind"] == "returned" for e in service.world.events)
    service.world.submit("replacement", task)
    advance_until(service.world, "replacement", "completed")


def test_blocked_return_keeps_cargo_locked_and_does_not_claim_cancellation_complete():
    service = ConversationService(BaselineBackend(), world=World())
    sid = accepted(service)
    advance_until(service.world, sid, "carrying")
    service.world.step(3)
    service.control_job(sid, "cancel")
    robot = next(r for r in service.world.robots if r.job == sid)
    robot.battery = 0
    service.world.step(10)
    assert service.job_update(sid).status == "returning"
    assert service.world.jobs[sid].cancelled is None
    assert service.world.snapshot()["metrics"]["cancelled"] == 0
    assert any(e["kind"] == "assistance" for e in service.world.events)


def test_duplicate_cancel_cannot_resume_paused_return():
    service = ConversationService(BaselineBackend(), world=World())
    sid = accepted(service)
    advance_until(service.world, sid, "carrying")
    service.control_job(sid, "cancel")
    service.control_job(sid, "pause")
    assert service.control_job(sid, "cancel").paused
    service.world.step(3)
    assert service.job_update(sid).status == "returning"
    service.control_job(sid, "resume")
    advance_until(service.world, sid, "cancelled")


@pytest.mark.parametrize("action", ["pause", "cancel"])
@pytest.mark.parametrize("via_chat", [False, True])
def test_failed_checkpoint_rolls_back_control_action(tmp_path, monkeypatch, action, via_chat):
    path = str(tmp_path / "state.db")
    store = Store(path)
    service = ConversationService(BaselineBackend(), world=World(), store=store)
    sid = accepted(service)
    advance_until(service.world, sid, "carrying")
    service.persist()
    before = service.checkpoint()

    def fail(_):
        raise OSError("Disk full")

    monkeypatch.setattr(store, "save", fail)
    with pytest.raises(OSError, match="Disk full"):
        service.reply(sid, action) if via_chat else service.control_job(sid, action)
    assert service.checkpoint() == before
    restored = ConversationService(BaselineBackend(), world=World(), store=Store(path))
    assert restored.checkpoint() == before


def test_old_checkpoint_loads_with_default_control_state():
    world = World()
    world.submit(
        "old",
        Task(
            tote_id="T17",
            source="A",
            destination="P2",
            priority="normal",
            requested_by="demo-operator",
        ),
    )
    saved = world.checkpoint()
    saved["jobs"][0].pop("paused")
    saved["jobs"][0].pop("cancelled")
    restored = World.restore(saved)
    assert not restored.jobs["old"].paused
    assert restored.jobs["old"].cancelled is None
    advance_until(restored, "old", "completed")


def test_job_controls_require_owner_or_current_supervisor():
    service = ConversationService(BaselineBackend(), world=World())
    sid = accepted(service)
    service.operator = Operator(identifier="different-operator")
    for call in (
        lambda: service.job_update(sid),
        lambda: service.control_job(sid, "cancel"),
        lambda: service.reply(sid, "cancel"),
    ):
        with pytest.raises(PermissionError):
            call()
    assert service.world.jobs[sid].status == "queued"
    service.operator = Operator(identifier="supervisor-1", role="supervisor")
    assert service.control_job(sid, "cancel").status == "cancelled"
    assert service.world.events[-1]["issuer"] == "supervisor-1"


def test_conversation_controls_never_create_another_transport_or_infer_completion():
    service = ConversationService(BaselineBackend(), world=World())
    sid = accepted(service)
    assert service.reply(sid, "pause the task").job.paused
    service.world.step(10)
    assert service.reply(sid, "What is the task status?").job.status == "queued"
    unknown = service.reply(sid, "Cancel T17 and move T23 instead")
    assert "No task change" in unknown.message
    assert unknown.job.paused
    assert not service.reply(sid, "resume").execution_dispatched
    advance_until(service.world, sid, "completed")
    result = service.reply(sid, "status")
    assert result.job.status == "completed" and "completed" in result.message
    assert len(service.world.jobs) == 1
    with pytest.raises(ValueError, match="completed"):
        service.reply(sid, "cancel")


def test_control_before_confirmation_does_not_dispatch_or_discard_proposal():
    service = ConversationService(BaselineBackend(), world=World())
    sid = service.new_session()
    service.reply(sid, "Move T17 to P2")
    for command in ("pause", "resume", "status"):
        assert service.reply(sid, command).status == "clarification"
        assert not service.world.jobs
        assert service.sessions[sid].pending is not None
    service.reply(sid, "cancel task")
    assert service.reply(sid, "confirm").status == "cancelled"


def test_authenticated_api_controls_and_conflicts():
    service = ConversationService(BaselineBackend(), world=World())
    sid = accepted(service)
    client = TestClient(create_app(service, TOKEN))
    url = f"/jobs/{sid}/actions"
    assert client.post(url, json={"action": "cancel"}).status_code == 401
    assert client.get(f"/jobs/{sid}").status_code == 401
    assert client.post(url, headers=HEADERS, json={"action": "pause"}).json()["paused"]
    assert client.get(f"/jobs/{sid}", headers=HEADERS).json()["status"] == "queued"
    assert client.post(url, headers=HEADERS, json={"action": "teleport"}).status_code == 422
    assert (
        client.post(
            url, headers=HEADERS, json={"action": "cancel", "role": "supervisor"}
        ).status_code
        == 422
    )
    service.operator = Operator(identifier="outsider")
    assert client.post(url, headers=HEADERS, json={"action": "cancel"}).status_code == 403
    assert client.get(f"/jobs/{sid}", headers=HEADERS).status_code == 403
    assert (
        client.post(
            f"/sessions/{sid}/messages", headers=HEADERS, json={"text": "cancel"}
        ).status_code
        == 403
    )
    service.operator = Operator()
    assert (
        client.post(url, headers=HEADERS, json={"action": "cancel"}).json()["status"] == "cancelled"
    )
    assert client.post(url, headers=HEADERS, json={"action": "resume"}).status_code == 409
    assert client.get("/jobs/absent", headers=HEADERS).status_code == 404
