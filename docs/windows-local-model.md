# Windows: first live model run on an 8 GB computer

Start with text and the three-robot simulator. The initial profile selects
`qwen2.5:1.5b`, a 4,096-token context, up to 512 generated tokens and a 180-second
HTTP timeout per model request. Ollama lists this quantized model as a **986 MB
download**; that is not total runtime memory. Available RAM, other applications,
CPU and GPU determine actual fit and response time. This is a starting profile,
not a measured performance claim for an 8 GB machine.

## 1. Prepare the model and Python runner

Ollama must already be installed. Open the Ollama application from the Start menu.
In PowerShell, check the available models:

```powershell
ollama list
```

If `qwen2.5:1.5b` is missing, download it explicitly:

```powershell
ollama pull qwen2.5:1.5b
```

If `uv --version` is not recognized, install uv, then close and reopen PowerShell:

```powershell
winget install --id=astral-sh.uv -e
```

No Git installation is required. [Download the project ZIP](https://github.com/mazyartaghavi/cooperative-warehouse-intelligence/archive/refs/heads/main.zip),
choose **Extract All**, and open the extracted folder containing `pyproject.toml`.
Open a terminal in that folder (Explorer's **Open in Terminal**, or type
`powershell` in its address bar). An existing Git checkout can instead use `git pull`
after preserving any local changes.

## 2. Run the validation

```powershell
.\scripts\validate-windows.cmd
```

The command installs the pinned project dependencies with uv and obtains Python
3.12 if needed. This first setup needs internet access. It does not install the
optional speech package, download a language model, change PowerShell execution
policy, start a public server, or require administrator access.

The runner checks the local model inventory, runs the offline comparator, then
executes the actual local LLM on 12 conversation scenarios and three procedure
questions. Scenarios cover clarification, correction, confirmation, permission
checks and six simulated deliveries. It prints progress and saves a new ZIP under
`outputs` for each run. A mismatched task is never automatically confirmed.

Close memory-heavy applications before testing. The complete suite may take several
minutes on a CPU. The timeout applies to each HTTP operation; it is not a deadline
for the entire suite. Pressing Ctrl+C while the Python evaluator runs saves an
interrupted report without a complete live score. An interruption during dependency
installation cannot produce an evaluation report.

To select another model already shown in `ollama list`:

```powershell
.\scripts\validate-windows.cmd --model your-installed-model-tag
```

To allow slower CPU responses:

```powershell
.\scripts\validate-windows.cmd --timeout-seconds 300
```

The same runner works without the Windows wrapper:

```powershell
uv run --locked --no-dev cwi-validate-local
```

## 3. Share the measured result

Attach the printed `outputs\validation-...zip` file when asking for analysis.
It contains only files created for that run:

| File | Contents |
|---|---|
| `environment.json` | OS/Python versions, CPU count, project version, Python source hash, resource limits and elapsed time |
| `runtime-readiness.json` | Selected model, installed model inventory and selected model digest |
| `language-baseline.json` | Explicit offline rules comparator |
| `live-language.json` | Actual model responses, per-turn latency and failures, or a blocked/interrupted status |

An interrupted run may omit checks it did not reach. The runner does not read
your operational database or microphone files, and it does not upload the report.
Reports remain excluded from Git. Readiness is an inventory check, not inference
quality. The source checks measure citation presence, not semantic faithfulness.

Exit codes are **0** for all comparator/live checks passing, **1** for a measured
mismatch or model error, **2** for unavailable runtime, and **130** for interruption
inside the evaluator. Keep and share a failing report too; do not replace it with
the baseline score. If the runtime is blocked, reopen Ollama and check that the
selected tag appears in `ollama list`.

## 4. Open the application with the same profile

After reviewing the report, set these variables in PowerShell inside the project:

```powershell
$env:CWI_BACKEND = "ollama"
$env:CWI_OLLAMA_MODEL = "qwen2.5:1.5b"
$env:CWI_OLLAMA_TIMEOUT_SECONDS = "180"
$env:CWI_OLLAMA_CONTEXT_TOKENS = "4096"
$env:CWI_OLLAMA_OUTPUT_TOKENS = "512"
$env:CWI_API_TOKEN = (uv run --locked --no-dev python -c "import secrets; print(secrets.token_urlsafe(24))")
Write-Host "Paste this local token into the dashboard: $env:CWI_API_TOKEN"
uv run --locked --no-dev uvicorn cwi.api.app:app_factory --factory --host 127.0.0.1 --port 8000 --workers 1
```

Open **http://127.0.0.1:8000**, enter the printed token, and click **Connect**.
Try `Move the blue tote to P2`, clarify `T17`, review and confirm, then click
**Run simulation**. The token identifies the local demo operator; it is not a
GitHub or model-provider key. Both intent extraction and grounded procedure answers
use these resource limits. Invalid or truncated model JSON still fails validation.

The small context is intended for short task conversations; start a new task
conversation after each delivery. Long histories can exceed the model context.
Use Ctrl+C to stop the application. When finished with all model requests,
`ollama stop qwen2.5:1.5b` releases the loaded model.

Add speech only after measuring this text path. Follow the separate
[speech and voice evaluation instructions](live-validation.md) with actual local
speech weights and recordings; this command does not claim speech validation.

## Primary references

- [Ollama Qwen2.5 1.5B model tag](https://ollama.com/library/qwen2.5:1.5b)
- [Ollama on Windows](https://docs.ollama.com/windows)
- [Ollama generation parameters](https://docs.ollama.com/modelfile)
- [Official uv installation options](https://docs.astral.sh/uv/getting-started/installation/)
