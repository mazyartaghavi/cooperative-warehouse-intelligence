"""Explicit agent graph: retrieve trusted evidence, propose intent, validate externally."""

from typing import TypedDict, cast

from langgraph.graph import END, START, StateGraph

from cwi.conversation.backends import Backend, BackendError, BaselineBackend
from cwi.conversation.models import Citation, Intent
from cwi.policy.validation import Decision, validate
from cwi.retrieval.service import Retriever
from cwi.state.warehouse import Operator, Warehouse


class State(TypedDict, total=False):
    turns: list[str]
    warehouse: Warehouse
    evidence: list[Citation]
    intent: Intent
    decision: Decision
    trace: list[str]


class Workflow:
    def __init__(self, backend: Backend, retriever: Retriever, operator: Operator) -> None:
        def retrieve(state: State) -> State:
            evidence = retriever.search(" ".join(state["turns"]))
            evidence.append(
                Citation(
                    document_id="OBSERVATION",
                    version="current",
                    title="Observed inventory",
                    excerpt=str(
                        [
                            {
                                "id": t.identifier,
                                "color": t.color,
                                "location": t.source,
                                "weight_kg": t.weight_kg,
                            }
                            for t in state["warehouse"].totes
                        ]
                    ),
                )
            )
            return {"evidence": evidence, "trace": ["retrieve_procedures_and_observations"]}

        def extract(state: State) -> State:
            intent = backend.extract(state["turns"], state["evidence"])
            try:
                if BaselineBackend().extract([state["turns"][-1]], []).disable_safety:
                    intent.disable_safety = True
            except BackendError:
                pass
            return {"intent": intent, "trace": state["trace"] + ["extract_intent"]}

        def check(state: State) -> State:
            decision = validate(state["intent"], state["turns"], state["warehouse"], operator)
            evidence = {c.document_id: c for c in state["evidence"]}
            evidence[decision.document] = retriever.required(decision.document)
            return {
                "decision": decision,
                "evidence": list(evidence.values()),
                "trace": state["trace"] + ["validate_policy"],
            }

        graph = StateGraph(State)
        graph.add_node("retrieve", retrieve)
        graph.add_node("extract", extract)
        graph.add_node("validate", check)
        graph.add_edge(START, "retrieve")
        graph.add_edge("retrieve", "extract")
        graph.add_edge("extract", "validate")
        graph.add_edge("validate", END)
        self.graph = graph.compile()

    def run(self, turns: list[str], warehouse: Warehouse) -> State:
        return cast(
            State,
            self.graph.invoke(
                {"turns": turns, "warehouse": warehouse}, config={"recursion_limit": 8}
            ),
        )
