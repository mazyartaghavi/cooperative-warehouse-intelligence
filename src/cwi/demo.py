"""Deterministic offline example, deliberately labeled as a rules baseline."""

from cwi.agents.service import ConversationService
from cwi.conversation.backends import BaselineBackend
from cwi.simulation.world import World


def main() -> None:
    service = ConversationService(BaselineBackend(), world=World())
    identifier = service.new_session()
    print("Cooperative Warehouse Intelligence — OFFLINE RULES BASELINE (no LLM)")
    for text in ["Move the blue tote to P2", "T17", "confirm"]:
        response = service.reply(identifier, text)
        print(f"\nOperator: {text}\nCoordinator [{response.status}]: {response.message}")
        print("Evidence: " + ", ".join(c.document_id + "@" + c.version for c in response.citations))

    assert service.world is not None
    service.world.obstacle((4, 2), True)
    service.world.step(100)
    print("\nSimulated result:", service.world.jobs[identifier].status)
    print("Metrics:", service.world.snapshot()["metrics"])


if __name__ == "__main__":
    main()
