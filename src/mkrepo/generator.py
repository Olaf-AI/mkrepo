from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import OpenAI


SYSTEM_PROMPT = """You are a repository generator.

Return ONLY valid JSON (no markdown, no extra text).
Schema:
{
  "repos": [
    {
      "name": "string",
      "dir": "string",
      "files": [
        {"path": "relative/path.ext", "content": "file content as plain text"}
      ]
    }
  ]
}

Rules:
- paths must be relative, no absolute paths
- keep repo small but runnable
- include a README.md when appropriate
"""


def _extract_json(text: str) -> Dict[str, Any]:
    """
    Best-effort: find first '{' and last '}' and parse.
    """
    s = text.find("{")
    e = text.rfind("}")
    if s == -1 or e == -1 or e <= s:
        raise ValueError("Model did not return JSON.")
    return json.loads(text[s : e + 1])


@dataclass
class LLMResult:
    repos: List[Dict[str, Any]]


def generate_repos(
    *,
    base_url: str,
    api_key: str,
    model: str,
    content: str,
    http_referer: str = "",
    x_title: str = "mkrepo",
) -> LLMResult:
    if not api_key:
        raise ValueError("Missing API key. Run `mkrepo -c` to configure.")

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
                "content": f"User request:\n{content}\n\nGenerate 1-3 repos if it makes sense.",
            },
        ],
    )

    text = resp.choices[0].message.content or ""
    data = _extract_json(text)

    repos = data.get("repos", [])
    if not isinstance(repos, list) or not repos:
        raise ValueError("JSON parsed but `repos` is empty/invalid.")

    # light validation
    for r in repos:
        if "name" not in r or "dir" not in r or "files" not in r:
            raise ValueError("Repo item missing required fields.")
        if not isinstance(r["files"], list):
            raise ValueError("Repo.files must be a list.")

    return LLMResult(repos=repos)
