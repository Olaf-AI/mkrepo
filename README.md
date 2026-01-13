# mkrepo

Generate a multi-file repository (project scaffold) from natural language — with a **previewable / editable** file plan
before writing.

## Features

- **Multi-provider**: OpenRouter / OpenAI / Anthropic (Claude) / Google Gemini / Any OpenAI-compatible gateway
- **Plan preview**: shows the file tree before writing
- **Plan editing**: press `e` to open an editor and modify the JSON plan
- **Regenerate**: press `r` to re-call the model and regenerate a plan
- **Safe writes**: blocks path traversal / unsafe paths

---

## Install (global)

### Option A: Install from PyPI

```bash
pipx install uv
uv tool install mkrepo
```

### Option B: Install from source (local clone)

```bash
pipx install uv
git clone git@github.com:Olaf-AI/mkrepo.git
cd mkrepo
uv tool install .
```

### Windows note (PowerShell / CMD)

After installing an uv tool, you may need to update your shell PATH:

```bash
uv tool update-shell
```

Then **open a new terminal** (if it still doesn't work, reboot once).

---

## Install (local dev)

```bash
uv venv
uv pip install -e .
```

---

## Usage

```bash
mkrepo --help
mkrepo -c            # configure provider/base_url/model/api_key
mkrepo               # interactive
mkrepo --dry-run     # preview only (no file writes)
```

---

## Providers

In `mkrepo -c`, set `provider` to one of:

- `openrouter` (default)
- `openai`
- `anthropic`
- `google`
- `openai_compat` (any OpenAI-compatible proxy/gateway)

When you switch provider, mkrepo will suggest a provider-appropriate **default model** (so you don’t accidentally keep
an incompatible model string).

### OpenRouter (default)

- `provider`: `openrouter`
- `base_url`: `https://openrouter.ai/api/v1`
- `api_key`: your OpenRouter key
- `model`: e.g. `openai/gpt-4o-mini`

### OpenAI

- `provider`: `openai`
- `base_url`: `https://api.openai.com/v1`
- `openai_api_key`: your OpenAI key
- `model`: e.g. `gpt-4o-mini`

### Anthropic (Claude)

- `provider`: `anthropic`
- `anthropic_base_url`: default `https://api.anthropic.com`
- `anthropic_api_key`: your key
- `model`: e.g. `claude-3-5-sonnet-20241022`

### Google Gemini

- `provider`: `google`
- `google_base_url`: default `https://generativelanguage.googleapis.com`
- `google_api_key`: your key
- `model`: e.g. `gemini-2.0-flash`

### OpenAI-compatible gateway / proxy

- `provider`: `openai_compat`
- `base_url`: your gateway base URL (OpenAI-compatible)
- `api_key`: gateway key
- `model`: depends on your gateway

---

