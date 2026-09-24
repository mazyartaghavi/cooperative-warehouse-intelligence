"""Collect a small-model validation bundle without downloading models or uploading data."""

import argparse
import hashlib
import json
import os
import platform
import tempfile
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from cwi.conversation.backends import BaselineBackend, OllamaBackend, OllamaSettings
from cwi.evaluation.language import evaluate
from cwi.evaluation.runtime import check_runtime


def source_digest() -> str:
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def passed(result: dict[str, Any]) -> bool:
    return result["scenario_accuracy"] == 1 and all(
        question["source_present"] for question in result["knowledge"]
    )


def summarize_repetitions(
    results: list[dict[str, Any]], requested_repetitions: int
) -> dict[str, Any]:
    """Summarize complete runs without hiding run-level failures or variability."""
    if not results:
        raise ValueError("Provide at least one completed live evaluation")
    if requested_repetitions < len(results):
        raise ValueError("Requested repetitions cannot be smaller than completed runs")
    scenario_names = [row["name"] for row in results[0]["scenarios"]]
    question_names = [row["question"] for row in results[0]["knowledge"]]
    for result in results[1:]:
        if [row["name"] for row in result["scenarios"]] != scenario_names:
            raise ValueError("Live evaluation scenario sets differ between repetitions")
        if [row["question"] for row in result["knowledge"]] != question_names:
            raise ValueError("Live evaluation knowledge sets differ between repetitions")

    completed = len(results)
    return {
        "summary_version": 1,
        "requested_repetitions": requested_repetitions,
        "completed_repetitions": completed,
        "complete_run_pass_rate": sum(passed(result) for result in results) / completed,
        "all_completed_runs_passed": all(passed(result) for result in results),
        "scenarios": [
            {
                "name": name,
                "matched_repetitions": sum(
                    bool(result["scenarios"][index]["matched"]) for result in results
                ),
                "completed_repetitions": completed,
                "match_rate": sum(bool(result["scenarios"][index]["matched"]) for result in results)
                / completed,
            }
            for index, name in enumerate(scenario_names)
        ],
        "knowledge": [
            {
                "question": question,
                "source_present_repetitions": sum(
                    bool(result["knowledge"][index]["source_present"]) for result in results
                ),
                "completed_repetitions": completed,
                "source_present_rate": sum(
                    bool(result["knowledge"][index]["source_present"]) for result in results
                )
                / completed,
            }
            for index, question in enumerate(question_names)
        ],
        "scope": "Descriptive repeatability across complete runs with identical settings. "
        "These rates are not confidence intervals or evidence of broad language quality.",
    }


def collect(backend: OllamaBackend, output_dir: Path, *, repetitions: int = 1) -> tuple[Path, int]:
    """Use fresh reports per run; a passing baseline cannot replace failed inference."""
    if not 1 <= repetitions <= 10:
        raise ValueError("repetitions must be between 1 and 10")
    started = datetime.now(UTC)
    clock = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix=f"validation-{started:%Y%m%dT%H%M%SZ}-", dir=output_dir))
    metadata: dict[str, Any] = {
        "report_version": 3,
        "started_utc": started.isoformat(),
        "project_version": version("cooperative-warehouse-intelligence"),
        "python_source_sha256": source_digest(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "logical_cpu_count": os.cpu_count(),
        "model": backend.model,
        "requested_live_repetitions": repetitions,
        "inference_settings": backend.settings.model_dump(exclude_none=True),
        "scope": "Synthetic English fixtures and isolated simulation. No microphone, "
        "speech model, operational database, physical robot or human usability evaluation.",
    }
    reports: dict[str, Any] = {"environment.json": metadata}
    live_results: list[dict[str, Any]] = []
    code = 2
    try:
        print("Checking the local Ollama model inventory...", flush=True)
        readiness = check_runtime(backend.model, backend.base_url)
        reports["runtime-readiness.json"] = readiness
        print("Running the offline rules comparator...", flush=True)
        baseline = evaluate(BaselineBackend())
        baseline.update(status="evaluated", model=None)
        reports["language-baseline.json"] = baseline
        if not readiness["ready"]:
            reports["live-language.json"] = {"status": "blocked", "readiness": readiness}
            print(
                "Live inference is blocked: " + readiness["language"]["reason"] + ".\n"
                "Open the Ollama application, then check 'ollama list'. "
                "Install the selected model explicitly if it is missing.",
                flush=True,
            )
        else:
            print(
                f"Running actual local inference with {backend.model}. "
                "CPU responses can take several minutes across the full suite.",
                flush=True,
            )
            for repetition in range(1, repetitions + 1):
                if repetitions > 1:
                    print(f"Live repetition {repetition}/{repetitions}", flush=True)

                def show_progress(message: str, current: int = repetition) -> None:
                    print(f"Run {current}/{repetitions} - {message}", flush=True)

                live = evaluate(
                    backend,
                    progress=show_progress,
                )
                live.update(
                    status="evaluated",
                    model=backend.model,
                    readiness=readiness,
                    repetition=repetition,
                )
                live_results.append(live)
                filename = (
                    "live-language.json"
                    if repetition == 1
                    else f"live-language-run-{repetition:02d}.json"
                )
                reports[filename] = live
                matched = sum(case["matched"] for case in live["scenarios"])
                sources = sum(question["source_present"] for question in live["knowledge"])
                print(
                    f"Run {repetition}: scenarios matched {matched}/{live['scenario_count']}; "
                    f"source checks {sources}/{len(live['knowledge'])}.",
                    flush=True,
                )
            if repetitions > 1:
                reports["repeatability.json"] = summarize_repetitions(live_results, repetitions)
            code = 0 if passed(baseline) and all(passed(live) for live in live_results) else 1
    except KeyboardInterrupt:
        code = 130
        interrupted = {
            "status": "interrupted",
            "score": None,
            "completed_repetitions": len(live_results),
            "requested_repetitions": repetitions,
        }
        interrupted_filename = (
            "live-language.json"
            if not live_results
            else f"live-language-run-{len(live_results) + 1:02d}.json"
        )
        reports[interrupted_filename] = interrupted
        if repetitions > 1 and live_results:
            repeatability = summarize_repetitions(live_results, repetitions)
            repeatability["status"] = "interrupted"
            reports["repeatability.json"] = repeatability
        print("Validation interrupted; no complete live score is claimed.", flush=True)
    metadata.update(elapsed_seconds=time.perf_counter() - clock, exit_code=code)
    archive = run.with_suffix(".zip")
    with ZipFile(archive, "x", compression=ZIP_DEFLATED) as bundle:
        for filename, result in reports.items():
            path = run / filename
            path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            bundle.write(path, arcname=filename)
    print(f"Report saved: {archive.resolve()}", flush=True)
    print("Nothing was uploaded. Attach this ZIP when sharing the results.", flush=True)
    return archive, code


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen2.5:1.5b", help="Already-installed Ollama tag")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--context-tokens", type=int, default=4096)
    parser.add_argument("--output-tokens", type=int, default=512)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="Complete live-suite repetitions with identical settings (1-10)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    try:
        backend = OllamaBackend(
            args.model,
            args.base_url,
            capture_diagnostics=True,
            settings=OllamaSettings(
                timeout_seconds=args.timeout_seconds,
                context_tokens=args.context_tokens,
                output_tokens=args.output_tokens,
            ),
        )
    except ValueError as exc:
        parser.error(str(exc))
    if not 1 <= args.repetitions <= 10:
        parser.error("--repetitions must be between 1 and 10")
    _, code = collect(backend, args.output_dir, repetitions=args.repetitions)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
