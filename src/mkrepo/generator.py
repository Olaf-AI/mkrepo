from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Dict, List

import httpx
from openai import OpenAI

SYSTEM_PROMPT = """You are a repository generator.

Return ONLY valid JSON (no markdown, no extra text).
Schema:
{
  \"repos\": [
    {
      \"name\": \"string\",
      \"dir\": \"string\",
      \"files\": [
        {\"path\": \"relative/path.ext\", \"content\": \"file content as plain text\"}
      ]
    }
  ]
}

Rules:
- paths must be relative, no absolute paths, no parent traversal
- keep repo small but runnable
- include a README.md when appropriate
"""


def _extract_json(text: str) -> Dict[str, Any]:
    """Best-effort: find first '{' and last '}' and parse."""
    s = text.find("{")
    e = text.rfind("}")
    if s == -1 or e == -1 or e <= s:
        raise ValueError("Model did not return JSON.")
    return json.loads(text[s: e + 1])


def _is_safe_rel_path(p: str) -> bool:
    if not p:
        return False
    p = p.replace("\\\\", "/").strip()
    if not p:
        return False
    if p.startswith("/"):
        return False
    # Windows drive letter like C:/...
    if len(p) >= 2 and p[1] == ":":
        return False
    pp = PurePosixPath(p)
    if pp.is_absolute():
        return False
    if ".." in pp.parts:
        return False
    return True


def validate_repos(repos: List[Dict[str, Any]]) -> None:
    """Validate plan structure and path safety."""
    if not isinstance(repos, list) or not repos:
        raise ValueError("JSON parsed but `repos` is empty/invalid.")

    for r in repos:
        if not isinstance(r, dict):
            raise ValueError("Repo item must be an object.")
        if "name" not in r or "dir" not in r or "files" not in r:
            raise ValueError("Repo item missing required fields (name/dir/files).")
        if not isinstance(r["files"], list):
            raise ValueError("Repo.files must be a list.")

        for f in r["files"]:
            if not isinstance(f, dict):
                raise ValueError("Repo.files item must be an object.")
            path = str(f.get("path", "")).strip()
            if not _is_safe_rel_path(path):
                raise ValueError(f"Unsafe or invalid path: {path!r}")
            # normalize content to string (CLI writes as text)
            if "content" in f and f["content"] is not None and not isinstance(f["content"], str):
                f["content"] = str(f["content"])


@dataclass
class LLMResult:
    repos: List[Dict[str, Any]]


def _call_openai_compat(
        *,
        base_url: str,
        api_key: str,
        model: str,
        user_content: str,
        http_referer: str = "",
        x_title: str = "mkrepo",
) -> str:
    if not api_key:
        raise ValueError("Missing API key.")

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        default_headers={
            **({"HTTP-Referer": http_referer} if http_referer else {}),
            **({"X-Title": x_title} if x_title else {}),
        },
    )

    resp = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": user_content,
            },
        ],
    )

    return resp.choices[0].message.content or ""


def _call_anthropic(
        *,
        base_url: str,
        api_key: str,
        model: str,
        user_content: str,
) -> str:
    if not api_key:
        raise ValueError("Missing Anthropic API key.")

    url = base_url.rstrip("/") + "/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 4096,
        "temperature": 0.2,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_content}],
    }

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, json=payload)

    if resp.status_code >= 400:
        # avoid leaking keys; show status + short body
        raise ValueError(f"Anthropic API error {resp.status_code}: {resp.text[:400]}")

    data = resp.json()
    blocks = data.get("content", [])
    if isinstance(blocks, list):
        texts: List[str] = []
        for b in blocks:
            if isinstance(b, dict) and b.get("type") == "text":
                t = b.get("text")
                if isinstance(t, str):
                    texts.append(t)
        if texts:
            return "\n".join(texts)

    # fallback
    return json.dumps(data, ensure_ascii=False)


def _call_gemini(
        *,
        base_url: str,
        api_key: str,
        model: str,
        user_content: str,
) -> str:
    if not api_key:
        raise ValueError("Missing Gemini API key.")

    url = base_url.rstrip("/") + f"/v1beta/models/{model}:generateContent"
    params = {"key": api_key}

    payload = {
        # REST examples commonly use snake_case for system instruction
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "generationConfig": {
            "temperature": 0.2,
            # Ask Gemini to emit JSON directly.
            "response_mime_type": "application/json",
        },
    }

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, params=params, json=payload)

    if resp.status_code >= 400:
        # Google's error sometimes includes the request URL (with key) in client-side libs.
        # Here we only include the response body and status.
        raise ValueError(f"Gemini API error {resp.status_code}: {resp.text[:400]}")

    data = resp.json()
    candidates = data.get("candidates", [])
    if isinstance(candidates, list) and candidates:
        c0 = candidates[0] or {}
        content = c0.get("content", {}) if isinstance(c0, dict) else {}
        parts = content.get("parts", []) if isinstance(content, dict) else []
        if isinstance(parts, list):
            texts = [p.get("text") for p in parts if isinstance(p, dict) and isinstance(p.get("text"), str)]
            if texts:
                return "\n".join(texts)

    # fallback
    return json.dumps(data, ensure_ascii=False)


def generate_repos(
        *,
        provider: str,
        model: str,
        content: str,
        # OpenAI-compatible settings
        base_url: str = "",
        api_key: str = "",
        http_referer: str = "",
        x_title: str = "mkrepo",
        # Anthropic/Gemini base urls
        anthropic_base_url: str = "https://api.anthropic.com",
        google_base_url: str = "https://generativelanguage.googleapis.com",
        # Provider-specific keys
        openai_api_key: str = "",
        anthropic_api_key: str = "",
        google_api_key: str = "",
) -> LLMResult:
    user_content = f"User request:\n{content}\n\nGenerate 1-3 repos if it makes sense."

    provider = (provider or "openrouter").strip().lower()

    if provider in ("openrouter", "openai_compat", "openai"):
        key = openai_api_key if provider == "openai" and openai_api_key else api_key
        if not key:
            raise ValueError("Missing API key. Run `mkrepo -c` to configure.")

        # Sensible defaults if user switches providers
        if provider == "openai" and not base_url:
            base_url = "https://api.openai.com/v1"

        text = _call_openai_compat(
            base_url=base_url,
            api_key=key,
            model=model,
            user_content=user_content,
            http_referer=http_referer,
            x_title=x_title,
        )

    elif provider == "anthropic":
        text = _call_anthropic(
            base_url=anthropic_base_url,
            api_key=anthropic_api_key or api_key,
            model=model,
            user_content=user_content,
        )

    elif provider == "google":
        gemini_model = model
        # REST endpoint expects model name without the "models/" prefix.
        if gemini_model.startswith("models/"):
            gemini_model = gemini_model.split("/", 1)[1]

        text = _call_gemini(
            base_url=google_base_url,
            api_key=google_api_key or api_key,
            model=gemini_model,
            user_content=user_content,
        )

    else:
        raise ValueError(f"Unknown provider: {provider}")

    data = _extract_json(text)
    repos = data.get("repos", [])
    validate_repos(repos)
    return LLMResult(repos=repos)
