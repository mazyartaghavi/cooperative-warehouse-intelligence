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


def collect(backend: OllamaBackend, output_dir: Path) -> tuple[Path, int]:
    """Use fresh reports per run; a passing baseline cannot replace failed inference."""
    started = datetime.now(UTC)
    clock = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix=f"validation-{started:%Y%m%dT%H%M%SZ}-", dir=output_dir))
    metadata: dict[str, Any] = {
        "report_version": 2,
        "started_utc": started.isoformat(),
        "project_version": version("cooperative-warehouse-intelligence"),
        "python_source_sha256": source_digest(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "logical_cpu_count": os.cpu_count(),
        "model": backend.model,
        "inference_settings": backend.settings.model_dump(exclude_none=True),
        "scope": "Synthetic English fixtures and isolated simulation. No microphone, "
        "speech model, operational database, physical robot or human usability evaluation.",
    }
    reports: dict[str, Any] = {"environment.json": metadata}
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
            live = evaluate(backend, progress=lambda message: print(message, flush=True))
            live.update(status="evaluated", model=backend.model, readiness=readiness)
            reports["live-language.json"] = live
            code = 0 if passed(baseline) and passed(live) else 1
            matched = sum(case["matched"] for case in live["scenarios"])
            sources = sum(question["source_present"] for question in live["knowledge"])
            print(
                f"Live scenarios matched: {matched}/{live['scenario_count']}; "
                f"source checks: {sources}/{len(live['knowledge'])}.",
                flush=True,
            )
    except KeyboardInterrupt:
        code = 130
        reports["live-language.json"] = {"status": "interrupted", "score": None}
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
    _, code = collect(backend, args.output_dir)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
