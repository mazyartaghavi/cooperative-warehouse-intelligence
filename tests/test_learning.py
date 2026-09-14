import random

import pytest

from cwi.rl.clarification import ClarificationPolicy, allowed, evaluate, transition


def test_uncertainty_guard_cannot_be_overridden_by_learned_values():
    policy = ClarificationPolicy()
    policy.q[(2, 0)]["proceed"] = 100000
    assert policy.choose((2, 0)) in allowed((2, 0))
    with pytest.raises(ValueError, match="masked"):
        transition((2, 0), "proceed", random.Random(1))


def test_learning_is_reproducible_and_round_trips(tmp_path):
    first, second = ClarificationPolicy(), ClarificationPolicy()
    first.train(seed=7)
    second.train(seed=7)
    assert first.q == second.q
    path = tmp_path / "policy.json"
    first.save(path)
    assert ClarificationPolicy.load(path).q == first.q
    assert evaluate(first)["mean_return"] > evaluate(first, baseline="always_ask")["mean_return"]
    assert first.choose((2, 0)) == "ask"
    assert first.choose((1, 1)) == "inspect"


def blocked_world(mode):
    from cwi.conversation.models import Task
    from cwi.simulation.world import World

    world = World(mode)
    world.operator_busy = True
    world.submit(
        "job",
        Task(
            tote_id="T17",
            source="A",
            destination="P2",
            priority="normal",
            requested_by="demo-operator",
        ),
    )
    robot = world.robots[0]
    robot.cell, robot.job, robot.phase = (3, 2), "job", "delivery"
    world.jobs["job"].status = "carrying"
    # A previously observed barrier now has an unobserved opening three cells away.
    world.known = {(4, y) for y in range(world.height)}
    world.hidden = world.known - {(4, 0)}
    return world, robot


def test_learned_inspection_updates_real_shared_map_and_unblocks_delivery():
    world, robot = blocked_world("q_learning")
    assert (4, 0) in world.known
    world.step()
    assert (4, 0) not in world.known
    assert world.inspections == 1
    assert any(e["kind"] == "assistance" and e["action"] == "inspect" for e in world.events)
    world.step(100)
    assert world.jobs["job"].status == "completed"
    assert robot.inspection_attempts <= 2


def test_always_ask_emits_operator_feedback_without_hidden_map_access():
    world, _ = blocked_world("always_ask")
    world.step()
    assert (4, 0) in world.known
    assert world.operator_questions == 1
    assert world.inspections == 0


def test_inspection_respects_energy_guard():
    world, robot = blocked_world("q_learning")
    robot.battery = world.reserve
    world.step()
    assert robot.battery == world.reserve
    assert world.inspections == 0
    assert world.operator_questions == 1
