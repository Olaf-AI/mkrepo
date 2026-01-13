from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal

from platformdirs import user_config_dir

APP_NAME = "mkrepo"

Provider = Literal["openrouter", "openai", "anthropic", "google", "openai_compat"]


@dataclass
class AppConfig:
    """Global config for mkrepo.

    provider:
      - openrouter: OpenRouter OpenAI-compatible API (default)
      - openai: OpenAI official API (OpenAI-compatible)
      - anthropic: Anthropic Claude Messages API
      - google: Google Gemini API (AI Studio key)
      - openai_compat: Any OpenAI-compatible gateway/proxy

    Notes:
      - For openrouter/openai_compat, use `api_key`.
      - For openai/anthropic/google, prefer the provider-specific key fields.
    """

    provider: Provider = "openrouter"

    # model name depends on provider:
    # - openrouter: e.g. "openai/gpt-4o-mini"
    # - openai: e.g. "gpt-4o-mini"
    # - anthropic: e.g. "claude-3-5-sonnet-20241022"
    # - google: e.g. "gemini-2.0-flash"
    model: str = "openai/gpt-4o-mini"

    # OpenAI-compatible base url (OpenAI/OpenRouter/any proxy)
    base_url: str = "https://openrouter.ai/api/v1"

    # Backward-compat key (used by openrouter/openai_compat)
    api_key: str = ""

    # Provider-specific keys (preferred when provider matches)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Provider-specific base urls (useful for proxies)
    anthropic_base_url: str = "https://api.anthropic.com"
    google_base_url: str = "https://generativelanguage.googleapis.com"

    # Optional OpenRouter headers
    http_referer: str = ""
    x_title: str = "mkrepo"


def config_path() -> Path:
    d = Path(user_config_dir(APP_NAME))
    d.mkdir(parents=True, exist_ok=True)
    return d / "config.json"


def load_config() -> AppConfig:
    p = config_path()
    if not p.exists():
        return AppConfig()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        # merge with defaults (backward compatible)
        cfg = AppConfig(**{**asdict(AppConfig()), **data})
        # light normalize
        if cfg.provider not in ("openrouter", "openai", "anthropic", "google", "openai_compat"):
            cfg.provider = "openrouter"
        return cfg
    except Exception:
        # if corrupted, fall back to defaults
        return AppConfig()


def save_config(cfg: AppConfig) -> None:
    p = config_path()
    p.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")


def redact_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:3] + "*" * (len(key) - 7) + key[-4:]
