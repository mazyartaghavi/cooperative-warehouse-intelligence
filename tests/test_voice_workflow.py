"""Explicit transcriber doubles verify orchestration, never speech-model quality."""

import json

import pytest

from cwi.conversation.backends import BaselineBackend
from cwi.evaluation.voice import evaluate_voice, load_voice_cases


def manifest(tmp_path, kind="synthetic"):
    (tmp_path / "request.wav").write_bytes(b"speech test double")
    task = {"tote_id": "T17", "destination": "P2", "priority": "normal"}
    payload = [
        {
            "identifier": "fixture",
            "recording_kind": kind,
            "condition": "test double",
            "turns": [
                {
                    "audio": "request.wav",
                    "reference": "Move T17 to P2",
                    "expected_status": "awaiting_confirmation",
                    "expected_task": task,
                },
                {"text": "confirm", "expected_status": "accepted", "expected_task": task},
            ],
            "expected_delivery": task,
        }
    ]
    path = tmp_path / "voice.json"
    path.write_text(json.dumps(payload))
    return path


class SpeechDouble:
    def __init__(self, text):
        self.text = text

    def transcribe(self, audio):
        assert audio == b"speech test double"
        return self.text


def test_recorded_turn_to_guarded_confirmation_and_delivery(tmp_path):
    result = evaluate_voice(SpeechDouble("Move T17 to P2"), BaselineBackend(), manifest(tmp_path))
    assert result["groups"]["synthetic"]["pass_rate"] == 1
    assert result["groups"]["human"]["pass_rate"] is None
    case = result["scenarios"][0]
    assert case["conversation"]["metrics"]["completed"] == 1
    assert case["transcriptions"][0]["wer"] == 0
    assert len(case["transcriptions"][0]["audio_sha256"]) == 64


def test_wrong_identifier_is_measured_and_never_confirmed(tmp_path):
    result = evaluate_voice(SpeechDouble("Move T23 to P2"), BaselineBackend(), manifest(tmp_path))
    case = result["scenarios"][0]
    assert not case["matched"]
    assert case["transcriptions"][0]["wer"] == 0.25
    assert len(case["conversation"]["turns"]) == 1
    assert case["conversation"]["metrics"]["completed"] == 0
    assert case["conversation"]["turns"][0]["reply"]["task"]["tote_id"] == "T23"


@pytest.mark.parametrize("transcript", ["", "...", "x" * 2001, None])
def test_failed_transcription_never_substitutes_reference_or_drops_case(tmp_path, transcript):
    result = evaluate_voice(
        SpeechDouble(transcript), BaselineBackend(), manifest(tmp_path, "human")
    )
    assert result["groups"]["human"]["scenarios"] == 1
    assert result["groups"]["human"]["transcription_failures"] == 1
    assert result["groups"]["human"]["pass_rate"] == 0
    assert result["scenarios"][0]["conversation"] is None


def test_transcription_exception_is_counted(tmp_path):
    class Unavailable:
        def transcribe(self, audio):
            raise RuntimeError("Decoder unavailable")

    result = evaluate_voice(Unavailable(), BaselineBackend(), manifest(tmp_path))
    assert result["groups"]["synthetic"]["transcription_failures"] == 1
    assert "Decoder unavailable" in result["scenarios"][0]["transcriptions"][0]["error"]


@pytest.mark.parametrize(
    "change",
    [
        {"audio": "../outside.wav"},
        {"reference": "..."},
        {"text": "Move T17 to P2"},
        {"audio": "missing.wav"},
        {"expected_status": "finished"},
    ],
)
def test_voice_manifest_rejects_ambiguous_and_invalid_inputs(tmp_path, change):
    path = manifest(tmp_path)
    raw = json.loads(path.read_text())
    raw[0]["turns"][0].update(change)
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        load_voice_cases(path)


def test_multiturn_clarification_can_mix_recorded_and_scripted_responses(tmp_path):
    path = manifest(tmp_path)
    raw = json.loads(path.read_text())
    raw[0]["turns"][0].update(
        reference="Move the blue tote to P2", expected_status="clarification", expected_task=None
    )
    raw[0]["turns"].insert(
        1,
        {
            "text": "T17",
            "expected_status": "awaiting_confirmation",
            "expected_task": raw[0]["expected_delivery"],
        },
    )
    path.write_text(json.dumps(raw))
    result = evaluate_voice(SpeechDouble("Move the blue tote to P2"), BaselineBackend(), path)
    assert result["scenarios"][0]["matched"]
    assert len(result["scenarios"][0]["conversation"]["turns"]) == 3
