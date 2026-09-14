"""Optional local transcription; audio is untrusted input to the normal conversation."""

import importlib
import os
import tempfile
import threading
from pathlib import Path
from typing import Protocol


class Transcriber(Protocol):
    def transcribe(self, audio: bytes) -> str: ...


class LocalWhisper:
    def __init__(self, model_path: str) -> None:
        if not Path(model_path).is_dir():
            raise ValueError("CWI_WHISPER_MODEL must point to an existing local model directory.")
        module = importlib.import_module("faster_whisper")
        self.model = module.WhisperModel(
            model_path, device="cpu", compute_type="int8", local_files_only=True
        )
        self.lock = threading.Lock()

    def transcribe(self, audio: bytes) -> str:
        if not audio or len(audio) > 10 * 1024 * 1024:
            raise ValueError("Audio must be nonempty and at most 10 MiB.")
        path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as file:
                path = file.name
                file.write(audio)
            with self.lock:
                segments, info = self.model.transcribe(path, beam_size=1, vad_filter=True)
                if info.duration > 60:
                    raise ValueError("Record at most 60 seconds per message.")
                text = " ".join(segment.text.strip() for segment in segments).strip()
            if not text or len(text) > 2000:
                raise ValueError("No usable speech or transcript exceeds 2000 characters.")
            return text
        finally:
            if path:
                os.unlink(path)
