"""Evaluate real local transcription against an explicitly supplied audio corpus."""

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from cwi.conversation.models import StrictModel
from cwi.speech.service import LocalWhisper, Transcriber


class AudioCase(StrictModel):
    identifier: str = Field(min_length=1)
    audio: str = Field(min_length=1)
    reference: str = Field(min_length=1, max_length=2000)
    recording_kind: Literal["human", "synthetic"]
    condition: str = Field(min_length=1, max_length=100)


def load_cases(manifest: Path) -> list[AudioCase]:
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not 1 <= len(raw) <= 1000:
        raise ValueError("Manifest must contain 1–1000 audio cases")
    cases = [AudioCase.model_validate(row) for row in raw]
    if len({c.identifier for c in cases}) != len(cases):
        raise ValueError("Audio case identifiers must be unique")
    root = manifest.resolve().parent
    for case in cases:
        path = (root / case.audio).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Audio must be inside the manifest directory")
        if path.suffix.lower() not in {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}:
            raise ValueError("Unsupported audio file extension")
        if not path.is_file() or not 0 < path.stat().st_size <= 10 * 1024 * 1024:
            raise ValueError("Each audio file must exist and contain 1 byte to 10 MiB")
        if not words(case.reference):
            raise ValueError("Reference must contain at least one word")
    return cases


def words(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold())


def edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for i, ref in enumerate(reference, 1):
        current = [i]
        for j, hyp in enumerate(hypothesis, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (ref != hyp)))
        previous = current
    return previous[-1]


def evaluate_speech(transcriber: Transcriber, manifest: Path) -> dict[str, Any]:
    rows = []
    for case in load_cases(manifest):
        audio = (manifest.resolve().parent / case.audio).read_bytes()
        row: dict[str, Any] = {
            **case.model_dump(),
            "audio_sha256": hashlib.sha256(audio).hexdigest(),
        }
        start = time.perf_counter()
        try:
            hypothesis = transcriber.transcribe(audio)
            reference_words, hypothesis_words = words(case.reference), words(hypothesis)
            if not hypothesis_words:
                raise ValueError("Transcriber returned no words")
            errors = edit_distance(reference_words, hypothesis_words)
            row.update(
                hypothesis=hypothesis,
                word_errors=errors,
                reference_words=len(reference_words),
                wer=errors / len(reference_words),
                exact_transcript=reference_words == hypothesis_words,
            )
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        row["latency_s"] = time.perf_counter() - start
        rows.append(row)
    groups = {}
    for kind in ("human", "synthetic"):
        subset = [r for r in rows if r["recording_kind"] == kind]
        successful = [r for r in subset if "error" not in r]
        total_words = sum(r["reference_words"] for r in successful)
        groups[kind] = {
            "cases": len(subset),
            "successful": len(successful),
            "errors": len(subset) - len(successful),
            "wer_on_successful": sum(r["word_errors"] for r in successful) / total_words
            if total_words
            else None,
            "exact_match_rate_all_cases": sum(r["exact_transcript"] for r in successful)
            / len(subset)
            if subset
            else None,
        }
    return {
        "cases": rows,
        "groups": groups,
        "scope": "Local speech recognition only; no commands are dispatched. WER is micro-averaged "
        "over successful files, with failures counted separately. Case and punctuation "
        "are normalized; spoken numbers and tote IDs are not rewritten. "
        "Synthetic audio does not establish human speech quality.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("outputs/live-speech.json"))
    args = parser.parse_args()
    load_cases(args.manifest)
    result = evaluate_speech(LocalWhisper(str(args.model_path)), args.manifest)
    result["model_path"] = str(args.model_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["groups"], indent=2))
    raise SystemExit(1 if any("error" in row for row in result["cases"]) else 0)


if __name__ == "__main__":
    main()
