# Live language and speech validation

This milestone supplies runnable measurement tools. It does **not** claim that a
live LLM, microphone or speech model has been validated on the development machine.
The default rules baseline and actual model inference are reported separately.

## Check installed services first

```sh
uv sync --locked
uv run cwi-check-runtime --model YOUR_INSTALLED_MODEL
```

The check reads the local Ollama model inventory, verifies the selected tag and
records its digest. It never downloads models or substitutes a rules backend.
`--base-url` supports another local HTTP port, subject to the same endpoint validation
as the application. It exits 2 when the requested runtime is unavailable. Readiness
is only an inventory/configuration check; it does not establish inference quality.

For speech, first install the optional adapter with `uv sync --locked --extra voice`,
then add `--speech-model /path/to/local/faster-whisper-model`. This checks the adapter
and `model.bin`; loading, decoding and transcription still need a real evaluation.
`CWI_OLLAMA_MODEL`, `CWI_OLLAMA_URL` and `CWI_WHISPER_MODEL` can configure this check.

## Test conversation through delivery

```sh
uv run cwi-evaluate-llm --model YOUR_INSTALLED_MODEL --output outputs/live-language.json
uv run cwi-evaluate-llm --baseline --output outputs/language-baseline.json
```

Use exactly one of `--model` or `--baseline`. The suite creates a fresh isolated
warehouse for each of 12 scenarios: explicit requests, ambiguous objects, corrections,
cancellation, unprompted confirmation, payload rejection, restricted destinations,
priority permissions, protective constraints, unknown IDs, supervisor privileges,
and a natural-language paraphrase. Five supported baseline cases complete a delivery.

A scenario passes only if every expected status, tote, destination, priority and
execution flag matches, and the expected delivery completes with the correct updated
inventory. Before confirmation, there must be no dispatched job. A mismatched proposal
is recorded as a failure and is **not automatically confirmed** by the evaluator.
These are scripted simulation confirmations, not real human consent or physical actions.

Three procedure questions additionally report whether the expected source is cited.
**Source presence is not semantic correctness or faithfulness.** Generated answers must
still be reviewed for unsupported claims and evaluated on a broader held-out corpus.
Per-turn responses and wall-clock latency are retained; errors remain in the denominator.
Model readiness/digest is included for Ollama runs. No inference score is emitted when
readiness fails. Exit codes: 0 all checks pass, 1 measured mismatch/error, 2 runtime blocked.

The recorded [rules result](../assets/language-baseline.json) passes **11/12 scenarios**
and all three source-presence checks. The unsupported `Please bring tote T17 to P2`
request remains a measured baseline limitation. The run correctly exits 1; it is not
a failed installation. This small synthetic fixture is a regression suite, not evidence
of broad language generalization. Do not compare live model performance with the
baseline until an actual live report has been collected.

## Measure speech on your recordings

Use a local directory containing audio files and a `manifest.json`. For example:

```json
[
  {
    "identifier": "operator-01-quiet",
    "audio": "command-01.wav",
    "reference": "Move T17 to P2",
    "recording_kind": "human",
    "condition": "quiet room"
  }
]
```

Record and transcribe each reference accurately; the example is a schema, not an
included recording. Label synthesized audio `synthetic`. Keep those results separate
from human recordings. Include multiple speakers, ambiguous references, corrections,
background noise and easily confused tote/station IDs for a useful later study.

```sh
uv run cwi-evaluate-speech --model-path /path/to/local/faster-whisper-model \
  --manifest /path/to/audio/manifest.json --output outputs/live-speech.json
```

All audio must be inside the manifest directory. Supported extensions are WAV, MP3,
M4A, FLAC, OGG and WebM, with the application's 10 MiB and 60-second per-file limits.
The evaluator measures transcription only; **it never dispatches robot commands**.
It records per-file latency, audio hashes, transcript/reference pairs, exact matching
and word error rate (WER). WER uses word-level edit distance with case/punctuation
normalization. It does not equate `T17` with `T seventeen`; inspect such errors manually
because identifier mistakes matter operationally. WER can exceed 1 due to insertions.

Human and synthetic groups are reported separately. WER is micro-averaged over
successfully transcribed files; failures are shown separately and count as failures
in the all-case exact-match denominator. A report with zero successful files has
null WER, never zero WER. Exit 1 indicates transcription errors, not a chosen WER
acceptance threshold. Set quality criteria before collecting evaluation data.

Reports contain transcripts and local filenames. Keep real operator data local
unless the participants authorize publication; `outputs/` is already ignored by Git.
No human or synthetic speech-quality score is published without an actual model run.

## Remaining validation

- Obtain and identify actual model versions, hardware, recordings and consent.
- Run live generation and speech, inspect failures and retain raw evidence locally.
- Evaluate the complete reviewed-transcript → clarification → confirmation → delivery
  workflow with operators, including noise, interruptions and recovery.
- Add held-out language/layout datasets and retrieval/agent ablations before research claims.
- Physical robotics and warehouse safety trials require hardware and a separate test plan.
