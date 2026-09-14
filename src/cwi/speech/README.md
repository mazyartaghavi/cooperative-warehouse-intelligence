# Local voice input

`service.py` provides a local faster-whisper adapter behind a small protocol. Audio is bounded, decoded with an existing CPU model, and deleted afterward. The API returns transcription for review; audio alone never dispatches a task. Optional model quality requires live evaluation.

See the [project README](../../../README.md) for startup, evidence and scope.
