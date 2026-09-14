# Engineering verification

Local verification on **2026-09-14**, Linux, Python 3.12.14, uv 0.12.11.

| Check | Observed result |
|---|---|
| Locked environment installation | Successful |
| pytest | 55 tests passed |
| Ruff lint and formatting | Passed |
| Strict mypy | Passed, 29 source files |
| Offline CLI | Clarify → confirm → dispatch → simulated delivery |
| Warehouse experiments | Three of three deliveries in both static and dynamic fixtures |
| Learned-policy integration | Active inspection discovers an unobserved opening and enables delivery |
| Persistence | Restart, idempotency, role revalidation and failed-write rollback covered |
| Speech and generation | Adapter contracts tested using synthetic doubles |
| Dashboard JavaScript | Syntax check passed |
| Live local Ollama | Unavailable; connection refused, no inference score claimed |
| Hosted browser workflow | Passed: clarification, confirmation, delivery, pause, no script errors or mobile overflow |
| Hosted Python quality | Passed: locked install, lint, format, type checking, tests, demo and evaluation |
| Docker runtime | Unavailable locally; Dockerfile supplied, no local container run claimed |

The API is also exercised through FastAPI's test client, including the complete
instruction/confirmation/advance/delivery path. That is an integration test, not a
real browser or live-model evaluation. The optional Playwright script checks the
actual UI, task flow, script errors and mobile overflow when a browser is available.
Hosted checks passed on commit `9e42d4b7f66c847835c9da69c56737cbd9b78597`: [GitHub Actions run](https://github.com/mazyartaghavi/cooperative-warehouse-intelligence/actions/runs/34817194358). Local browser download failed, so the actual browser test was executed on the hosted runner. Its desktop/mobile screenshots are attached to that run.

Upstream deprecation warnings from the test client and imported dependencies are
visible and not suppressed. They do not fail the current suite.

## Recorded experiment interpretation

`assets/evaluation.json` contains actual generated output. At this revision the
static and dynamic fixtures complete three deliveries with zero soft-deadline
lateness. Their distances differ partly because assignments and charger returns
change; this is not an efficiency claim about obstacles.

Across five seeds, mean synthetic return is approximately 8.009 for Q-learning,
7.346 for always-ask, and 8.012 for inspect-when-possible. These assumed-cost results
show no clear advantage of learning over the stronger fixed inspection baseline.
The JSON records full precision, sample standard deviations and per-seed metrics.
No significance test or human productivity gain is claimed.

The integrated stale-barrier experiment separately exercises the policy in the
warehouse. Inspection can discover the opening; asking alone leaves the job blocked
unless a human changes the environment. This does not validate the assumed training
transition probabilities.

## Evidence limits

No physical robot, microphone recording, live speech model, or live LLM inference
was evaluated locally. The procedure corpus and warehouse fixtures are synthetic.
Collision checks concern discrete grid cells and ticks, not braking distances or
industrial human safety. Real-world robustness, prompt-injection resistance,
production access control and deployment scale remain unestablished.
