"""Run deterministic integration scenarios and seeded clarification experiments."""

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

from cwi.agents.service import ConversationService
from cwi.conversation.backends import BaselineBackend
from cwi.conversation.models import Task
from cwi.retrieval.service import Retriever
from cwi.rl.clarification import ClarificationPolicy, evaluate
from cwi.simulation.world import World


def warehouse_scenario(dynamic: bool = True) -> dict[str, Any]:
    service = ConversationService(BaselineBackend(), world=World())
    assert service.world is not None
    transcript = []
    for turns in (
        ("Move the blue tote to P2", "T17", "confirm"),
        ("Move T23 to P1", "confirm"),
        ("Move T42 to P2", "confirm"),
    ):
        sid = service.new_session()
        for text in turns:
            reply = service.reply(sid, text)
            transcript.append({"operator": text, "status": reply.status, "reply": reply.message})
    if dynamic:
        service.world.obstacle((4, 2), True)
    for _ in range(150):
        service.world.step()
    state = service.world.snapshot()
    return {
        "scenario": "dynamic" if dynamic else "static",
        "metrics": state["metrics"],
        "deliveries": [
            {"tote": j.task.tote_id, "status": j.status, "tick": j.completed}
            for j in service.world.jobs.values()
        ],
        "observations": sum(e["kind"] == "observation" for e in service.world.events),
        "transcript": transcript,
    }


def assistance_scenario(mode: str) -> dict[str, Any]:
    world = World(mode)
    world.operator_busy = True
    world.submit(
        "inspection-demo",
        Task(
            tote_id="T17",
            source="A",
            destination="P2",
            priority="normal",
            requested_by="demo-operator",
        ),
    )
    robot = world.robots[0]
    robot.cell, robot.job, robot.phase = (3, 2), "inspection-demo", "delivery"
    world.jobs["inspection-demo"].status = "carrying"
    world.known = {(4, y) for y in range(world.height)}
    world.hidden = world.known - {(4, 0)}
    world.step(100)
    return {
        "policy": mode,
        "metrics": world.snapshot()["metrics"],
        "job_status": world.jobs["inspection-demo"].status,
        "fixture": "Previously observed barrier has a hidden nearby opening; operator busy",
    }


def retrieval_report() -> dict[str, Any]:
    cases = [
        ("urgent supervisor priority", "PRIORITY"),
        ("restricted Q1 destination", "ACCESS"),
        ("payload kg capacity limit", "PAYLOAD"),
        ("collision emergency protection", "SAFETY"),
        ("ambiguous tote confirm destination", "TRANSPORT"),
    ]
    hits = sum(Retriever().search(query)[0].document_id == expected for query, expected in cases)
    return {
        "fixture_queries": len(cases),
        "top1_accuracy": hits / len(cases),
        "limitation": "Tiny hand-authored synthetic fixture; not a held-out language benchmark.",
    }


def run() -> dict[str, Any]:
    reports: dict[str, list[dict[str, float]]] = {
        k: [] for k in ("q_learning", "always_ask", "inspect_when_possible")
    }
    for seed in (7, 17, 27, 37, 47):
        policy = ClarificationPolicy()
        policy.train(seed=seed)
        for method in reports:
            reports[method].append(
                evaluate(
                    policy, seed=seed + 1000, baseline=None if method == "q_learning" else method
                )
            )
    summary = {
        method: {
            metric: {
                "mean": statistics.mean(r[metric] for r in rows),
                "std": statistics.stdev(r[metric] for r in rows),
            }
            for metric in rows[0]
        }
        for method, rows in reports.items()
    }
    return {
        "warehouse": [warehouse_scenario(False), warehouse_scenario(True)],
        "retrieval": retrieval_report(),
        "integrated_assistance": [assistance_scenario(mode) for mode in reports],
        "clarification": {
            "train_seeds": [7, 17, 27, 37, 47],
            "episodes_per_seed": 5000,
            "evaluation_episodes_per_seed": 1000,
            "results": summary,
            "per_seed": reports,
        },
        "limitations": [
            "Synthetic simulator and synthetic clarification transitions",
            "No live LLM inference, microphone, or physical robot evaluation",
            "Inspection probability and interruption costs are assumed",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("outputs/evaluation.json"))
    parser.add_argument("--policy", type=Path, default=Path("outputs/clarification-policy.json"))
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    policy = ClarificationPolicy()
    policy.train()
    policy.save(args.policy)
    print(
        json.dumps(
            {
                "warehouse": [w["metrics"] for w in result["warehouse"]],
                "retrieval": result["retrieval"],
                "clarification": result["clarification"]["results"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
