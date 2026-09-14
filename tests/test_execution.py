import pytest

from cwi.agents.service import ConversationService
from cwi.conversation.backends import BaselineBackend
from cwi.conversation.models import Task
from cwi.planning.scheduler import Assignment, assign
from cwi.simulation.world import World
from cwi.state.store import Store


def task(tote="T17", destination="P2", source="A"):
    return Task(
        tote_id=tote,
        source=source,
        destination=destination,
        priority="normal",
        requested_by="demo-operator",
    )


def test_optimizer_beats_greedy_and_never_double_assigns():
    costs = [
        Assignment("R1", "A", 1),
        Assignment("R1", "B", 2),
        Assignment("R2", "A", 2),
        Assignment("R2", "B", 100),
    ]
    result = assign(costs)
    assert sum(a.cost for a in result) == 4
    assert len({a.robot for a in result}) == len({a.job for a in result}) == 2


def test_three_robot_delivery_and_collision_invariants():
    world = World()
    for key, command in [("a", task()), ("b", task("T23", "P1")), ("c", task("T42", "P2", "B"))]:
        world.submit(key, command)
    for _ in range(150):
        previous = {r.identifier: r.cell for r in world.robots}
        world.step()
        cells = [r.cell for r in world.robots]
        assert len(set(cells)) == 3
        assert all(r.battery >= 0 for r in world.robots)
        for r in world.robots:
            assert all(r.cell != cell for other, cell in previous.items() if other != r.identifier)
    assert all(j.status == "completed" for j in world.jobs.values())
    assert len({e["robot"] for e in world.events if e["kind"] == "assigned"}) == 3


def test_hidden_changes_are_discovered_locally_and_rerouted():
    world = World()
    world.obstacle((4, 2), True)
    assert (4, 2) not in world.snapshot()["observed_obstacles"]
    world.submit("a", task())
    world.step(100)
    assert world.jobs["a"].status == "completed"
    assert any(e["kind"] == "observation" for e in world.events)
    assert all(r.cell != (4, 2) for r in world.robots)


def test_infeasible_energy_waits_instead_of_dispatch():
    world = World()
    for r in world.robots:
        r.battery = 1
    world.submit("a", task())
    world.step()
    assert world.jobs["a"].status == "queued"
    world.step(120)
    assert world.jobs["a"].status == "completed"


def test_confirmation_dispatch_is_idempotent_and_survives_restart(tmp_path):
    path = str(tmp_path / "state.db")
    service = ConversationService(BaselineBackend(), world=World(), store=Store(path))
    sid = service.new_session()
    service.reply(sid, "Move T17 to P2")
    accepted = service.reply(sid, "confirm")
    assert accepted.execution_dispatched
    restored = ConversationService(BaselineBackend(), world=World(), store=Store(path))
    assert restored.reply(sid, "confirm") == accepted
    assert len(restored.world.jobs) == 1
    restored.world.step(100)
    restored.persist()
    again = ConversationService(BaselineBackend(), world=World(), store=Store(path))
    assert again.world.jobs[sid].status == "completed"
    assert next(t for t in again.warehouse.totes if t.identifier == "T17").source == "P2"


def test_tote_lock_and_changed_location():
    world = World()
    world.submit("a", task())
    with pytest.raises(ValueError, match="active"):
        world.submit("b", task())
    world.step(100)
    with pytest.raises(ValueError, match="state changed"):
        world.submit("b", task())
    world.submit("b", task(source="P2", destination="P1"))
    world.step(100)
    assert world.jobs["b"].status == "completed"


def test_world_checkpoint_preserves_hidden_state():
    world = World()
    world.obstacle((7, 7), True)
    restored = World.restore(world.checkpoint())
    assert restored.checkpoint() == world.checkpoint()
    assert restored.snapshot()["observed_obstacles"] == []
