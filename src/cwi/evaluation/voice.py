"""Recorded speech through guarded conversation to delivery in isolated simulation."""

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from cwi.conversation.backends import Backend, BaselineBackend, OllamaBackend
from cwi.conversation.models import StrictModel
from cwi.evaluation.language import Scenario, Turn, evaluate
from cwi.evaluation.runtime import check_runtime
from cwi.evaluation.speech import audio_path, edit_distance, words
from cwi.speech.service import LocalWhisper, Transcriber


class ExpectedTask(StrictModel):
    tote_id: str
    destination: str
    priority: Literal["normal", "urgent"] = "normal"

    def key(self) -> tuple[str, str, str]:
        return self.tote_id, self.destination, self.priority


class VoiceTurn(StrictModel):
    audio: str | None = None
    reference: str | None = None
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    expected_status: Literal[
        "clarification", "awaiting_confirmation", "accepted", "rejected", "cancelled"
    ]
    expected_task: ExpectedTask | None = None

    @model_validator(mode="after")
    def source(self) -> Self:
        if (self.audio is None) == (self.text is None):
            raise ValueError("Provide exactly one audio file or scripted text per turn")
        if self.audio is not None:
            if not self.reference or not words(self.reference) or len(self.reference) > 2000:
                raise ValueError(
                    "Each recording needs a nonempty reference of at most 2000 characters"
                )
        elif self.reference is not None:
            raise ValueError("Only recorded turns have transcription references")
        return self


class VoiceScenario(StrictModel):
    identifier: str = Field(min_length=1, max_length=100)
    recording_kind: Literal["human", "synthetic"]
    condition: str = Field(min_length=1, max_length=100)
    role: Literal["operator", "supervisor"] = "operator"
    turns: list[VoiceTurn] = Field(min_length=1, max_length=20)
    expected_delivery: ExpectedTask | None = None


def load_voice_cases(manifest: Path) -> list[VoiceScenario]:
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not 1 <= len(raw) <= 100:
        raise ValueError("Voice manifest must contain 1-100 scenarios")
    cases = [VoiceScenario.model_validate(row) for row in raw]
    if len({c.identifier for c in cases}) != len(cases):
        raise ValueError("Voice scenario identifiers must be unique")
    for case in cases:
        if not any(t.audio is not None for t in case.turns):
            raise ValueError("Every voice scenario must contain at least one recording")
        for turn in case.turns:
            if turn.audio is not None:
                audio_path(manifest.parent, turn.audio)
    return cases


def evaluate_voice(transcriber: Transcriber, backend: Backend, manifest: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for case in load_voice_cases(manifest):
        row: dict[str, Any] = {
            "identifier": case.identifier,
            "recording_kind": case.recording_kind,
            "condition": case.condition,
            "matched": False,
            "transcriptions": [],
            "conversation": None,
        }
        turns = []
        for turn in case.turns:
            text = turn.text
            if turn.audio is not None:
                audio = audio_path(manifest.parent, turn.audio).read_bytes()
                speech: dict[str, Any] = {
                    "audio": turn.audio,
                    "reference": turn.reference,
                    "audio_sha256": hashlib.sha256(audio).hexdigest(),
                }
                start = time.perf_counter()
                try:
                    text = transcriber.transcribe(audio)
                    if not isinstance(text, str) or not words(text) or len(text) > 2000:
                        raise ValueError("No usable transcript or transcript too long")
                    reference_words = words(turn.reference or "")
                    speech.update(
                        hypothesis=text,
                        wer=edit_distance(reference_words, words(text)) / len(reference_words),
                    )
                except Exception as exc:
                    speech["error"] = f"{type(exc).__name__}: {exc}"
                speech["latency_s"] = time.perf_counter() - start
                row["transcriptions"].append(speech)
                if "error" in speech:
                    break  # Never feed a partial failed conversation to the task runner.
            assert text is not None
            turns.append(
                Turn(
                    text,
                    turn.expected_status,
                    turn.expected_task.key() if turn.expected_task else None,
                )
            )
        if len(turns) == len(case.turns):
            scenario = Scenario(
                case.identifier,
                tuple(turns),
                case.expected_delivery.key() if case.expected_delivery else None,
                case.role,
            )
            result = evaluate(backend, (scenario,), include_knowledge=False)["scenarios"][0]
            row.update(conversation=result, matched=result["matched"])
        rows.append(row)
    groups = {}
    for kind in ("human", "synthetic"):
        subset = [r for r in rows if r["recording_kind"] == kind]
        groups[kind] = {
            "scenarios": len(subset),
            "passed": sum(r["matched"] for r in subset),
            "pass_rate": sum(r["matched"] for r in subset) / len(subset) if subset else None,
            "transcription_failures": sum(
                any("error" in t for t in r["transcriptions"]) for r in subset
            ),
        }
    return {
        "backend": backend.name,
        "inference_settings": (
            backend.settings.model_dump(exclude_none=True)
            if isinstance(backend, OllamaBackend)
            else None
        ),
        "scenarios": rows,
        "groups": groups,
        "scope": "Recorded speech and scripted confirmations in isolated simulation only. "
        "A wrong proposal stops the case before confirmation. No hardware commands are sent. "
        "References are used for scoring, never as substitute transcripts. Human and synthetic "
        "recordings remain separate; this is not an operator usability study.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speech-model", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--model", help="Installed local Ollama model")
    selection.add_argument("--baseline", action="store_true")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--output", type=Path, default=Path("outputs/live-voice-workflow.json"))
    args = parser.parse_args()
    load_voice_cases(args.manifest)
    result: dict[str, Any]
    readiness = check_runtime(args.model, args.base_url, args.speech_model) if args.model else None
    try:
        if readiness is not None and not readiness["ready"]:
            raise RuntimeError("Requested local model runtime is unavailable")
        transcriber = LocalWhisper(str(args.speech_model))
    except (ImportError, ValueError, OSError, RuntimeError) as exc:
        result = {"status": "blocked", "reason": str(exc), "readiness": readiness}
        code = 2
    else:
        backend: Backend = (
            OllamaBackend(args.model, args.base_url) if args.model else BaselineBackend()
        )
        result = evaluate_voice(transcriber, backend, args.manifest)
        result.update(
            status="evaluated",
            model=args.model,
            readiness=readiness,
            speech_model_path=str(args.speech_model),
        )
        code = 0 if all(r["matched"] for r in result["scenarios"]) else 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
