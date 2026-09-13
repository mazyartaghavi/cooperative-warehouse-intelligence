"""Deterministic offline example, deliberately labeled as a rules baseline."""

from cwi.agents.service import ConversationService
from cwi.conversation.backends import BaselineBackend


def main() -> None:
    service = ConversationService(BaselineBackend())
    identifier = service.new_session()
    print("Cooperative Warehouse Intelligence — OFFLINE RULES BASELINE (no LLM)")
    for text in ["Move the blue tote to P2", "T17", "confirm"]:
        response = service.reply(identifier, text)
        print(f"\nOperator: {text}\nCoordinator [{response.status}]: {response.message}")
        print("Evidence: " + ", ".join(c.document_id + "@" + c.version for c in response.citations))


if __name__ == "__main__":
    main()
