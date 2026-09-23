# Live language and speech validation

This milestone supplies runnable measurement tools. It does **not** claim that a
live LLM, microphone or speech model has been validated on the development machine.
The default rules baseline and actual model inference are reported separately.

For Windows with 8 GB RAM, use the [small-model guide](windows-local-model.md).
`scripts\validate-windows.cmd` runs the comparator and actual inference with an
explicit 4,096-token context, 512-token output cap and 180-second request timeout.
It preserves timestamped ZIP reports, including blocked runs, without uploading them.
The underlying `uv run cwi-validate-local` command also works on other platforms.

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
and a natural-language paraphrase. Six supported baseline cases complete a delivery.

A scenario passes only if every expected status, tote, destination, priority and
execution flag matches, and the expected delivery completes with the correct updated
inventory. Before confirmation, there must be no dispatched job. A mismatched proposal
is recorded as a failure and is **not automatically confirmed** by the evaluator.
These are scripted simulation confirmations, not real human consent or physical actions.

Evaluation version 2 additionally checks the authoritative `policy_document` for
payload, restricted-access, priority and safety rejections. Merely refusing every
request cannot pass these distinct policy cases. Earlier scores are not directly
comparable because they checked rejection status without its reason.

Three procedure questions additionally report whether the expected source is cited.
**Source presence is not semantic correctness or faithfulness.** Generated answers must
still be reviewed for unsupported claims and evaluated on a broader held-out corpus.
Per-turn responses and wall-clock latency are retained; errors remain in the denominator.
The language CLI and Windows runner enable `model_calls` diagnostics: bounded raw
model JSON, completion reason, available token counts and generation/validation errors.
This distinguishes citation failures, malformed JSON, output limits and HTTP failures.
The ordinary API does not retain raw diagnostics. These traces contain generated
text; inspect a report before sharing it. Nothing is uploaded by the evaluator.
Model readiness/digest is included for Ollama runs. No inference score is emitted when
readiness fails. Exit codes: 0 all checks pass, 1 measured mismatch/error, 2 runtime blocked.

`CWI_OLLAMA_TIMEOUT_SECONDS`, `CWI_OLLAMA_CONTEXT_TOKENS` and
`CWI_OLLAMA_OUTPUT_TOKENS` configure resource limits for the ordinary language/voice
evaluators and API. The language report records the selected settings. The bundled
`cwi-validate-local` runner uses its explicit CLI profile instead of these environment
values, so it reproduces the same settings on different machines.

The recorded [rules result](../assets/language-baseline.json) passes **12/12 scenarios**
and all three source-presence checks. The previously unsupported `Please bring tote
T17 to P2` request is now handled by the controlled grammar; negated requests remain
rejected. The run exits 0. This small synthetic fixture is a regression suite, not evidence
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

## Measure recorded voice through simulated delivery

`cwi-evaluate-voice` joins actual transcription with the conversation evaluator.
Use a separate scenario manifest alongside your recordings. This is a schema example,
not an included audio dataset:

```json
[
  {
    "identifier": "operator-01-transport",
    "recording_kind": "human",
    "condition": "quiet room",
    "turns": [
      {
        "audio": "command-01.wav",
        "reference": "Move T17 to P2",
        "expected_status": "awaiting_confirmation",
        "expected_task": {"tote_id": "T17", "destination": "P2", "priority": "normal"}
      },
      {
        "text": "confirm",
        "expected_status": "accepted",
        "expected_task": {"tote_id": "T17", "destination": "P2", "priority": "normal"}
      }
    ],
    "expected_delivery": {"tote_id": "T17", "destination": "P2", "priority": "normal"}
  }
]
```

```sh
uv run cwi-evaluate-voice --speech-model /path/to/local/faster-whisper-model \
  --model YOUR_INSTALLED_MODEL --manifest /path/to/audio/voice-scenarios.json \
  --output outputs/live-voice-workflow.json
```

Use `--baseline` instead of `--model` to explicitly pair actual transcription with
the rules parser. Label synthesized recordings `synthetic`; do not describe such
runs as evidence about human operators. Cases have separate human/synthetic pass
rates, transcript hashes, word-error rates, latency, task replies and execution metrics.
Every case must contain a recording; text turns represent scripted clarification
or confirmation steps. Rejected or cancelled cases may omit `expected_delivery`.

The evaluator feeds the **actual transcript**, never the reference, to an isolated
simulation. Transcription failure leaves the case failed and never dispatches work.
An incorrect proposed tote, destination, priority or status stops execution before
the next scripted confirmation. These controls validate the pipeline, not human
review or genuine operator consent. Nothing connects to physical robot hardware.
Exit 0 means all specified cases match, 1 means a measured failure, and 2 means
the configured model runtime could not be initialized. No live voice report is
included until the command has actually run against supplied models and recordings.

## Remaining validation

- Obtain and identify actual model versions, hardware, recordings and consent.
- Run live generation and speech, inspect failures and retain raw evidence locally.
- Evaluate the complete reviewed-transcript → clarification → confirmation → delivery
  workflow with operators, including noise, interruptions and recovery.
- Add held-out language/layout datasets and retrieval/agent ablations before research claims.
- Physical robotics and warehouse safety trials require hardware and a separate test plan.
