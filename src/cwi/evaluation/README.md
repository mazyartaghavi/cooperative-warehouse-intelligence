# Reproducible experiments

`run.py` executes three-robot scenarios, retrieval fixtures, seeded clarification experiments and integrated blocked-route assistance comparisons. `language.py` evaluates a specified live Ollama model and records actual errors and latency. Generated outputs default to ignored `outputs/` paths.

`runtime.py` checks installed local model availability. `speech.py` measures supplied
recordings without dispatch. `voice.py` evaluates actual transcripts through
clarification, checked confirmation and isolated simulated delivery, with separate
human/synthetic results and no substitution of reference text. See the
[validation guide](../../../docs/live-validation.md) for corpus schemas and commands.

See the [project README](../../../README.md) for startup, evidence and scope.
