# mkrepo

Generate a small repo (multi-file project) from natural language.

## Install (local dev)

uv venv
uv pip install -e .

## Usage

```bash
mkrepo --help
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

## TODO

* [DONE] 第二次输入key 是能看到的，不安全
* 预览的内容有些问题 需要去提前显示文件结构
* 支持更多的调用base
