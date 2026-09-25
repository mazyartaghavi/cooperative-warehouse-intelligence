import json
import sys

import httpx
import pytest

from cwi.conversation.backends import BackendError, BaselineBackend
from cwi.conversation.models import Intent
from cwi.evaluation.language import (
    SCENARIOS,
    Scenario,
    Turn,
    evaluate,
    load_scenarios,
    manifest_digest,
)
from cwi.evaluation.language import (
    main as language_main,
)
from cwi.evaluation.runtime import check_runtime
from cwi.evaluation.speech import edit_distance, evaluate_speech, load_cases, words


def transport(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)
    )


def test_readiness_records_exact_installed_model_and_digest(monkeypatch):
    transport(
        monkeypatch,
        lambda request: httpx.Response(
            200, json={"models": [{"name": "demo:latest", "digest": "fixture-digest"}]}
        ),
    )
    result = check_runtime("demo")
    assert result["ready"]
    assert result["language"]["model_digest"] == "fixture-digest"
    assert not check_runtime("demo:other")["ready"]
    assert not check_runtime(None)["ready"]


@pytest.mark.parametrize(
    "payload", [{}, {"models": None}, {"models": [None]}, {"models": [{"name": 42}]}]
)
def test_malformed_inventory_is_not_ready(monkeypatch, payload):
    transport(monkeypatch, lambda request: httpx.Response(200, json=payload))
    assert not check_runtime("demo")["ready"]


def test_unavailable_runtime_cannot_be_reported_ready(monkeypatch):
    transport(monkeypatch, lambda request: httpx.Response(503))
    assert not check_runtime("demo")["ready"]
    with pytest.raises(ValueError, match="local"):
        check_runtime("demo", "http://example.com")


def test_conversation_and_delivery_suite_includes_bring_paraphrase():
    result = evaluate(BaselineBackend())
    assert result["scenario_count"] == 12
    assert all(c["matched"] for c in result["scenarios"])
    assert sum(c["metrics"]["completed"] for c in result["scenarios"]) == 6
    assert all(q["source_present"] for q in result["knowledge"])


def test_wrong_task_is_never_confirmed_by_evaluator():
    class WrongTask:
        name = "test double"

        def extract(self, turns, evidence):
            return Intent(action="transport", tote_id="T17", destination="P1")

    expected = ("T17", "P2", "normal")
    case = Scenario(
        "wrong",
        (
            Turn("Move T17 from P1 to P2", "awaiting_confirmation", expected),
            Turn("confirm", "accepted", expected),
        ),
        expected,
    )
    result = evaluate(WrongTask(), (case,))
    assert not result["scenarios"][0]["matched"]
    assert len(result["scenarios"][0]["turns"]) == 1
    assert result["scenarios"][0]["metrics"]["completed"] == 0


def test_model_failures_stay_in_denominator():
    class Unavailable:
        name = "test double"

        def extract(self, turns, evidence):
            raise BackendError("test outage")

    result = evaluate(
        Unavailable(), tuple(c for c in SCENARIOS if c.name != "unprompted_confirmation")
    )
    assert result["scenario_accuracy"] == 0
    assert result["scenario_count"] == 11
    assert all("error" in c["turns"][0] for c in result["scenarios"])
    with pytest.raises(ValueError, match="at least one"):
        evaluate(BaselineBackend(), ())


def language_manifest(tmp_path, rows):
    manifest = tmp_path / "heldout.json"
    manifest.write_text(json.dumps(rows), encoding="utf-8")
    return manifest


def test_private_language_manifest_runs_through_guarded_delivery(tmp_path):
    task = {"tote_id": "T17", "destination": "P2", "priority": "normal"}
    manifest = language_manifest(
        tmp_path,
        [
            {
                "name": "private-case-01",
                "turns": [
                    {
                        "text": "Move T17 to P2",
                        "expected_status": "awaiting_confirmation",
                        "expected_task": task,
                    },
                    {"text": "confirm", "expected_status": "accepted", "expected_task": task},
                ],
                "expected_delivery": task,
            }
        ],
    )
    scenarios = load_scenarios(manifest)
    result = evaluate(BaselineBackend(), scenarios, include_knowledge=False)
    assert result["scenario_count"] == 1
    assert result["scenarios"][0]["matched"]
    assert result["scenarios"][0]["metrics"]["completed"] == 1


def test_language_cli_records_path_independent_manifest_provenance(tmp_path, monkeypatch):
    manifest = language_manifest(
        tmp_path,
        [
            {
                "name": "private-cancel",
                "turns": [{"text": "cancel", "expected_status": "cancelled"}],
            }
        ],
    )
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cwi-evaluate-llm",
            "--baseline",
            "--scenario-manifest",
            str(manifest),
            "--output",
            str(output),
        ],
    )
    with pytest.raises(SystemExit) as stopped:
        language_main()
    assert stopped.value.code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["scenario_manifest"] == {
        "sha256": manifest_digest(manifest),
        "scenario_count": 1,
    }
    assert str(manifest) not in output.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "rows, message",
    [
        (
            [
                {
                    "name": "duplicate",
                    "turns": [{"text": "confirm", "expected_status": "cancelled"}],
                },
                {
                    "name": "duplicate",
                    "turns": [{"text": "confirm", "expected_status": "cancelled"}],
                },
            ],
            "unique",
        ),
        (
            [
                {
                    "name": "missing-task",
                    "turns": [{"text": "confirm", "expected_status": "accepted"}],
                }
            ],
            "expected task",
        ),
        (
            [
                {
                    "name": "unknown-field",
                    "turns": [{"text": "confirm", "expected_status": "cancelled"}],
                    "secret": "not allowed",
                }
            ],
            "Extra inputs",
        ),
    ],
)
def test_language_manifest_rejects_invalid_cases(tmp_path, rows, message):
    with pytest.raises(ValueError, match=message):
        load_scenarios(language_manifest(tmp_path, rows))


def test_wer_counts_insertions_and_preserves_tote_ids():
    assert edit_distance(words("Move T17 to P2"), words("move T23 to P2!")) == 1
    assert edit_distance(words("go"), words("please now move there")) == 4
    assert words("T17") != words("T seventeen")


def corpus(tmp_path):
    rows = []
    for name, kind in [("ok", "human"), ("fail", "human"), ("wrong", "synthetic")]:
        (tmp_path / f"{name}.wav").write_bytes(name.encode())
        rows.append(
            {
                "identifier": name,
                "audio": f"{name}.wav",
                "reference": "Move T17 to P2",
                "recording_kind": kind,
                "condition": "test double",
            }
        )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(rows))
    return manifest


def test_speech_failures_and_synthetic_audio_are_not_hidden(tmp_path):
    class FakeTranscriber:
        def transcribe(self, audio):
            if audio == b"fail":
                raise ValueError("fixture error")
            return "Move T23 to P2" if audio == b"wrong" else "move T17 to P2!"

    result = evaluate_speech(FakeTranscriber(), corpus(tmp_path))
    assert result["groups"]["human"]["errors"] == 1
    assert result["groups"]["human"]["exact_match_rate_all_cases"] == 0.5
    assert result["groups"]["human"]["wer_on_successful"] == 0
    assert result["groups"]["synthetic"]["wer_on_successful"] == 0.25


@pytest.mark.parametrize(
    "change",
    [
        {"audio": "../outside.wav"},
        {"reference": "..."},
        {"audio": "missing.wav"},
        {"recording_kind": "unknown"},
    ],
)
def test_speech_manifest_rejects_invalid_or_outside_audio(tmp_path, change):
    manifest = corpus(tmp_path)
    rows = json.loads(manifest.read_text())
    rows[0].update(change)
    manifest.write_text(json.dumps(rows))
    with pytest.raises(ValueError):
        load_cases(manifest)
