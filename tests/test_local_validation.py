import json
from zipfile import ZipFile

import httpx
import pytest

from cwi.conversation.backends import BackendError, BaselineBackend, OllamaBackend, OllamaSettings
from cwi.conversation.knowledge import answer_question
from cwi.evaluation.local_validation import collect, summarize_repetitions
from cwi.retrieval.service import Retriever


def install_transport(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)
    )


def profile():
    return OllamaSettings(timeout_seconds=180, context_tokens=4096, output_tokens=512)


def test_small_model_limits_apply_to_both_generation_paths(monkeypatch):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        assert body["options"] == {"temperature": 0, "num_ctx": 4096, "num_predict": 512}
        assert request.extensions["timeout"]["read"] == 180
        calls.append(body["format"]["title"])
        content = (
            {"action": "transport", "tote_id": "T17", "destination": "P2"}
            if calls[-1] == "Intent"
            else {"answer": "Only supervisors.", "document_ids": ["PRIORITY"]}
        )
        return httpx.Response(200, json={"message": {"content": json.dumps(content)}})

    install_transport(monkeypatch, handler)
    backend = OllamaBackend("test-double", settings=profile())
    assert backend.extract(["Move T17 to P2"], []).tote_id == "T17"
    assert answer_question("urgent priority", Retriever(), backend).mode == "generated"
    assert calls == ["Intent", "Answer"]


def test_application_profile_loads_environment_and_explicit_settings_take_priority(monkeypatch):
    monkeypatch.setenv("CWI_OLLAMA_TIMEOUT_SECONDS", "180")
    monkeypatch.setenv("CWI_OLLAMA_CONTEXT_TOKENS", "4096")
    monkeypatch.setenv("CWI_OLLAMA_OUTPUT_TOKENS", "512")
    assert OllamaBackend("fixture").settings == profile()
    explicit = OllamaSettings(timeout_seconds=60)
    assert OllamaBackend("fixture", settings=explicit).settings == explicit
    monkeypatch.setenv("CWI_OLLAMA_TIMEOUT_SECONDS", "nan")
    with pytest.raises(ValueError):
        OllamaBackend("fixture")


@pytest.mark.parametrize(
    "settings",
    [
        {"timeout_seconds": 0},
        {"timeout_seconds": float("inf")},
        {"context_tokens": 32},
        {"context_tokens": 32769},
        {"output_tokens": -1},
        {"output_tokens": 4097},
    ],
)
def test_invalid_resource_limits_are_rejected(settings):
    with pytest.raises(ValueError):
        OllamaSettings(**settings)


def test_truncated_generation_still_fails_contract(monkeypatch):
    install_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200, json={"message": {"content": '{"action":"transport"'}, "done_reason": "length"}
        ),
    )
    with pytest.raises(BackendError):
        OllamaBackend("fixture", settings=profile()).extract(["Move T17 to P2"], [])


def read_bundle(archive):
    with ZipFile(archive) as bundle:
        return {name: json.loads(bundle.read(name)) for name in bundle.namelist()}


def test_blocked_bundle_does_not_infer_or_include_unrelated_files(tmp_path, monkeypatch):
    def handler(request):
        assert request.method == "GET" and request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": []})

    install_transport(monkeypatch, handler)
    (tmp_path / "private.json").write_text('{"secret":"excluded"}')
    backend = OllamaBackend("missing", settings=profile())
    first, code = collect(backend, tmp_path)
    original = first.read_bytes()
    second, _ = collect(backend, tmp_path)
    assert code == 2 and first != second and first.read_bytes() == original
    report = read_bundle(first)
    assert set(report) == {
        "environment.json",
        "runtime-readiness.json",
        "language-baseline.json",
        "live-language.json",
    }
    assert report["live-language.json"]["status"] == "blocked"
    assert "scenario_accuracy" not in report["live-language.json"]
    assert report["language-baseline.json"]["scenario_accuracy"] == 1
    assert report["environment.json"]["inference_settings"] == profile().model_dump()


def test_inference_failure_cannot_be_replaced_by_passing_baseline(tmp_path, monkeypatch):
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": "fixture:latest", "digest": "test-only"}]}
            )
        return httpx.Response(503)

    install_transport(monkeypatch, handler)
    archive, code = collect(OllamaBackend("fixture", settings=profile()), tmp_path)
    report = read_bundle(archive)
    assert code == 1
    assert report["language-baseline.json"]["scenario_accuracy"] == 1
    live = report["live-language.json"]
    assert live["backend"] == "ollama" and live["status"] == "evaluated"
    assert live["scenario_accuracy"] < 1
    assert live["readiness"]["language"]["model_digest"] == "test-only"
    assert "error" in live["scenarios"][0]["turns"][0]
    assert live["scenarios"][0]["metrics"]["completed"] == 0


def test_successful_bundle_with_explicit_http_model_double(tmp_path, monkeypatch):
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": "test-double:latest", "digest": "not-a-model"}]}
            )
        body = json.loads(request.content)
        context = json.loads(body["messages"][1]["content"])
        if body["format"]["title"] == "Intent":
            content = BaselineBackend().extract(context["operator_turns"], []).model_dump()
        else:
            content = {
                "answer": "Test-only source IDs, not an actual generated answer.",
                "document_ids": [evidence["document_id"] for evidence in context["evidence"]],
            }
        return httpx.Response(200, json={"message": {"content": json.dumps(content)}})

    install_transport(monkeypatch, handler)
    archive, code = collect(OllamaBackend("test-double", settings=profile()), tmp_path)
    report = read_bundle(archive)
    assert code == 0
    live = report["live-language.json"]
    assert live["model"] == "test-double" and live["scenario_accuracy"] == 1
    assert live["inference_settings"] == report["environment.json"]["inference_settings"]
    assert sum(case["metrics"]["completed"] for case in live["scenarios"]) == 6


def test_repeated_runs_preserve_each_result_and_report_stability(tmp_path, monkeypatch):
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": "test-double:latest", "digest": "repeat"}]}
            )
        body = json.loads(request.content)
        context = json.loads(body["messages"][1]["content"])
        if body["format"]["title"] == "Intent":
            content = BaselineBackend().extract(context["operator_turns"], []).model_dump()
        else:
            content = {
                "answer": "Test-only answer.",
                "document_ids": [item["document_id"] for item in context["evidence"]],
            }
        return httpx.Response(200, json={"message": {"content": json.dumps(content)}})

    install_transport(monkeypatch, handler)
    archive, code = collect(
        OllamaBackend("test-double", settings=profile()), tmp_path, repetitions=2
    )
    report = read_bundle(archive)
    assert code == 0
    assert report["environment.json"]["requested_live_repetitions"] == 2
    assert report["live-language.json"]["repetition"] == 1
    assert report["live-language-run-02.json"]["repetition"] == 2
    summary = report["repeatability.json"]
    assert summary["completed_repetitions"] == 2
    assert summary["complete_run_pass_rate"] == 1
    assert all(row["match_rate"] == 1 for row in summary["scenarios"])
    assert all(row["source_present_rate"] == 1 for row in summary["knowledge"])


def test_repeatability_summary_rejects_inconsistent_or_empty_runs():
    with pytest.raises(ValueError, match="at least one"):
        summarize_repetitions([], 2)
    first = {
        "scenario_accuracy": 1,
        "scenarios": [{"name": "one", "matched": True}],
        "knowledge": [{"question": "source?", "source_present": True}],
    }
    second = {
        "scenario_accuracy": 0,
        "scenarios": [{"name": "different", "matched": False}],
        "knowledge": [{"question": "source?", "source_present": False}],
    }
    with pytest.raises(ValueError, match="scenario sets differ"):
        summarize_repetitions([first, second], 2)


@pytest.mark.parametrize("repetitions", [0, 11])
def test_repetition_bounds_are_enforced(tmp_path, repetitions):
    with pytest.raises(ValueError, match="between 1 and 10"):
        collect(OllamaBackend("fixture", settings=profile()), tmp_path, repetitions=repetitions)


def test_interrupted_run_preserves_diagnostics_without_quality_score(tmp_path, monkeypatch):
    def handler(request):
        raise KeyboardInterrupt

    install_transport(monkeypatch, handler)
    archive, code = collect(OllamaBackend("fixture", settings=profile()), tmp_path)
    report = read_bundle(archive)
    assert code == 130
    assert report["live-language.json"] == {
        "status": "interrupted",
        "score": None,
        "completed_repetitions": 0,
        "requested_repetitions": 1,
    }
