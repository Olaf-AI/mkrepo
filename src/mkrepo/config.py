from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from platformdirs import user_config_dir

APP_NAME = "mkrepo"


@dataclass
class AppConfig:
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "openai/gpt-4o-mini"
    api_key: str = ""  # consider using env in real world

    # optional OpenRouter headers
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
        cfg = AppConfig(**{**asdict(AppConfig()), **data})
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
