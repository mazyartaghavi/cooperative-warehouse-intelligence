"""Local authenticated API. The configured token represents one demo operator."""

import logging
import os
import secrets
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import Field

from cwi.agents.service import ConversationService
from cwi.conversation.backends import BackendError, BaselineBackend, OllamaBackend
from cwi.conversation.knowledge import KnowledgeReply, answer_question
from cwi.conversation.models import JobControl, JobUpdate, Message, Reply, StrictModel
from cwi.retrieval.service import Retriever
from cwi.simulation.world import World
from cwi.speech.service import LocalWhisper, Transcriber
from cwi.state.store import Store
from cwi.state.warehouse import Operator

logger = logging.getLogger(__name__)


class Advance(StrictModel):
    ticks: int = Field(default=1, ge=1, le=500)


class Workload(StrictModel):
    busy: bool


class Obstacle(StrictModel):
    x: int
    y: int
    present: bool = True


def create_app(
    service: ConversationService, token: str, transcriber: Transcriber | None = None
) -> FastAPI:
    if len(token) < 16:
        raise ValueError("CWI_API_TOKEN must be at least 16 characters.")
    app = FastAPI(title="Cooperative Warehouse Intelligence", version="0.2.0")

    def authenticate(x_cwi_token: Annotated[str | None, Header()] = None) -> None:
        if x_cwi_token is None or not secrets.compare_digest(x_cwi_token, token):
            raise HTTPException(status_code=401, detail="Invalid operator token")

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return Path(__file__).with_name("dashboard.html").read_text()

    @app.post("/knowledge", dependencies=[Depends(authenticate)])
    def knowledge(body: Message) -> KnowledgeReply:
        if not body.text.strip():
            raise HTTPException(422, "Question cannot be blank")
        try:
            with service.lock:
                model = service.backend if isinstance(service.backend, OllamaBackend) else None
                return answer_question(body.text, service.retriever, model)
        except BackendError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.post("/speech/transcribe", dependencies=[Depends(authenticate)])
    async def transcribe(file: UploadFile) -> dict[str, str]:
        if transcriber is None:
            raise HTTPException(503, "Local speech model is not configured")
        from starlette.concurrency import run_in_threadpool

        try:
            audio = await file.read(10 * 1024 * 1024 + 1)
            if len(audio) > 10 * 1024 * 1024:
                raise HTTPException(413, "Audio exceeds 10 MiB")
            text = await run_in_threadpool(transcriber.transcribe, audio)
            return {"text": text}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, "Speech decoding failed; no task was executed") from exc
        finally:
            await file.close()

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "backend": service.backend.name,
            "robot_dispatch": service.world is not None,
            "speech": transcriber is not None,
        }

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
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/jobs/{job_id}", dependencies=[Depends(authenticate)])
    def job_status(job_id: str) -> JobUpdate:
        try:
            return service.job_update(job_id)
        except KeyError as exc:
            raise HTTPException(404, "Unknown job") from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/jobs/{job_id}/actions", dependencies=[Depends(authenticate)])
    def job_control(job_id: str, body: JobControl) -> JobUpdate:
        try:
            return service.control_job(job_id, body.action)
        except KeyError as exc:
            raise HTTPException(404, "Unknown job") from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/warehouse/operator-workload", dependencies=[Depends(authenticate)])
    def workload(body: Workload) -> dict[str, bool]:
        with service.lock:
            if service.world is None:
                raise HTTPException(409, "Simulation is disabled")
            previous = service.world.operator_busy
            service.world.operator_busy = body.busy
            try:
                service.persist()
            except Exception:
                service.world.operator_busy = previous
                raise
            return {"busy": body.busy}

    @app.get("/warehouse", dependencies=[Depends(authenticate)])
    def warehouse() -> dict[str, Any]:
        with service.lock:
            if service.world is None:
                raise HTTPException(409, "Simulation is disabled")
            return service.world.snapshot()

    @app.post("/warehouse/advance", dependencies=[Depends(authenticate)])
    def advance(body: Advance) -> dict[str, Any]:
        with service.lock:
            if service.world is None:
                raise HTTPException(409, "Simulation is disabled")
            previous = service.checkpoint()
            try:
                service.world.step(body.ticks)
                service.warehouse = service.world.warehouse
                service.persist()
                return service.world.snapshot()
            except Exception:
                service.restore(previous)
                raise

    @app.post("/warehouse/obstacles", dependencies=[Depends(authenticate)])
    def obstacle(body: Obstacle) -> dict[str, bool]:
        with service.lock:
            if service.world is None:
                raise HTTPException(409, "Simulation is disabled")
            previous = service.checkpoint()
            try:
                service.world.obstacle((body.x, body.y), body.present)
                service.persist()
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            except Exception:
                service.restore(previous)
                raise
            return {"updated": True}

    return app


def app_factory() -> FastAPI:
    backend_name = os.environ.get("CWI_BACKEND", "baseline")
    role = os.environ.get("CWI_OPERATOR_ROLE", "operator")
    if role not in {"operator", "supervisor"}:
        raise ValueError("CWI_OPERATOR_ROLE must be operator or supervisor.")
    operator = Operator(role="supervisor" if role == "supervisor" else "operator")
    if backend_name not in {"baseline", "ollama"}:
        raise ValueError("CWI_BACKEND must be baseline or ollama.")
    from cwi.conversation.backends import Backend

    backend: Backend = (
        BaselineBackend()
        if backend_name == "baseline"
        else OllamaBackend(
            os.environ.get("CWI_OLLAMA_MODEL", ""),
            os.environ.get("CWI_OLLAMA_URL", "http://localhost:11434"),
        )
    )
    token = os.environ.get("CWI_API_TOKEN", "")
    if len(token) < 16:
        raise ValueError("CWI_API_TOKEN must be at least 16 characters.")
    store = Store(os.environ.get("CWI_DB", "data/local/cwi.db"))
    speech_path = os.environ.get("CWI_WHISPER_MODEL", "")
    speech = LocalWhisper(speech_path) if speech_path else None
    return create_app(
        ConversationService(
            backend,
            operator,
            retriever=Retriever(store.procedures()),
            world=World(os.environ.get("CWI_ASSISTANCE_POLICY", "inspect_when_possible")),
            store=store,
        ),
        token,
        speech,
    )
