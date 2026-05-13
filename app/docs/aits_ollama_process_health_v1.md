# AITS Ollama Process Health v1

## 1. Purpose

This layer diagnoses the local Ollama executable, process visibility, version command, and model directory path before AITS enables any local inference path.

It is a health check layer only. It does not run `ollama generate`, `ollama chat`, provider APIs, or order execution.

## 2. Executable Discovery Policy

Ollama executable discovery follows the distribution path policy:

1. Bundled runtime: `runtime/ollama/ollama.exe`
2. User runtime: `%LOCALAPPDATA%/AITS/runtime/ollama/ollama.exe`
3. PATH runtime: `ollama`

The preferred path is resolved without creating directories or downloading files.

## 3. Version Check vs Inference Check

`ollama --version` only verifies that the executable can start and print version information. It is not inference.

Inference checks would call model execution commands such as `generate` or `chat`. Those calls remain forbidden in this step.

## 4. Model Directory Policy

The model directory is checked by path existence only:

- Development: `runtime/ollama/models`
- Packaged: `<exe_dir>/runtime/ollama/models`
- User fallback: `%LOCALAPPDATA%/AITS/runtime/ollama/models`

Missing model directories are reported as warnings. This step does not create directories or download models.

## 5. Runtime Status Separation

The runtime status now separates:

- `executable_ready`
- `model_dir_ready`
- `inference_ready`

For SPRINT-01-B1, `inference_ready` remains false because no local inference call is made.

## 6. Next Steps

- B2: Ollama model inventory
- B3: Ollama local inference gate
- B4: UI runtime status sync
