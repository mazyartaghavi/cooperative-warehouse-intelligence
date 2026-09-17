"""Read-only local model readiness checks; never download weights or claim quality."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

import httpx

from cwi.conversation.backends import OllamaBackend


def check_runtime(
    model: str | None, base_url: str = "http://localhost:11434", speech_model: Path | None = None
) -> dict[str, Any]:
    backend = OllamaBackend(model or "readiness-probe", base_url)
    language: dict[str, Any] = {"ready": False, "requested_model": model}
    try:
        with httpx.Client(timeout=3, trust_env=False) as client:
            response = client.get(backend.base_url + "/api/tags")
            response.raise_for_status()
        models = response.json()["models"]
        if not isinstance(models, list) or any(not isinstance(m, dict) for m in models):
            raise ValueError("Invalid model inventory")
        names = [m.get("name", m.get("model")) for m in models]
        if any(not isinstance(n, str) for n in names):
            raise ValueError("Invalid model name")
        selected = model if model and ":" in model else f"{model}:latest"
        match = next((m for m, n in zip(models, names, strict=True) if n == selected), None)
        language.update(
            ready=bool(model and match is not None),
            installed_models=names,
            model_digest=match.get("digest") if match else None,
            reason="Model is available" if match else "Select an installed model name",
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        language["reason"] = f"Local model inventory unavailable ({type(exc).__name__})"
    speech: dict[str, Any] = {"requested": speech_model is not None, "ready": False}
    if speech_model is not None:
        dependency = importlib.util.find_spec("faster_whisper") is not None
        weights = speech_model.is_dir() and (speech_model / "model.bin").is_file()
        speech.update(
            dependency_installed=dependency,
            weights_present=weights,
            ready=dependency and weights,
            reason="Readiness only; loading and inference still require evaluation",
        )
    return {
        "language": language,
        "speech": speech,
        "ready": language["ready"] and (speech_model is None or speech["ready"]),
        "scope": "Configuration and inventory checks only; not an inference or quality score",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=os.environ.get("CWI_OLLAMA_MODEL"))
    parser.add_argument(
        "--base-url", default=os.environ.get("CWI_OLLAMA_URL", "http://localhost:11434")
    )
    parser.add_argument("--speech-model", type=Path, default=os.environ.get("CWI_WHISPER_MODEL"))
    parser.add_argument("--output", type=Path, default=Path("outputs/runtime-readiness.json"))
    args = parser.parse_args()
    result = check_runtime(args.model, args.base_url, args.speech_model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ready"] else 2)


if __name__ == "__main__":
    main()
