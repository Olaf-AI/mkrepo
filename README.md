# mkrepo

Generate a small repo (multi-file project) from natural language.

## Install (local dev)

uv venv
uv pip install -e .

## Usage

```bash
mkrepo -h
mkrepo -c # configure base_url/model/api_key
mkrepo # interactive
mkrepo --dry-run
```

## build

```bash
uv tool install mkrepo
mkrepo -c
mkrepo
```

## OpenRouter default

base_url: https://openrouter.ai/api/v1
api_key: your OpenRouter key
model: openai/gpt-4o-mini (example)