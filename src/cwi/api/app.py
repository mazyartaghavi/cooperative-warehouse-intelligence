"""Local authenticated API. The configured token represents one demo operator."""

import logging
import os
import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException

from cwi.agents.service import ConversationService
from cwi.conversation.backends import BackendError, BaselineBackend, OllamaBackend
from cwi.conversation.models import Message, Reply
from cwi.state.warehouse import Operator

logger = logging.getLogger(__name__)


def create_app(service: ConversationService, token: str) -> FastAPI:
    if len(token) < 16:
        raise ValueError("CWI_API_TOKEN must be at least 16 characters.")
    app = FastAPI(title="Cooperative Warehouse Intelligence", version="0.1.0")

    def authenticate(x_cwi_token: Annotated[str | None, Header()] = None) -> None:
        if x_cwi_token is None or not secrets.compare_digest(x_cwi_token, token):
            raise HTTPException(status_code=401, detail="Invalid operator token")

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {"status": "ok", "backend": service.backend.name, "robot_dispatch": False}

    @app.post("/sessions", dependencies=[Depends(authenticate)], status_code=201)
    def new_session() -> dict[str, str]:
        try:
            return {"session_id": service.new_session()}
        except ValueError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc

    @app.post("/sessions/{session_id}/messages", dependencies=[Depends(authenticate)])
    def message(session_id: str, body: Message) -> Reply:
        try:
            return service.reply(session_id, body.text)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown session") from exc
        except BackendError as exc:
            # Log the failure class, not raw operator text or model responses.
            logger.warning("Intent backend failed: %s", type(exc).__name__)
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


def app_factory() -> FastAPI:
    backend_name = os.environ.get("CWI_BACKEND", "baseline")
    role = os.environ.get("CWI_OPERATOR_ROLE", "operator")
    if role not in {"operator", "supervisor"}:
        raise ValueError("CWI_OPERATOR_ROLE must be operator or supervisor.")
    operator = Operator(role="supervisor" if role == "supervisor" else "operator")
    if backend_name == "baseline":
        return create_app(
            ConversationService(BaselineBackend(), operator), os.environ.get("CWI_API_TOKEN", "")
        )
    if backend_name != "ollama":
        raise ValueError("CWI_BACKEND must be baseline or ollama.")
    model = OllamaBackend(
        os.environ.get("CWI_OLLAMA_MODEL", ""),
        os.environ.get("CWI_OLLAMA_URL", "http://localhost:11434"),
    )
    return create_app(ConversationService(model, operator), os.environ.get("CWI_API_TOKEN", ""))
